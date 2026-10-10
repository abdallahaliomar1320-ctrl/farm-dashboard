# -*- coding: utf-8 -*-
"""الإعدادات العامة: التحقق من المدخلات، والتوثيق، وسجل تدقيق غير قابل للمحو."""
import main


def _settings_body(**overrides):
    payload = {
        "free_ops_limit": 250,
        "alert_threshold_1": 200,
        "alert_threshold_2": 240,
        "subscription_price": None,
        "subscription_currency": "YER",
        "subscription_duration_days": 30,
        "grace_period_days": 7,
        "timezone": "Asia/Aden",
        "actor": "test",
    }
    payload.update(overrides)
    return payload


def test_threshold_order_validated(client, admin_headers):
    r = client.put("/api/admin/settings", headers=admin_headers,
                   json=_settings_body(alert_threshold_1=260, alert_threshold_2=240))
    assert r.status_code == 400
    assert "عتبة" in r.json()["detail"]


def test_thresholds_must_not_exceed_limit(client, admin_headers):
    r = client.put("/api/admin/settings", headers=admin_headers,
                   json=_settings_body(alert_threshold_2=300))
    assert r.status_code == 400


def test_unknown_timezone_rejected(client, admin_headers):
    r = client.put("/api/admin/settings", headers=admin_headers,
                   json=_settings_body(timezone="Not/AZone"))
    assert r.status_code == 400
    assert "منطقة زمنية" in r.json()["detail"]


def test_limit_bounds_validated(client, admin_headers):
    r = client.put("/api/admin/settings", headers=admin_headers,
                   json=_settings_body(free_ops_limit=0))
    assert r.status_code == 422


def test_valid_settings_update_persists_and_audited(client, admin_headers, canonical_settings):
    canonical_settings()
    r = client.put("/api/admin/settings", headers=admin_headers,
                   json=_settings_body(free_ops_limit=300, grace_period_days=10,
                                       subscription_price=4000))
    assert r.status_code == 200, r.text

    r = client.get("/api/admin/settings", headers=admin_headers)
    s = r.json()
    assert s["free_ops_limit"] == 300
    assert s["grace_period_days"] == 10
    assert s["subscription_price"] == 4000
    assert s["price_set"] is True
    assert s["updated_by"] == "test"

    # التغيير موثق بالقيم قبل/بعد
    r = client.get("/api/admin/audit", headers=admin_headers,
                   params={"action": "settings.update"})
    assert r.status_code == 200
    entry = r.json()["items"][0]
    assert "free_ops_limit" in (entry["details"] or "")
    canonical_settings()  # إعادة القيم القياسية لبقية الاختبارات


def test_audit_log_is_append_only(client, admin_headers):
    """لا توجد أي واجهة تسمح بحذف أو تعديل سجل التدقيق أو حذف المزارع."""
    for route in main.app.routes:
        methods = set(getattr(route, "methods", None) or [])
        path = getattr(route, "path", "")
        if "/api/admin/audit" in path:
            assert methods <= {"GET", "HEAD", "OPTIONS"}, f"مسار تدقيق قابل للتعديل: {path} {methods}"
        if "/api/admin/farms" in path:
            assert "DELETE" not in methods, f"حذف مزارع مسموح عبر {path}"


def test_audit_lists_entries_desc(client, admin_headers, make_farm):
    make_farm()
    r = client.get("/api/admin/audit", headers=admin_headers)
    assert r.status_code == 200
    d = r.json()
    assert d["total"] >= 1
    ids = [e["id"] for e in d["items"]]
    assert ids == sorted(ids, reverse=True)


def test_overview_reflects_current_state(client, admin_headers, make_farm):
    farm = make_farm()
    r = client.get("/api/admin/overview", headers=admin_headers)
    assert r.status_code == 200
    d = r.json()
    assert d["farms_total"] >= 2  # المزرعة الافتراضية + المزرعة الجديدة
    assert d["farms_active"] >= 1
    assert "month" in d
    assert "settings" in d
