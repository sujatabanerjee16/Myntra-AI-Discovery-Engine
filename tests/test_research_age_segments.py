"""Tests for research Excel age-band normalization and dual-workbook fetch."""

from pathlib import Path

import pandas as pd

from ingestion.connectors.research_excel import (
    AGE_18_24,
    AGE_25_35,
    fetch_all_research_records,
    normalize_age_band,
)
from ingestion.stages.chunk import TextChunk
from ingestion.stages.enrich import enrich_chunk


def test_normalize_age_band():
    assert normalize_age_band("18-24") == AGE_18_24
    assert normalize_age_band("25-35") == AGE_25_35
    assert normalize_age_band("25-34") == AGE_25_35
    assert normalize_age_band("22") == AGE_18_24
    assert normalize_age_band("") is None


def test_enrich_prefers_age_metadata():
    chunk = TextChunk(
        text="I am waiting for a sale before buying this wishlist item",
        chunk_index=0,
        document_ref="research:test:1",
        matched_signals=["price_sensitivity_waiting"],
        metadata={"age_band": AGE_18_24},
    )
    enriched = enrich_chunk(chunk)
    assert enriched.segment == AGE_18_24


def test_fetch_both_research_workbooks():
    root = Path(__file__).resolve().parents[1]
    paths = [
        root / "Myntra Wishlist.xlsx",
        root / "Your Wishlist Habits (Responses).xlsx",
    ]
    if not all(p.exists() for p in paths):
        return
    records = fetch_all_research_records(paths)
    assert len(records) >= 40
    age_segments = {
        r.metadata.get("age_band") for r in records if r.metadata.get("age_band")
    }
    assert AGE_18_24 in age_segments
    assert AGE_25_35 in age_segments


def test_research_bundle_via_registry(tmp_path):
    from ingestion.connectors.registry import fetch_source_records

    path = tmp_path / "survey.xlsx"
    pd.DataFrame(
        [
            {
                "Timestamp": "2026-01-01",
                "Which age range are you in?": "18-24",
                "Why have you not bought it yet?": "Waiting for a sale on my wishlist item",
            },
            {
                "Timestamp": "2026-01-02",
                "Which age range are you in?": "25-34",
                "Why have you not bought it yet?": "Unsure about fit on wishlist shoes",
            },
        ]
    ).to_excel(path, index=False)

    records = fetch_source_records("research", research_excel_paths=[str(path)])
    assert len(records) >= 2
    bands = {r.metadata.get("age_band") for r in records}
    assert AGE_18_24 in bands
    assert AGE_25_35 in bands
