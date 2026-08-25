"""Tests for insights API routes (mocked DB/analytics)."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from analytics.pipeline import AnalyticsResult
from api.main import app
from common.db import get_session

client = TestClient(app)


def test_ranked_reasons_endpoint():
    mock_row = MagicMock()
    mock_row.reason_category = "price_sensitivity_waiting"
    mock_row.evidence_volume = 20
    mock_row.confidence = 0.82
    mock_row.sources = ["research", "play_store"]
    mock_row.active_shortlist_count = 15
    mock_row.passive_bookmark_count = 5

    mock_session = MagicMock()
    mock_session.scalar.return_value = "analytics-test"
    mock_session.execute.return_value.scalars.return_value.all.return_value = [mock_row]

    def override_session():
        yield mock_session

    with patch("api.backend.use_json_backend", return_value=False):
        app.dependency_overrides[get_session] = override_session
        resp = client.get("/insights/reasons")
    assert resp.status_code == 200
    body = resp.json()
    assert body["reasons"][0]["reason_category"] == "price_sensitivity_waiting"


def test_run_analytics_endpoint():
    mock_result = AnalyticsResult(
        run_version="analytics-test",
        chunks_analyzed=70,
        insights_created=12,
        reason_aggregates=6,
        theme_clusters=4,
    )

    def override_session():
        yield MagicMock()

    with patch("api.routes.insights.run_semantic_analytics_db", return_value=mock_result):
        app.dependency_overrides[get_session] = override_session
        resp = client.post("/analytics/run", json={"replace_existing": True})

    assert resp.status_code == 200
    assert resp.json()["insights_created"] == 12
