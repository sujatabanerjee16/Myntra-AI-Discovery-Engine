"""Tests for reason taxonomy classification."""

from analytics.taxonomy import classify_reason


def test_price_reason_from_sale_waiting_text():
    result = classify_reason(
        "The price is too high and I am waiting for a sale before buying wishlist items.",
        signals=["price_sensitivity_waiting", "wishlist_usage"],
    )
    assert result.primary == "price_sensitivity_waiting"


def test_fit_reason_from_size_uncertainty():
    result = classify_reason(
        "My preferred size is unavailable and I am unsure about the fit.",
        signals=["fit_size_styling_quality_trust_occasion"],
    )
    assert result.primary == "fit_sizing_uncertainty"


def test_external_comparison_reason():
    result = classify_reason(
        "I compare prices on Amazon and Flipkart before purchasing.",
        signals=["external_comparison_seeking"],
    )
    assert result.primary == "external_comparison"


def test_wishlist_usage_signal_is_not_a_friction():
    result = classify_reason(
        "I added this dress to my Myntra wishlist yesterday.",
        signals=["wishlist_usage"],
    )
    assert result.primary is None


def test_explicit_inspiration_save_is_passive_bookmarking():
    result = classify_reason(
        "I just bookmark outfits for inspiration and do not revisit them.",
        signals=["wishlist_usage"],
    )
    assert result.primary == "passive_bookmarking"
