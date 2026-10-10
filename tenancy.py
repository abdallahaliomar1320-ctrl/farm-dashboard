# -*- coding: utf-8 -*-
"""
وحدة تعدد المزارع والباقات — المصدر النهائي لصحة البيانات والاحتساب.

تحتوي على:
- ترحيل غير هدّام لقاعدة البيانات الحالية (إضافة أعمدة farm_id وجداول جديدة مع نسخة احتياطية).
- منطق احتساب العمليات الشهرية ومنع التكرار (idempotency).
- التحقق من الاشتراك والحد المجاني وفترة السماح.
- سجل تدقيق محمي (إضافة فقط).
"""
import os
import json
import shutil
import secrets
from datetime import datetime, timedelta, date

from sqlalchemy import text
from fastapi import HTTPException

import models
from database import engine, SessionLocal

DEFAULT_FARM_NAME = "المزرعة الرئيسية"
LEGACY_TABLES = [
    "workers", "advances", "merchants", "merchant_transactions",
    "crop_sales", "qat_sales", "expenses",
]

# أنواع العمليات المحتسبة (إنشاء سجل جديد فقط — التعديل والحذف وإعادة المزامنة لا تُحتسب)
COUNTED_OP_TYPES = {
    "worker", "advance", "merchant", "merchant_payment",
    "crop_sale", "qat_sale", "expense",
}


def run_migrations():
    """ترحيل غير هدّام: ينشئ الجداول/الأعمدة الناقصة فقط، وينسخ farm.db احتياطياً قبل أول تعديل."""
    db_path = _sqlite_file_path()
    with engine.connect() as conn:
        existing_tables = {
            r[0] for r in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }

        needs_alter = any(
            t in existing_tables and not _table_has_column(conn, t, "farm_id")
            for t in LEGACY_TABLES
        )
        if needs_alter and db_path and os.path.exists(db_path):
            backup = f"farm_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2(db_path, backup)

        # 1) إنشاء الجداول الجديدة إن لم تكن موجودة
        models.Base.metadata.create_all(bind=engine)

        # 2) إضافة عمود farm_id للجداول القديمة إن لم يوجد
        for t in LEGACY_TABLES:
            if t in existing_tables and not _table_has_column(conn, t, "farm_id"):
                conn.execute(text(f"ALTER TABLE [{t}] ADD COLUMN farm_id INTEGER"))
        conn.commit()

    with SessionLocal() as db:
        # 3) مزرعة افتراضية تُنسب إليها البيانات الحالية (تُنشأ مرة واحدة فقط)
        default_farm = db.query(models.Farm).filter(models.Farm.id == 1).first()
        if default_farm is None:
            default_farm = models.Farm(
                id=1,
                name=DEFAULT_FARM_NAME,
                api_key=_new_api_key(),
                status="active",
                notes="المزرعة الافتراضية — تضم البيانات السابقة لتطبيق تعدد المزارع",
                created_at=_now_iso(),
            )
            db.add(default_farm)
            db.commit()

        # 4) إسناد الصفوف القديمة للمزرعة الافتراضية
        with engine.connect() as conn:
            for t in LEGACY_TABLES:
                conn.execute(
                    text(f"UPDATE [{t}] SET farm_id = 1 WHERE farm_id IS NULL")
                )
            conn.commit()

        # 5) صف الإعدادات العام
        if db.query(models.AppSettings).count() == 0:
            db.add(models.AppSettings(id=1, updated_at=_now_iso()))
            db.commit()


def _sqlite_file_path():
    url = str(engine.url)
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    return None


def _table_has_column(conn, table, column):
    cols = [r[1] for r in conn.execute(text(f"PRAGMA table_info([{table}])"))]
    return column in cols


def _now_iso():
    return datetime.now().isoformat(timespec="seconds")


def _new_api_key():
    return "farm_" + secrets.token_urlsafe(32)


# ---------------------------------------------------------------- الوقت والشهر

def system_now(db: SessionLocal) -> datetime:
    """الوقت الحالي بتوقيت النظام المضبوط في الإعدادات — لا يُعتمد على ساعة العميل."""
    from zoneinfo import ZoneInfo
    from datetime import timezone
    tz_name = get_settings(db).timezone or "Asia/Aden"
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        pass
    for fallback_tz in ("Asia/Aden", "UTC"):
        try:
            return datetime.now(ZoneInfo(fallback_tz))
        except Exception:
            continue
    return datetime.now(timezone.utc)


def current_month_key(db: SessionLocal) -> str:
    return system_now(db).strftime("%Y-%m")


def month_key_for(month: str):
    """تحقق من صحة مفتاح الشهر YYYY-MM"""
    try:
        datetime.strptime(month, "%Y-%m")
        return month
    except ValueError:
        raise HTTPException(status_code=400, detail="صيغة الشهر غير صحيحة، استخدم YYYY-MM")


