"""Tests for the Myntra Wishlist research Excel connector."""

from pathlib import Path

from common.models import SourceType
from ingestion.connectors.research_excel import fetch_research_records

EXCEL_PATH = Path("Myntra Wishlist.xlsx")


def test_fetch_research_records_from_excel():
    assert EXCEL_PATH.exists(), "Myntra Wishlist.xlsx fixture missing"
    records = fetch_research_records(EXCEL_PATH)
    assert len(records) == 9
    assert all(r.source == SourceType.research for r in records)
    assert all(r.source_ref.startswith("research:myntra-wishlist:row:") for r in records)
    assert all(len(r.text) > 50 for r in records)


def test_research_records_contain_wishlist_signals():
    records = fetch_research_records(EXCEL_PATH)
    combined = " ".join(r.text.lower() for r in records)
    assert "wishlist" in combined
    assert any("price" in r.text.lower() or "sale" in r.text.lower() for r in records)
