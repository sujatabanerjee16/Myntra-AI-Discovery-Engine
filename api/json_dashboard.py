"""Dashboard queries backed by exported JSON (no PostgreSQL required)."""

from __future__ import annotations

import uuid
from collections import defaultdict

from analytics.schemas import (
    ComparisonItem,
    ComparisonResponse,
    CompetitiveAnalysisResponse,
    DashboardFiltersResponse,
    EvidenceExcerpt,
    EvidenceSummaryResponse,
    HeatmapCell,
    HeatmapResponse,
    IntentBreakdownItem,
    IntentBreakdownResponse,
    JourneyTrendItem,
    ReasonRankItem,
    ThemeClusterItem,
    ThemeClusterResponse,
    TrendsResponse,
)
from api.json_store import chunk_lookup, load_corpus_chunks, load_insights_payload, parse_chunk_uuid
from assistant.schemas import AggregateContext


def _payload() -> dict:
    return load_insights_payload()


def normalize_filter_key(value: str | None) -> str | None:
    """Slug a UI filter so 'Clothing' and 'clothing' hit the same rows."""
    if not value:
        return None
    key = (
        str(value)
        .strip()
        .lower()
        .replace("–", "_")
        .replace("—", "_")
        .replace("-", "_")
        .replace(" ", "_")
    )
    while "__" in key:
        key = key.replace("__", "_")
    return key or None


def _keys_match(stored: str | None, wanted: str | None) -> bool:
    if not wanted:
        return True
    return normalize_filter_key(stored) == wanted


_SOURCE_ALIASES = {
    "play_store": {"play_store", "playstore", "google_play", "app"},
    "youtube": {"youtube", "yt"},
    "reddit": {"reddit"},
    "product_review": {"product_review", "product_reviews", "review", "reviews"},
    "social": {"social", "instagram", "twitter", "x"},
    "research": {"research", "survey", "interview"},
}


