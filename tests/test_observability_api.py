"""Tests for observability API routes."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from api.main import app
from api.routes.observability import quality_dashboard

client = TestClient(app)


def test_cost_controls_endpoint():
    resp = client.get("/observability/cost-controls")
    assert resp.status_code == 200
    body = resp.json()
    assert "enabled" in body
    assert "caches" in body


def test_quality_dashboard_payload():
    mock_session = MagicMock()
    mock_session.scalar.return_value = 0

    eval_execute = MagicMock()
    eval_execute.scalar_one_or_none.return_value = None
    trace_execute = MagicMock()
    trace_execute.scalars.return_value = iter([])
    pipeline_execute = MagicMock()
    pipeline_execute.scalars.return_value = iter([])
    mock_session.execute.side_effect = [eval_execute, trace_execute, pipeline_execute]

    result = quality_dashboard(session=mock_session)
    assert result.eval_summary.targets["retrieval_hit"] == 0.8
    assert result.recent_traces == []
