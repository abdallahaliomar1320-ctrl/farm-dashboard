# -*- coding: utf-8 -*-
"""مزامنة السجلات المحفوظة دون اتصال: لا فقدان ولا ازدواج ولا حذف."""
import uuid

import models
from conftest import create_worker, farm_usage, seed_operations, worker_payload


def _sync(client, key, records):
    r = client.post("/api/v1/farms/me/sync", headers={"X-Farm-Key": key},
                    json={"records": records})
    assert r.status_code == 200, r.text
    return r.json()


def _worker_record(cu, **overrides):
    return {"client_uuid": cu, "type": "worker", "data": worker_payload(**overrides)}


def test_sync_beyond_limit_never_loses_data(client, make_farm, db_session):
    """المزامنة بعد بلوغ الحد تُقبل كاملة وتُعلَّم كمتجاوزة، دون رفض أي سجل."""
    farm = make_farm()
    key = farm["api_key"]
    seed_operations(db_session, farm["id"], 250)

    tag = uuid.uuid4().hex[:8]
    d = _sync(client, key, [
        _worker_record(f"sync-{tag}-1", name="عامل غير متصل 1"),
        _worker_record(f"sync-{tag}-2", name="عامل غير متصل 2"),
        _worker_record(f"sync-{tag}-3", name="عامل غير متصل 3"),
    ])

    assert d["accepted"] == 3
    assert d["duplicates"] == 0
    assert d["failed"] == 0
    assert all(res["status"] == "created" and res["record_id"] for res in d["results"])

    assert d["usage"]["used"] == 253
    assert d["usage"]["over_limit"] is True
    assert d["new_operations_blocked"] is True
    assert "تجاوزت المزرعة الحد المجاني" in d["message"]
    assert "محفوظة" in d["message"]
    assert "0500000000" in d["message"]  # جهة الدعم ظاهرة بوضوح

    # كل السجلات موجودة فعلاً في قاعدة البيانات
    r = client.get("/api/v1/farms/me/records/worker", headers={"X-Farm-Key": key})
    names = {w["name"] for w in r.json()["items"]}
    assert {"عامل غير متصل 1", "عامل غير متصل 2", "عامل غير متصل 3"} <= names


def test_resync_same_batch_not_recounted(client, make_farm, db_session):
    """إعادة مزامنة نفس الدفعة (تكرار بعد فشل): مكررة لا محتسبة من جديد."""
    farm = make_farm()
    key = farm["api_key"]
    seed_operations(db_session, farm["id"], 250)
    tag = uuid.uuid4().hex[:8]
    batch = [_worker_record(f"sync-{tag}-{i}") for i in range(3)]

    d1 = _sync(client, key, batch)
    assert d1["accepted"] == 3 and d1["duplicates"] == 0
    d2 = _sync(client, key, batch)
    assert d2["accepted"] == 0
    assert d2["duplicates"] == 3
    assert all(res["status"] == "duplicate" for res in d2["results"])
    assert d2["usage"]["used"] == 253  # 250 مزروعة + 3 فقط


def test_batch_with_invalid_record_isolated(client, make_farm):
    """سجل غير صالح في الدفعة يفشل وحده ولا يمنع قبول بقية السجلات."""
    farm = make_farm()
    key = farm["api_key"]
    tag = uuid.uuid4().hex[:8]

    d = _sync(client, key, [
        _worker_record(f"sync-{tag}-ok1"),
        {"client_uuid": f"sync-{tag}-bad", "type": "merchant_payment",
         "data": {"merchant_id": 999999, "amount": 50, "description": "غير موجود",
                  "date": "2026-10-01"}},
        _worker_record(f"sync-{tag}-ok2"),
    ])

    assert d["accepted"] == 2
    assert d["failed"] == 1
    by_uuid = {res["client_uuid"]: res for res in d["results"]}
    assert by_uuid[f"sync-{tag}-bad"]["status"] == "invalid"
    assert "error" in by_uuid[f"sync-{tag}-bad"]
    # السجل الفاشل لم يُحتسب
    assert farm_usage(client, key)["usage"]["used"] == 2


def test_direct_create_blocked_after_overlimit_sync_data_kept(client, make_farm, db_session):
    """بعد تجاوز الحد بالمزامنة: الإنشاء المباشر ممنوع والبيانات المزامنة محفوظة."""
    farm = make_farm()
    key = farm["api_key"]
    seed_operations(db_session, farm["id"], 250)
    tag = uuid.uuid4().hex[:8]
    d = _sync(client, key, [_worker_record(f"sync-{tag}-{i}") for i in range(3)])
    assert d["accepted"] == 3

    r = create_worker(client, key, f"direct-after-{uuid.uuid4().hex[:8]}")
    assert r.status_code == 402

    r = client.get("/api/v1/farms/me/records/worker", headers={"X-Farm-Key": key})
    assert r.json()["count"] == 3  # لا حذف ولا فقدان


def test_month_key_determined_by_server_not_client_timestamp(client, make_farm, db_session):
    """شهر الاحتساب من توقيت النظام حتى لو أرسل العميل occurred_at قديماً."""
    import tenancy
    farm = make_farm()
    key = farm["api_key"]
    cu = f"sync-oldts-{uuid.uuid4().hex[:8]}"

    d = _sync(client, key, [{
        "client_uuid": cu, "type": "worker",
        "occurred_at": "2020-01-01T00:00:00",
        "data": worker_payload(),
    }])
    assert d["accepted"] == 1

    op = db_session.query(models.Operation).filter(
        models.Operation.farm_id == farm["id"],
        models.Operation.client_uuid == cu,
    ).first()
    assert op is not None
    assert op.month_key == tenancy.current_month_key(db_session)


def test_sync_shares_idempotency_with_direct_create(client, make_farm):
    """سجل أنشئ مباشرة ثم أُرسل في مزامنة = مكرر (معرف واحد لكلتا المسارين)."""
    farm = make_farm()
    key = farm["api_key"]
    cu = f"sync-shared-{uuid.uuid4().hex[:8]}"

    r = create_worker(client, key, cu)
    assert r.status_code == 201

    d = _sync(client, key, [_worker_record(cu)])
    assert d["accepted"] == 0
    assert d["duplicates"] == 1
    assert farm_usage(client, key)["usage"]["used"] == 1


def test_sync_rejects_malformed_record_shape(client, make_farm):
    """حقل غير صالح (نوع سجل مجهول) يرفض الطلب كاملاً قبل تنفيذ أي شيء."""
    farm = make_farm()
    key = farm["api_key"]
    r = client.post("/api/v1/farms/me/sync", headers={"X-Farm-Key": key},
                    json={"records": [{"client_uuid": "abcdefgh", "type": "unknown_type",
                                       "data": {}}]})
    assert r.status_code == 422
    assert farm_usage(client, key)["usage"]["used"] == 0
