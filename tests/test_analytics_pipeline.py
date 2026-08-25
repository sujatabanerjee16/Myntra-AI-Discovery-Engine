"""Tests for semantic analytics pipeline (no database)."""

from analytics.confidence import compute_confidence
from analytics.pipeline import run_semantic_analytics


def test_confidence_increases_with_evidence_and_sources():
    low = compute_confidence(evidence_volume=1, sources={"play_store"}, avg_quality=0.5)
    high = compute_confidence(
        evidence_volume=12,
        sources={"research", "play_store"},
        avg_quality=0.9,
    )
    assert high > low


def test_run_semantic_analytics_on_sample_chunks():
    raw_chunks = [
        {
            "chunk_id": "research:row:0:0",
            "text": "Wishlist price too high, waiting for a sale and coupon discount.",
            "signals": ["wishlist_usage", "price_sensitivity_waiting"],
            "category": "clothing",
            "segment": "price_sensitive",
            "quality_score": 0.8,
            "source": "research",
        },
        {
            "chunk_id": "research:row:1:0",
            "text": "Unsure about fit and preferred size unavailable in wishlist items.",
            "signals": ["fit_size_styling_quality_trust_occasion", "purchase_hesitation"],
            "category": "footwear",
            "segment": "fit_uncertain",
            "quality_score": 0.75,
            "source": "research",
        },
        {
            "chunk_id": "play_store:1:0",
            "text": "Compare prices on Amazon before buying from wishlist.",
            "signals": ["external_comparison_seeking", "wishlist_usage"],
            "category": None,
            "segment": "comparison_shopper",
            "quality_score": 0.7,
            "source": "play_store",
        },
    ]

    result = run_semantic_analytics(raw_chunks, run_version="test-analytics")

    assert result.chunks_analyzed == 3
    assert result.insights_created >= 2
    assert result.reason_aggregates >= 2
    assert all(i["confidence"] is not None for i in result.insights)
    assert all(i["evidence_chunk_ids"] for i in result.insights)
