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


def test_research_bundle_fetch(monkeypatch, tmp_path):
    from ingestion.connectors import registry

    def fake_research(excel_path, **_kwargs):
        assert excel_path.endswith("x.xlsx")
        return [
            RawRecord(
                source=SourceType.research,
                source_ref="research:test:1",
                text="Wishlist price waiting for sale discount",
                matched_signals=["price_sensitivity_waiting"],
            )
        ]

    def fake_open(excel_path, **_kwargs):
        return []

    monkeypatch.setattr(registry, "fetch_research_records", fake_research)
    monkeypatch.setattr(registry, "fetch_research_open_text_records", fake_open)
    records = fetch_source_records("research", research_excel_path=str(tmp_path / "x.xlsx"))
    assert len(records) == 1


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
