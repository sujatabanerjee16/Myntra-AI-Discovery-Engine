"""Join public-evidence reasons with observed internal conversion behavior."""

from __future__ import annotations

from dataclasses import dataclass

REASON_SEGMENT_AFFINITY: dict[str, list[str]] = {
    "price_sensitivity_waiting": ["price_sensitive"],
    "fit_sizing_uncertainty": ["fit_uncertain"],
    "quality_trust_doubt": ["quality_concerned"],
    "styling_decision_uncertainty": ["comparison_shopper"],
    "review_trust": ["quality_concerned"],
    "timing_occasion": ["price_sensitive"],
    "external_comparison": ["comparison_shopper"],
    "passive_bookmarking": ["comparison_shopper"],
    "logistics_friction": ["fit_uncertain", "price_sensitive"],
}


@dataclass(frozen=True, slots=True)
class CorroborationRow:
    reason_category: str
    public_confidence: float | None
    public_evidence_volume: int
    internal_non_conversion_share: float | None
    corroboration_score: float
    status: str
    segment_affinity: list[str]


def _status(score: float) -> str:
    if score >= 0.75:
        return "corroborated"
    if score >= 0.5:
        return "partial"
    return "weak"


def compute_corroboration(
    reason_aggregates: list[dict],
    segment_non_conversion: dict[str, float],
) -> list[CorroborationRow]:
    """Score how well public reasons align with internal non-conversion patterns."""
    if not reason_aggregates:
        return []

    max_volume = max(item.get("evidence_volume", 0) for item in reason_aggregates) or 1
    rows: list[CorroborationRow] = []

    for item in reason_aggregates:
        category = str(item.get("reason_category", ""))
        volume = int(item.get("evidence_volume", 0))
        confidence = item.get("confidence")
        segments = REASON_SEGMENT_AFFINITY.get(category, [])

        internal_shares = [
            segment_non_conversion[segment]
            for segment in segments
            if segment in segment_non_conversion
        ]
        internal_share = sum(internal_shares) / len(internal_shares) if internal_shares else None

        public_signal = volume / max_volume
        if internal_share is None:
            score = round(public_signal * 0.5, 4)
        else:
            score = round((0.55 * public_signal) + (0.45 * internal_share), 4)

        if confidence is not None:
            score = round((0.7 * score) + (0.3 * float(confidence)), 4)

        rows.append(
            CorroborationRow(
                reason_category=category,
                public_confidence=float(confidence) if confidence is not None else None,
                public_evidence_volume=volume,
                internal_non_conversion_share=internal_share,
                corroboration_score=min(score, 1.0),
                status=_status(score),
                segment_affinity=segments,
            )
        )

    rows.sort(key=lambda row: row.corroboration_score, reverse=True)
    return rows
