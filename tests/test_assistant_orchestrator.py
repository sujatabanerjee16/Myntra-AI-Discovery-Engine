"""Tests for the RAG orchestrator (mocked retrieval/generation)."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from assistant.orchestrator import answer_question
from common.models import SourceType
from storage.schemas import RetrievedChunk


def _chunk(score: float, text: str, source: SourceType = SourceType.play_store) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        text=text,
        score=score,
        source=source,
        source_ref="play_store:review:1" if source != SourceType.research else "research:row:1",
        category=None,
        occasion=None,
        price_band="sale_waiting",
        segment="price_sensitive",
        matched_signals=["price_sensitivity_waiting"],
        quality_score=0.85,
        document_created_at=None,
    )


@patch("assistant.orchestrator.fetch_relevant_aggregates")
@patch("assistant.orchestrator.backend.search_with_fallback")
@patch("api.backend.use_json_backend", return_value=False)
def test_answer_question_grounded(mock_json_backend, mock_search, mock_aggregates):
    mock_search.return_value = [
        _chunk(0.88, "Users wait for sales before purchasing wishlist items."),
        _chunk(0.74, "Price drops trigger purchases from saved items."),
        _chunk(
            0.71,
            "Q: What usually stops you from buying? A: I am waiting for a sale",
            SourceType.research,
        ),
    ]
    mock_aggregates.return_value = MagicMock(
        run_version="analytics-test",
        ranked_reasons=[
            {
                "reason_category": "price_sensitivity_waiting",
                "evidence_volume": 12,
                "confidence": 0.81,
                "sources": ["research"],
                "active_shortlist_count": 8,
                "passive_bookmark_count": 4,
            }
        ],
        theme_clusters=[],
    )

    session = MagicMock()
    trace_id = uuid4()
    session.flush.side_effect = lambda: setattr(session.add.call_args[0][0], "id", trace_id)

    response = answer_question(
        session,
        question="What prevents wishlisted products from being purchased?",
        persist_trace=True,
    )

    assert response.insufficient_evidence is False
    assert response.retrieved_chunk_count == 3
    assert response.answer
    assert len(response.citations) >= 1
    assert all(item.source != "research" for item in response.citations)
    assert response.confidence > 0
    session.commit.assert_called_once()


@patch("api.backend.use_json_backend", return_value=True)
def test_answer_question_out_of_scope_is_clean(mock_json_backend):
    response = answer_question(
        MagicMock(),
        question="what is the capital of France",
        persist_trace=False,
    )

    assert "outside" in response.answer.lower() or "wishlist" in response.answer.lower()
    assert response.insufficient_evidence is False
    assert response.citations == []
    assert response.retrieved_chunk_count == 0
    assert response.reason_categories == []
    assert response.limitations == ""
    assert response.confidence == 0.0


@patch("assistant.orchestrator.fetch_relevant_aggregates")
@patch("assistant.orchestrator.backend.search_with_fallback")
@patch("api.backend.use_json_backend", return_value=False)
def test_answer_question_rejects_fabricated_premise(
    mock_json_backend, mock_search, mock_aggregates
):
    mock_search.return_value = [
        _chunk(0.88, "Users wait for sales before purchasing wishlist items."),
        _chunk(0.74, "Price drops trigger purchases from saved items."),
    ]
    mock_aggregates.return_value = MagicMock(
        run_version="analytics-test",
        ranked_reasons=[],
        theme_clusters=[],
    )

    session = MagicMock()
    trace_id = uuid4()
    session.flush.side_effect = lambda: setattr(session.add.call_args[0][0], "id", trace_id)

    response = answer_question(
        session,
        question="why do left-handed users abandon their wishlist on Tuesdays",
        persist_trace=True,
    )

    assert response.insufficient_evidence is True
    assert "shopper comments" in response.answer.lower() or "don't have" in response.answer.lower()


@patch("assistant.orchestrator.fetch_relevant_aggregates")
@patch("assistant.orchestrator.backend.search_with_fallback")
@patch("api.backend.use_json_backend", return_value=False)
def test_answer_question_insufficient_evidence(mock_json_backend, mock_search, mock_aggregates):
    mock_search.return_value = [
        _chunk(0.18, "Unrelated app performance feedback."),
    ]
    mock_aggregates.return_value = MagicMock(
        run_version="analytics-test",
        ranked_reasons=[],
        theme_clusters=[],
    )

    session = MagicMock()
    trace_id = uuid4()
    session.flush.side_effect = lambda: setattr(session.add.call_args[0][0], "id", trace_id)

    response = answer_question(
        session,
        question="How do users compare shortlisted products?",
        persist_trace=True,
    )

    assert response.insufficient_evidence is True
    assert "shopper comments" in response.answer.lower() or "don't have" in response.answer.lower()
    session.commit.assert_called_once()


@patch("assistant.orchestrator.fetch_relevant_aggregates")
@patch("assistant.orchestrator.backend.search_with_fallback")
@patch("api.backend.use_json_backend", return_value=False)
def test_answer_question_backfills_public_source_chips(
    mock_json_backend, mock_search, mock_aggregates
):
    research_hits = [
        _chunk(0.88, "Q: What usually stops you? A: The price is too high", SourceType.research),
        _chunk(0.84, "Q: Biggest reason? A: Waiting for a sale", SourceType.research),
        _chunk(0.80, "Q: Why not buy? A: Fit is uncertain", SourceType.research),
    ]
    public_hits = [
        _chunk(0.72, "I keep saving dresses until they go on sale.", SourceType.reddit),
        _chunk(0.70, "Wishlist is just waiting for discounts.", SourceType.play_store),
        _chunk(0.66, "Size charts are not enough to buy.", SourceType.youtube),
    ]
    mock_search.side_effect = [research_hits, public_hits]
    mock_aggregates.return_value = MagicMock(
        run_version="analytics-test",
        ranked_reasons=[
            {
                "reason_category": "price_sensitivity_waiting",
                "evidence_volume": 12,
                "confidence": 0.81,
                "sources": ["research"],
                "active_shortlist_count": 8,
                "passive_bookmark_count": 4,
            }
        ],
        theme_clusters=[],
        competitive=[],
    )

    session = MagicMock()
    trace_id = uuid4()
    session.flush.side_effect = lambda: setattr(session.add.call_args[0][0], "id", trace_id)

    response = answer_question(
        session,
        question="What prevents wishlisted products from eventually being purchased?",
        persist_trace=True,
    )

    assert response.insufficient_evidence is False
    assert {item.source for item in response.citations} <= {"reddit", "play_store", "youtube"}
    assert {item.source for item in response.citations} >= {"reddit", "play_store"}
    assert "(confidence" not in response.answer.lower()
    assert mock_search.call_count == 2
    second_filters = mock_search.call_args_list[1].kwargs.get("filters")
    assert second_filters is not None
    assert second_filters.sources is not None
    assert "reddit" in second_filters.sources
