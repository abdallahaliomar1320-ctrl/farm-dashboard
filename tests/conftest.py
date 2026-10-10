# -*- coding: utf-8 -*-
"""
إعداد اختبارات pytest — قاعدة بيانات معزولة مؤقتة لكل جلسة اختبار.

لا تلمس هذه الاختبارات farm.db أبداً: يُضبط FARM_DB_URL قبل استيراد أي
وحدة من المشروع ليشير إلى ملف مؤقت يُحذف تلقائياً مع مجلد temporaries.
"""
import os
import sys
import tempfile
import uuid

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_TESTS_DIR)
if _PROJECT_DIR not in sys.path:
    sys.path.insert(0, _PROJECT_DIR)

_TMP_DIR = tempfile.mkdtemp(prefix="farm_pytest_")
_DB_PATH = os.path.join(_TMP_DIR, "farm_test.db").replace("\\", "/")
os.environ["FARM_DB_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["OWNER_SERVICE_TOKEN"] = "test-service-token"
os.environ["SUPPORT_CONTACT"] = "0500000000"

import pytest  # noqa: E402
import models  # noqa: E402  (بعد ضبط FARM_DB_URL)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    import main
    with TestClient(main.app) as c:
        yield c


@pytest.fixture()
def admin_headers():
    return {"X-Service-Token": "test-service-token"}


@pytest.fixture()
def make_farm(client, admin_headers):
    """ينشئ مزرعة جديدة ويعيد استجابة الإنشاء (مع مفتاح API الذي يظهر مرة واحدة)."""
    counter = {"n": 0}

    def _make(name=None):
        counter["n"] += 1
        r = client.post(
            "/api/admin/farms",
            headers=admin_headers,
            json={"name": name or f"مزرعة اختبار {uuid.uuid4().hex[:8]}"},
        )
        assert r.status_code == 201, r.text
        return r.json()

    return _make


@pytest.fixture()
def db_session():
    from database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def canonical_settings(client, admin_headers):
    """يعيد الإعدادات العامة إلى قيم قياسية معروفة (مع تجاوزات اختيارية)."""
    def _apply(**overrides):
        payload = {
            "free_ops_limit": 250,
            "alert_threshold_1": 200,
            "alert_threshold_2": 240,
            "subscription_price": None,
            "subscription_currency": "YER",
            "subscription_duration_days": 30,
            "grace_period_days": 7,
            "timezone": "Asia/Aden",
        }
        payload.update(overrides)
        r = client.put("/api/admin/settings", headers=admin_headers, json=payload)
        assert r.status_code == 200, r.text
        return r.json()

    return _apply


# ---------------------------------------------------------------- مساعدات مشتركة

def worker_payload(**overrides):
    p = {
        "name": "عامل اختبار",
        "phone": "0700000000",
        "start_date": "2026-01-01",
        "job": "عامل",
        "pay_type": "شهري",
        "pay_amount": 50000,
    }
    p.update(overrides)
    return p


def create_worker(client, api_key, client_uuid=None, **overrides):
    return client.post(
        "/api/v1/farms/me/records/worker",
        headers={"X-Farm-Key": api_key},
        json={"client_uuid": client_uuid or f"w-{uuid.uuid4().hex}", "data": worker_payload(**overrides)},
    )


def farm_usage(client, api_key):
    r = client.get("/api/v1/farms/me/status", headers={"X-Farm-Key": api_key})
    assert r.status_code == 200, r.text
    return r.json()


def seed_operations(db, farm_id, count, month_key=None, prefix=None):
    """يزرع عمليات محتسبة مباشرة في الجدول (تسريعاً لاختبارات الحد)."""
    import tenancy
    mk = month_key or tenancy.current_month_key(db)
    prefix = prefix or uuid.uuid4().hex[:8]
    for i in range(count):
        db.add(models.Operation(
            farm_id=farm_id,
            client_uuid=f"{prefix}-{i}",
            op_type="worker",
            record_table="workers",
            month_key=mk,
            created_at="2026-01-01T00:00:00",
        ))
    db.commit()


def prev_month_key(mk):
    y, m = int(mk[:4]), int(mk[5:7])
    m -= 1
    if m == 0:
        y, m = y - 1, 12
    return f"{y:04d}-{m:02d}"