# ---------------------------------------------------------------- الإعدادات

def get_settings(db: SessionLocal) -> models.AppSettings:
    s = db.query(models.AppSettings).filter(models.AppSettings.id == 1).first()
    if s is None:
        s = models.AppSettings(id=1, updated_at=_now_iso())
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


# ---------------------------------------------------------------- سجل التدقيق (إضافة فقط)

def audit(db: SessionLocal, actor: str, action: str, entity: str = None,
          entity_id=None, reason: str = None, details: dict = None):
    entry = models.AuditLog(
        actor=actor or "system",
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        reason=reason,
        details=json.dumps(details, ensure_ascii=False) if details else None,
        created_at=_now_iso(),
    )
    db.add(entry)
    db.commit()


# ---------------------------------------------------------------- الاحتساب

def count_operations(db: SessionLocal, farm_id: int, month_key: str) -> int:
    return db.query(models.Operation).filter(
        models.Operation.farm_id == farm_id,
        models.Operation.month_key == month_key,
    ).count()


def usage_snapshot(db: SessionLocal, farm_id: int, month_key: str = None) -> dict:
    """لقطة استخدام المزرعة لشهر معين (الحالي افتراضاً) مقارنةً بالحد المجاني."""
    s = get_settings(db)
    mk = month_key or current_month_key(db)
    used = count_operations(db, farm_id, mk)
    limit = s.free_ops_limit or 250
    return {
        "month": mk,
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
        "over_limit": used > limit,
        "at_limit": used >= limit,
        "percent": round(used * 100.0 / limit, 1) if limit else 0.0,
        "threshold_1_reached": used >= (s.alert_threshold_1 or 200),
        "threshold_2_reached": used >= (s.alert_threshold_2 or 240),
    }


class BlockedError(HTTPException):
    """حجب إنشاء عمليات جديدة (تعليق حساب أو بلوغ الحد) مع رسالة واضحة."""
    def __init__(self, code: str, message: str):
        super().__init__(status_code=403 if code == "farm_suspended" else 402, detail=message)
        self.code = code


def claim_operation(db: SessionLocal, farm_id: int, client_uuid: str, op_type: str,
                    record_table: str, enforce_limit: bool = True,
                    farm: "models.Farm" = None) -> bool:
    """
    يحجز المعرف الفريد للعملية ويسجلها في سجل الاحتساب، مع فحص الحد والتعليق.

    - إعادة نفس المعرف (فشل اتصال، مزامنة مكررة، طلبات متزامنة) → False دون احتساب جديد.
    - القيد الفريد (farm_id, client_uuid) يحسم سباق الطلبات المتزامنة.
    - فحص الحد يجري داخل نفس المعاملة بعد الإدراج، فلا يمكن أن يتزاحم مع طلب موازٍ.
    - enforce_limit=False (مسار المزامنة غير المتصلة): يقبل دائماً ولا يرفض سجلاً أبداً.

    يرفع BlockedError عند الحجب (التراجع كامل فلا يُحتسب شيء).
    """
    exists = db.query(models.Operation).filter(
        models.Operation.farm_id == farm_id,
        models.Operation.client_uuid == client_uuid,
    ).first()
    if exists:
        return False
    if enforce_limit and farm is not None and farm.status == "suspended":
        raise BlockedError("farm_suspended", (
            "حساب المزرعة معلق حالياً، لا يمكن إنشاء عمليات جديدة. "
            "بياناتك المحلية محفوظة ولم تُحذف. للاستفسار تواصل مع الدعم."
        ))
    op = models.Operation(
        farm_id=farm_id,
        client_uuid=client_uuid,
        op_type=op_type,
        record_table=record_table,
        month_key=current_month_key(db),
        created_at=_now_iso(),
    )
    db.add(op)
    try:
        db.flush()
        if enforce_limit:
            s = get_settings(db)
            limit = s.free_ops_limit or 250
            used_including_this = db.query(models.Operation).filter(
                models.Operation.farm_id == farm_id,
                models.Operation.month_key == op.month_key,
            ).count()
            sub = subscription_info(db, farm_id)
            if not sub["active"] and used_including_this > limit:
                db.rollback()
                msg = (
                    f"بلغت المزرعة الحد المجاني ({limit} عملية في الشهر). "
                    "للاستمرار في تسجيل عمليات جديدة يلزم اشتراك مدفوع."
                )
                contact = os.environ.get("SUPPORT_CONTACT", "")
                if contact:
                    msg += f" للدعم: {contact}"
                raise BlockedError("limit_reached", msg)
        db.commit()
    except BlockedError:
        raise
    except Exception:
        # سباق تزامن: حجز طلب آخر نفس المعرف أولاً — ليست عملية جديدة
        db.rollback()
        return False
    return True


