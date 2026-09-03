"""Tests for evaluation metrics."""

import uuid

from common.models import SourceType
from eval.datasets import default_taxonomy_cases
from eval.faithfulness import compute_faithfulness_metrics, score_answer_faithfulness
from eval.metrics import compute_retrieval_metrics, compute_taxonomy_metrics
from eval.schemas import FaithfulnessEvalCase, RetrievalEvalCase
from storage.schemas import RetrievedChunk


def _chunk(text: str, *, signals: list[str] | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=0,
        text=text,
        score=0.72,
        source=SourceType.research,
        source_ref="test",
        category=None,
        occasion=None,
        price_band=None,
        segment=None,
        matched_signals=signals or [],
        quality_score=0.8,
        document_created_at=None,
    )


def test_taxonomy_accuracy_perfect_on_defaults():
    cases = default_taxonomy_cases()
    result = compute_taxonomy_metrics(cases, target=0.8)
    assert result.passed
    assert result.value == 1.0


def test_retrieval_hit_at_k():
    case = RetrievalEvalCase(
        query="price waiting",
        expected_reason_categories=["price_sensitivity_waiting"],
        expected_keywords=["sale", "price"],
    )
    chunks = [
        _chunk("Unrelated logistics issue with delivery delays."),
        _chunk("I am waiting for a sale because the price is too high."),
    ]
    result = compute_retrieval_metrics(
        [case],
        {"price waiting": chunks},
        k=2,
        target=0.5,
    )
    assert result.passed
    assert result.details["hit_at_k"] == 1.0


def test_faithfulness_refusal_scoring():
    score = score_answer_faithfulness(
        "I don't have a clear enough match in shopper comments to answer that yet.",
        [],
        should_refuse=True,
    )
    assert score == 1.0


def test_faithfulness_supported_answer():
    result = compute_faithfulness_metrics(
        [
            FaithfulnessEvalCase(
                question="Why wait?",
                answer="Users wait for sales before buying wishlist items.",
                evidence_texts=["I am waiting for a sale before buying."],
            )
        ],
        target=0.5,
    )
    assert result.passed
    assert result.value >= 0.5
