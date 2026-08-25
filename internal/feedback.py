"""PM feedback loop for validating and adjusting insight confidence."""

from __future__ import annotations

from collections import Counter

VERDICT_ADJUSTMENTS: dict[str, float] = {
    "validated": 0.05,
    "flagged": -0.12,
    "needs_review": -0.03,
}


def adjust_confidence(base_confidence: float | None, verdict: str) -> float | None:
    """Apply a PM verdict adjustment to a base confidence score."""
    if base_confidence is None:
        return None
    delta = VERDICT_ADJUSTMENTS.get(verdict, 0.0)
    return round(min(max(base_confidence + delta, 0.0), 1.0), 3)


def aggregate_feedback_adjustment(feedback_verdicts: list[str]) -> float:
    """Net confidence adjustment from multiple PM feedback records."""
    counts = Counter(feedback_verdicts)
    total = 0.0
    for verdict, count in counts.items():
        total += VERDICT_ADJUSTMENTS.get(verdict, 0.0) * count
    return round(total, 3)


def apply_feedback_to_confidence(
    base_confidence: float | None,
    feedback_verdicts: list[str],
) -> float | None:
    """Blend base confidence with accumulated PM feedback."""
    if base_confidence is None:
        return None
    adjusted = base_confidence + aggregate_feedback_adjustment(feedback_verdicts)
    return round(min(max(adjusted, 0.0), 1.0), 3)
