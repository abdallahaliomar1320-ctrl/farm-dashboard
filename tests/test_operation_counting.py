# -*- coding: utf-8 -*-
"""اختبارات احتساب الحد المجاني (250 عملية/شهر) وتغيير الشهر."""
import uuid

from conftest import create_worker, farm_usage, prev_month_key, seed_operations


def test_operation_250_allowed_251_blocked(client, admin_headers, make_farm, db_session):
    """العملية رقم 250 مسموحة، والعملية 251 ممنوعة مع رسالة واضحة، دون احتساب وهمي."""
    farm = make_farm()
    key = farm["api_key"]
    seed_operations(db_session, farm["id"], 249)

    r = create_worker(client, key, "limit-worker-250")
    assert r.status_code == 201, r.text
    usage = farm_usage(client, key)["usage"]
    assert usage["used"] == 250
    assert usage["at_limit"] is True
    assert usage["remaining"] == 0

    r = create_worker(client, key, "limit-worker-251")
    assert r.status_code == 402
    assert "الحد المجاني" in r.json()["detail"]

    # لا عملية وهمية محتسبة بعد الرفض
    assert farm_usage(client, key)["usage"]["used"] == 250


def test_month_rollover_resets_usage(client, make_farm, db_session):
    """تغيير الشهر يصفّر الاحتساب: عمليات الشهر الماضي لا تحسب على الشهر الحالي."""
    import tenancy
    farm = make_farm()
    key = farm["api_key"]
    prev = prev_month_key(tenancy.current_month_key(db_session))
    seed_operations(db_session, farm["id"], 250, month_key=prev)

    r = create_worker(client, key, "new-month-worker-1")
    assert r.status_code == 201, r.text
    usage = farm_usage(client, key)["usage"]
    assert usage["used"] == 1
    assert usage["over_limit"] is False


def test_usage_month_key_is_server_timezone(client, make_farm, db_session):
    """مفتاح الشهر يُحدده الخادم بتوقيت النظام (لا ساعة الجهاز)."""
    import tenancy
    farm = make_farm()
    usage = farm_usage(client, farm["api_key"])["usage"]
    assert usage["month"] == tenancy.current_month_key(db_session)


def test_all_record_types_counted_once(client, make_farm):
    """كل نوع سجل جديد يُحتسب عملية واحدة (عامل/سلفة/تاجر/دفعة/مبيعات/مصروف)."""
    farm = make_farm()
    key = farm["api_key"]
    tag = uuid.uuid4().hex[:6]

    r = client.post("/api/v1/farms/me/records/worker", headers={"X-Farm-Key": key},
                    json={"client_uuid": f"{tag}-w", "data": {
                        "name": "عامل", "phone": "070", "start_date": "2026-01-01",
                        "job": "عامل", "pay_type": "شهري", "pay_amount": 1000}})
    assert r.status_code == 201, r.text
    worker_id = r.json()["record"]["id"]

    r = client.post("/api/v1/farms/me/records/merchant", headers={"X-Farm-Key": key},
                    json={"client_uuid": f"{tag}-m", "data": {"name": "تاجر", "phone": "071"}})
    assert r.status_code == 201, r.text
    merchant_id = r.json()["record"]["id"]

    r = client.post("/api/v1/farms/me/records/advance", headers={"X-Farm-Key": key},
                    json={"client_uuid": f"{tag}-a", "data": {"worker_id": worker_id, "amount": 100, "date": "2026-10-01"}})
    assert r.status_code == 201, r.text

    r = client.post("/api/v1/farms/me/records/merchant_payment", headers={"X-Farm-Key": key},
                    json={"client_uuid": f"{tag}-mp", "data": {"merchant_id": merchant_id, "amount": 50, "description": "دفعة", "date": "2026-10-01"}})
    assert r.status_code == 201, r.text

    r = client.post("/api/v1/farms/me/records/crop_sale", headers={"X-Farm-Key": key},
                    json={"client_uuid": f"{tag}-cs", "data": {
                        "crop_name": "طماطم", "unit": "كيس", "quantity": 10, "price_per_unit": 50,
                        "total_price": 500, "paid_amount": 500, "remaining_amount": 0, "date": "2026-10-01"}})
    assert r.status_code == 201, r.text

    r = client.post("/api/v1/farms/me/records/qat_sale", headers={"X-Farm-Key": key},
                    json={"client_uuid": f"{tag}-qs", "data": {
                        "qat_type": "قصاص", "unit": "حزمة", "quantity": 5, "total_price": 250,
                        "paid_amount": 250, "remaining_amount": 0, "date": "2026-10-01"}})
    assert r.status_code == 201, r.text

    r = client.post("/api/v1/farms/me/records/expense", headers={"X-Farm-Key": key},
                    json={"client_uuid": f"{tag}-e", "data": {"category": "وقود", "amount": 30, "date": "2026-10-01"}})
    assert r.status_code == 201, r.text

    usage = farm_usage(client, key)["usage"]
    assert usage["used"] == 7


def test_admin_usage_endpoint_lists_at_limit_farm(client, admin_headers, make_farm, db_session):
    farm = make_farm()
    seed_operations(db_session, farm["id"], 251)  # فوق الحد: used > limit
    r = client.get("/api/admin/usage", headers=admin_headers)
    assert r.status_code == 200
    d = r.json()
    over = [f["farm_id"] for f in d.get("over_limit", [])]
    assert farm["id"] in over


def test_admin_alerts_report_thresholds(client, admin_headers, make_farm, db_session):
    farm = make_farm()
    seed_operations(db_session, farm["id"], 205)  # بين العتبتين 200 و240
    r = client.get("/api/admin/alerts", headers=admin_headers)
    assert r.status_code == 200
    levels = {a["farm_id"]: a["level"] for a in r.json()["alerts"]}
    assert levels.get(farm["id"]) == "threshold_1"
