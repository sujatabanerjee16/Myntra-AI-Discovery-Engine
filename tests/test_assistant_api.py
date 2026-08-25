"""Tests for grounded assistant API routes."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from api.main import app
from assistant.schemas import AssistantAskResponse, Citation
from common.db import get_session

client = TestClient(app)


def test_list_key_questions():
    resp = client.get("/assistant/questions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["questions"]) == 10
    assert "wishlist" in body["questions"][0].lower()


def test_ask_assistant_endpoint():
    chunk_id = uuid4()
    mock_response = AssistantAskResponse(
        trace_id=uuid4(),
        question="What prevents wishlisted products from being purchased?",
        answer="Price sensitivity and waiting for sales are common blockers.",
        citations=[
            Citation(
                chunk_id=chunk_id,
                source="research",
                excerpt="Waiting for a sale before buying wishlist items.",
                score=0.87,
            )
        ],
        confidence=0.78,
        limitations="Public feedback only.",
        insufficient_evidence=False,
        retrieved_chunk_count=3,
        reason_categories=["price_sensitivity_waiting"],
    )

    def override_session():
        yield MagicMock()

    with patch("api.routes.assistant.answer_question", return_value=mock_response):
        app.dependency_overrides[get_session] = override_session
        resp = client.post(
            "/assistant/ask",
            json={"question": "What prevents wishlisted products from being purchased?"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["confidence"] == 0.78
    assert body["citations"][0]["chunk_id"] == str(chunk_id)


def test_list_traces_endpoint():
    trace_id = uuid4()
    chunk_id = uuid4()
    mock_row = MagicMock()
    mock_row.id = trace_id
    mock_row.question = "Why do users wishlist items?"
    mock_row.answer = "To shortlist options."
    mock_row.citations = ["[research] excerpt"]
    mock_row.confidence = 0.7
    mock_row.limitations = "Limited corpus."
    mock_row.retrieved_chunk_ids = [chunk_id]
    mock_row.created_at = datetime.now(UTC)

    mock_session = MagicMock()
    mock_session.scalar.return_value = 1
    mock_session.execute.return_value.scalars.return_value = iter([mock_row])

    def override_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_session
    resp = client.get("/assistant/traces")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["traces"][0]["id"] == str(trace_id)
