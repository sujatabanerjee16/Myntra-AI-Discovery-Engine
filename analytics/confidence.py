"""Confidence scoring for semantic insights."""

from __future__ import annotations

SOURCE_RELIABILITY: dict[str, float] = {
    "research": 0.9,
    "play_store": 0.7,
    "product_review": 0.75,
    "youtube": 0.65,
    "social": 0.6,
    "reddit": 0.6,
}


def source_agreement(sources: set[str]) -> float:
    """Higher when multiple independent source types support the insight."""
    if len(sources) >= 3:
        return 1.0
    if len(sources) == 2:
        return 0.85
    if len(sources) == 1:
        return 0.65
    return 0.4


def compute_confidence(
    *,
    evidence_volume: int,
    sources: set[str],
    avg_quality: float,
    agreement: float | None = None,
) -> float:
    """Combine evidence volume, source reliability, quality, and agreement."""
    volume_score = min(evidence_volume / 10.0, 1.0) * 0.35

    if sources:
        reliability = sum(SOURCE_RELIABILITY.get(s, 0.55) for s in sources) / len(sources)
    else:
        reliability = 0.5
    source_score = reliability * 0.25

    quality_score = max(0.0, min(avg_quality, 1.0)) * 0.2
    agreement_score = (agreement if agreement is not None else source_agreement(sources)) * 0.2

    total = volume_score + source_score + quality_score + agreement_score
    return round(min(total, 1.0), 3)
