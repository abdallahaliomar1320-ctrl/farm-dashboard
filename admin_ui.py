import os
import secrets
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import models
import tenancy
from database import SessionLocal
from admin_api import _farm_payload, _settings_payload

router = APIRouter()
templates = Jinja2Templates(directory="templates")
security = HTTPBasic()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    expected_user = os.environ.get("ADMIN_USER", "admin")
    expected_pass = os.environ.get("ADMIN_PASS", "123456")
    correct_username = secrets.compare_digest(credentials.username, expected_user)
    correct_password = secrets.compare_digest(credentials.password, expected_pass)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Context processor for templates
def render(request: Request, name: str, context: dict = {}):
    ctx = {"request": request, "app_name": "إدارة المزارع"}
    ctx.update(context)
    return templates.TemplateResponse(request=request, name=name, context=ctx)

@router.get("/admin/offline-keys", response_class=HTMLResponse)
def offline_keys_page(request: Request, device_id: str = "", ops: str = "500", _: str = Depends(require_admin)):
    SECRET_KEY = "FARM_2026_SECRET"
    code = ""
    
    if device_id:
        raw = f"{device_id.upper()}-{ops}-{SECRET_KEY}"
        hash_val = 0
        for char in raw:
            hash_val = (hash_val * 31 + ord(char)) % 1000000
        hex_val = f"{hash_val:04X}"
        hash_code = hex_val[-4:]
        code = f"{ops}-{hash_code}"

    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <title>مولد أكواد التفعيل</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-light">
        <div class="container mt-5" style="max-width: 600px;">
            <h2 class="mb-4">🔑 مولد أكواد التفعيل الأوفلاين</h2>
            <div class="card p-4 shadow-sm border-0">
                <form method="get">
                    <div class="mb-3">
                        <label>رمز جهاز العميل (4 حروف/أرقام):</label>
                        <input type="text" name="device_id" value="{device_id}" class="form-control form-control-lg text-center" style="letter-spacing: 5px;" required>
                    </div>
                    <div class="mb-3">
                        <label>الباقة (عدد العمليات مثلاً 500 أو 10000):</label>
                        <input type="number" name="ops" value="{ops}" class="form-control form-control-lg text-center" required>
                    </div>
                    <button type="submit" class="btn btn-success btn-lg w-100">توليد كود التفعيل</button>
                </form>
                {f"<hr><div class='text-center mt-3'><p class='text-muted'>أعطِ العميل هذا الكود:</p><h1 class='text-primary' style='letter-spacing: 5px;'>{code}</h1></div>" if code else ""}
            </div>
            <div class="text-center mt-4">
                <a href="/admin" class="btn btn-secondary">العودة للوحة المزارع</a>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db), _: str = Depends(require_admin)):
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

    data = {
        "farms_total": len(farms),
        "farms_active": sum(1 for f in farms if f.status == "active"),
        "farms_suspended": sum(1 for f in farms if f.status == "suspended"),
        "subscriptions_active": sum(
            1 for f in farms if tenancy.subscription_info(db, f.id, now)["active"]
        ),
        "subscriptions_expiring_soon": expiring_soon,
        "total_operations": total_operations,
        "month_operations": month_operations,
    }
    return render(request, "dashboard.html", {"data": data, "active_route": "dashboard"})

@router.get("/admin/farms", response_class=HTMLResponse)
def admin_farms(request: Request, search: str = "", status: str = "", db: Session = Depends(get_db), _: str = Depends(require_admin)):
    q = db.query(models.Farm)
    if search:
        q = q.filter(models.Farm.name.contains(search))
    if status:
        q = q.filter(models.Farm.status == status)
    farms = q.order_by(models.Farm.id).all()
    
    items = []
    for f in farms:
        items.append(_farm_payload(db, f))
        
    return render(request, "farms/index.html", {"items": items, "search": search, "status": status, "active_route": "farms"})

@router.get("/admin/farms/create", response_class=HTMLResponse)
def admin_farms_create(request: Request, _: str = Depends(require_admin)):
    return render(request, "farms/create.html", {"active_route": "farms"})

@router.post("/admin/farms")
def admin_farms_store(request: Request, name: str = Form(...), contact_name: str = Form(""), contact_phone: str = Form(""), notes: str = Form(""), db: Session = Depends(get_db), actor: str = Depends(require_admin)):
    if db.query(models.Farm).filter(models.Farm.name == name).first():
        return render(request, "farms/create.html", {"error": "توجد مزرعة بنفس الاسم مسبقاً", "active_route": "farms"})
    
    farm = models.Farm(
        name=name,
        contact_name=contact_name,
        contact_phone=contact_phone,
        notes=notes,
        api_key=tenancy._new_api_key(),
        status="active",
        created_at=tenancy._now_iso(),
    )
    db.add(farm)
    db.commit()
    db.refresh(farm)
    tenancy.audit(db, actor, "farm.create", "farm", farm.id, details={"name": farm.name})
    return RedirectResponse(url=f"/admin/farms/{farm.id}?success=1", status_code=303)