def attach_record_id(db: SessionLocal, farm_id: int, client_uuid: str, record_id: int):
    """يربط السجل المنشأ بعملية الاحتساب المحجوزة مسبقاً."""
    db.query(models.Operation).filter(
        models.Operation.farm_id == farm_id,
        models.Operation.client_uuid == client_uuid,
    ).update({"record_id": record_id})
    db.commit()


# ---------------------------------------------------------------- الاشتراك

def active_subscription(db: SessionLocal, farm_id: int, now: datetime = None) -> models.Subscription:
    """أحدث اشتراك فعال: لم ينتهِ، أو ضمن فترة السماح بعد الانتهاء."""
    s = get_settings(db)
    now = now or system_now(db)
    grace = timedelta(days=s.grace_period_days or 0)
    subs = (
        db.query(models.Subscription)
        .filter(models.Subscription.farm_id == farm_id, models.Subscription.status == "active")
        .order_by(models.Subscription.end_date.desc())
        .all()
    )
    for sub in subs:
        try:
            end = date.fromisoformat(sub.end_date) if sub.end_date else None
        except ValueError:
            end = None
        if end is None:
            return sub
        if now.date() <= end + grace:
            return sub
    return None


def subscription_info(db: SessionLocal, farm_id: int, now: datetime = None) -> dict:
    s = get_settings(db)
    now = now or system_now(db)
    sub = active_subscription(db, farm_id, now)
    if sub is None:
        latest = (
            db.query(models.Subscription)
            .filter(models.Subscription.farm_id == farm_id)
            .order_by(models.Subscription.end_date.desc())
            .first()
        )
        return {
            "active": False,
            "in_grace": False,
            "status": "none" if latest is None else "expired",
            "end_date": latest.end_date if latest else None,
            "payment_status": latest.payment_status if latest else None,
            "price": latest.price if latest else None,
            "currency": s.subscription_currency,
            "id": latest.id if latest else None,
        }
    try:
        end = date.fromisoformat(sub.end_date) if sub.end_date else None
    except ValueError:
        end = None
    in_grace = end is not None and end < now.date() and now.date() <= end + timedelta(days=s.grace_period_days or 0)
    return {
        "active": True,
        "in_grace": in_grace,
        "status": "grace" if in_grace else "active",
        "end_date": sub.end_date,
        "payment_status": sub.payment_status,
        "price": sub.price,
        "currency": sub.currency,
        "id": sub.id,
    }


def new_operations_blocked(db: SessionLocal, farm: models.Farm, month_key: str = None) -> dict:
    """سياسة الحد: تُمنع العمليات الجديدة (المباشرة) عند بلوغ الحد دون اشتراك فعّال أو عند التعليق."""
    usage = usage_snapshot(db, farm.id, month_key)
    sub = subscription_info(db, farm.id)
    if farm.status == "suspended":
        return {
            "blocked": True,
            "code": "farm_suspended",
            "message": (
                "حساب المزرعة معلق حالياً ولا يمكن إنشاء عمليات جديدة. "
                "بياناتك المحلية محفوظة ولم تُحذف. للاستفسار تواصل مع الدعم."
            ),
        }
    if not sub["active"] and usage["at_limit"]:
        s = get_settings(db)
        contact = os.environ.get("SUPPORT_CONTACT", "")
        msg = (
            f"بلغت المزرعة الحد المجاني ({s.free_ops_limit} عملية في الشهر). "
            "للاستمرار في تسجيل عمليات جديدة يلزم اشتراك مدفوع."
        )
        if contact:
            msg += f" للدعم: {contact}"
        return {"blocked": True, "code": "limit_reached", "message": msg}
    return {"blocked": False, "code": None, "message": None}


def ensure_farm_or_404(db: SessionLocal, farm_id: int) -> models.Farm:
    farm = db.query(models.Farm).filter(models.Farm.id == farm_id).first()
    if farm is None:
        raise HTTPException(status_code=404, detail="المزرعة غير موجودة")
    return farm


def farm_totals(db: SessionLocal, farm_id: int) -> dict:
    """إجماليات سجلات المزرعة (للعرض فقط)."""
    return {
        "workers": db.query(models.Worker).filter(models.Worker.farm_id == farm_id).count(),
        "advances": db.query(models.Advance).filter(models.Advance.farm_id == farm_id).count(),
        "merchants": db.query(models.Merchant).filter(models.Merchant.farm_id == farm_id).count(),
        "crop_sales": db.query(models.CropSale).filter(models.CropSale.farm_id == farm_id).count(),
        "qat_sales": db.query(models.QatSale).filter(models.QatSale.farm_id == farm_id).count(),
        "expenses": db.query(models.Expense).filter(models.Expense.farm_id == farm_id).count(),
    }