def _parse_csv_param(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _insight_sources(row: dict) -> list[str]:
    sources = row.get("sources") or []
    if isinstance(sources, str):
        return [sources]
    return [str(item) for item in sources if item]


def _matches_sources(row: dict, selected: list[str]) -> bool:
    if not selected:
        return True
    aliases = {alias for key in selected for alias in _SOURCE_ALIASES.get(key, {key})}
    row_sources = _insight_sources(row)
    if not row_sources:
        return False
    return any(source.lower().replace(" ", "_") in aliases for source in row_sources)


def _matches_platforms(row: dict, selected: list[str]) -> bool:
    if not selected:
        return True
    wanted = {item.lower() for item in selected}
    platforms = [str(item).lower() for item in (row.get("platforms") or [])]
    if not platforms:
        return "other" in wanted
    return any(item in wanted for item in platforms)


def _chunk_price_bands() -> dict[str, str]:
    index: dict[str, str] = {}
    for chunk in load_corpus_chunks():
        band = chunk.get("price_band")
        chunk_id = chunk.get("chunk_id")
        if band and chunk_id:
            index[str(chunk_id)] = str(band)
    return index


def _matches_price_band(row: dict, price_band: str | None, price_index: dict[str, str]) -> bool:
    if not price_band:
        return True
    wanted = normalize_filter_key(price_band)
    for raw_id in row.get("evidence_chunk_ids") or []:
        if normalize_filter_key(price_index.get(str(raw_id))) == wanted:
            return True
    return False


def _insights(
    *,
    segment: str | None = None,
    category: str | None = None,
    reason_category: str | None = None,
    min_confidence: float | None = None,
    sources: list[str] | None = None,
    platforms: list[str] | None = None,
    intent: str | None = None,
    price_band: str | None = None,
) -> list[dict]:
    rows = _payload().get("insights", [])
    segment = normalize_filter_key(segment)
    category = normalize_filter_key(category)
    reason_category = normalize_filter_key(reason_category)
    intent = normalize_filter_key(intent)
    price_band = normalize_filter_key(price_band)
    price_index = _chunk_price_bands() if price_band else {}
    filtered: list[dict] = []
    for row in rows:
        if not _keys_match(row.get("segment"), segment):
            continue
        if not _keys_match(row.get("category"), category):
            continue
        if not _keys_match(row.get("reason_category"), reason_category):
            continue
        if min_confidence is not None:
            conf = row.get("confidence")
            if conf is None or float(conf) < min_confidence:
                continue
        if not _matches_sources(row, sources or []):
            continue
        if not _matches_platforms(row, platforms or []):
            continue
        if not _keys_match(row.get("intent_type"), intent):
            continue
        if not _matches_price_band(row, price_band, price_index):
            continue
        filtered.append(row)
    return filtered


def fetch_relevant_aggregates_json(reason_categories: list[str]) -> AggregateContext:
    payload = load_insights_payload()
    reasons = payload.get("reasons", [])
    clusters = payload.get("clusters", [])
    competitive = payload.get("competitive", [])
    competitive_summary = payload.get("competitive_summary") or {}

    if reason_categories:
        reasons = sorted(
            reasons,
            key=lambda row: (
                0 if row.get("reason_category") in reason_categories else 1,
                -(row.get("evidence_volume") or 0),
            ),
        )[:5]
    else:
        reasons = reasons[:5]

    if reason_categories:
        clusters = sorted(
            clusters,
            key=lambda row: (
                0 if row.get("reason_category") in reason_categories else 1,
                -(row.get("evidence_volume") or 0),
            ),
        )[:5]
    else:
        clusters = clusters[:5]

    return AggregateContext(
        run_version=payload.get("run_version"),
        ranked_reasons=[
            {
                "reason_category": row["reason_category"],
                "evidence_volume": row.get("evidence_volume", 0),
                "confidence": row.get("confidence"),
                "sources": row.get("sources") or [],
                "active_shortlist_count": row.get("active_shortlist_count", 0),
                "passive_bookmark_count": row.get("passive_bookmark_count", 0),
            }
            for row in reasons
        ],
        theme_clusters=[
            {
                "cluster_key": row["cluster_key"],
                "label": row["label"],
                "reason_category": row.get("reason_category"),
                "evidence_volume": row.get("evidence_volume", 0),
                "confidence": row.get("confidence"),
            }
            for row in clusters
        ],
        competitive=competitive[:20],
        competitive_summary=competitive_summary,
    )


def get_theme_clusters(_run_version: str | None = None) -> ThemeClusterResponse:
    payload = load_insights_payload()
    clusters = [
        ThemeClusterItem(
            cluster_key=row["cluster_key"],
            label=row["label"],
            reason_category=row.get("reason_category"),
            evidence_volume=row.get("evidence_volume", 0),
            confidence=row.get("confidence"),
            sources=row.get("sources") or [],
            chunk_ids=[parse_chunk_uuid(cid) for cid in row.get("chunk_ids") or []],
        )
        for row in payload.get("clusters", [])
    ]
    return ThemeClusterResponse(run_version=payload.get("run_version"), clusters=clusters)


def get_dashboard_filters(_run_version: str | None = None) -> DashboardFiltersResponse:
    payload = _payload()
    insights = payload.get("insights", [])
    chunks = load_corpus_chunks()

    def _distinct_from_insights(key: str) -> list[str]:
        return sorted({str(row[key]) for row in insights if row.get(key)})

    return DashboardFiltersResponse(
        run_version=payload.get("run_version"),
        segments=_distinct_from_insights("segment"),
        categories=_distinct_from_insights("category"),
        occasions=sorted({str(row["occasion"]) for row in chunks if row.get("occasion")}),
        price_bands=sorted({str(row["price_band"]) for row in chunks if row.get("price_band")}),
        reason_categories=_distinct_from_insights("reason_category"),
    )


def loosened_reason_attempts(
    *,
    run_version: str | None = None,
    segment: str | None = None,
    category: str | None = None,
    reason_category: str | None = None,
    min_confidence: float | None = None,
    sources: list[str] | None = None,
    platforms: list[str] | None = None,
    intent: str | None = None,
    price_band: str | None = None,
) -> list[tuple[dict, str | None]]:
    """Strict filters first, then drop intent / price / age so a real category slice can show."""
    category = normalize_filter_key(category)
    segment = normalize_filter_key(segment)
    reason_category = normalize_filter_key(reason_category)
    intent = normalize_filter_key(intent)
    price_band = normalize_filter_key(price_band)
    base = {
        "run_version": run_version,
        "category": category,
        "reason_category": reason_category,
        "min_confidence": min_confidence,
        "sources": sources,
        "platforms": platforms,
    }
    cat_label = (category or "this filter").replace("_", " ")
    attempts: list[tuple[dict, str | None]] = [
        ({**base, "segment": segment, "intent": intent, "price_band": price_band}, None),
    ]
    if intent:
        kind = "high-intent" if intent == "active_shortlist" else "low-intent"
        attempts.append(
            (
                {**base, "segment": segment, "intent": None, "price_band": price_band},
                f"No {kind} comments for {cat_label}. Showing all comments.",
            )
        )
    if price_band:
        attempts.append(
            (
                {**base, "segment": segment, "intent": None, "price_band": None},
                f"No comments for that price filter. Showing all {cat_label}.",
            )
        )
    if category and segment:
        age = segment.replace("age_", "").replace("_", "–")
        attempts.append(
            (
                {**base, "segment": None, "intent": intent, "price_band": price_band},
                f"No comments for Age {age} + {cat_label}. Showing all {cat_label}.",
            )
        )
        attempts.append(
            (
                {**base, "segment": None, "intent": None, "price_band": None},
                f"No comments for Age {age} + {cat_label}. Showing all {cat_label}.",
            )
        )
    return attempts


def rank_reasons_for_dashboard(
    *,
    run_version: str | None = None,
    segment: str | None = None,
    category: str | None = None,
    reason_category: str | None = None,
    min_confidence: float | None = None,
    sources: list[str] | None = None,
    platforms: list[str] | None = None,
    intent: str | None = None,
    price_band: str | None = None,
) -> tuple[list[ReasonRankItem], str | None]:
    """Rank reasons; loosen intent/price/age when the intersection is empty."""
    seen: set[tuple] = set()
    for kwargs, note in loosened_reason_attempts(
        run_version=run_version,
        segment=segment,
        category=category,
        reason_category=reason_category,
        min_confidence=min_confidence,
        sources=sources,
        platforms=platforms,
        intent=intent,
        price_band=price_band,
    ):
        key = (kwargs.get("segment"), kwargs.get("intent"), kwargs.get("price_band"), kwargs.get("category"))
        if key in seen:
            continue
        seen.add(key)
        items = get_filtered_reason_ranks(**kwargs)
        if items:
            return items, note
    return [], None


def get_filtered_reason_ranks(
    *,
    run_version: str | None = None,
    segment: str | None = None,
    category: str | None = None,
    reason_category: str | None = None,
    min_confidence: float | None = None,
    sources: list[str] | None = None,
    platforms: list[str] | None = None,
    intent: str | None = None,
    price_band: str | None = None,
) -> list[ReasonRankItem]:
    groups: dict[str, dict] = defaultdict(
        lambda: {
            "evidence_volume": 0,
            "confidences": [],
            "sources": set(),
            "active_shortlist_count": 0,
            "passive_bookmark_count": 0,
        }
    )
    for row in _insights(
        segment=segment,
        category=category,
        reason_category=reason_category,
        min_confidence=min_confidence,
        sources=sources,
        platforms=platforms,
        intent=intent,
        price_band=price_band,
    ):
        reason = row.get("reason_category")
        if not reason:
            continue
        bucket = groups[reason]
        try:
            bucket["evidence_volume"] += int(row.get("evidence_volume") or 0)
        except (TypeError, ValueError):
            bucket["evidence_volume"] += 0
        try:
            if row.get("confidence") is not None:
                bucket["confidences"].append(float(row["confidence"]))
        except (TypeError, ValueError):
            pass
        row_sources = row.get("sources") or []
        if isinstance(row_sources, str):
            row_sources = [row_sources]
        if isinstance(row_sources, list):
            bucket["sources"].update(str(item) for item in row_sources if item is not None)
        try:
            volume = int(row.get("evidence_volume") or 0)
        except (TypeError, ValueError):
            volume = 0
        if row.get("intent_type") == "active_shortlist":
            bucket["active_shortlist_count"] += volume
        else:
            bucket["passive_bookmark_count"] += volume

    items = [
        ReasonRankItem(
            reason_category=reason,
            evidence_volume=bucket["evidence_volume"],
            confidence=round(sum(bucket["confidences"]) / len(bucket["confidences"]), 3)
            if bucket["confidences"]
            else None,
            sources=sorted(bucket["sources"]),
            active_shortlist_count=bucket["active_shortlist_count"],
            passive_bookmark_count=bucket["passive_bookmark_count"],
        )
        for reason, bucket in groups.items()
    ]
    items.sort(key=lambda item: item.evidence_volume, reverse=True)
    return items


def research_respondent_counts() -> dict[str, int]:
    """Count unique Excel survey rows per age band.

    Interviews and open-text extras are not Excel respondents — including them
    made 18–24 + 25–35 sum to more people than the 43-person survey card.
    """
    seen: dict[str, set[str]] = {"age_18_24": set(), "age_25_35": set()}
    for chunk in load_corpus_chunks():
        source = chunk.get("source")
        if hasattr(source, "value"):
            source = source.value
        if source != "research":
            continue
        meta = chunk.get("metadata") or {}
        if meta.get("kind") == "interview" or meta.get("workbook") == "interview-docx":
            continue
        segment = chunk.get("segment") or meta.get("age_band")
        if segment not in seen:
            continue
        ref = str(chunk.get("source_ref") or "")
        if ":open:" in ref or "interview" in ref:
            continue
        row_key = ref
        if meta.get("workbook") is not None and meta.get("row_index") is not None:
            row_key = f"{meta.get('workbook')}:{meta.get('row_index')}"
        elif ":row:" not in ref:
            continue
        seen[segment].add(str(row_key))
    return {key: len(refs) for key, refs in seen.items()}


def age_band_origin_counts() -> dict[str, dict[str, int]]:
    """Unique aged items per band: survey rows vs Play Store vs other scrapes."""
    survey = research_respondent_counts()
    play_store: dict[str, set[str]] = {"age_18_24": set(), "age_25_35": set()}
    other: dict[str, set[str]] = {"age_18_24": set(), "age_25_35": set()}
    for chunk in load_corpus_chunks():
        source = chunk.get("source")
        if hasattr(source, "value"):
            source = source.value
        source = str(source or "")
        if source == "research":
            continue
        meta = chunk.get("metadata") or {}
        segment = chunk.get("segment") or meta.get("age_band")
        if segment not in play_store:
            continue
        ref = str(chunk.get("source_ref") or "")
        if not ref:
            continue
        if source == "play_store":
            play_store[segment].add(ref)
        else:
            other[segment].add(ref)
    return {
        band: {
            "survey": int(survey.get(band, 0)),
            "play_store": len(play_store[band]),
            "other_scrape": len(other[band]),
        }
        for band in ("age_18_24", "age_25_35")
    }


def get_segment_comparisons(
    *,
    run_version: str | None = None,
    group_by: str = "segment",
    segment: str | None = None,
    category: str | None = None,
    reason_category: str | None = None,
) -> ComparisonResponse:
    payload = _payload()
    dimension_key = "segment" if group_by == "segment" else "category"
    groups: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"evidence_volume": 0, "confidences": [], "active": 0, "passive": 0}
    )

    for row in _insights(segment=segment, category=category, reason_category=reason_category):
        dim = row.get(dimension_key)
        reason = row.get("reason_category")
        if not dim or not reason:
            continue
        key = (str(dim), str(reason))
        bucket = groups[key]
        volume = int(row.get("evidence_volume") or 0)
        bucket["evidence_volume"] += volume
        if row.get("confidence") is not None:
            bucket["confidences"].append(float(row["confidence"]))
        if row.get("intent_type") == "active_shortlist":
            bucket["active"] += volume
        else:
            bucket["passive"] += volume

    items = [
        ComparisonItem(
            dimension=dim,
            reason_category=reason,
            evidence_volume=bucket["evidence_volume"],
            confidence=round(sum(bucket["confidences"]) / len(bucket["confidences"]), 3)
            if bucket["confidences"]
            else None,
            active_shortlist_count=bucket["active"],
            passive_bookmark_count=bucket["passive"],
        )
        for (dim, reason), bucket in groups.items()
    ]
    items.sort(key=lambda item: item.evidence_volume, reverse=True)
    return ComparisonResponse(
        run_version=payload.get("run_version"),
        group_by=group_by,
        items=items,
        respondent_counts=research_respondent_counts() if group_by == "segment" else {},
        age_origin_counts=age_band_origin_counts() if group_by == "segment" else {},
    )


