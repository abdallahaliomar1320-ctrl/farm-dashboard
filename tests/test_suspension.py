# -*- coding: utf-8 -*-
"""تعليق المزرعة: يمنع العمليات الجديدة دون أي حذف أو فقدان للبيانات."""
import uuid

import models
from conftest import create_worker, farm_usage


def _suspend(client, admin_headers, farm_id, reason="اختبار التعليق"):
    r = client.post(f"/api/admin/farms/{farm_id}/status", headers=admin_headers,
                    json={"status": "suspended", "reason": reason})
    assert r.status_code == 200, r.text
    return r.json()


def _activate(client, admin_headers, farm_id, reason="إنهاء الاختبار"):
    r = client.post(f"/api/admin/farms/{farm_id}/status", headers=admin_headers,
                    json={"status": "active", "reason": reason})
    assert r.status_code == 200, r.text
    return r.json()


def test_suspension_blocks_creation_without_deleting(client, admin_headers, make_farm, db_session):
    farm = make_farm()
    key = farm["api_key"]
    r = create_worker(client, key, f"susp-w-{uuid.uuid4().hex[:8]}", name="عامل قبل التعليق")
    assert r.status_code == 201, r.text
    workers_before = db_session.query(models.Worker).filter(
        models.Worker.farm_id == farm["id"]).count()

    _suspend(client, admin_headers, farm["id"])

    r = create_worker(client, key, f"susp-w2-{uuid.uuid4().hex[:8]}")
    assert r.status_code == 403
    assert "معلق" in r.json()["detail"]

    # القراءة مستمرة والبيانات محفوظة كما هي
    r = client.get("/api/v1/farms/me/records/worker", headers={"X-Farm-Key": key})
    assert r.status_code == 200
    assert r.json()["count"] == workers_before
    assert db_session.query(models.Worker).filter(
        models.Worker.farm_id == farm["id"]).count() == workers_before


def test_status_shows_blocked_and_reason(client, admin_headers, make_farm):
    farm = make_farm()
    key = farm["api_key"]
    reason = "سبب تعليق تجريبي"
    _suspend(client, admin_headers, farm["id"], reason)

    d = farm_usage(client, key)
    assert d["farm"]["status"] == "suspended"
    assert d["farm"]["suspension_reason"] == reason
    assert d["new_operations_blocked"] is True
    assert "معلق" in (d["message"] or "")


def test_duplicate_retry_while_suspended_returns_existing(client, admin_headers, make_farm):
    """إعادة محاولة سجل موجود أثناء التعليق تعيد السجل نفسه (idempotency قبل الحجب)."""
    farm = make_farm()
    key = farm["api_key"]
    cu = f"susp-dup-{uuid.uuid4().hex[:8]}"
    r1 = create_worker(client, key, cu)
    assert r1.status_code == 201
    rec_id = r1.json()["record"]["id"]

    _suspend(client, admin_headers, farm["id"])
    r2 = create_worker(client, key, cu)
    assert r2.status_code == 200
    assert r2.json()["record"]["id"] == rec_id


def test_reactivation_restores_creation(client, admin_headers, make_farm):
    farm = make_farm()
    key = farm["api_key"]
    _suspend(client, admin_headers, farm["id"])
    _activate(client, admin_headers, farm["id"])

    r = create_worker(client, key, f"susp-w3-{uuid.uuid4().hex[:8]}")
    assert r.status_code == 201, r.text
    d = farm_usage(client, key)
    assert d["farm"]["status"] == "active"
    assert d["farm"]["suspension_reason"] is None
    assert d["new_operations_blocked"] is False


def test_sync_from_suspended_farm_accepted_without_loss(client, admin_headers, make_farm):
    """المزامنة من مزرعة معلقة تُقبل حفاظاً على البيانات المحلية (سياسة معلنة)."""
    farm = make_farm()
    key = farm["api_key"]
    _suspend(client, admin_headers, farm["id"])

    cu = f"susp-sync-{uuid.uuid4().hex[:8]}"
    r = client.post("/api/v1/farms/me/sync", headers={"X-Farm-Key": key},
                    json={"records": [{"client_uuid": cu, "type": "worker", "data": {
                        "name": "عامل أثناء التعليق", "phone": "070", "start_date": "2026-01-01",
                        "job": "عامل", "pay_type": "شهري", "pay_amount": 1000}}]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["accepted"] == 1
    assert d["failed"] == 0

    # السجل محفوظ فعلاً
    r = client.get("/api/v1/farms/me/records/worker", headers={"X-Farm-Key": key})
    assert any(w["name"] == "عامل أثناء التعليق" for w in r.json()["items"])


def test_duplicate_status_change_rejected(client, admin_headers, make_farm):
    farm = make_farm()
    _suspend(client, admin_headers, farm["id"])
    r = client.post(f"/api/admin/farms/{farm['id']}/status", headers=admin_headers,
                    json={"status": "suspended", "reason": "محاولة تكرار"})
    assert r.status_code == 400


def test_suspension_audited_with_reason(client, admin_headers, make_farm):
    farm = make_farm()
    reason = f"سبب موثق {uuid.uuid4().hex[:6]}"
    _suspend(client, admin_headers, farm["id"], reason)

    r = client.get("/api/admin/audit", headers=admin_headers,
                   params={"action": "farm.suspended", "entity": "farm"})
    assert r.status_code == 200
    entries = [e for e in r.json()["items"] if e["entity_id"] == str(farm["id"])]
    assert entries, "لم يُسجل التعليق في سجل التدقيق"
    assert entries[0]["reason"] == reason

    # إعادة التنشيط تُسجل أيضاً
    _activate(client, admin_headers, farm["id"])
    r = client.get("/api/admin/audit", headers=admin_headers,
                   params={"action": "farm.active", "entity": "farm"})
    assert any(e["entity_id"] == str(farm["id"]) for e in r.json()["items"])


def test_admin_farms_filter_suspended(client, admin_headers, make_farm):
    farm = make_farm()
    _suspend(client, admin_headers, farm["id"])
    r = client.get("/api/admin/farms", headers=admin_headers, params={"status": "suspended"})
    assert r.status_code == 200
    ids = [f["id"] for f in r.json()["items"]]
    assert farm["id"] in ids
    assert all(f["status"] == "suspended" for f in r.json()["items"])
