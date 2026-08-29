"""Assemble grounded context from retrieved chunks and dashboard aggregates."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from assistant.schemas import AggregateContext
from common.models import CompetitiveAggregate, ReasonAggregate, ThemeCluster
from storage.schemas import RetrievedChunk


def fetch_relevant_aggregates(
    session: Session,
    reason_categories: list[str],
    *,
    limit: int = 5,
) -> AggregateContext:
    """Load ranked reasons and theme clusters relevant to the parsed question."""
    latest_run = session.scalar(
        select(ReasonAggregate.run_version).order_by(ReasonAggregate.computed_at.desc()).limit(1)
    )

    reason_stmt = select(ReasonAggregate).order_by(ReasonAggregate.evidence_volume.desc())
    if latest_run:
        reason_stmt = reason_stmt.where(ReasonAggregate.run_version == latest_run)
    reason_rows = session.execute(reason_stmt.limit(limit * 2)).scalars().all()

    if reason_categories:
        prioritized = [row for row in reason_rows if row.reason_category in reason_categories]
        remainder = [row for row in reason_rows if row.reason_category not in reason_categories]
        reason_rows = (prioritized + remainder)[:limit]
    else:
        reason_rows = reason_rows[:limit]

    cluster_stmt = select(ThemeCluster).order_by(ThemeCluster.evidence_volume.desc())
    if latest_run:
        cluster_stmt = cluster_stmt.where(ThemeCluster.run_version == latest_run)
    cluster_rows = session.execute(cluster_stmt.limit(limit)).scalars().all()

    if reason_categories:
        cluster_rows = sorted(
            cluster_rows,
            key=lambda row: (
                0 if row.reason_category in reason_categories else 1,
                -(row.evidence_volume or 0),
            ),
        )[:limit]

    competitive_stmt = select(CompetitiveAggregate).order_by(CompetitiveAggregate.count.desc())
    if latest_run:
        competitive_stmt = competitive_stmt.where(CompetitiveAggregate.run_version == latest_run)
    competitive_rows = session.execute(competitive_stmt.limit(20)).scalars().all()
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
        }
        for row in competitive_rows
    ]

    return AggregateContext(
        run_version=latest_run,
        ranked_reasons=[
            {
                "reason_category": row.reason_category,
                "evidence_volume": row.evidence_volume,
                "confidence": row.confidence,
                "sources": row.sources or [],
                "active_shortlist_count": row.active_shortlist_count,
                "passive_bookmark_count": row.passive_bookmark_count,
            }
            for row in reason_rows
        ],
        theme_clusters=[
            {
                "cluster_key": row.cluster_key,
                "label": row.label,
                "reason_category": row.reason_category,
                "evidence_volume": row.evidence_volume,
                "confidence": row.confidence,
            }
            for row in cluster_rows
        ],
        competitive=competitive,
    )


def build_grounded_context(
    chunks: list[RetrievedChunk],
    aggregates: AggregateContext,
) -> str:
    """Format evidence excerpts and aggregate facts for the LLM prompt."""
    sections: list[str] = []

    if aggregates.ranked_reasons:
        lines = ["## Ranked non-conversion reasons (aggregate facts)"]
        for item in aggregates.ranked_reasons:
            lines.append(
                "- {category}: volume={volume}, confidence={confidence}, sources={sources}".format(
                    category=item["reason_category"],
                    volume=item["evidence_volume"],
                    confidence=item.get("confidence"),
                    sources=", ".join(item.get("sources") or []),
                )
            )
        sections.append("\n".join(lines))

    if aggregates.theme_clusters:
        lines = ["## Emerging themes (aggregate facts)"]
        for item in aggregates.theme_clusters:
            lines.append(
                "- {label} ({category}): volume={volume}, confidence={confidence}".format(
                    label=item["label"],
                    category=item.get("reason_category"),
                    volume=item["evidence_volume"],
                    confidence=item.get("confidence"),
                )
            )
        sections.append("\n".join(lines))

    if aggregates.segment_comparisons:
        lines = ["## Age cohort comparison (Age 18–24 vs Age 25–35 only)"]
        for item in aggregates.segment_comparisons[:10]:
            lines.append(
                "- {segment}: {reason} volume={volume}".format(
                    segment=item.get("dimension"),
                    reason=item.get("reason_category"),
                    volume=item.get("evidence_volume"),
                )
            )
        sections.append("\n".join(lines))

    if aggregates.competitive:
        lines = ["## Competitive wishlist comparison (Myntra vs Nykaa vs Ajio)"]
        for item in aggregates.competitive[:12]:
            lines.append(
                "- {platform} {metric}: {label} count={count} share={share} scope={scope}".format(
                    platform=item.get("platform"),
                    metric=item.get("metric_type"),
                    label=item.get("label"),
                    count=item.get("count"),
                    share=item.get("share"),
                    scope=item.get("shared_vs_unique"),
                )
            )
        sections.append("\n".join(lines))

    if chunks:
        lines = ["## Retrieved evidence excerpts"]
        for index, chunk in enumerate(chunks, start=1):
            excerpt = chunk.text.strip().replace("\n", " ")
            if len(excerpt) > 400:
                excerpt = excerpt[:397] + "..."
            lines.append(
                f"[{index}] chunk_id={chunk.chunk_id} source={chunk.source.value} "
                f"score={chunk.score}: {excerpt}"
            )
        sections.append("\n".join(lines))

    return "\n\n".join(sections)
