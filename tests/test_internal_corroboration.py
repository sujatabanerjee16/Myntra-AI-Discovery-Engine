"""Tests for reason corroboration and PM feedback adjustments."""

from internal.corroboration import compute_corroboration
from internal.feedback import adjust_confidence, apply_feedback_to_confidence


def test_corroboration_ranks_price_reason_when_segments_align():
    reasons = [
        {
            "reason_category": "price_sensitivity_waiting",
            "evidence_volume": 20,
            "confidence": 0.8,
        },
        {
            "reason_category": "logistics_friction",
            "evidence_volume": 5,
            "confidence": 0.5,
        },
    ]
    segment_rates = {"price_sensitive": 0.9, "fit_uncertain": 0.4}
    rows = compute_corroboration(reasons, segment_rates)
    assert rows[0].reason_category == "price_sensitivity_waiting"
    assert rows[0].status in {"corroborated", "partial"}


def test_pm_feedback_validated_boosts_confidence():
    assert adjust_confidence(0.7, "validated") == 0.75


def test_pm_feedback_flagged_reduces_confidence():
    assert adjust_confidence(0.7, "flagged") == 0.58


def test_accumulated_feedback_adjustment():
    adjusted = apply_feedback_to_confidence(0.7, ["validated", "flagged"])
    assert adjusted == 0.63
