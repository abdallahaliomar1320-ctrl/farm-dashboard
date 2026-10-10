# -*- coding: utf-8 -*-
"""منع تكرار العملية (idempotency) وحماية تزامن الطلبات."""
import concurrent.futures

from conftest import create_worker, farm_usage, seed_operations


def test_duplicate_uuid_returns_same_record(client, make_farm):
    """إعادة نفس المعرف الفريد تعيد السجل نفسه دون احتساب جديد (إعادة بعد فشل اتصال)."""
    farm = make_farm()
    key = farm["api_key"]

    r1 = create_worker(client, key, "dup-worker-0001")
    assert r1.status_code == 201
    assert r1.json()["created"] is True
    rec_id = r1.json()["record"]["id"]

    r2 = create_worker(client, key, "dup-worker-0001")
    assert r2.status_code == 200
    assert r2.json()["created"] is False
    assert r2.json()["duplicate"] is True
    assert r2.json()["record"]["id"] == rec_id

    assert farm_usage(client, key)["usage"]["used"] == 1


def test_concurrent_same_uuid_single_record(client, make_farm):
    """طلبات متزامنة بنفس المعرف: سجل واحد فقط يُنشأ ويُحتسب مرة واحدة."""
    farm = make_farm()
    key = farm["api_key"]

    def post(_):
        return create_worker(client, key, "race-same-uuid-01")

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(post, range(6)))

    codes = sorted(r.status_code for r in results)
    assert codes.count(201) == 1
    assert codes.count(200) == 5
    ids = {r.json()["record"]["id"] for r in results}
    assert len(ids) == 1

    assert farm_usage(client, key)["usage"]["used"] == 1
    r = client.get("/api/v1/farms/me/records/worker", headers={"X-Farm-Key": key})
    assert len(r.json()["items"]) == 1


def test_concurrent_distinct_uuids_at_limit_no_overshoot(client, make_farm, db_session):
    """سباق على آخر خانة مجانية: نجاح واحد فقط والباقي يُرفض بوضوح (لا تجاوز للحد)."""
    farm = make_farm()
    key = farm["api_key"]
    seed_operations(db_session, farm["id"], 249)

    def post(i):
        return create_worker(client, key, f"race-distinct-{i:04d}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(post, range(4)))

    codes = sorted(r.status_code for r in results)
    assert codes.count(201) == 1
    assert codes.count(402) == 3

    usage = farm_usage(client, key)["usage"]
    assert usage["used"] == 250
    assert usage["over_limit"] is False


def test_blocked_attempt_leaves_no_phantom_operation(client, make_farm, db_session):
    """الطلب المرفوض (بعد بلوغ الحد) لا يترك أثراً في سجل الاحتساب."""
    farm = make_farm()
    key = farm["api_key"]
    seed_operations(db_session, farm["id"], 250)

    r = create_worker(client, key, "blocked-worker-0001")
    assert r.status_code == 402
    r = create_worker(client, key, "blocked-worker-0001")
    assert r.status_code == 402
    assert farm_usage(client, key)["usage"]["used"] == 250
