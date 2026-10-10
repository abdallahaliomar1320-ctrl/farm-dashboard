# -*- coding: utf-8 -*-
"""الاشتراكات: السعر من الإعدادات أو الصفقة، التجديد، فترة السماح، الإلغاء، حالة الدفع."""
import uuid
from calendar import monthrange
from datetime import timedelta

import models
import tenancy
from conftest import create_worker, farm_usage, seed_operations


def _add_month(d):
    y, m = d.year, d.month + 1
    if m > 12:
        y, m = y + 1, 1
    return d.replace(day=min(d.day, monthrange(y, m)[1]), month=m, year=y)


def _create_subscription(client, admin_headers, farm_id, **body):
    payload = {"actor": "test", "payment_status": "pending"}
    payload.update(body)
    r = client.post(f"/api/admin/farms/{farm_id}/subscription",
                    headers=admin_headers, json=payload)
    return r


def _latest_sub(db, farm_id):
    return (db.query(models.Subscription)
            .filter(models.Subscription.farm_id == farm_id)
            .order_by(models.Subscription.id.desc())
            .first())


def _set_end_date(db, farm_id, end_date):
    sub = _latest_sub(db, farm_id)
    sub.end_date = end_date.isoformat()
    db.commit()


def test_subscription_rejected_without_price(client, admin_headers, make_farm, canonical_settings):
    """لا يُخترع سعر: بدون سعر في الإعدادات ولا سعر في الطلب يُرفض الاشتراك."""
    canonical_settings(subscription_price=None)
    farm = make_farm()

    r = _create_subscription(client, admin_headers, farm["id"], months=1)
    assert r.status_code == 400
    assert "سعر" in r.json()["detail"]

    # مع سعر محدد للصفقة يعمل
    r = _create_subscription(client, admin_headers, farm["id"], months=1, price=5000)
    assert r.status_code == 200, r.text
    assert r.json()["subscription_created"]["price"] == 5000


def test_settings_price_used_as_default(client, admin_headers, make_farm, canonical_settings):
    canonical_settings(subscription_price=5000)
    farm = make_farm()

    r = _create_subscription(client, admin_headers, farm["id"], months=1)
    assert r.status_code == 200, r.text
    created = r.json()["subscription_created"]
    assert created["price"] == 5000
    assert created["currency"] == "YER"
    assert created["payment_status"] == "pending"

    d = farm_usage(client, farm["api_key"])
    assert d["subscription"]["active"] is True
    assert d["subscription"]["payment_status"] == "pending"


def test_subscription_allows_creation_beyond_limit(client, admin_headers, make_farm,
                                                   canonical_settings, db_session):
    canonical_settings(subscription_price=5000)
    farm = make_farm()
    key = farm["api_key"]
    seed_operations(db_session, farm["id"], 250)

    r = _create_subscription(client, admin_headers, farm["id"], months=1, price=5000)
    assert r.status_code == 200, r.text

    r = create_worker(client, key, f"sub-w-{uuid.uuid4().hex[:8]}")
    assert r.status_code == 201, r.text
    d = farm_usage(client, key)
    assert d["usage"]["used"] == 251
    assert d["new_operations_blocked"] is False


def test_renewal_extends_from_current_end(client, admin_headers, make_farm, canonical_settings,
                                           db_session):
    """التجديد يبدأ من اليوم التالي لنهاية الاشتراك الساري (لا يُهدر ما تبقى)."""
    canonical_settings(subscription_price=5000)
    farm = make_farm()

    r = _create_subscription(client, admin_headers, farm["id"], months=1, days=15, price=5000)
    assert r.status_code == 200, r.text
    first = r.json()["subscription_created"]

    today = tenancy.system_now(db_session).date()
    assert first["start_date"] == today.isoformat()
    expected_first_end = (_add_month(today) + timedelta(days=15)).isoformat()
    assert first["end_date"] == expected_first_end

    r = _create_subscription(client, admin_headers, farm["id"], months=1, price=5000)
    assert r.status_code == 200, r.text
    second = r.json()["subscription_created"]

    expected_start = (_add_month(today) + timedelta(days=16)).isoformat()
    assert second["start_date"] == expected_start
    expected_second_end = _add_month(_add_month(today) + timedelta(days=16)).isoformat()
    assert second["end_date"] == expected_second_end


def test_expired_beyond_grace_blocks_at_limit(client, admin_headers, make_farm,
                                               canonical_settings, db_session):
    canonical_settings(subscription_price=5000, grace_period_days=7)
    farm = make_farm()
    key = farm["api_key"]

    r = _create_subscription(client, admin_headers, farm["id"], months=1, price=5000)
    assert r.status_code == 200, r.text

    today = tenancy.system_now(db_session).date()
    _set_end_date(db_session, farm["id"], today - timedelta(days=8))
    seed_operations(db_session, farm["id"], 250)

    r = create_worker(client, key, f"exp-w-{uuid.uuid4().hex[:8]}")
    assert r.status_code == 402

    d = farm_usage(client, key)
    assert d["subscription"]["active"] is False
    assert d["subscription"]["status"] == "expired"
    assert d["new_operations_blocked"] is True


