# -*- coding: utf-8 -*-
"""عزل بيانات المزارع: لا ترى مزرعة بيانات مزرعة أخرى حتى بمعرفات صحيحة."""
import uuid

from conftest import create_worker, farm_usage


def _list_records(client, key, rec_type):
    r = client.get(f"/api/v1/farms/me/records/{rec_type}", headers={"X-Farm-Key": key})
    assert r.status_code == 200, r.text
    return r.json()


def test_records_scoped_per_farm(client, make_farm):
    """سجلات المزرعة أ لا تظهر في قوائم المزرعة ب."""
    farm_a = make_farm()
    farm_b = make_farm()
    name = f"عامل معزول {uuid.uuid4().hex[:6]}"

    r = create_worker(client, farm_a["api_key"], f"iso-w-{uuid.uuid4().hex[:8]}", name=name)
    assert r.status_code == 201, r.text

    a = _list_records(client, farm_a["api_key"], "worker")
    b = _list_records(client, farm_b["api_key"], "worker")
    assert a["count"] >= 1
    assert any(w["name"] == name for w in a["items"])
    assert b["count"] == 0
    assert all(w["name"] != name for w in b["items"])


def test_cross_farm_worker_id_rejected(client, make_farm):
    """سلفة على عامل من مزرعة أخرى تُرفض 404 (منع الوصول بتغيير المعرفات)."""
    farm_a = make_farm()
    farm_b = make_farm()
    r = create_worker(client, farm_a["api_key"], f"iso-wa-{uuid.uuid4().hex[:8]}")
    assert r.status_code == 201, r.text
    worker_a_id = r.json()["record"]["id"]

    r = client.post("/api/v1/farms/me/records/advance", headers={"X-Farm-Key": farm_b["api_key"]},
                    json={"client_uuid": f"iso-adv-{uuid.uuid4().hex[:8]}",
                          "data": {"worker_id": worker_a_id, "amount": 100, "date": "2026-10-01"}})
    assert r.status_code == 404
    assert "هذه المزرعة" in r.json()["detail"]

    # لم تُحتسب أي عملية على المزرعة ب
    assert farm_usage(client, farm_b["api_key"])["usage"]["used"] == 0


def test_cross_farm_merchant_id_rejected(client, make_farm):
    """بيع بدين لتاجر من مزرعة أخرى يُرفض، ولا يتأثر رصيد التاجر الأصلي."""
    farm_a = make_farm()
    farm_b = make_farm()
    tag = uuid.uuid4().hex[:6]
    r = client.post("/api/v1/farms/me/records/merchant", headers={"X-Farm-Key": farm_a["api_key"]},
                    json={"client_uuid": f"{tag}-m", "data": {"name": "تاجر أ", "phone": "071"}})
    assert r.status_code == 201, r.text
    merchant_a_id = r.json()["record"]["id"]

    # بيع محصول بدين موجّه لتاجر المزرعة أ لكن عبر مفتاح المزرعة ب
    r = client.post("/api/v1/farms/me/records/crop_sale", headers={"X-Farm-Key": farm_b["api_key"]},
                    json={"client_uuid": f"{tag}-cs",
                          "data": {"crop_name": "طماطم", "unit": "كيس", "quantity": 10,
                                   "price_per_unit": 50, "total_price": 500, "paid_amount": 100,
                                   "remaining_amount": 400, "merchant_id": merchant_a_id,
                                   "date": "2026-10-01"}})
    assert r.status_code == 404
    assert "هذه المزرعة" in r.json()["detail"]

    # دفعة تاجر عبر مفتاح المزرعة ب لنفس التاجر
    r = client.post("/api/v1/farms/me/records/merchant_payment", headers={"X-Farm-Key": farm_b["api_key"]},
                    json={"client_uuid": f"{tag}-mp",
                          "data": {"merchant_id": merchant_a_id, "amount": 50,
                                   "description": "دفعة", "date": "2026-10-01"}})
    assert r.status_code == 404

    # رصيد التاجر في المزرعة أ لم يتأثر بأي محاولة
    merchants = _list_records(client, farm_a["api_key"], "merchant")
    orig = next(m for m in merchants["items"] if m["id"] == merchant_a_id)
    assert orig["balance"] == 0


def test_same_client_uuid_independent_per_farm(client, make_farm):
    """المعرف الفريد فريد لكل مزرعة: نفس المعرف في مزرعتين = عمليتان مستقلتان."""
    farm_a = make_farm()
    farm_b = make_farm()
    shared_uuid = f"shared-{uuid.uuid4().hex[:10]}"

    ra = create_worker(client, farm_a["api_key"], shared_uuid)
    rb = create_worker(client, farm_b["api_key"], shared_uuid)
    assert ra.status_code == 201
    assert rb.status_code == 201
    assert ra.json()["record"]["id"] != rb.json()["record"]["id"]

    assert farm_usage(client, farm_a["api_key"])["usage"]["used"] == 1
    assert farm_usage(client, farm_b["api_key"])["usage"]["used"] == 1


def test_admin_farm_detail_totals_isolated(client, admin_headers, make_farm):
    """تفاصيل المزرعة الإدارية تعرض إجماليات المزرعة نفسها فقط."""
    farm_a = make_farm()
    farm_b = make_farm()
    create_worker(client, farm_a["api_key"])
    create_worker(client, farm_a["api_key"])
    create_worker(client, farm_b["api_key"])

    for fid, expected in [(farm_a["id"], 2), (farm_b["id"], 1)]:
        r = client.get(f"/api/admin/farms/{fid}", headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["totals"]["workers"] == expected


def test_legacy_endpoints_do_not_leak_tenant_farms(client, make_farm):
    """الواجهات القديمة (المزرعة الرئيسية 1) لا تكشف سجلات المزارع الجديدة."""
    farm = make_farm()
    name = f"عامل مستقل {uuid.uuid4().hex[:6]}"
    r = create_worker(client, farm["api_key"], f"iso-legacy-{uuid.uuid4().hex[:8]}", name=name)
    assert r.status_code == 201, r.text

    r = client.get("/api/workers/")
    assert r.status_code == 200
    assert all(w["name"] != name for w in r.json())
