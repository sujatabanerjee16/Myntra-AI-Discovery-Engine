"""Tests for retrieval and storage API routes (mocked DB layer)."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from api.main import app
from common.db import get_session
from common.models import SourceType
from storage.schemas import RetrievedChunk


def _override_session():
    yield MagicMock()


app.dependency_overrides[get_session] = _override_session
client = TestClient(app)


def test_storage_stats_endpoint():
    with patch(
        "api.routes.storage.get_storage_stats",
        return_value={
            "document_count": 43,
            "chunk_count": 70,
            "embedded_chunk_count": 0,
            "by_source": {"research": 9, "play_store": 34},
            "latest_run_version": "run-test",
        },
    ):
        resp = client.get("/storage/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["document_count"] == 43
    assert body["chunk_count"] == 70


def test_retrieval_search_endpoint():
    chunk_id = uuid4()
    doc_id = uuid4()
    mock_result = [
        RetrievedChunk(
            chunk_id=chunk_id,
            document_id=doc_id,
            chunk_index=0,
            text="Waiting for a sale before buying wishlist items.",
            score=0.91,
            source=SourceType.research,
            source_ref="research:row:0",
            category=None,
            occasion=None,
            price_band="sale_waiting",
            segment="price_sensitive",
            matched_signals=["price_sensitivity_waiting"],
            quality_score=0.9,
            document_created_at=None,
        )
    ]

    with patch("api.routes.retrieval.search_with_fallback", return_value=mock_result):
        resp = client.post(
            "/retrieval/search",
            json={
                "query": "why users wait for sales on wishlist items",
                "top_k": 5,
                "filters": {"source": "research", "segment": "price_sensitive"},
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["top_k"] == 5
    assert len(body["results"]) == 1
    assert body["results"][0]["score"] == 0.91
    assert body["results"][0]["segment"] == "price_sensitive"
