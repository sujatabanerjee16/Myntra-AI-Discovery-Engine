"""Smoke tests for the Phase 0 API shell (no database required)."""

from fastapi.testclient import TestClient

from api.main import WEB_DIST, app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "app" in body


def test_root_ok():
    """``/`` serves the dashboard only when ``web/dist`` exists.

    Production users hit the Vercel frontend, not this backend root route, so a
    missing local/CI build must not fail the Python test job.
    """
    resp = client.get("/")
    if not WEB_DIST.is_dir():
        assert resp.status_code == 404
        return

    assert resp.status_code == 200
    content_type = resp.headers.get("content-type", "")
    if "text/html" in content_type:
        assert 'id="root"' in resp.text
        assert "Wishlist" in resp.text
        return

    assert resp.json()["health"] == "/health"


def test_api_meta_ok():
    resp = client.get("/api/meta")
    assert resp.status_code == 200
    body = resp.json()
    assert body["health"] == "/health"
