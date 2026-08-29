"""Unit tests for RAG guardrails and query understanding."""

from uuid import uuid4

from assistant.guardrails import assess_evidence, build_limitations, question_in_scope
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


def test_assess_evidence_rejects_unsupported_specific_claims():
    chunks = [
        _chunk(0.88, "Users wait for sales before purchasing wishlist items."),
        _chunk(0.74, "Price drops trigger purchases from saved items."),
    ]
    result = assess_evidence(
        chunks,
        question="why do left-handed users abandon their wishlist on Tuesdays",
    )
    assert result.sufficient is False
    assert result.unsupported_terms
    assert any(
        term in {"left", "handed", "tuesdays", "tuesday"} for term in result.unsupported_terms
    )


def test_assess_evidence_allows_general_wishlist_questions():
    chunks = [
        _chunk(0.88, "Users wait for sales before purchasing wishlist items."),
        _chunk(0.74, "Price drops trigger purchases from saved items."),
    ]
    result = assess_evidence(
        chunks,
        question="help me understand my wishlist users",
    )
    assert result.sufficient is True
    assert result.unsupported_terms == ()


def test_question_in_scope_accepts_hinglish_shopping():
    assert question_in_scope("sasta ethnic wear log kyun nahi kharidte") is True
    assert question_in_scope("kapde kyun nahi kharidte") is True
    assert question_in_scope("what is the capital of France") is False
    assert question_in_scope("write me a python function to sort a list") is False


def test_question_in_scope_accepts_user_segment_compare():
    assert question_in_scope("How do these behaviors differ across user segments?") is True
    assert question_in_scope("How do wishlist behaviors differ between Age 18–24 and Age 25–35?") is True


def test_assess_evidence_allows_user_segment_compare_without_claim_words():
    chunks = [
        _chunk(0.88, "Age band: 18-24. I am waiting for a sale and the right occasion."),
        _chunk(0.74, "Age band: 25-35. The price is too high and I am unsure about fit."),
    ]
    result = assess_evidence(
        chunks,
        question="How do these behaviors differ across user segments?",
    )
    assert result.sufficient is True
    assert result.unsupported_terms == ()


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
