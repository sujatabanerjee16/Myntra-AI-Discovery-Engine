"""Smoke tests for offline conversion warm-up used at API startup."""

from internal.offline import get_offline_store, run_offline_internal_pipeline


def test_offline_pipeline_populates_conversion_snapshot():
    """Startup lifespan calls this when use_json_backend() is true."""
    result = run_offline_internal_pipeline()
    store = get_offline_store()
    assert result.events_loaded > 0
    assert store.conversion is not None
    assert store.conversion.wishlist_users > 0
