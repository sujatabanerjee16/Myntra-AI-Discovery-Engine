"""Dashboard query helpers for the Insights API (Phase 5)."""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from analytics.confidence import compute_confidence
from analytics.schemas import (
    ComparisonItem,
    ComparisonResponse,
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
    TrendsResponse,
)
from common.models import Chunk, Document, Insight, ReasonAggregate, ThemeCluster


def resolve_insight_run_version(session: Session, run_version: str | None) -> str | None:
    if run_version:
        return run_version
    return session.scalar(
        select(Insight.run_version).order_by(Insight.created_at.desc()).limit(1)
    ) or session.scalar(
        select(ReasonAggregate.run_version).order_by(ReasonAggregate.computed_at.desc()).limit(1)
    )


def _insight_filters(
    stmt,
    *,
    run_version: str | None,
    segment: str | None = None,
    category: str | None = None,
    occasion: str | None = None,
    price_band: str | None = None,
    reason_category: str | None = None,
):
    if run_version:
        stmt = stmt.where(Insight.run_version == run_version)
    if segment:
        stmt = stmt.where(Insight.segment == segment)
    if category:
        stmt = stmt.where(Insight.category == category)
    if reason_category:
        stmt = stmt.where(Insight.reason_category == reason_category)
    return stmt


def get_filtered_reason_ranks(
    session: Session,
    *,
    run_version: str | None,
    segment: str | None = None,
    category: str | None = None,
    reason_category: str | None = None,
) -> list[ReasonRankItem]:
    """Aggregate reason ranks from insights when dashboard filters are applied."""
    run_version = resolve_insight_run_version(session, run_version)
    stmt = select(
        Insight.reason_category,
        func.sum(Insight.evidence_volume),
        func.avg(Insight.confidence),
    ).group_by(Insight.reason_category)
    stmt = _insight_filters(
        stmt,
        run_version=run_version,
        segment=segment,
        category=category,
        reason_category=reason_category,
    )

    rows = session.execute(stmt).all()
    intent_stmt = select(
        Insight.reason_category,
        Insight.intent_type,
        func.sum(Insight.evidence_volume),
    ).group_by(Insight.reason_category, Insight.intent_type)
    intent_stmt = _insight_filters(
        intent_stmt,
        run_version=run_version,
        segment=segment,
        category=category,
        reason_category=reason_category,
    )
    intent_rows = session.execute(intent_stmt).all()

    intent_map: dict[str, dict[str, int]] = defaultdict(
        lambda: {"active_shortlist": 0, "passive_bookmark": 0}
    )
    source_map: dict[str, set[str]] = defaultdict(set)

    source_stmt = select(Insight.reason_category, Insight.sources)
    source_stmt = _insight_filters(
        source_stmt,
        run_version=run_version,
        segment=segment,
        category=category,
        reason_category=reason_category,
    )
    for reason, sources in session.execute(source_stmt).all():
        if reason and sources:
            source_map[str(reason)].update(sources)

    for reason, intent_type, volume in intent_rows:
        if reason is None or intent_type is None:
            continue
        intent_map[str(reason)][intent_type.value] += int(volume or 0)

    items: list[ReasonRankItem] = []
    for reason, volume, confidence in rows:
        if reason is None:
            continue
        key = str(reason)
        counts = intent_map.get(key, {})
        items.append(
            ReasonRankItem(
                reason_category=key,
                evidence_volume=int(volume or 0),
                confidence=round(float(confidence), 3) if confidence is not None else None,
                sources=sorted(source_map.get(key, set())),
                active_shortlist_count=counts.get("active_shortlist", 0),
                passive_bookmark_count=counts.get("passive_bookmark", 0),
            )
        )

    items.sort(key=lambda item: item.evidence_volume, reverse=True)
    return items


def get_dashboard_filters(session: Session, run_version: str | None) -> DashboardFiltersResponse:
    run_version = resolve_insight_run_version(session, run_version)

    def _distinct(column):
        stmt = select(column).select_from(Insight).where(column.isnot(None)).distinct()
        if run_version:
            stmt = stmt.where(Insight.run_version == run_version)
        return sorted(str(value) for value in session.scalars(stmt).all() if value)

    occasions = session.scalars(
        select(Chunk.occasion)
        .where(Chunk.occasion.isnot(None))
        .distinct()
        .order_by(Chunk.occasion)
    ).all()
    price_bands = session.scalars(
        select(Chunk.price_band)
        .where(Chunk.price_band.isnot(None))
        .distinct()
        .order_by(Chunk.price_band)
    ).all()

    return DashboardFiltersResponse(
        run_version=run_version,
        segments=_distinct(Insight.segment),
        categories=_distinct(Insight.category),
        occasions=sorted(str(value) for value in occasions if value),
        price_bands=sorted(str(value) for value in price_bands if value),
        reason_categories=_distinct(Insight.reason_category),
    )


