"""Tests for Phase 5 dashboard Insights API endpoints."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from analytics.schemas import (
    DashboardFiltersResponse,
    EvidenceExcerpt,
    EvidenceSummaryResponse,
    HeatmapCell,
    HeatmapResponse,
    IntentBreakdownItem,
    IntentBreakdownResponse,
    ReasonRankItem,
    TrendsResponse,
)
from api.main import app
from common.db import get_session

client = TestClient(app)


def test_dashboard_filters_endpoint():
    mock_response = DashboardFiltersResponse(
        run_version="analytics-test",
        segments=["price_sensitive"],
        categories=["footwear"],
        occasions=["wedding"],
        price_bands=["sale_waiting"],
        reason_categories=["price_sensitivity_waiting"],
    )

    def override_session():
        yield MagicMock()

    with patch("api.backend.use_json_backend", return_value=False):
        with patch("api.routes.insights.db_get_dashboard_filters", return_value=mock_response):
            app.dependency_overrides[get_session] = override_session
            resp = client.get("/insights/filters")

    assert resp.status_code == 200
    assert resp.json()["segments"] == ["price_sensitive"]


def test_heatmap_endpoint():
    mock_response = HeatmapResponse(
        run_version="analytics-test",
        row_key="reason_category",
        column_key="segment",
        rows=["price_sensitivity_waiting"],
        columns=["price_sensitive"],
        cells=[
            HeatmapCell(
                row="price_sensitivity_waiting",
                column="price_sensitive",
                value=12,
                confidence=0.8,
            )
        ],
    )

    def override_session():
        yield MagicMock()

    with patch("api.backend.use_json_backend", return_value=False):
        with patch("api.routes.insights.db_get_friction_heatmap", return_value=mock_response):
            app.dependency_overrides[get_session] = override_session
            resp = client.get("/insights/heatmap")

    assert resp.status_code == 200
    assert resp.json()["cells"][0]["value"] == 12


def test_evidence_summary_endpoint():
    chunk_id = uuid4()
    mock_response = EvidenceSummaryResponse(
        run_version="analytics-test",
        reason_category="price_sensitivity_waiting",
        evidence_volume=15,
        confidence=0.82,
        sources=["research"],
        excerpts=[
            EvidenceExcerpt(
                chunk_id=chunk_id,
                text="Waiting for a sale before buying.",
                source="research",
                source_ref="research:row:1",
                segment="price_sensitive",
                category=None,
                confidence=0.9,
                quality_score=0.9,
            )
        ],
    )

    def override_session():
        yield MagicMock()

    with patch("api.backend.use_json_backend", return_value=False):
        with patch("api.routes.insights.db_get_evidence_summary", return_value=mock_response):
            app.dependency_overrides[get_session] = override_session
            resp = client.get("/insights/evidence?reason_category=price_sensitivity_waiting")

    assert resp.status_code == 200
    assert resp.json()["excerpts"][0]["chunk_id"] == str(chunk_id)


def test_intent_and_trends_endpoints():
    intent = IntentBreakdownResponse(
        run_version="analytics-test",
        total_active=20,
        total_passive=8,
        by_reason=[
            IntentBreakdownItem(
                reason_category="price_sensitivity_waiting",
                active_shortlist_count=15,
                passive_bookmark_count=5,
                evidence_volume=20,
                confidence=0.82,
            )
        ],
    )
    trends = TrendsResponse(run_version="analytics-test", journey_stages=[], emerging_themes=[])

    def override_session():
        yield MagicMock()

    with patch("api.backend.use_json_backend", return_value=False):
        with patch("api.routes.insights.db_get_intent_breakdown", return_value=intent):
            with patch("api.routes.insights.db_get_trends", return_value=trends):
                app.dependency_overrides[get_session] = override_session
                intent_resp = client.get("/insights/intent")
                trends_resp = client.get("/insights/trends")

    assert intent_resp.json()["total_active"] == 20
    assert trends_resp.status_code == 200


def test_filtered_reason_ranks_endpoint():
    mock_reasons = [
        ReasonRankItem(
            reason_category="price_sensitivity_waiting",
            evidence_volume=12,
            confidence=0.8,
            sources=["research"],
            active_shortlist_count=8,
            passive_bookmark_count=4,
        )
    ]

    def override_session():
        yield MagicMock()

    with patch("api.backend.use_json_backend", return_value=False):
        with patch("api.routes.insights.db_get_filtered_reason_ranks", return_value=mock_reasons):
            with patch(
                "api.routes.insights.resolve_insight_run_version",
                return_value="analytics-test",
            ):
                app.dependency_overrides[get_session] = override_session
                resp = client.get("/insights/reasons?segment=price_sensitive")

    assert resp.status_code == 200
    assert resp.json()["reasons"][0]["evidence_volume"] == 12