def get_friction_heatmap(
    *,
    run_version: str | None = None,
    row_key: str = "reason_category",
    column_key: str = "segment",
    segment: str | None = None,
    category: str | None = None,
) -> HeatmapResponse:
    payload = _payload()
    row_field = "reason_category" if row_key == "reason_category" else "category"
    col_field = "segment" if column_key == "segment" else "category"
    cells_map: dict[tuple[str, str], dict] = defaultdict(lambda: {"value": 0, "confidences": []})

    for row in _insights(segment=segment, category=category):
        row_label = row.get(row_field)
        col_label = row.get(col_field)
        if not row_label or not col_label:
            continue
        key = (str(row_label), str(col_label))
        cells_map[key]["value"] += int(row.get("evidence_volume") or 0)
        if row.get("confidence") is not None:
            cells_map[key]["confidences"].append(float(row["confidence"]))

    rows = sorted({key[0] for key in cells_map})
    columns = sorted({key[1] for key in cells_map})
    cells = [
        HeatmapCell(
            row=row,
            column=col,
            value=bucket["value"],
            confidence=round(sum(bucket["confidences"]) / len(bucket["confidences"]), 3)
            if bucket["confidences"]
            else None,
        )
        for (row, col), bucket in cells_map.items()
    ]
    return HeatmapResponse(
        run_version=payload.get("run_version"),
        row_key=row_key,
        column_key=column_key,
        rows=rows,
        columns=columns,
        cells=cells,
    )


