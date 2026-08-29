"""Tests for Phase 7 connectors and validation."""

from collections import Counter

from common.models import SourceType
from ingestion.connectors.product_review import fetch_product_review_records
from ingestion.connectors.reddit import fetch_reddit_records
from ingestion.connectors.registry import ALL_SOURCES, fetch_source_records
from ingestion.connectors.social import fetch_social_records
from ingestion.connectors.youtube import fetch_youtube_records
from ingestion.schemas import RawRecord
from ingestion.validation import summarize_source_coverage, validate_corpus


def test_all_sources_registered():
    assert len(ALL_SOURCES) == 6
    assert "reddit" in ALL_SOURCES
    assert "youtube" in ALL_SOURCES


def test_seed_connectors_return_records():
    connectors = (
        fetch_reddit_records,
        fetch_youtube_records,
        fetch_product_review_records,
        fetch_social_records,
    )
    for connector in connectors:
        records = connector()
        assert records
        assert all(record.text for record in records)


def test_research_bundle_fetch(tmp_path):
    path = tmp_path / "x.xlsx"
    import pandas as pd

    pd.DataFrame(
        [
            {
                "Timestamp": "2026-01-01",
                "Which age range are you in?": "18-24",
                "Why waiting": "Wishlist price waiting for sale discount",
            }
        ]
    ).to_excel(path, index=False)
    records = fetch_source_records("research", research_excel_path=str(path))
    assert len(records) >= 1
    assert records[0].metadata.get("age_band") == "age_18_24"


def test_validate_corpus_reports_cross_source_duplicates():
    shared = "I keep wishlist items and wait for a sale before buying."
    records = [
        RawRecord(
            source=SourceType.reddit,
            source_ref="r:1",
            text=shared,
            matched_signals=["wishlist_usage"],
        ),
        RawRecord(
            source=SourceType.social,
            source_ref="s:1",
            text=shared,
            matched_signals=["wishlist_usage"],
        ),
    ]
    report = validate_corpus(records)
    assert report.cross_source_duplicates == 1


def test_summarize_source_coverage():
    coverage = summarize_source_coverage(Counter({"research": 3, "reddit": 2}))
    assert coverage["research"] is True
    assert coverage["reddit"] is True
    assert coverage["youtube"] is False
