"""Insights API routes (Phase 3 semantic analytics outputs)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analytics.pipeline import run_semantic_analytics_db
from analytics.schemas import (
    AnalyticsRunRequest,
    AnalyticsRunResult,
    ComparisonResponse,
    CompetitiveAnalysisResponse,
    DashboardFiltersResponse,
    EvidenceSummaryResponse,
    HeatmapResponse,
    InsightListResponse,
    InsightRecord,
    IntentBreakdownResponse,
    ReasonRankItem,
    ReasonRankResponse,
    ThemeClusterItem,
    ThemeClusterResponse,
    TrendsResponse,
)
from api import backend
from api import json_dashboard as json_dash
from api.dashboard_queries import (
    get_dashboard_filters as db_get_dashboard_filters,
)
from api.dashboard_queries import (
    get_evidence_summary as db_get_evidence_summary,
)
from api.dashboard_queries import (
    get_filtered_reason_ranks as db_get_filtered_reason_ranks,
)
from api.dashboard_queries import (
    get_friction_heatmap as db_get_friction_heatmap,
)
from api.dashboard_queries import (
    get_intent_breakdown as db_get_intent_breakdown,
)
from api.dashboard_queries import (
    get_segment_comparisons as db_get_segment_comparisons,
)
from api.dashboard_queries import (
    get_trends as db_get_trends,
)
from api.dashboard_queries import (
    resolve_insight_run_version,
)
from common.db import get_session
from common.models import Insight, ReasonAggregate, ThemeCluster

router = APIRouter(tags=["insights"])


@router.post("/analytics/run", response_model=AnalyticsRunResult)
def run_analytics(
    body: AnalyticsRunRequest,
    session: Session = Depends(get_session),
) -> AnalyticsRunResult:
    """Run the semantic analytics pipeline against stored chunks."""
    result = run_semantic_analytics_db(
        session,
        run_version=body.run_version,
        replace_existing=body.replace_existing,
    )
    return AnalyticsRunResult(
        run_version=result.run_version,
        insights_created=result.insights_created,
        reason_aggregates=result.reason_aggregates,
        theme_clusters=result.theme_clusters,
        chunks_analyzed=result.chunks_analyzed,
    )


@router.get("/insights", response_model=InsightListResponse)
def list_insights(
    run_version: str | None = None,
    reason_category: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> InsightListResponse:
    """List structured insight records with optional filters."""
    count_stmt = select(func.count()).select_from(Insight)
    if run_version:
        count_stmt = count_stmt.where(Insight.run_version == run_version)
    if reason_category:
        count_stmt = count_stmt.where(Insight.reason_category == reason_category)
    total = session.scalar(count_stmt) or 0

    list_stmt = select(Insight)
    if run_version:
        list_stmt = list_stmt.where(Insight.run_version == run_version)
    if reason_category:
        list_stmt = list_stmt.where(Insight.reason_category == reason_category)

    rows = session.execute(
        list_stmt.order_by(Insight.confidence.desc().nullslast(), Insight.evidence_volume.desc())
        .offset(offset)
        .limit(limit)
    ).scalars()

    insights = [
        InsightRecord(
            id=row.id,
            reason_category=row.reason_category,
            intent_type=row.intent_type,
            journey_stage=row.journey_stage,
            segment=row.segment,
            category=row.category,
            evidence_volume=row.evidence_volume,
            confidence=row.confidence,
            sources=row.sources or [],
            evidence_chunk_ids=row.evidence_chunk_ids or [],
            run_version=row.run_version,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return InsightListResponse(total=total, insights=insights)


@router.get("/insights/reasons", response_model=ReasonRankResponse)
def ranked_reasons(
    run_version: str | None = None,
    segment: str | None = None,
    category: str | None = None,
    reason_category: str | None = None,
    session: Session = Depends(get_session),
) -> ReasonRankResponse:
    """Return ranked non-conversion reason categories for the dashboard."""

    def _from_json() -> ReasonRankResponse:
        return ReasonRankResponse(
            run_version=json_dash._payload().get("run_version"),
            reasons=json_dash.get_filtered_reason_ranks(
                run_version=run_version,
                segment=segment,
                category=category,
                reason_category=reason_category,
            ),
        )

    if backend.use_json_backend():
        return _from_json()

    return backend.call_with_json_fallback(
        session,
        db_call=lambda s: _ranked_reasons_db(
            s,
            run_version=run_version,
            segment=segment,
            category=category,
            reason_category=reason_category,
        ),
        json_call=_from_json,
        label="ranked_reasons",
    )


def _ranked_reasons_db(
    session: Session,
    *,
    run_version: str | None,
    segment: str | None,
    category: str | None,
    reason_category: str | None,
) -> ReasonRankResponse:
    if segment or category or reason_category:
        resolved = resolve_insight_run_version(session, run_version)
        return ReasonRankResponse(
            run_version=resolved,
            reasons=db_get_filtered_reason_ranks(
                session,
                run_version=resolved,
                segment=segment,
                category=category,
                reason_category=reason_category,
            ),
        )

    stmt = select(ReasonAggregate).order_by(ReasonAggregate.evidence_volume.desc())
    if run_version:
        stmt = stmt.where(ReasonAggregate.run_version == run_version)
    else:
        latest = session.scalar(
            select(ReasonAggregate.run_version)
            .order_by(ReasonAggregate.computed_at.desc())
            .limit(1)
        )
        run_version = latest
        if latest:
            stmt = stmt.where(ReasonAggregate.run_version == latest)

    rows = session.execute(stmt).scalars().all()
    return ReasonRankResponse(
        run_version=run_version,
        reasons=[
            ReasonRankItem(
                reason_category=row.reason_category,
                evidence_volume=row.evidence_volume,
                confidence=row.confidence,
                sources=row.sources or [],
                active_shortlist_count=row.active_shortlist_count,
                passive_bookmark_count=row.passive_bookmark_count,
            )
            for row in rows
        ],
    )


@router.get("/insights/clusters", response_model=ThemeClusterResponse)
def theme_clusters(
    run_version: str | None = None,
    session: Session = Depends(get_session),
) -> ThemeClusterResponse:
    """Return emerging theme clusters grouped by semantic similarity."""
    return backend.call_with_json_fallback(
        session,
        db_call=lambda s: _theme_clusters_db(s, run_version),
        json_call=lambda: json_dash.get_theme_clusters(run_version),
        label="theme_clusters",
    )


def _theme_clusters_db(session: Session, run_version: str | None) -> ThemeClusterResponse:
    stmt = select(ThemeCluster).order_by(ThemeCluster.evidence_volume.desc())
    if run_version:
        stmt = stmt.where(ThemeCluster.run_version == run_version)
    else:
        latest = session.scalar(
            select(ThemeCluster.run_version).order_by(ThemeCluster.computed_at.desc()).limit(1)
        )
        run_version = latest
        if latest:
            stmt = stmt.where(ThemeCluster.run_version == latest)

    rows = session.execute(stmt).scalars().all()
    return ThemeClusterResponse(
        run_version=run_version,
        clusters=[
            ThemeClusterItem(
                cluster_key=row.cluster_key,
                label=row.label,
                reason_category=row.reason_category,
                evidence_volume=row.evidence_volume,
                confidence=row.confidence,
                sources=row.sources or [],
                chunk_ids=row.chunk_ids or [],
            )
            for row in rows
        ],
    )


@router.get("/insights/filters", response_model=DashboardFiltersResponse)
def dashboard_filters(
    run_version: str | None = None,
    session: Session = Depends(get_session),
) -> DashboardFiltersResponse:
    """Return available dashboard filter values."""
    return backend.call_with_json_fallback(
        session,
        db_call=lambda s: db_get_dashboard_filters(s, run_version),
        json_call=lambda: json_dash.get_dashboard_filters(run_version),
        label="dashboard_filters",
    )


@router.get("/insights/comparisons", response_model=ComparisonResponse)
def segment_comparisons(
    run_version: str | None = None,
    group_by: str = Query(default="segment", pattern="^(segment|category)$"),
    segment: str | None = None,
    category: str | None = None,
    reason_category: str | None = None,
    session: Session = Depends(get_session),
) -> ComparisonResponse:
    """Compare non-conversion reasons across segments or categories."""
    return backend.call_with_json_fallback(
        session,
        db_call=lambda s: db_get_segment_comparisons(
            s,
            run_version=run_version,
            group_by=group_by,
            segment=segment,
            category=category,
            reason_category=reason_category,
        ),
        json_call=lambda: json_dash.get_segment_comparisons(
            run_version=run_version,
            group_by=group_by,
            segment=segment,
            category=category,
            reason_category=reason_category,
        ),
        label="segment_comparisons",
    )


@router.get("/insights/heatmap", response_model=HeatmapResponse)
def friction_heatmap(
    run_version: str | None = None,
    row_key: str = Query(default="reason_category", pattern="^(reason_category|category)$"),
    column_key: str = Query(default="segment", pattern="^(segment|category)$"),
    segment: str | None = None,
    category: str | None = None,
    session: Session = Depends(get_session),
) -> HeatmapResponse:
    """Return uncertainty/friction heatmap cells for visualization."""
    return backend.call_with_json_fallback(
        session,
        db_call=lambda s: db_get_friction_heatmap(
            s,
            run_version=run_version,
            row_key=row_key,
            column_key=column_key,
            segment=segment,
            category=category,
        ),
        json_call=lambda: json_dash.get_friction_heatmap(
            run_version=run_version,
            row_key=row_key,
            column_key=column_key,
            segment=segment,
            category=category,
        ),
        label="friction_heatmap",
    )


@router.get("/insights/intent", response_model=IntentBreakdownResponse)
def intent_breakdown(
    run_version: str | None = None,
    reason_category: str | None = None,
    session: Session = Depends(get_session),
) -> IntentBreakdownResponse:
    """Return active shortlist vs passive bookmarking breakdown."""
    return backend.call_with_json_fallback(
        session,
        db_call=lambda s: db_get_intent_breakdown(
            s,
            run_version=run_version,
            reason_category=reason_category,
        ),
        json_call=lambda: json_dash.get_intent_breakdown(
            run_version=run_version,
            reason_category=reason_category,
        ),
        label="intent_breakdown",
    )


@router.get("/insights/trends", response_model=TrendsResponse)
def insight_trends(
    run_version: str | None = None,
    session: Session = Depends(get_session),
) -> TrendsResponse:
    """Return journey-stage distribution and emerging theme clusters."""
    return backend.call_with_json_fallback(
        session,
        db_call=lambda s: db_get_trends(s, run_version=run_version),
        json_call=lambda: json_dash.get_trends(run_version=run_version),
        label="insight_trends",
    )


@router.get("/insights/evidence", response_model=EvidenceSummaryResponse)
def evidence_summary(
    reason_category: str = Query(min_length=3),
    run_version: str | None = None,
    segment: str | None = None,
    category: str | None = None,
    limit: int = Query(default=10, ge=1, le=30),
    session: Session = Depends(get_session),
) -> EvidenceSummaryResponse:
    """Return evidence excerpts for drill-down on a reason category."""
    return backend.call_with_json_fallback(
        session,
        db_call=lambda s: db_get_evidence_summary(
            s,
            run_version=run_version,
            reason_category=reason_category,
            segment=segment,
            category=category,
            limit=limit,
        ),
        json_call=lambda: json_dash.get_evidence_summary(
            run_version=run_version,
            reason_category=reason_category,
            segment=segment,
            category=category,
            limit=limit,
        ),
        label="evidence_summary",
    )


@router.get("/insights/competitive", response_model=CompetitiveAnalysisResponse)
def competitive_analysis(
    run_version: str | None = None,
    session: Session = Depends(get_session),
) -> CompetitiveAnalysisResponse:
    """Compare wishlist motives and non-purchase barriers across Myntra / Nykaa / Ajio."""

    def _from_json() -> CompetitiveAnalysisResponse:
        return json_dash.get_competitive_analysis()

    if backend.use_json_backend():
        return _from_json()

    return backend.call_with_json_fallback(
        session,
        db_call=lambda s: _competitive_from_db(s, run_version=run_version),
        json_call=_from_json,
        label="competitive_analysis",
    )


def _competitive_from_db(
    session: Session,
    *,
    run_version: str | None,
) -> CompetitiveAnalysisResponse:
    from analytics.competitive import summarize_competitive
    from analytics.schemas import CompetitiveMetricItem, CompetitiveTopItem
    from api.json_dashboard import WHY_NOT_PURCHASE_NARRATIVE
    from common.models import CompetitiveAggregate

    stmt = select(CompetitiveAggregate)
    if run_version:
        stmt = stmt.where(CompetitiveAggregate.run_version == run_version)
    else:
        latest = session.scalar(
            select(CompetitiveAggregate.run_version)
            .order_by(CompetitiveAggregate.computed_at.desc())
            .limit(1)
        )
        run_version = latest
        if latest:
            stmt = stmt.where(CompetitiveAggregate.run_version == latest)

    rows = session.execute(stmt).scalars().all()
    competitive = [
        {
            "platform": row.platform,
            "metric_type": row.metric_type,
            "label": row.label,
            "count": row.count,
            "share": row.share,
            "evidence_volume": row.evidence_volume,
            "confidence": row.confidence,
            "shared_vs_unique": row.shared_vs_unique,
            "sources": row.sources or [],
            "run_version": row.run_version,
        }
        for row in rows
    ]
    summary = summarize_competitive(competitive)

    def _items(metric_rows: list[dict]) -> list[CompetitiveMetricItem]:
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
            for row in metric_rows
        ]

    def _tops(mapping: dict) -> dict[str, CompetitiveTopItem]:
        return {
            platform: CompetitiveTopItem(
                label=row["label"],
                count=int(row.get("count") or 0),
                share=row.get("share"),
                confidence=row.get("confidence"),
            )
            for platform, row in (mapping or {}).items()
        }

    return CompetitiveAnalysisResponse(
        run_version=run_version,
        platforms=summary.get("platforms") or [],
        motives=_items(summary.get("motives") or []),
        barriers=_items(summary.get("barriers") or []),
        shared_motives=summary.get("shared_motives") or [],
        unique_motives_by_platform=summary.get("unique_motives_by_platform") or {},
        top_motive_by_platform=_tops(summary.get("top_motive_by_platform") or {}),
        top_barrier_by_platform=_tops(summary.get("top_barrier_by_platform") or {}),
        why_not_purchase=summary.get("why_not_purchase") or WHY_NOT_PURCHASE_NARRATIVE,
        limitations=(
            "Competitive comparisons are directional public-evidence inferences from platform "
            "mentions (Myntra / Nykaa / Ajio / other). They are not competitor private analytics "
            "or ground-truth conversion rates."
        ),
    )
