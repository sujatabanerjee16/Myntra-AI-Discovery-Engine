"""Grounding faithfulness checks for assistant answers."""

from __future__ import annotations

import re

from eval.metrics import tokenize
from eval.schemas import FaithfulnessEvalCase, MetricResult


def _is_refusal(answer: str) -> bool:
    lowered = answer.lower()
    markers = (
        "cannot provide a grounded answer",
        "insufficient evidence",
        "not enough evidence",
        "no relevant evidence",
    )
    return any(marker in lowered for marker in markers)


def score_answer_faithfulness(
    answer: str,
    evidence_texts: list[str],
    *,
    should_refuse: bool = False,
) -> float:
    """Score how well an answer is supported by cited evidence (0–1)."""
    if should_refuse:
        return 1.0 if _is_refusal(answer) else 0.0

    if not evidence_texts:
        return 0.0

    evidence_tokens = set()
    for text in evidence_texts:
        evidence_tokens.update(tokenize(text))

    if not evidence_tokens:
        return 0.0

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", answer.strip())
        if sentence.strip()
    ]
    if not sentences:
        return 0.0

    supported = 0
    for sentence in sentences:
        sentence_tokens = tokenize(sentence)
        if not sentence_tokens:
            continue
        overlap = len(sentence_tokens & evidence_tokens) / len(sentence_tokens)
        if overlap >= 0.25:
            supported += 1

    return supported / len(sentences)


def compute_faithfulness_metrics(
    cases: list[FaithfulnessEvalCase],
    *,
    target: float,
) -> MetricResult:
    """Average faithfulness score across labeled answer/evidence pairs."""
    if not cases:
        return MetricResult(
            name="grounding_faithfulness",
            value=0.0,
            target=target,
            passed=False,
            details={"error": "No faithfulness eval cases configured"},
        )

    scores: list[float] = []
    per_case: list[dict[str, float | bool | str]] = []

    for case in cases:
        score = score_answer_faithfulness(
            case.answer,
            case.evidence_texts,
            should_refuse=case.should_refuse,
        )
        scores.append(score)
        per_case.append(
            {
                "question": case.question[:80],
                "score": round(score, 4),
                "should_refuse": case.should_refuse,
            }
        )

    average = sum(scores) / len(scores)
    return MetricResult(
        name="grounding_faithfulness",
        value=round(average, 4),
        target=target,
        passed=average >= target,
        details={
            "average": round(average, 4),
            "cases": len(cases),
            "per_case": per_case,
        },
    )
