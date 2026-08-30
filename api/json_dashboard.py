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


def _insights(
    *,
    segment: str | None = None,
    category: str | None = None,
    reason_category: str | None = None,
) -> list[dict]:
    rows = _payload().get("insights", [])
    filtered: list[dict] = []
    for row in rows:
        if segment and row.get("segment") != segment:
            continue
        if category and row.get("category") != category:
            continue
        if reason_category and row.get("reason_category") != reason_category:
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


def rank_reasons_for_dashboard(
    *,
    run_version: str | None = None,
    segment: str | None = None,
    category: str | None = None,
    reason_category: str | None = None,
) -> tuple[list[ReasonRankItem], str | None]:
    """Rank reasons; if age+category is empty, fall back to category-only excerpts."""
    items = get_filtered_reason_ranks(
        run_version=run_version,
        segment=segment,
        category=category,
        reason_category=reason_category,
    )
    if items:
        return items, None
    if category and segment:
        loosened = get_filtered_reason_ranks(
            run_version=run_version,
            category=category,
            reason_category=reason_category,
        )
        if loosened:
            age = segment.replace("age_", "").replace("_", "–")
            label = category.replace("_", " ")
            return loosened, (
                f"No excerpts match Age {age} + {label} — showing all {label} excerpts"
            )
    return [], None


def get_filtered_reason_ranks(
    *,
    run_version: str | None = None,
    segment: str | None = None,
    category: str | None = None,
    reason_category: str | None = None,
) -> list[ReasonRankItem]:
    payload = _payload()
    if segment or category or reason_category:
        groups: dict[str, dict] = defaultdict(
            lambda: {
                "evidence_volume": 0,
                "confidences": [],
                "sources": set(),
                "active_shortlist_count": 0,
                "passive_bookmark_count": 0,
            }
        )
        for row in _insights(segment=segment, category=category, reason_category=reason_category):
            reason = row["reason_category"]
            bucket = groups[reason]
            bucket["evidence_volume"] += int(row.get("evidence_volume") or 0)
            if row.get("confidence") is not None:
                bucket["confidences"].append(float(row["confidence"]))
            bucket["sources"].update(row.get("sources") or [])
            if row.get("intent_type") == "active_shortlist":
                bucket["active_shortlist_count"] += int(row.get("evidence_volume") or 0)
            else:
                bucket["passive_bookmark_count"] += int(row.get("evidence_volume") or 0)

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

    return [
        ReasonRankItem(
            reason_category=row["reason_category"],
            evidence_volume=row["evidence_volume"],
            confidence=row.get("confidence"),
            sources=row.get("sources") or [],
            active_shortlist_count=row.get("active_shortlist_count", 0),
            passive_bookmark_count=row.get("passive_bookmark_count", 0),
        )
        for row in payload.get("reasons", [])
    ]


def research_respondent_counts() -> dict[str, int]:
    """Count unique survey *rows* per age band (not chunks or open-text extras)."""
    stored = _payload().get("respondent_counts")
    if isinstance(stored, dict):
        baked = {
            key: int(stored[key])
            for key in ("age_18_24", "age_25_35")
            if stored.get(key) not in (None, "")
        }
        if any(baked.values()):
            return {key: baked.get(key, 0) for key in ("age_18_24", "age_25_35")}

    seen: dict[str, set[str]] = {"age_18_24": set(), "age_25_35": set()}
    for chunk in load_corpus_chunks():
        source = chunk.get("source")
        if hasattr(source, "value"):
            source = source.value
        if source != "research":
            continue
        meta = chunk.get("metadata") or {}
        segment = chunk.get("segment") or meta.get("age_band")
        if segment not in seen:
            continue
        ref = str(chunk.get("source_ref") or "")
        if ":open:" in ref:
            continue
        row_key = ref
        if meta.get("workbook") is not None and meta.get("row_index") is not None:
            row_key = f"{meta.get('workbook')}:{meta.get('row_index')}"
        elif ":row:" not in ref:
            continue
        seen[segment].add(str(row_key))
    return {key: len(refs) for key, refs in seen.items()}


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
        "External / competitive comparison - checking Nykaa, Ajio, Amazon, or "
        "Flipkart before committing."
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
    from analytics.competitive import build_why_not_purchase_narrative, summarize_competitive
    from analytics.schemas import CompetitiveMetricItem, CompetitiveTopItem

    payload = _payload()
    competitive = payload.get("competitive") or []
    summary = payload.get("competitive_summary") or summarize_competitive(competitive)
    if competitive and not summary.get("platforms"):
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
            "mentions (Myntra / Nykaa / Ajio / other). They are not competitor private analytics "
            "or ground-truth conversion rates."
        ),
    )