def get_segment_comparisons(
    session: Session,
    *,
    run_version: str | None,
    group_by: str = "segment",
    segment: str | None = None,
    category: str | None = None,
    reason_category: str | None = None,
) -> ComparisonResponse:
    run_version = resolve_insight_run_version(session, run_version)
    dimension_col = Insight.segment if group_by == "segment" else Insight.category

    stmt = select(
        dimension_col,
        Insight.reason_category,
        func.sum(Insight.evidence_volume),
        func.avg(Insight.confidence),
    ).group_by(dimension_col, Insight.reason_category)

    stmt = _insight_filters(
        stmt,
        run_version=run_version,
        segment=segment,
        category=category,
        reason_category=reason_category,
    )
    stmt = stmt.where(dimension_col.isnot(None))

    rows = session.execute(stmt).all()
    intent_stmt = select(
        dimension_col,
        Insight.reason_category,
        Insight.intent_type,
        func.sum(Insight.evidence_volume),
    ).group_by(dimension_col, Insight.reason_category, Insight.intent_type)
    intent_stmt = _insight_filters(
        intent_stmt,
        run_version=run_version,
        segment=segment,
        category=category,
        reason_category=reason_category,
    ).where(dimension_col.isnot(None))
    intent_rows = session.execute(intent_stmt).all()

    intent_map: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"active_shortlist": 0, "passive_bookmark": 0}
    )
    for dim, reason, intent_type, volume in intent_rows:
        if dim is None or reason is None:
            continue
        key = (str(dim), str(reason))
        if intent_type is not None:
            intent_map[key][intent_type.value] += int(volume or 0)

    items: list[ComparisonItem] = []
    for dim, reason, volume, confidence in rows:
        if dim is None or reason is None:
            continue
        key = (str(dim), str(reason))
        counts = intent_map.get(key, {})
        items.append(
            ComparisonItem(
                dimension=str(dim),
                reason_category=str(reason),
                evidence_volume=int(volume or 0),
                confidence=round(float(confidence), 3) if confidence is not None else None,
                active_shortlist_count=counts.get("active_shortlist", 0),
                passive_bookmark_count=counts.get("passive_bookmark", 0),
            )
        )

    items.sort(key=lambda item: item.evidence_volume, reverse=True)
    return ComparisonResponse(run_version=run_version, group_by=group_by, items=items)


def get_friction_heatmap(
    session: Session,
    *,
    run_version: str | None,
    row_key: str = "reason_category",
    column_key: str = "segment",
    segment: str | None = None,
    category: str | None = None,
) -> HeatmapResponse:
    run_version = resolve_insight_run_version(session, run_version)
    row_col = Insight.reason_category if row_key == "reason_category" else Insight.category
    col_col = Insight.segment if column_key == "segment" else Insight.category

    stmt = select(
        row_col,
        col_col,
        func.sum(Insight.evidence_volume),
        func.avg(Insight.confidence),
    ).group_by(row_col, col_col)
    stmt = _insight_filters(
        stmt,
        run_version=run_version,
        segment=segment,
        category=category,
    ).where(row_col.isnot(None), col_col.isnot(None))

    rows = session.execute(stmt).all()
    cells: list[HeatmapCell] = []
    row_labels: set[str] = set()
    col_labels: set[str] = set()

    for row, col, volume, confidence in rows:
        if row is None or col is None:
            continue
        row_label = str(row)
        col_label = str(col)
        row_labels.add(row_label)
        col_labels.add(col_label)
        cells.append(
            HeatmapCell(
                row=row_label,
                column=col_label,
                value=int(volume or 0),
                confidence=round(float(confidence), 3) if confidence is not None else None,
            )
        )

    return HeatmapResponse(
        run_version=run_version,
        row_key=row_key,
        column_key=column_key,
        rows=sorted(row_labels),
        columns=sorted(col_labels),
        cells=cells,
    )


def get_intent_breakdown(
    session: Session,
    *,
    run_version: str | None,
    reason_category: str | None = None,
) -> IntentBreakdownResponse:
    run_version = resolve_insight_run_version(session, run_version)
    stmt = select(ReasonAggregate).order_by(ReasonAggregate.evidence_volume.desc())
    if run_version:
        stmt = stmt.where(ReasonAggregate.run_version == run_version)
    if reason_category:
        stmt = stmt.where(ReasonAggregate.reason_category == reason_category)

    rows = session.execute(stmt).scalars().all()
    by_reason: list[IntentBreakdownItem] = []
    total_active = 0
    total_passive = 0

    for row in rows:
        total_active += row.active_shortlist_count
        total_passive += row.passive_bookmark_count
        by_reason.append(
            IntentBreakdownItem(
                reason_category=row.reason_category,
                active_shortlist_count=row.active_shortlist_count,
                passive_bookmark_count=row.passive_bookmark_count,
                evidence_volume=row.evidence_volume,
                confidence=row.confidence,
            )
        )

    return IntentBreakdownResponse(
        run_version=run_version,
        total_active=total_active,
        total_passive=total_passive,
        by_reason=by_reason,
    )


