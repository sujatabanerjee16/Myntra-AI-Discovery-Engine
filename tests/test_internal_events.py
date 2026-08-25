"""Tests for internal events connector."""

from pathlib import Path

from internal.connectors.events import load_internal_events


def test_load_seed_internal_events():
    path = Path("data/seeds/internal_wishlist_events.json")
    records = load_internal_events(path)
    assert len(records) >= 10
    assert any(record.event_type == "wishlist_add" for record in records)
    assert any(record.event_type == "purchase" for record in records)
