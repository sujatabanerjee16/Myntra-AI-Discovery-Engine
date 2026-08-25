"""Tests for wishlist conversion metric computation."""

from datetime import UTC, datetime

from internal.conversion import compute_wishlist_conversion, segment_non_conversion_rates
from internal.schemas import InternalEventRecord


def _event(user: str, product: str, event_type: str, day: int, segment: str | None = None):
    return InternalEventRecord(
        user_hash=user,
        product_id=product,
        event_type=event_type,
        segment=segment,
        event_at=datetime(2026, 7, day, tzinfo=UTC),
    )


def test_conversion_rate_for_mixed_cohort():
    events = [
        _event("u1", "p1", "wishlist_add", 1),
        _event("u1", "p1", "purchase", 10),
        _event("u2", "p2", "wishlist_add", 2),
        _event("u3", "p3", "wishlist_add", 3),
        _event("u3", "p3", "purchase", 20),
    ]
    result = compute_wishlist_conversion(events, window_days=30)
    assert result.wishlist_users == 3
    assert result.converted_users == 2
    assert result.conversion_rate == round(2 / 3, 4)


def test_purchase_outside_window_does_not_convert():
    events = [
        _event("u1", "p1", "wishlist_add", 1, "price_sensitive"),
        InternalEventRecord(
            user_hash="u1",
            product_id="p1",
            event_type="purchase",
            segment="price_sensitive",
            event_at=datetime(2026, 9, 1, tzinfo=UTC),
        ),
    ]
    result = compute_wishlist_conversion(events, window_days=30)
    assert result.converted_users == 0


def test_segment_non_conversion_rates():
    events = [
        _event("u1", "p1", "wishlist_add", 1, "price_sensitive"),
        _event("u1", "p1", "purchase", 5, "price_sensitive"),
        _event("u2", "p2", "wishlist_add", 2, "price_sensitive"),
        _event("u3", "p3", "wishlist_add", 3, "fit_uncertain"),
    ]
    rates = segment_non_conversion_rates(events, window_days=30)
    assert rates["price_sensitive"] == 0.5
    assert rates["fit_uncertain"] == 1.0