def get_intent_breakdown(
    *,
    run_version: str | None = None,
    reason_category: str | None = None,
) -> IntentBreakdownResponse:
    payload = _payload()
    reasons = payload.get("reasons", [])
    if reason_category:
        reasons = [row for row in reasons if row.get("reason_category") == reason_category]

    by_reason = [
        IntentBreakdownItem(
            reason_category=row["reason_category"],
            active_shortlist_count=row.get("active_shortlist_count", 0),
            passive_bookmark_count=row.get("passive_bookmark_count", 0),
            evidence_volume=row.get("evidence_volume", 0),
            confidence=row.get("confidence"),
        )
        for row in reasons
    ]
    return IntentBreakdownResponse(
        run_version=payload.get("run_version"),
        total_active=sum(item.active_shortlist_count for item in by_reason),
        total_passive=sum(item.passive_bookmark_count for item in by_reason),
        by_reason=by_reason,
    )


def get_trends(*, run_version: str | None = None) -> TrendsResponse:
    payload = _payload()
    journey_groups: dict[str, dict] = defaultdict(lambda: {"volume": 0, "confidences": []})
    for row in payload.get("insights", []):
        stage = row.get("journey_stage")
        if not stage:
            continue
        bucket = journey_groups[str(stage)]
        bucket["volume"] += int(row.get("evidence_volume") or 0)
        if row.get("confidence") is not None:
            bucket["confidences"].append(float(row["confidence"]))

    journey_stages = [
        JourneyTrendItem(
            journey_stage=stage,
            evidence_volume=bucket["volume"],
            confidence=round(sum(bucket["confidences"]) / len(bucket["confidences"]), 3)
            if bucket["confidences"]
            else None,
        )
        for stage, bucket in journey_groups.items()
    ]
    journey_stages.sort(key=lambda item: item.evidence_volume, reverse=True)

    emerging = [
        ThemeClusterItem(
            cluster_key=row["cluster_key"],
            label=row["label"],
            reason_category=row.get("reason_category"),
            evidence_volume=row.get("evidence_volume", 0),
            confidence=row.get("confidence"),
            sources=row.get("sources") or [],
            chunk_ids=[parse_chunk_uuid(cid) for cid in row.get("chunk_ids") or []],
        )
        for row in payload.get("clusters", [])
    ]
    return TrendsResponse(
        run_version=payload.get("run_version"),
        journey_stages=journey_stages,
        emerging_themes=emerging,
    )


