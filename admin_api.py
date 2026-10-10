# -*- coding: utf-8 -*-
"""
واجهات API للوحة مالك التطبيق (Laravel) وواجهات المزارع والمزامنة.

- /api/admin/*  : محمية برمز خدمة (X-Service-Token) — يستخدمها خادم Laravel فقط،
                  ولا يجوز استدعاؤها من المتصفح.
- /api/v1/farms/me/* : محمية بمفتاح المزرعة (X-Farm-Key) — لتطبيق المزرعة.
- /api/v1/farms/me/sync : نقطة مزامنة السجلات المحفوظة دون اتصال.
"""
import os
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.orm import Session

import models
import schemas
import tenancy
import record_ops
from database import SessionLocal

router = APIRouter()

SUPPORT_CONTACT = os.environ.get("SUPPORT_CONTACT", "")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------- المصادقة

def require_service_token(x_service_token: str = Header(default=None)):
    """مصادقة خدمة إلى خدمة: يقارن رمز الخدمة الآمن من متغير البيئة."""
    expected = os.environ.get("OWNER_SERVICE_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503, detail="رمز الخدمة غير مضبوط على الخادم")
    if not x_service_token or not secrets.compare_digest(x_service_token, expected):
        raise HTTPException(status_code=401, detail="رمز الخدمة غير صحيح")


def require_farm(x_farm_key: str = Header(default=None), db: Session = Depends(get_db)):
    """
    مصادقة المزرعة عبر مفتاح API خاص بها.
    المزرعة المعلقة يمكنها قراءة بياناتها (لا حذف ولا فقدان)،
    أما الإنشاء المباشر فيُمنع داخل record_ops عبر new_operations_blocked.
    """
    if not x_farm_key:
        raise HTTPException(status_code=401, detail="مفتاح المزرعة مطلوب")
    farm = db.query(models.Farm).filter(models.Farm.api_key == x_farm_key).first()
    if farm is None:
        raise HTTPException(status_code=401, detail="مفتاح المزرعة غير صحيح")
    return farm


# ---------------------------------------------------------------- نماذج الطلبات

class FarmCreate(BaseModel):
    name: str = Field(min_length=1)
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None
    actor: str = "owner-panel"


class FarmAutoRegister(BaseModel):
    name: Optional[str] = "مزرعة جديدة"
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None


class FarmStatusChange(BaseModel):
    status: str = Field(pattern="^(active|suspended)$")
    reason: str = Field(min_length=1)
    actor: str = "owner-panel"


class SubscriptionCreate(BaseModel):
    months: int = Field(default=0, ge=0, le=60)
    days: int = Field(default=0, ge=0, le=3650)
    price: Optional[float] = None
    payment_status: str = Field(default="pending", pattern="^(paid|pending)$")
    notes: Optional[str] = None
    actor: str = "owner-panel"


class SubscriptionCancel(BaseModel):
    reason: str = Field(min_length=1)
    actor: str = "owner-panel"


class SettingsUpdate(BaseModel):
    free_ops_limit: int = Field(ge=1, le=1000000)
    alert_threshold_1: int = Field(ge=1, le=1000000)
    alert_threshold_2: int = Field(ge=1, le=1000000)
    subscription_price: Optional[float] = Field(default=None, ge=0)
    subscription_currency: str = Field(default="YER", min_length=1, max_length=10)
    subscription_duration_days: int = Field(ge=1, le=3650)
    grace_period_days: int = Field(ge=0, le=365)
    timezone: str = Field(default="Asia/Aden", min_length=1, max_length=64)
    actor: str = "owner-panel"


class SyncRecord(BaseModel):
    client_uuid: str = Field(min_length=8, max_length=64)
    type: str = Field(pattern="^(worker|advance|merchant|merchant_payment|crop_sale|qat_sale|expense)$")
    data: dict
    occurred_at: Optional[str] = None


class SyncRequest(BaseModel):
    records: List[SyncRecord] = Field(max_length=1000)


# ---------------------------------------------------------------- مساعدات

def _farm_payload(db: Session, farm: models.Farm, with_totals: bool = False) -> dict:
    usage = tenancy.usage_snapshot(db, farm.id)
    sub = tenancy.subscription_info(db, farm.id)
    payload = {
        "id": farm.id,
        "name": farm.name,
        "contact_name": farm.contact_name,
        "contact_phone": farm.contact_phone,
        "status": farm.status,
        "suspension_reason": farm.suspension_reason,
        "notes": farm.notes,
        "created_at": farm.created_at,
        "usage": usage,
        "subscription": sub,
        "operations_total": db.query(models.Operation).filter(
            models.Operation.farm_id == farm.id
        ).count(),
    }
    if with_totals:
        payload["totals"] = tenancy.farm_totals(db, farm.id)
    return payload


# ---------------------------------------------------------------- واجهات المالك

@router.get("/api/admin/overview")
def admin_overview(db: Session = Depends(get_db), _: None = Depends(require_service_token)):
    month = tenancy.current_month_key(db)
    farms = db.query(models.Farm).all()
    s = tenancy.get_settings(db)
    now = tenancy.system_now(db)

    expiring_soon = []
    for f in farms:
        info = tenancy.subscription_info(db, f.id, now)
        if info["active"] and info["end_date"]:
            from datetime import date
            try:
                end = date.fromisoformat(info["end_date"])
                days_left = (end - now.date()).days
                if 0 <= days_left <= 14:
                    expiring_soon.append({
                        "farm_id": f.id, "farm_name": f.name,
                        "end_date": info["end_date"], "days_left": days_left,
                        "in_grace": info["in_grace"],
                    })
            except ValueError:
                pass

    total_operations = db.query(models.Operation).count()
    month_operations = db.query(models.Operation).filter(
        models.Operation.month_key == month
    ).count()

    return {
        "month": month,
        "farms_total": len(farms),
        "farms_active": sum(1 for f in farms if f.status == "active"),
        "farms_suspended": sum(1 for f in farms if f.status == "suspended"),
        "subscriptions_active": sum(
            1 for f in farms if tenancy.subscription_info(db, f.id, now)["active"]
        ),
        "subscriptions_expiring_soon": expiring_soon,
        "total_operations": total_operations,
        "month_operations": month_operations,
        "settings": _settings_payload(s),
    }


@router.get("/api/admin/farms")
def admin_farms(
    search: str = "",
    status: Optional[str] = Query(default=None, pattern="^(active|suspended)$"),
    subscription: Optional[str] = Query(default=None, pattern="^(active|none|expired)$"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: None = Depends(require_service_token),
):
    q = db.query(models.Farm)
    if search:
        q = q.filter(models.Farm.name.contains(search))
    if status:
        q = q.filter(models.Farm.status == status)
    farms = q.order_by(models.Farm.id).all()

    items = []
    for f in farms:
        info = tenancy.subscription_info(db, f.id)
        if subscription == "active" and not info["active"]:
            continue
        if subscription == "none" and info["status"] != "none":
            continue
        if subscription == "expired" and info["status"] != "expired":
            continue
        items.append(_farm_payload(db, f))

    total = len(items)
    start = (page - 1) * per_page
    return {
        "items": items[start:start + per_page],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.post("/api/admin/farms", status_code=201)
def admin_create_farm(body: FarmCreate, db: Session = Depends(get_db),
                      _: None = Depends(require_service_token)):
    if db.query(models.Farm).filter(models.Farm.name == body.name).first():
        raise HTTPException(status_code=409, detail="توجد مزرعة بنفس الاسم مسبقاً")
    farm = models.Farm(
        name=body.name,
        contact_name=body.contact_name,
        contact_phone=body.contact_phone,
        notes=body.notes,
        api_key=tenancy._new_api_key(),
        status="active",
        created_at=tenancy._now_iso(),
    )
    db.add(farm)
    db.commit()
    db.refresh(farm)
    tenancy.audit(db, body.actor, "farm.create", "farm", farm.id,
                  details={"name": farm.name})
    payload = _farm_payload(db, farm)
    payload["api_key"] = farm.api_key  # يُعرض مرة واحدة فقط عند الإنشاء
    return payload


@router.get("/api/admin/farms/{farm_id}")
def admin_farm_detail(farm_id: int, db: Session = Depends(get_db),
                      _: None = Depends(require_service_token)):
    farm = tenancy.ensure_farm_or_404(db, farm_id)
    payload = _farm_payload(db, farm, with_totals=True)
    # آخر عمليات المزرعة
    ops = db.query(models.Operation).filter(
        models.Operation.farm_id == farm.id
    ).order_by(models.Operation.id.desc()).limit(20).all()
    payload["recent_operations"] = [
        {"type": o.op_type, "month": o.month_key, "created_at": o.created_at,
         "client_uuid": o.client_uuid} for o in ops
    ]
    subs = db.query(models.Subscription).filter(
        models.Subscription.farm_id == farm.id
    ).order_by(models.Subscription.id.desc()).all()
    payload["subscriptions_history"] = [
        {"id": x.id, "status": x.status, "start_date": x.start_date, "end_date": x.end_date,
         "price": x.price, "currency": x.currency, "payment_status": x.payment_status,
         "notes": x.notes, "created_by": x.created_by, "created_at": x.created_at}
        for x in subs
    ]
    return payload


@router.post("/api/admin/farms/{farm_id}/status")
def admin_farm_status(farm_id: int, body: FarmStatusChange,
                      db: Session = Depends(get_db),
                      _: None = Depends(require_service_token)):
    farm = tenancy.ensure_farm_or_404(db, farm_id)
    if farm.status == body.status:
        raise HTTPException(status_code=400, detail="المزرعة في هذه الحالة مسبقاً")
    farm.status = body.status
    farm.suspension_reason = body.reason if body.status == "suspended" else None
    db.commit()
    db.refresh(farm)
    tenancy.audit(db, body.actor, f"farm.{body.status}", "farm", farm.id,
                  reason=body.reason, details={"name": farm.name})
    return _farm_payload(db, farm)


@router.post("/api/admin/farms/{farm_id}/subscription")
def admin_set_subscription(farm_id: int, body: SubscriptionCreate,
                           db: Session = Depends(get_db),
                           _: None = Depends(require_service_token)):
    farm = tenancy.ensure_farm_or_404(db, farm_id)
    s = tenancy.get_settings(db)
    if body.months == 0 and body.days == 0:
        raise HTTPException(status_code=400, detail="حدد مدة الاشتراك بالأشهر أو الأيام")
    if s.subscription_price is None and body.price is None:
        raise HTTPException(
            status_code=400,
            detail="سعر الاشتراك غير مضبوط في الإعدادات العامة ولم يُحدد سعر لهذا الاشتراك. "
                   "اضبط السعر أولاً من إعدادات النظام أو أدخل سعراً لهذا الاشتراك.",
        )

    now = tenancy.system_now(db)
    # التجديد يمتد من نهاية الاشتراك الحالي إن كان ما زال سارياً
    from datetime import date
    current = tenancy.active_subscription(db, farm.id, now)
    start = now.date()
    if current is not None and current.end_date:
        try:
            cur_end = date.fromisoformat(current.end_date)
            if cur_end >= start:
                start = cur_end + timedelta(days=1)
        except ValueError:
            pass
    # الأشهر تُحتسب تقويمياً ثم تضاف الأيام
    try:
        end = start
        for _ in range(body.months):
            end = _add_month(end)
        end = end + timedelta(days=body.days)
    except Exception:
        end = start + timedelta(days=body.months * 30 + body.days)

    sub = models.Subscription(
        farm_id=farm.id,
        status="active",
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        price=body.price if body.price is not None else s.subscription_price,
        currency=s.subscription_currency,
        payment_status=body.payment_status,
        notes=body.notes,
        created_by=body.actor,
        created_at=tenancy._now_iso(),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    tenancy.audit(db, body.actor, "subscription.create", "farm", farm.id,
                  details={"start": sub.start_date, "end": sub.end_date,
                           "price": sub.price, "payment_status": sub.payment_status})
    payload = _farm_payload(db, farm)
    payload["subscription_created"] = {
        "id": sub.id, "start_date": sub.start_date, "end_date": sub.end_date,
        "price": sub.price, "currency": sub.currency,
        "payment_status": sub.payment_status,
    }
    return payload


@router.post("/api/admin/farms/{farm_id}/subscription/cancel")
def admin_cancel_subscription(farm_id: int, body: SubscriptionCancel,
                               db: Session = Depends(get_db),
                               _: None = Depends(require_service_token)):
    farm = tenancy.ensure_farm_or_404(db, farm_id)
    current = tenancy.active_subscription(db, farm.id)
    if current is None:
        raise HTTPException(status_code=400, detail="لا يوجد اشتراك سارٍ لهذه المزرعة")
    current.status = "cancelled"
    db.commit()
    tenancy.audit(db, body.actor, "subscription.cancel", "farm", farm.id,
                  reason=body.reason, details={"subscription_id": current.id})
    return _farm_payload(db, farm)


@router.post("/api/admin/farms/{farm_id}/payment-status")
def admin_payment_status(farm_id: int, body: dict,
                          db: Session = Depends(get_db),
                          _: None = Depends(require_service_token)):
    """متابعة إدارية لحالة الدفع فقط — لا يوجد دفع إلكتروني مدمج."""
    farm = tenancy.ensure_farm_or_404(db, farm_id)
    status = body.get("payment_status")
    actor = body.get("actor", "owner-panel")
    if status not in ("paid", "pending"):
        raise HTTPException(status_code=400, detail="حالة الدفع يجب أن تكون paid أو pending")
    current = tenancy.active_subscription(db, farm.id)
    if current is None:
        raise HTTPException(status_code=400, detail="لا يوجد اشتراك سارٍ لهذه المزرعة")
    current.payment_status = status
    db.commit()
    tenancy.audit(db, actor, "subscription.payment_status", "farm", farm.id,
                  details={"subscription_id": current.id, "payment_status": status})
    return _farm_payload(db, farm)


@router.post("/api/admin/farms/{farm_id}/regenerate-key")
def admin_regenerate_key(farm_id: int, body: dict,
                         db: Session = Depends(get_db),
                         _: None = Depends(require_service_token)):
    farm = tenancy.ensure_farm_or_404(db, farm_id)
    actor = body.get("actor", "owner-panel")
    farm.api_key = tenancy._new_api_key()
    db.commit()
    tenancy.audit(db, actor, "farm.regenerate_key", "farm", farm.id)
    return {"id": farm.id, "api_key": farm.api_key}


def _add_month(d):
    from calendar import monthrange
    y, m = d.year, d.month + 1
    if m > 12:
        y, m = y + 1, 1
    return d.replace(day=min(d.day, monthrange(y, m)[1]), month=m, year=y)


@router.get("/api/admin/usage")
def admin_usage(month: Optional[str] = None, db: Session = Depends(get_db),
                _: None = Depends(require_service_token)):
    mk = tenancy.month_key_for(month) if month else tenancy.current_month_key(db)
    s = tenancy.get_settings(db)
    farms = db.query(models.Farm).order_by(models.Farm.id).all()
    items = []
    for f in farms:
        usage = tenancy.usage_snapshot(db, f.id, mk)
        items.append({
            "farm_id": f.id, "farm_name": f.name, "status": f.status,
            "usage": usage,
        })
    near_limit = [i for i in items if i["usage"]["threshold_1_reached"] and not i["usage"]["over_limit"]]
    over_limit = [i for i in items if i["usage"]["over_limit"]]
    at_limit = [i for i in items if i["usage"]["at_limit"] and not i["usage"]["over_limit"]]
    return {
        "month": mk,
        "items": items,
        "near_limit": near_limit,
        "at_limit": at_limit,
        "over_limit": over_limit,
    }


@router.get("/api/admin/alerts")
def admin_alerts(month: Optional[str] = None, db: Session = Depends(get_db),
                 _: None = Depends(require_service_token)):
    mk = tenancy.month_key_for(month) if month else tenancy.current_month_key(db)
    s = tenancy.get_settings(db)
    farms = db.query(models.Farm).all()
    alerts = []
    for f in farms:
        usage = tenancy.usage_snapshot(db, f.id, mk)
        level = None
        if usage["over_limit"]:
            level = "over_limit"
        elif usage["threshold_2_reached"]:
            level = "threshold_2"
        elif usage["threshold_1_reached"]:
            level = "threshold_1"
        if level:
            sub = tenancy.subscription_info(db, f.id)
            alerts.append({
                "farm_id": f.id, "farm_name": f.name, "level": level,
                "used": usage["used"], "limit": usage["limit"],
                "has_subscription": sub["active"],
                "message": _alert_message(level, f.name, usage, s),
            })
    return {"month": mk, "thresholds": [s.alert_threshold_1, s.alert_threshold_2],
            "alerts": alerts}


def _alert_message(level, farm_name, usage, s):
    if level == "over_limit":
        return (f"تجاوزت مزرعة {farm_name} الحد المجاني: {usage['used']} من {usage['limit']} عملية "
                f"هذا الشهر — يلزم اشتراك للعمليات الجديدة")
    if level == "threshold_2":
        return f"اقتربت مزرعة {farm_name} من الحد المجاني: استخدمت {usage['used']} من {usage['limit']} عملية هذا الشهر"
    return f"تنبيه لمزرعة {farm_name}: استخدمت {usage['used']} من {usage['limit']} عملية هذا الشهر"


def _settings_payload(s: models.AppSettings) -> dict:
    return {
        "free_ops_limit": s.free_ops_limit,
        "alert_threshold_1": s.alert_threshold_1,
        "alert_threshold_2": s.alert_threshold_2,
        "subscription_price": s.subscription_price,
        "subscription_currency": s.subscription_currency,
        "subscription_duration_days": s.subscription_duration_days,
        "grace_period_days": s.grace_period_days,
        "timezone": s.timezone,
        "updated_at": s.updated_at,
        "updated_by": s.updated_by,
        "price_set": s.subscription_price is not None,
    }


@router.get("/api/admin/settings")
def admin_get_settings(db: Session = Depends(get_db),
                        _: None = Depends(require_service_token)):
    s = tenancy.get_settings(db)
    return _settings_payload(s)


@router.put("/api/admin/settings")
def admin_update_settings(body: SettingsUpdate, db: Session = Depends(get_db),
                          _: None = Depends(require_service_token)):
    from zoneinfo import ZoneInfo
    try:
        ZoneInfo(body.timezone)
    except Exception:
        raise HTTPException(status_code=400, detail="منطقة زمنية غير معروفة")
    if body.alert_threshold_1 > body.alert_threshold_2:
        raise HTTPException(status_code=400, detail="عتبة التنبيه الأولى يجب أن تكون أقل من الثانية")
    if body.alert_threshold_1 > body.free_ops_limit or body.alert_threshold_2 > body.free_ops_limit:
        raise HTTPException(status_code=400, detail="عتبات التنبيه يجب ألا تتجاوز الحد المجاني")

    s = tenancy.get_settings(db)
    changes = {}
    for field in ["free_ops_limit", "alert_threshold_1", "alert_threshold_2",
                  "subscription_price", "subscription_currency",
                  "subscription_duration_days", "grace_period_days", "timezone"]:
        new_val = getattr(body, field)
        old_val = getattr(s, field)
        if new_val != old_val:
            changes[field] = {"old": old_val, "new": new_val}
        setattr(s, field, new_val)
    s.updated_at = tenancy._now_iso()
    s.updated_by = body.actor
    db.commit()
    if changes:
        tenancy.audit(db, body.actor, "settings.update", "settings", 1, details=changes)
    return _settings_payload(s)


@router.get("/api/admin/audit")
def admin_audit(action: str = "", entity: str = "", page: int = Query(default=1, ge=1),
                per_page: int = Query(default=50, ge=1, le=200),
                db: Session = Depends(get_db),
                _: None = Depends(require_service_token)):
    q = db.query(models.AuditLog)
    if action:
        q = q.filter(models.AuditLog.action.contains(action))
    if entity:
        q = q.filter(models.AuditLog.entity == entity)
    total = q.count()
    items = q.order_by(models.AuditLog.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [
            {"id": a.id, "actor": a.actor, "action": a.action, "entity": a.entity,
             "entity_id": a.entity_id, "reason": a.reason, "details": a.details,
             "created_at": a.created_at}
            for a in items
        ],
        "total": total, "page": page, "per_page": per_page,
    }


# ---------------------------------------------------------------- واجهات المزرعة (للتطبيق)

@router.post("/api/v1/farms/register", status_code=201)
def farm_auto_register(body: FarmAutoRegister = None, db: Session = Depends(get_db)):
    """إنشاء مزرعة تلقائياً عند فتح التطبيق لأول مرة (التسجيل الذاتي)"""
    if body is None:
        body = FarmAutoRegister()
        
    farm = models.Farm(
        name=body.name,
        contact_name=body.contact_name,
        contact_phone=body.contact_phone,
        api_key=tenancy._new_api_key(),
        status="active",
        created_at=tenancy._now_iso(),
    )
    db.add(farm)
    db.commit()
    db.refresh(farm)
    tenancy.audit(db, "app_auto_register", "farm.create", "farm", farm.id,
                  details={"name": farm.name})
    
    return {
        "id": farm.id,
        "name": farm.name,
        "api_key": farm.api_key,
        "message": "تم إنشاء المزرعة بنجاح! يمكنك الآن استخدام الباقة المجانية."
    }

@router.get("/api/v1/farms/me/status")
def farm_status(farm: models.Farm = Depends(require_farm), db: Session = Depends(get_db)):
    usage = tenancy.usage_snapshot(db, farm.id)
    sub = tenancy.subscription_info(db, farm.id)
    blocked = tenancy.new_operations_blocked(db, farm)
    return {
        "farm": {
            "id": farm.id, "name": farm.name, "status": farm.status,
            "suspension_reason": farm.suspension_reason if farm.status == "suspended" else None,
        },
        "usage": usage,
        "subscription": sub,
        "new_operations_blocked": blocked["blocked"],
        "message": blocked["message"],
    }


# تعيينات التحقق لكل نوع سجل (نماذج pydantic الحالية)
_TYPE_SCHEMAS = {
    "worker": schemas.WorkerCreate,
    "merchant": schemas.MerchantCreate,
    "crop_sale": schemas.CropSaleCreate,
    "qat_sale": schemas.QatSaleCreate,
    "expense": schemas.ExpenseCreate,
}


def _create_by_type(db: Session, farm: models.Farm, rec_type: str, data: dict,
                    client_uuid: str, enforce_limit: bool):
    if rec_type == "advance":
        worker_id = data.get("worker_id")
        if worker_id is None:
            raise ValueError("worker_id مطلوب للسلفة")
        validated = schemas.AdvanceCreate(**{k: v for k, v in data.items() if k != "worker_id"})
        return record_ops.create_advance(
            db, farm, int(worker_id), validated.model_dump(),
            client_uuid=client_uuid, enforce_limit=enforce_limit)
    if rec_type == "merchant_payment":
        merchant_id = data.get("merchant_id")
        if merchant_id is None:
            raise ValueError("merchant_id مطلوب لدفعة التاجر")
        validated = {k: v for k, v in data.items() if k != "merchant_id"}
        return record_ops.create_merchant_payment(
            db, farm, int(merchant_id), validated,
            client_uuid=client_uuid, enforce_limit=enforce_limit)
    schema = _TYPE_SCHEMAS.get(rec_type)
    if schema is None:
        raise ValueError("نوع سجل غير مدعوم")
    validated = schema(**data)
    creator = {
        "worker": record_ops.create_worker,
        "merchant": record_ops.create_merchant,
        "crop_sale": record_ops.create_crop_sale,
        "qat_sale": record_ops.create_qat_sale,
        "expense": record_ops.create_expense,
    }[rec_type]
    return creator(db, farm, validated.model_dump(), client_uuid=client_uuid,
                   enforce_limit=enforce_limit)


@router.post("/api/v1/farms/me/records/{rec_type}")
def farm_create_record(rec_type: str, body: dict,
                       farm: models.Farm = Depends(require_farm),
                       db: Session = Depends(get_db)):
    """إنشاء مباشر (عند الاتصال): يُطبَّق الحد والاشتراك، مع حماية التكرار."""
    client_uuid = body.get("client_uuid")
    data = body.get("data", {})
    if not client_uuid:
        raise HTTPException(status_code=400, detail="client_uuid مطلوب")
    try:
        result, created = _create_by_type(db, farm, rec_type, data, client_uuid, True)
    except record_ops.BlockedError:
        raise
    except HTTPException:
        raise  # أخطاء موجهة أصلاً (404 عزل المزارع وغيرها) تبقى برمزها الصحيح
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"بيانات غير صالحة: {e}")
    if result is None:
        raise HTTPException(status_code=404, detail="السجل المطلوب غير موجود")
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"created": created, "duplicate": not created, "record": _serialize(result)},
        status_code=201 if created else 200,
    )


@router.post("/api/v1/farms/me/sync")
def farm_sync(body: SyncRequest, farm: models.Farm = Depends(require_farm),
              db: Session = Depends(get_db)):
    """
    مزامنة السجلات المحفوظة دون اتصال:
    - تُقبل كل السجلات ولا تُفقد أبداً حتى لو تجاوزت الحد (تُعلَّم كمتجاوزة).
    - المعرف الفريد يمنع احتساب أي سجل مرتين حتى مع تكرار المزامنة أو تزامن الطلبات.
    - شهر الاحتساب يُحدده الخادم بتوقيت النظام ولا يعتمد على ساعة الجهاز.
    """
    results = []
    accepted = duplicates = failed = 0
    for rec in body.records:
        try:
            result, created = _create_by_type(db, farm, rec.type, rec.data, rec.client_uuid, False)
            if created:
                accepted += 1
                results.append({"client_uuid": rec.client_uuid, "status": "created",
                                "record_id": result.id if result else None})
            else:
                duplicates += 1
                results.append({"client_uuid": rec.client_uuid, "status": "duplicate",
                                "record_id": result.id if result else None})
        except record_ops.BlockedError:
            failed += 1
            results.append({"client_uuid": rec.client_uuid, "status": "rejected"})
        except Exception as e:
            failed += 1
            results.append({"client_uuid": rec.client_uuid, "status": "invalid",
                            "error": str(e)})

    usage = tenancy.usage_snapshot(db, farm.id)
    sub = tenancy.subscription_info(db, farm.id)
    blocked = tenancy.new_operations_blocked(db, farm)
    resp = {
        "farm_id": farm.id,
        "results": results,
        "accepted": accepted,
        "duplicates": duplicates,
        "failed": failed,
        "usage": usage,
        "subscription": sub,
        "new_operations_blocked": blocked["blocked"],
        "message": None,
    }
    if usage["over_limit"] and not sub["active"]:
        resp["message"] = (
            f"تم قبول سجلاتك وحفظها كاملة ({accepted} سجل جديد). "
            f"تجاوزت المزرعة الحد المجاني ({usage['used']} من {usage['limit']} عملية هذا الشهر)؛ "
            "لا يمكن تسجيل عمليات جديدة إلا بعد الاشتراك المدفوع. "
            "بياناتك السابقة كلها محفوظة." +
            (f" للدعم: {SUPPORT_CONTACT}" if SUPPORT_CONTACT else "")
        )
    return resp


def _serialize(obj):
    """تحويل سجل إلى قاموس JSON بسيط."""
    import pydantic
    from datetime import date as _date, datetime as _dt
    if obj is None:
        return None
    if isinstance(obj, models.Base):
        out = {}
        for c in obj.__table__.columns:
            v = getattr(obj, c.name)
            if isinstance(v, (_date, _dt)):
                v = v.isoformat()
            out[c.name] = v
        return out
    return pydantic.TypeAdapter(type(obj)).dump_python(obj)


@router.get("/api/v1/farms/me/records/{rec_type}")
def farm_list_records(rec_type: str, skip: int = 0, limit: int = Query(default=100, le=1000),
                      farm: models.Farm = Depends(require_farm),
                      db: Session = Depends(get_db)):
    tables = {
        "worker": models.Worker, "advance": models.Advance,
        "merchant": models.Merchant, "merchant_payment": models.MerchantTransaction,
        "crop_sale": models.CropSale, "qat_sale": models.QatSale,
        "expense": models.Expense,
    }
    table = tables.get(rec_type)
    if table is None:
        raise HTTPException(status_code=404, detail="نوع سجل غير مدعوم")
    # عزل بيانات المزارع: كل استعلام مقيد بمعرف المزرعة دوماً
    rows = db.query(table).filter(table.farm_id == farm.id).offset(skip).limit(limit).all()
    return {"items": [_serialize(r) for r in rows], "count": len(rows)}
