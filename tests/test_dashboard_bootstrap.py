"""Smoke test for the combined dashboard bootstrap payload."""

from api.json_store import json_data_available


def test_bootstrap_endpoint_returns_reasons():
    if not json_data_available():
        return
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    resp = client.get("/insights/bootstrap")
    assert resp.status_code == 200
    body = resp.json()
    assert "filters" in body
    assert "reasons" in body
    assert isinstance(body["reasons"].get("reasons"), list)
    assert client.get("/api/insights/bootstrap").status_code == 200
