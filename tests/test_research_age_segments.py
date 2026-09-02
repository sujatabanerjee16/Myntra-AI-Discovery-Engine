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


def test_enrich_tags_beauty_and_footwear_terms():
    beauty = enrich_chunk(
        TextChunk(
            document_ref="test:beauty",
            chunk_index=0,
            text="This lipstick and kajal stay on my wishlist",
            matched_signals=["wishlist_usage"],
            metadata={},
        )
    )
    footwear = enrich_chunk(
        TextChunk(
            document_ref="test:footwear",
            chunk_index=0,
            text="Waiting for a sale on these sandals and heels",
            matched_signals=["price_sensitivity_waiting"],
            metadata={},
        )
    )
    assert beauty.category == "beauty"
    assert footwear.category == "footwear"


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


def test_survey_purchase_habits_from_excel():
    from api.survey_habits import get_survey_purchase_habits

    payload = get_survey_purchase_habits()
    assert payload["respondents"] == 42
    assert payload["checkout_rate_available"] is False
    files = {row["file"] for row in payload["workbooks"]}
    assert "Myntra Wishlist.xlsx" in files
    assert "Your Wishlist Habits (Responses).xlsx" in files
    young = get_survey_purchase_habits(segment="age_18_24")
    assert young["respondents"] == 27
    for book in payload["workbooks"]:
        assert sum(row["count"] for row in book["answers"]) == book["n"]


def test_research_respondent_counts_from_corpus():
    from api.json_dashboard import research_respondent_counts

    counts = research_respondent_counts()
    assert counts["age_18_24"] == 27
    assert counts["age_25_35"] == 15
    assert counts["age_18_24"] + counts["age_25_35"] == 42


def test_survey_card_count_matches_age_split():
    from api.json_store import load_corpus_scrape_stats

    stats = load_corpus_scrape_stats()
    assert stats["survey_respondents"] == 42
    assert sum(row["respondents"] for row in stats["survey_by_workbook"]) == 42


def test_age_origin_counts_split_survey_and_play_store():
    from api.json_dashboard import age_band_origin_counts

    origins = age_band_origin_counts()
    assert origins["age_18_24"]["survey"] == 27
    assert origins["age_25_35"]["survey"] == 15
    assert origins["age_18_24"]["play_store"] >= 0
    assert "other_scrape" in origins["age_18_24"]


def test_reasons_http_source_and_confidence_filters():
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    all_rows = client.get("/insights/reasons").json()["reasons"]
    research = client.get("/insights/reasons", params={"sources": "research"}).json()["reasons"]
    high = client.get("/insights/reasons", params={"min_confidence": 0.6}).json()["reasons"]
    empty = client.get("/insights/reasons", params={"min_confidence": 0.95}).json()["reasons"]
    assert all_rows and research and high
    assert research[0]["evidence_volume"] != all_rows[0]["evidence_volume"] or research[0][
        "reason_category"
    ] != all_rows[0]["reason_category"]
    assert sum(row["evidence_volume"] for row in high) < sum(row["evidence_volume"] for row in all_rows)
    assert empty == []


def test_reason_ranks_change_when_source_filter_applied():
    from api.json_dashboard import get_filtered_reason_ranks

    all_rows = get_filtered_reason_ranks()
    play = get_filtered_reason_ranks(sources=["play_store"])
    research = get_filtered_reason_ranks(sources=["research"])
    assert all_rows and play and research
    assert play[0].evidence_volume != research[0].evidence_volume or play[0].reason_category != research[0].reason_category


def test_reason_ranks_change_when_min_confidence_rises():
    from api.json_dashboard import get_filtered_reason_ranks

    baseline = get_filtered_reason_ranks()
    mid = get_filtered_reason_ranks(min_confidence=0.65)
    empty = get_filtered_reason_ranks(min_confidence=0.95)
    assert baseline
    assert mid
    assert mid[0].reason_category != baseline[0].reason_category or mid[0].evidence_volume != baseline[0].evidence_volume
    assert empty == []


def test_reason_rank_falls_back_to_category_when_age_combo_empty():
    from api.json_dashboard import rank_reasons_for_dashboard

    items, note = rank_reasons_for_dashboard(
        segment="age_25_35",
        category="beauty",
    )
    if items:
        assert note is None or "showing all beauty" in (note or "").lower()
    empty, empty_note = rank_reasons_for_dashboard(
        segment="age_18_24",
        category="__no_such_category__",
    )
    assert empty == []
    assert empty_note is None


def test_category_filter_accepts_display_labels():
    from api.json_dashboard import rank_reasons_for_dashboard

    titled, _ = rank_reasons_for_dashboard(category="Clothing")
    lower, _ = rank_reasons_for_dashboard(category="clothing")
    beauty, _ = rank_reasons_for_dashboard(category="Beauty")
    assert titled and lower
    assert titled[0].reason_category == lower[0].reason_category
    assert beauty


def test_high_intent_does_not_zero_a_category_with_data():
    from api.json_dashboard import rank_reasons_for_dashboard

    sources = ["play_store", "youtube", "reddit", "product_review", "social"]
    clothing, clothing_note = rank_reasons_for_dashboard(
        category="clothing",
        intent="active_shortlist",
        sources=sources,
        min_confidence=0.5,
    )
    beauty, beauty_note = rank_reasons_for_dashboard(
        category="beauty",
        intent="active_shortlist",
        sources=sources,
        min_confidence=0.5,
    )
    assert clothing
    assert beauty
    assert sum(item.evidence_volume for item in clothing) > 0
    assert sum(item.evidence_volume for item in beauty) > 0
    assert clothing_note is None or "intent" in clothing_note.lower()
    assert beauty_note is None or "intent" in beauty_note.lower()


def test_voice_preview_uses_real_excerpts():
    from api.json_dashboard import get_voice_preview

    groups = get_voice_preview(sources=["play_store", "youtube", "reddit", "product_review", "social"])
    assert len(groups) >= 5
    keys = {group["reason_category"] for group in groups}
    assert "fit_sizing_uncertainty" in keys
    assert "external_comparison" in keys
    assert "timing_occasion" in keys
    for group in groups:
        assert group["evidence_volume"] > 0
        assert group["code"]
        assert len(group["lines"]) == 1
        assert group["lines"][0]["text"]


def test_survey_pain_preview_uses_form_quotes():
    from api.json_dashboard import get_survey_pain_preview

    preview = get_survey_pain_preview()
    assert len(preview["reasons"]) == 4
    assert preview["reasons"][0]["reason_category"] == "price_sensitivity_waiting"
    assert preview["reasons"][0]["evidence_volume"] == 62
    assert len(preview["quotes"]) == 4
    texts = [item["text"].lower() for item in preview["quotes"]]
    assert any("price" in text or "expensive" in text or "budget" in text for text in texts)
    assert any("fit" in text for text in texts)
    assert all(item["origin"] in ("form", "interview") for item in preview["quotes"])