def get_evidence_summary(
    *,
    run_version: str | None = None,
    reason_category: str,
    segment: str | None = None,
    category: str | None = None,
    limit: int = 10,
) -> EvidenceSummaryResponse:
    payload = _payload()
    lookup = chunk_lookup()
    matching = _insights(segment=segment, category=category, reason_category=reason_category)

    chunk_ids: list[uuid.UUID] = []
    sources: set[str] = set()
    total_volume = 0
    confidences: list[float] = []

    for insight in matching:
        total_volume += int(insight.get("evidence_volume") or 0)
        if insight.get("confidence") is not None:
            confidences.append(float(insight["confidence"]))
        sources.update(insight.get("sources") or [])
        for raw_id in insight.get("evidence_chunk_ids") or []:
            chunk_id = parse_chunk_uuid(raw_id)
            if chunk_id not in chunk_ids:
                chunk_ids.append(chunk_id)
            if len(chunk_ids) >= limit:
                break
        if len(chunk_ids) >= limit:
            break

    excerpts: list[EvidenceExcerpt] = []
    for chunk_id in chunk_ids:
        chunk = lookup.get(chunk_id)
        if chunk is None:
            continue
        excerpts.append(
            EvidenceExcerpt(
                chunk_id=chunk_id,
                text=chunk["text"],
                source=chunk["source"],
                source_ref=chunk.get("source_ref"),
                segment=chunk.get("segment"),
                category=chunk.get("category"),
                confidence=chunk.get("quality_score"),
                quality_score=chunk.get("quality_score"),
            )
        )

    confidence = round(sum(confidences) / len(confidences), 3) if confidences else None
    return EvidenceSummaryResponse(
        run_version=payload.get("run_version"),
        reason_category=reason_category,
        evidence_volume=total_volume,
        confidence=confidence,
        sources=sorted(sources),
        excerpts=excerpts,
    )


