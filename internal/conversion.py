"""Compute wishlist-to-purchase 30-day conversion from internal events."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from internal.schemas import InternalEventRecord


@dataclass(frozen=True, slots=True)
class ConversionResult:
    window_days: int
    wishlist_users: int
    converted_users: int
    conversion_rate: float
    cohort_start: datetime | None
    cohort_end: datetime | None

    @property
    def non_conversion_rate(self) -> float:
        return round(1.0 - self.conversion_rate, 4)


def compute_wishlist_conversion(
    events: list[InternalEventRecord],
    *,
    window_days: int = 30,
) -> ConversionResult:
    """Compute user-level wishlist-to-purchase conversion within *window_days*."""
    wishlist_by_user: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    purchases_by_user: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    event_times: list[datetime] = []

    for event in events:
        event_times.append(event.event_at)
        if event.event_type == "wishlist_add":
            wishlist_by_user[event.user_hash].append((event.event_at, event.product_id))
        elif event.event_type == "purchase":
            purchases_by_user[event.user_hash].append((event.event_at, event.product_id))

    converted_users = 0
    for user_hash, wishlist_items in wishlist_by_user.items():
        user_purchases = purchases_by_user.get(user_hash, [])
        if _user_converted(wishlist_items, user_purchases, window_days=window_days):
            converted_users += 1

    wishlist_users = len(wishlist_by_user)
    conversion_rate = round(converted_users / wishlist_users, 4) if wishlist_users else 0.0

    cohort_start = min(event_times) if event_times else None
    cohort_end = max(event_times) if event_times else None

    return ConversionResult(
        window_days=window_days,
        wishlist_users=wishlist_users,
        converted_users=converted_users,
        conversion_rate=conversion_rate,
        cohort_start=cohort_start,
        cohort_end=cohort_end,
    )


def _user_converted(
    wishlist_items: list[tuple[datetime, str]],
    purchases: list[tuple[datetime, str]],
    *,
    window_days: int,
) -> bool:
    window = timedelta(days=window_days)
    for wishlist_at, product_id in wishlist_items:
        for purchase_at, purchased_id in purchases:
            if purchased_id != product_id:
                continue
            if wishlist_at <= purchase_at <= wishlist_at + window:
                return True
    return False


def segment_non_conversion_rates(
    events: list[InternalEventRecord],
    *,
    window_days: int = 30,
) -> dict[str, float]:
    """Return non-conversion share by segment from internal behavioral data."""
    users_by_segment: dict[str, set[str]] = defaultdict(set)
    converted_by_segment: dict[str, set[str]] = defaultdict(set)

    wishlist_by_user: dict[str, list[tuple[datetime, str, str | None]]] = defaultdict(list)
    purchases_by_user: dict[str, list[tuple[datetime, str]]] = defaultdict(list)

    for event in events:
        if event.event_type == "wishlist_add":
            wishlist_by_user[event.user_hash].append(
                (event.event_at, event.product_id, event.segment)
            )
        elif event.event_type == "purchase":
            purchases_by_user[event.user_hash].append((event.event_at, event.product_id))

    for user_hash, items in wishlist_by_user.items():
        segment = next((seg for _, _, seg in items if seg), "unknown")
        users_by_segment[segment].add(user_hash)
        if _user_converted(
            [(at, pid) for at, pid, _ in items],
            purchases_by_user.get(user_hash, []),
            window_days=window_days,
        ):
            converted_by_segment[segment].add(user_hash)

    rates: dict[str, float] = {}
    for segment, users in users_by_segment.items():
        converted = len(converted_by_segment.get(segment, set()))
        rates[segment] = round(1.0 - (converted / len(users)), 4) if users else 0.0
    return rates
