"""Tests for ingestion pipeline stages (no DB/network)."""

from common.models import SourceType
from ingestion.schemas import RawRecord
from ingestion.stages.chunk import chunk_records
from ingestion.stages.clean import clean_records
from ingestion.stages.dedupe import dedupe_records
from ingestion.stages.enrich import enrich_chunks
from ingestion.stages.pii import scrub_records


def _sample_record(text: str, ref: str = "test:1") -> RawRecord:
    return RawRecord(
        source=SourceType.research,
        source_ref=ref,
        text=text,
        matched_signals=["wishlist_usage"],
    )


def test_clean_scrubs_short_text():
    records = [_sample_record("too short")]
    assert clean_records(records) == []


def test_pii_scrubs_email():
    records = [_sample_record("Contact me at user@example.com about wishlist fit issues")]
    out = scrub_records(records)
    assert "[email]" in out[0].text
    assert "user@example.com" not in out[0].text


def test_dedupe_removes_duplicate_content():
    a = _sample_record("I hesitate to buy wishlist items due to price.", "a")
    b = _sample_record("I hesitate to buy wishlist items due to price.", "b")
    out = dedupe_records([a, b])
    assert len(out) == 1


def test_chunk_splits_long_text():
    long_text = ("Wishlist sizing uncertainty. " * 40).strip()
    chunks = chunk_records([_sample_record(long_text)])
    assert len(chunks) >= 2


def test_enrich_tags_price_segment():
    text = "Waiting for a discount sale before buying wishlist shoes; comparing on Amazon."
    enriched = enrich_chunks(chunk_records([_sample_record(text)]))
    assert enriched[0].price_band == "sale_waiting"
    assert enriched[0].segment == "comparison_shopper"
