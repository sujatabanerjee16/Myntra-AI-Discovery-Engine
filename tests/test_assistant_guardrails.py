"""Unit tests for RAG guardrails and query understanding."""

from uuid import uuid4

from assistant.guardrails import assess_evidence, build_limitations
from assistant.query import understand_query
from common.models import SourceType
from storage.schemas import RetrievedChunk


def _chunk(score: float, text: str = "sample evidence") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        text=text,
        score=score,
        source=SourceType.research,
        source_ref="research:row:1",
        category=None,
        occasion=None,
        price_band=None,
        segment=None,
        matched_signals=[],
        quality_score=0.8,
        document_created_at=None,
    )


def test_assess_evidence_rejects_empty():
    result = assess_evidence([])
    assert result.sufficient is False
    assert result.chunk_count == 0


def test_assess_evidence_accepts_strong_matches():
    chunks = [_chunk(0.82), _chunk(0.71), _chunk(0.66)]
    result = assess_evidence(chunks)
    assert result.sufficient is True
    assert result.top_score == 0.82


def test_assess_evidence_rejects_low_scores():
    chunks = [_chunk(0.25), _chunk(0.22)]
    result = assess_evidence(chunks)
    assert result.sufficient is False


def test_understand_query_detects_reason_and_source():
    parsed = understand_query(
        "Why do price sensitive users wait for a sale before buying wishlist items from research?"
    )
    assert "price_sensitivity_waiting" in parsed.reason_categories
    assert parsed.filters is not None
    assert parsed.filters.source == SourceType.research


def test_build_limitations_mentions_sources():
    text = build_limitations(
        [_chunk(0.7, "waiting for discount")],
        run_version="analytics-test",
        reason_categories=["price_sensitivity_waiting"],
    )
    assert "research" in text
    assert "analytics-test" in text