def test_within_grace_allows_creation(client, admin_headers, make_farm,
                                      canonical_settings, db_session):
    canonical_settings(subscription_price=5000, grace_period_days=7)
    farm = make_farm()
    key = farm["api_key"]

    r = _create_subscription(client, admin_headers, farm["id"], months=1, price=5000)
    assert r.status_code == 200, r.text

    today = tenancy.system_now(db_session).date()
    _set_end_date(db_session, farm["id"], today - timedelta(days=1))
    seed_operations(db_session, farm["id"], 250)

    r = create_worker(client, key, f"grace-w-{uuid.uuid4().hex[:8]}")
    assert r.status_code == 201, r.text

    d = farm_usage(client, key)
    assert d["subscription"]["active"] is True
    assert d["subscription"]["in_grace"] is True
    assert d["subscription"]["status"] == "grace"


def test_cancel_subscription_blocks_at_limit(client, admin_headers, make_farm,
                                             canonical_settings, db_session):
    canonical_settings(subscription_price=5000)
    farm = make_farm()
    key = farm["api_key"]

    r = _create_subscription(client, admin_headers, farm["id"], months=1, price=5000)
    assert r.status_code == 200, r.text
    seed_operations(db_session, farm["id"], 250)

    r = client.post(f"/api/admin/farms/{farm['id']}/subscription/cancel",
                    headers=admin_headers, json={"reason": "إلغاء تجريبي", "actor": "test"})
    assert r.status_code == 200, r.text

    r = create_worker(client, key, f"cancel-w-{uuid.uuid4().hex[:8]}")
    assert r.status_code == 402
    d = farm_usage(client, key)
    assert d["subscription"]["active"] is False

    # الإلغاء موثق في سجل التدقيق
    r = client.get("/api/admin/audit", headers=admin_headers,
                   params={"action": "subscription.cancel"})
    assert any(e["entity_id"] == str(farm["id"]) for e in r.json()["items"])


def test_cancel_without_active_subscription_rejected(client, admin_headers, make_farm):
    farm = make_farm()
    r = client.post(f"/api/admin/farms/{farm['id']}/subscription/cancel",
                    headers=admin_headers, json={"reason": "لا يوجد اشتراك", "actor": "test"})
    assert r.status_code == 400


def test_payment_status_tracked_administratively(client, admin_headers, make_farm,
                                                  canonical_settings):
    """متابعة إدارية لحالة الدفع فقط (لا بوابة دفع ولا بيانات بطاقات)."""
    canonical_settings(subscription_price=5000)
    farm = make_farm()

    r = _create_subscription(client, admin_headers, farm["id"], months=1, price=5000)
    assert r.status_code == 200, r.text

    r = client.get(f"/api/admin/farms/{farm['id']}", headers=admin_headers)
    assert r.json()["subscription"]["payment_status"] == "pending"

    r = client.post(f"/api/admin/farms/{farm['id']}/payment-status", headers=admin_headers,
                    json={"payment_status": "paid", "actor": "test"})
    assert r.status_code == 200, r.text

    r = client.get(f"/api/admin/farms/{farm['id']}", headers=admin_headers)
    assert r.json()["subscription"]["payment_status"] == "paid"

    # قيمة غير صالحة ترفض
    r = client.post(f"/api/admin/farms/{farm['id']}/payment-status", headers=admin_headers,
                    json={"payment_status": "maybe", "actor": "test"})
    assert r.status_code == 400

    # تغيير حالة الدفع موثق
    r = client.get("/api/admin/audit", headers=admin_headers,
                   params={"action": "subscription.payment_status"})
    assert r.status_code == 200
    assert any(e["entity_id"] == str(farm["id"]) for e in r.json()["items"])


def test_zero_duration_subscription_rejected(client, admin_headers, make_farm,
                                             canonical_settings):
    canonical_settings(subscription_price=5000)
    farm = make_farm()
    r = _create_subscription(client, admin_headers, farm["id"], months=0, days=0)
    assert r.status_code == 400


def test_subscription_creation_audited(client, admin_headers, make_farm, canonical_settings):
    canonical_settings(subscription_price=5000)
    farm = make_farm()
    r = _create_subscription(client, admin_headers, farm["id"], months=1, price=5000)
    assert r.status_code == 200, r.text

    r = client.get("/api/admin/audit", headers=admin_headers,
                   params={"action": "subscription.create"})
    assert r.status_code == 200
    entries = [e for e in r.json()["items"] if e["entity_id"] == str(farm["id"])]
    assert entries