WHY_NOT_PURCHASE_NARRATIVE = [
    (
        "Price / sale waiting - users shortlist now and delay until discounts "
        "(strong on Myntra and Ajio)."
    ),
    (
        "Fit & sizing uncertainty - apparel wishlists stall when size charts "
        "feel inconsistent (Myntra-heavy)."
    ),
    "Passive bookmarking - inspiration saves never enter a 30-day purchase window.",
    (
        "External / competitive comparison - checking Nykaa, Ajio, or other apps "
        "before committing."
    ),
    "Trust & authenticity - especially beauty on Nykaa; review doubt blocks checkout.",
    "Timing / occasion - saved for weddings, festivals, or later seasons.",
    "Logistics friction - delivery, returns, and stock issues reduce urgency.",
    (
        "Competitive platform preference - users finish the journey on the app "
        "they trust for that category."
    ),
]


def get_competitive_analysis() -> CompetitiveAnalysisResponse:
    from analytics.competitive import (
        build_why_not_purchase_narrative,
        filter_ui_competitive_payloads,
        summarize_competitive,
    )
    from analytics.schemas import CompetitiveMetricItem, CompetitiveTopItem

    payload = _payload()
    competitive = filter_ui_competitive_payloads(payload.get("competitive") or [])
    summary = summarize_competitive(competitive)

    def _items(rows: list[dict]) -> list[CompetitiveMetricItem]:
        return [
            CompetitiveMetricItem(
                platform=row["platform"],
                metric_type=row["metric_type"],
                label=row["label"],
                count=int(row.get("count") or 0),
                share=row.get("share"),
                evidence_volume=int(row.get("evidence_volume") or row.get("count") or 0),
                confidence=row.get("confidence"),
                shared_vs_unique=row.get("shared_vs_unique"),
                sources=row.get("sources") or [],
            )
            for row in rows
        ]

    def _tops(mapping: dict) -> dict[str, CompetitiveTopItem]:
        out: dict[str, CompetitiveTopItem] = {}
        for platform, row in (mapping or {}).items():
            out[platform] = CompetitiveTopItem(
                label=row["label"],
                count=int(row.get("count") or 0),
                share=row.get("share"),
                confidence=row.get("confidence"),
            )
        return out

    why = summary.get("why_not_purchase") or build_why_not_purchase_narrative(summary)
    if not why:
        why = WHY_NOT_PURCHASE_NARRATIVE

    return CompetitiveAnalysisResponse(
        run_version=payload.get("run_version"),
        platforms=summary.get("platforms") or [],
        motives=_items(
            summary.get("motives") or [r for r in competitive if r.get("metric_type") == "motive"]
        ),
        barriers=_items(
            summary.get("barriers") or [r for r in competitive if r.get("metric_type") == "barrier"]
        ),
        shared_motives=summary.get("shared_motives") or [],
        unique_motives_by_platform=summary.get("unique_motives_by_platform") or {},
        top_motive_by_platform=_tops(summary.get("top_motive_by_platform") or {}),
        top_barrier_by_platform=_tops(summary.get("top_barrier_by_platform") or {}),
        why_not_purchase=why,
        limitations=(
            "Competitive comparisons are directional public-evidence inferences from platform "
            "mentions (Myntra / Nykaa / Ajio). They are not competitor private analytics "
            "or ground-truth conversion rates."
        ),
    )


