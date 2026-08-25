"""Smoke tests for the Phase 0 API shell (no database required)."""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "app" in body


def test_root_ok():
    resp = client.get("/")
    assert resp.status_code == 200
    content_type = resp.headers.get("content-type", "")
    if "text/html" in content_type:
        assert "Wishlist Conversion Discovery Engine" in resp.text
        return

    assert resp.json()["health"] == "/health"


def test_api_meta_ok():
    resp = client.get("/api/meta")
    assert resp.status_code == 200
    body = resp.json()
    assert body["health"] == "/health"
