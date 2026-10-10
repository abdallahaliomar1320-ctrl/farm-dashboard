# -*- coding: utf-8 -*-
"""حماية واجهات المالك بمصادقة الخدمة، وواجهات المزرعة بمفتاحها."""


def test_admin_endpoints_require_service_token(client):
    for path in ["/api/admin/overview", "/api/admin/farms", "/api/admin/settings",
                 "/api/admin/usage", "/api/admin/alerts", "/api/admin/audit"]:
        r = client.get(path)
        assert r.status_code == 401, f"{path}: {r.status_code}"


def test_admin_wrong_token_rejected(client):
    r = client.get("/api/admin/overview", headers={"X-Service-Token": "wrong-token"})
    assert r.status_code == 401


def test_admin_correct_token_accepted(client, admin_headers):
    r = client.get("/api/admin/overview", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["settings"]["free_ops_limit"] == 250


def test_admin_blocked_when_service_token_unset(client, monkeypatch):
    monkeypatch.delenv("OWNER_SERVICE_TOKEN", raising=False)
    r = client.get("/api/admin/overview", headers={"X-Service-Token": "anything"})
    assert r.status_code == 503


def test_farm_endpoints_require_farm_key(client):
    for path in ["/api/v1/farms/me/status", "/api/v1/farms/me/records/worker"]:
        r = client.get(path)
        assert r.status_code == 401, f"{path}: {r.status_code}"


def test_farm_wrong_key_rejected(client):
    r = client.get("/api/v1/farms/me/status", headers={"X-Farm-Key": "farm_wrong"})
    assert r.status_code == 401


def test_api_key_not_exposed_after_creation(client, admin_headers, make_farm):
    farm = make_farm()
    r = client.get("/api/admin/farms", headers=admin_headers)
    assert r.status_code == 200
    assert all(not f.get("api_key") for f in r.json()["items"])
    r = client.get(f"/api/admin/farms/{farm['id']}", headers=admin_headers)
    assert r.status_code == 200
    assert "api_key" not in r.json()
