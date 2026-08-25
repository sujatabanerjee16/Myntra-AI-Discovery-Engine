"""Tests for priority-signal relevance filtering."""

from ingestion.filters.relevance import detect_signals, is_relevant


def test_wishlist_usage_detected():
    text = "I use the wishlist to save items for later purchase."
    result = is_relevant(text)
    assert result.is_relevant
    assert "wishlist_usage" in result.matched_signals


def test_unrelated_review_rejected():
    text = "Great app UI, very fast delivery, love the packaging."
    result = is_relevant(text)
    assert not result.is_relevant


def test_price_sensitivity_detected():
    text = "Waiting for a sale before buying from my saved wishlist items."
    signals = detect_signals(text)
    assert "price_sensitivity_waiting" in signals
    assert "wishlist_usage" in signals


def test_research_survey_row_always_included():
    text = "I add items a few times a week and purchase often."
    result = is_relevant(text, always_include=True)
    assert result.is_relevant