@router.get("/admin/farms/{farm_id}", response_class=HTMLResponse)
def admin_farms_show(request: Request, farm_id: int, success: str = "", db: Session = Depends(get_db), _: str = Depends(require_admin)):
    farm = tenancy.ensure_farm_or_404(db, farm_id)
    payload = _farm_payload(db, farm, with_totals=True)
    subs = db.query(models.Subscription).filter(
        models.Subscription.farm_id == farm.id
    ).order_by(models.Subscription.id.desc()).all()
    payload["subscriptions_history"] = [
        {"id": x.id, "status": x.status, "start_date": x.start_date, "end_date": x.end_date,
         "price": x.price, "currency": x.currency, "payment_status": x.payment_status}
        for x in subs
    ]
    return render(request, "farms/show.html", {"farm": payload, "success": success, "active_route": "farms"})

@router.post("/admin/farms/{farm_id}/status")
def admin_farms_status(farm_id: int, status: str = Form(...), reason: str = Form(""), db: Session = Depends(get_db), actor: str = Depends(require_admin)):
    farm = tenancy.ensure_farm_or_404(db, farm_id)
    farm.status = status
    farm.suspension_reason = reason if status == "suspended" else None
    db.commit()
    tenancy.audit(db, actor, f"farm.{status}", "farm", farm.id, reason=reason)
    return RedirectResponse(url=f"/admin/farms/{farm.id}?success=status_updated", status_code=303)

@router.post("/admin/farms/{farm_id}/subscription")
def admin_farms_subscription(farm_id: int, months: int = Form(1), days: int = Form(0), price: float = Form(0), payment_status: str = Form("paid"), db: Session = Depends(get_db), actor: str = Depends(require_admin)):
    from datetime import date, timedelta
    farm = tenancy.ensure_farm_or_404(db, farm_id)
    s = tenancy.get_settings(db)
    now = tenancy.system_now(db)
    
    current = tenancy.active_subscription(db, farm.id, now)
    start = now.date()
    if current is not None and current.end_date:
        try:
            cur_end = date.fromisoformat(current.end_date)
            if cur_end >= start:
                start = cur_end + timedelta(days=1)
        except ValueError:
            pass
            
    end = start + timedelta(days=months * 30 + days)
    
    sub = models.Subscription(
        farm_id=farm.id, status="active", start_date=start.isoformat(),
        end_date=end.isoformat(), price=price or s.subscription_price or 0.0,
        currency=s.subscription_currency, payment_status=payment_status,
        created_by=actor, created_at=tenancy._now_iso(),
    )
    db.add(sub)
    db.commit()
    tenancy.audit(db, actor, "subscription.create", "farm", farm.id)
    return RedirectResponse(url=f"/admin/farms/{farm.id}?success=sub_added", status_code=303)

@router.get("/admin/usage", response_class=HTMLResponse)
def admin_usage(request: Request, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    mk = tenancy.current_month_key(db)
    farms = db.query(models.Farm).order_by(models.Farm.id).all()
    items = []
    for f in farms:
        items.append({
            "farm_id": f.id, "farm_name": f.name, "status": f.status,
            "usage": tenancy.usage_snapshot(db, f.id, mk),
        })
    near_limit = [i for i in items if i["usage"]["threshold_1_reached"] and not i["usage"]["over_limit"]]
    over_limit = [i for i in items if i["usage"]["over_limit"]]
    at_limit = [i for i in items if i["usage"]["at_limit"] and not i["usage"]["over_limit"]]
    
    data = {"month": mk, "items": items, "near_limit": near_limit, "at_limit": at_limit, "over_limit": over_limit}
    return render(request, "usage/index.html", {"data": data, "active_route": "usage"})

@router.get("/admin/settings", response_class=HTMLResponse)
def admin_settings(request: Request, success: str = "", db: Session = Depends(get_db), _: str = Depends(require_admin)):
    s = tenancy.get_settings(db)
    return render(request, "settings/edit.html", {"settings": _settings_payload(s), "success": success, "active_route": "settings"})

@router.post("/admin/settings")
def admin_settings_update(
    free_ops_limit: int = Form(...), alert_threshold_1: int = Form(...), alert_threshold_2: int = Form(...),
    subscription_price: float = Form(0), subscription_currency: str = Form(...),
    subscription_duration_days: int = Form(...), grace_period_days: int = Form(...), timezone: str = Form(...),
    db: Session = Depends(get_db), actor: str = Depends(require_admin)
):
    s = tenancy.get_settings(db)
    s.free_ops_limit = free_ops_limit
    s.alert_threshold_1 = alert_threshold_1
    s.alert_threshold_2 = alert_threshold_2
    s.subscription_price = subscription_price
    s.subscription_currency = subscription_currency
    s.subscription_duration_days = subscription_duration_days
    s.grace_period_days = grace_period_days
    s.timezone = timezone
    s.updated_at = tenancy._now_iso()
    s.updated_by = actor
    db.commit()
    tenancy.audit(db, actor, "settings.update", "settings", 1)
    return RedirectResponse(url="/admin/settings?success=1", status_code=303)

@router.get("/admin/audit", response_class=HTMLResponse)
def admin_audit(request: Request, db: Session = Depends(get_db), _: str = Depends(require_admin)):
    items = db.query(models.AuditLog).order_by(models.AuditLog.id.desc()).limit(100).all()
    return render(request, "audit/index.html", {"items": items, "active_route": "audit"})