# Matches web DEFAULT_SIDEBAR so the static snapshot paints the same first view.
_BOOTSTRAP_SOURCES = ["play_store", "youtube", "reddit", "product_review", "social"]


def get_dashboard_bootstrap() -> dict:
    """One payload for the first dashboard paint (filters + reasons + extras)."""
    from analytics.schemas import ReasonRankResponse, SurveyHabitsResponse
    from api.json_feedback import list_feedback
    from api.json_store import load_corpus_scrape_stats
    from api.survey_habits import get_survey_purchase_habits

    payload = _payload()
    reasons, note = rank_reasons_for_dashboard(
        min_confidence=0.5,
        sources=_BOOTSTRAP_SOURCES,
    )
    conversion: dict | None = None
    try:
        from internal.offline import get_offline_store, run_offline_internal_pipeline

        store = get_offline_store()
        if store.conversion is None:
            run_offline_internal_pipeline()
            store = get_offline_store()
        snap = store.conversion
        if snap is not None:
            conversion = {
                "run_version": snap.run_version,
                "window_days": snap.window_days,
                "wishlist_users": snap.wishlist_users,
                "converted_users": snap.converted_users,
                "conversion_rate": snap.conversion_rate,
                "non_conversion_rate": round(1.0 - snap.conversion_rate, 4),
                "cohort_start": snap.cohort_start.isoformat() if snap.cohort_start else None,
                "cohort_end": snap.cohort_end.isoformat() if snap.cohort_end else None,
            }
    except Exception:  # noqa: BLE001
        conversion = None

    habits = get_survey_purchase_habits()
    stats = load_corpus_scrape_stats()
    return {
        "filters": get_dashboard_filters().model_dump(mode="json"),
        "reasons": ReasonRankResponse(
            run_version=payload.get("run_version"),
            reasons=reasons,
            scope_note=note,
        ).model_dump(mode="json"),
        "comparisons": get_segment_comparisons(group_by="segment").model_dump(mode="json"),
        "competitive": get_competitive_analysis().model_dump(mode="json"),
        "corpus_stats": stats,
        "survey_habits": SurveyHabitsResponse.model_validate(habits).model_dump(mode="json"),
        "conversion": conversion,
        "feedback": list_feedback().model_dump(mode="json"),
    }
