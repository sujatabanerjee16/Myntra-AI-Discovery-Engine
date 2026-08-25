"""Evaluation metrics for retrieval relevance and taxonomy quality."""

from __future__ import annotations

import re

from analytics.taxonomy import classify_reason
from eval.schemas import MetricResult, RetrievalEvalCase, TaxonomyEvalCase
from storage.schemas import RetrievedChunk


def _chunk_matches_case(chunk: RetrievedChunk, case: RetrievalEvalCase) -> bool:
    if case.expected_reason_categories:
        classification = classify_reason(chunk.text, signals=chunk.matched_signals)
        if classification.primary in case.expected_reason_categories:
            return True
        if any(cat in classification.matched for cat in case.expected_reason_categories):
            return True

    if case.expected_keywords:
        text_lower = chunk.text.lower()
        hits = sum(1 for kw in case.expected_keywords if kw.lower() in text_lower)
        if hits >= max(1, len(case.expected_keywords) // 2):
            return True

    return False


def compute_retrieval_metrics(
    cases: list[RetrievalEvalCase],
    retrieved_by_query: dict[str, list[RetrievedChunk]],
    *,
    k: int,
    target: float,
) -> MetricResult:
    """Compute hit@k and mean reciprocal rank over labeled queries."""
    if not cases:
        return MetricResult(
            name="retrieval_relevance",
            value=0.0,
            target=target,
            passed=False,
            details={"error": "No retrieval eval cases configured"},
        )

    hits = 0
    reciprocal_ranks: list[float] = []
    per_case: list[dict[str, float | bool | str]] = []

    for case in cases:
        chunks = retrieved_by_query.get(case.query, [])
        rank = 0
        for index, chunk in enumerate(chunks[:k], start=1):
            if _chunk_matches_case(chunk, case):
                rank = index
                break

        case_hit = rank > 0
        hits += int(case_hit)
        reciprocal_ranks.append(1.0 / rank if rank else 0.0)
        per_case.append(
            {
                "query": case.query[:80],
                "hit": case_hit,
                "rank": rank,
                "retrieved": len(chunks),
            }
        )

    hit_at_k = hits / len(cases)
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)

    return MetricResult(
        name="retrieval_relevance",
        value=round(hit_at_k, 4),
        target=target,
        passed=hit_at_k >= target,
        details={
            "hit_at_k": round(hit_at_k, 4),
            "mrr": round(mrr, 4),
            "k": k,
            "cases": len(cases),
            "per_case": per_case,
        },
    )


def compute_taxonomy_metrics(
    cases: list[TaxonomyEvalCase],
    *,
    target: float,
) -> MetricResult:
    """Compute taxonomy classification accuracy on labeled examples."""
    if not cases:
        return MetricResult(
            name="taxonomy_classification",
            value=0.0,
            target=target,
            passed=False,
            details={"error": "No taxonomy eval cases configured"},
        )

    correct = 0
    mismatches: list[dict[str, str]] = []

    for case in cases:
        result = classify_reason(case.text, signals=case.signals or None)
        if result.primary == case.expected_category:
            correct += 1
        else:
            mismatches.append(
                {
                    "text": case.text[:80],
                    "expected": case.expected_category,
                    "predicted": result.primary,
                }
            )

    accuracy = correct / len(cases)
    return MetricResult(
        name="taxonomy_classification",
        value=round(accuracy, 4),
        target=target,
        passed=accuracy >= target,
        details={
            "accuracy": round(accuracy, 4),
            "correct": correct,
            "total": len(cases),
            "mismatches": mismatches[:10],
        },
    )


def tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 3 and token not in {"that", "this", "with", "from", "have", "they", "their"}
    }