def get_trends(session: Session, *, run_version: str | None) -> TrendsResponse:
    run_version = resolve_insight_run_version(session, run_version)

    journey_stmt = (
        select(
            Insight.journey_stage,
            func.sum(Insight.evidence_volume),
            func.avg(Insight.confidence),
        )
        .where(Insight.journey_stage.isnot(None))
        .group_by(Insight.journey_stage)
    )
    if run_version:
        journey_stmt = journey_stmt.where(Insight.run_version == run_version)

    journey_rows = session.execute(journey_stmt).all()
    journey_stages = [
        JourneyTrendItem(
            journey_stage=stage.value,
            evidence_volume=int(volume or 0),
            confidence=round(float(confidence), 3) if confidence is not None else None,
        )
        for stage, volume, confidence in journey_rows
        if stage is not None
    ]
    journey_stages.sort(key=lambda item: item.evidence_volume, reverse=True)

    cluster_stmt = select(ThemeCluster).order_by(ThemeCluster.evidence_volume.desc())
    if run_version:
        cluster_stmt = cluster_stmt.where(ThemeCluster.run_version == run_version)
    cluster_rows = session.execute(cluster_stmt.limit(8)).scalars().all()

    emerging = [
        ThemeClusterItem(
            cluster_key=row.cluster_key,
            label=row.label,
            reason_category=row.reason_category,
            evidence_volume=row.evidence_volume,
            confidence=row.confidence,
            sources=row.sources or [],
            chunk_ids=row.chunk_ids or [],
        )
        for row in cluster_rows
    ]

    return TrendsResponse(
        run_version=run_version,
        journey_stages=journey_stages,
        emerging_themes=emerging,
    )


def get_evidence_summary(
    session: Session,
    *,
    run_version: str | None,
    reason_category: str,
    segment: str | None = None,
    category: str | None = None,
    limit: int = 10,
) -> EvidenceSummaryResponse:
    run_version = resolve_insight_run_version(session, run_version)
    stmt = select(Insight).where(Insight.reason_category == reason_category)
    stmt = _insight_filters(
        stmt,
        run_version=run_version,
        segment=segment,
        category=category,
    )
    insights = session.execute(
        stmt.order_by(Insight.confidence.desc().nullslast(), Insight.evidence_volume.desc())
    ).scalars().all()

    chunk_ids: list[uuid.UUID] = []
    sources: set[str] = set()
    total_volume = 0
    confidences: list[float] = []

    for insight in insights:
        total_volume += insight.evidence_volume
        if insight.confidence is not None:
            confidences.append(insight.confidence)
        sources.update(insight.sources or [])
        for chunk_id in insight.evidence_chunk_ids or []:
            if chunk_id not in chunk_ids:
                chunk_ids.append(chunk_id)
            if len(chunk_ids) >= limit:
                break
        if len(chunk_ids) >= limit:
            break

    excerpts: list[EvidenceExcerpt] = []
    if chunk_ids:
        rows = session.execute(
            select(Chunk, Document)
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.id.in_(chunk_ids))
        ).all()
        row_map = {chunk.id: (chunk, document) for chunk, document in rows}
        for chunk_id in chunk_ids:
            pair = row_map.get(chunk_id)
            if pair is None:
                continue
            chunk, document = pair
            excerpts.append(
                EvidenceExcerpt(
                    chunk_id=chunk.id,
                    text=chunk.text,
                    source=document.source.value,
                    source_ref=document.source_ref,
                    segment=chunk.segment,
                    category=chunk.category,
                    confidence=chunk.quality_score,
                    quality_score=chunk.quality_score,
                )
            )

    confidence = None
    if confidences:
        confidence = round(sum(confidences) / len(confidences), 3)
    elif excerpts:
        qualities = [item.quality_score for item in excerpts if item.quality_score is not None]
        if qualities:
            confidence = compute_confidence(
                evidence_volume=total_volume,
                sources=set(sources),
                avg_quality=sum(qualities) / len(qualities),
            )

    return EvidenceSummaryResponse(
        run_version=run_version,
        reason_category=reason_category,
        evidence_volume=total_volume,
        confidence=confidence,
        sources=sorted(sources),
        excerpts=excerpts,
    )
