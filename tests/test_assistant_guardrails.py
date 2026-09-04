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


def test_question_in_scope_accepts_starter_questions():
    from assistant.questions import KEY_QUESTIONS

    for question in KEY_QUESTIONS:
        assert question_in_scope(question) is True


def test_question_in_scope_accepts_wishlist_age_wording_without_special_case():
    # No dedicated age-compare path; wishlist vocabulary keeps the question in scope.
    assert question_in_scope("How do wishlist behaviors differ between Age 18–24 and Age 25–35?") is True


def test_assess_evidence_allows_starter_questions_without_claim_words():
    chunks = [
        _chunk(0.88, "Users wait for sales before purchasing wishlist items."),
        _chunk(0.74, "Fit and photos still make people hesitate after they like an item."),
    ]
    for question in (
        "What unmet needs emerge consistently across user conversations?",
        "What uncertainties remain after users have identified a product they like?",
    ):
        result = assess_evidence(chunks, question=question)
        assert result.sufficient is True, question
        assert result.unsupported_terms == ()


def test_assess_evidence_no_longer_bypasses_claim_check_for_age_wording():
    chunks = [
        _chunk(0.88, "I am waiting for a sale and the right occasion."),
        _chunk(0.74, "The price is too high and I am unsure about fit."),
    ]
    result = assess_evidence(
        chunks,
        question="How do wishlist behaviors differ between Age 18–24 and Age 25–35 left-handed Tuesday buyers?",
    )
    assert result.sufficient is False
    assert result.unsupported_terms


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
    assert "shopper comments" in text.lower()
    assert "research" not in text.lower()
    assert "analytics-test" not in text


def test_citations_skip_research_interviews():
    from assistant.guardrails import citations_from_chunks

    research = _chunk(0.9, "Q: What stops you? A: Waiting for a sale")
    public = _chunk(0.8, "Waiting for a sale on a wishlisted dress.")
    public.source = SourceType.play_store
    public.source_ref = "play_store:review:1"
    cites = citations_from_chunks([research, public])
    assert len(cites) == 1
    assert cites[0].source == "play_store"
    assert "Q:" not in cites[0].excerpt


def test_append_public_chunks_keeps_research_first():
    from assistant.guardrails import append_public_chunks

    research = _chunk(0.9, "Q: What stops you? A: Waiting for a sale")
    reddit = _chunk(0.7, "Price is the only reason I still have it saved.")
    reddit.source = SourceType.reddit
    reddit.source_ref = "reddit:thread:1"
    play = _chunk(0.6, "Waiting for a sale on wishlist items.")
    play.source = SourceType.play_store
    play.source_ref = "play_store:review:2"

    merged = append_public_chunks([research], [reddit, play], min_public=3)
    assert merged[0].source == SourceType.research
    assert [item.source for item in merged[1:]] == [SourceType.reddit, SourceType.play_store]
