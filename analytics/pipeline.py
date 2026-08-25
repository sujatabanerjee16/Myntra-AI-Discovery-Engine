"""Semantic analytics pipeline: classify, cluster, score, and persist insights."""

from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from analytics.clustering import AnalyzedChunk, cluster_themes
from analytics.competitive import build_competitive_aggregates, summarize_competitive
from analytics.confidence import compute_confidence, source_agreement
from analytics.intent import detect_intent
from analytics.journey import map_journey_stage
from analytics.motives import classify_wishlist_motives
from analytics.platforms import comparison_scope, tag_platforms
from analytics.taxonomy import classify_reason
from common.models import (
    Chunk,
    CompetitiveAggregate,
    Document,
    Insight,
    IntentType,
    JourneyStage,
    ReasonAggregate,
    ThemeCluster,
)

logger = logging.getLogger(__name__)


@dataclass
class AnalyticsResult:
    run_version: str
    chunks_analyzed: int = 0
    insights_created: int = 0
    reason_aggregates: int = 0
    theme_clusters: int = 0
    competitive_aggregates: int = 0
    insights: list[dict[str, Any]] = field(default_factory=list)
    reasons: list[dict[str, Any]] = field(default_factory=list)
    clusters: list[dict[str, Any]] = field(default_factory=list)
    competitive: list[dict[str, Any]] = field(default_factory=list)
    competitive_summary: dict[str, Any] = field(default_factory=dict)


def _default_run_version() -> str:
    return datetime.now(UTC).strftime("analytics-%Y%m%dT%H%M%SZ")


def _parse_uuid(value: str | uuid.UUID) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_URL, str(value))


def _load_chunks_from_session(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        select(
            Chunk.id,
            Chunk.text,
            Chunk.matched_signals,
            Chunk.category,
            Chunk.segment,
            Chunk.quality_score,
            Document.source,
        ).join(Document, Chunk.document_id == Document.id)
    ).all()

    return [
        {
            "chunk_id": row[0],
            "text": row[1],
            "signals": row[2] or [],
            "category": row[3],
            "segment": row[4],
            "quality_score": row[5] or 0.5,
            "source": row[6].value,
        }
        for row in rows
    ]


def _load_chunks_from_json(json_path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
    chunks: list[dict[str, Any]] = []
    for doc in payload.get("documents", []):
        source = doc["source"]
        doc_signals = doc.get("matched_signals") or []
        for chunk in doc.get("chunks", []):
            chunk_id = f"{doc['source_ref']}:{chunk.get('chunk_index', 0)}"
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "text": chunk["text"],
                    "signals": chunk.get("matched_signals") or doc_signals,
                    "category": chunk.get("category"),
                    "segment": chunk.get("segment"),
                    "quality_score": chunk.get("quality_score") or 0.5,
                    "source": source,
                }
            )
    return chunks


def analyze_chunks(raw_chunks: list[dict[str, Any]]) -> list[AnalyzedChunk]:
    """Run taxonomy, intent, journey, platform, and motive analysis on each chunk."""
    analyzed: list[AnalyzedChunk] = []
    for item in raw_chunks:
        text = item["text"]
        signals = item.get("signals") or []
        reason = classify_reason(text, signals=signals)
        platform_tags = tag_platforms(text)
        motives = classify_wishlist_motives(text, platforms=platform_tags.platforms)
        analyzed.append(
            AnalyzedChunk(
                chunk_id=item["chunk_id"],
                text=text,
                source=item["source"],
                reason_category=reason.primary,
                signals=signals,
                segment=item.get("segment"),
                category=item.get("category"),
                quality_score=float(item.get("quality_score") or 0.5),
                platforms=platform_tags.platforms,
                wishlist_motive=motives.primary,
                platform_attribution_confidence=platform_tags.attribution_confidence,
                comparison_scope=comparison_scope(platform_tags.platforms),
            )
        )
    return analyzed


def _group_insights(
    raw_chunks: list[dict[str, Any]],
    analyzed: list[AnalyzedChunk],
    run_version: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Build insight, reason aggregate, theme cluster, and competitive payloads."""
    groups: dict[tuple, dict[str, Any]] = defaultdict(
        lambda: {
            "chunk_ids": [],
            "sources": set(),
            "quality_scores": [],
            "intent_counts": defaultdict(int),
            "platforms": set(),
            "motives": set(),
        }
    )

    competitive_rows: list[dict[str, Any]] = []

    for _raw, item in zip(raw_chunks, analyzed, strict=True):
        intent = detect_intent(item.text, reason_category=item.reason_category)
        journey = map_journey_stage(item.text, reason_category=item.reason_category)
        platforms = item.platforms or ["myntra"]
        motive = item.wishlist_motive or "assortment_discovery"
        key = (
            item.reason_category,
            intent.value,
            journey.value,
            item.segment,
            item.category,
        )
        bucket = groups[key]
        bucket["chunk_ids"].append(_parse_uuid(item.chunk_id))
        bucket["sources"].add(item.source)
        bucket["quality_scores"].append(item.quality_score)
        bucket["intent_counts"][intent.value] += 1
        bucket["reason_category"] = item.reason_category
        bucket["intent_type"] = intent.value
        bucket["journey_stage"] = journey.value
        bucket["segment"] = item.segment
        bucket["category"] = item.category
        bucket["platforms"].update(platforms)
        bucket["motives"].add(motive)

        competitive_rows.append(
            {
                "platforms": platforms,
                "wishlist_motive": motive,
                "reason_category": item.reason_category,
                "source": item.source,
                "quality_score": item.quality_score,
                "platform_attribution_confidence": item.platform_attribution_confidence,
            }
        )

    insight_payloads: list[dict[str, Any]] = []
    for bucket in groups.values():
        sources = sorted(bucket["sources"])
        avg_quality = sum(bucket["quality_scores"]) / len(bucket["quality_scores"])
        confidence = compute_confidence(
            evidence_volume=len(bucket["chunk_ids"]),
            sources=set(sources),
            avg_quality=avg_quality,
            agreement=source_agreement(set(sources)),
        )
        platforms = sorted(bucket["platforms"])
        motives = sorted(bucket["motives"])
        insight_payloads.append(
            {
                "reason_category": bucket["reason_category"],
                "intent_type": bucket["intent_type"],
                "journey_stage": bucket["journey_stage"],
                "segment": bucket["segment"],
                "category": bucket["category"],
                "platforms": platforms,
                "wishlist_motive": motives[0] if motives else None,
                "comparison_scope": comparison_scope(platforms),
                "evidence_chunk_ids": bucket["chunk_ids"],
                "evidence_volume": len(bucket["chunk_ids"]),
                "confidence": confidence,
                "sources": sources,
                "run_version": run_version,
            }
        )

    reason_groups: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "evidence_volume": 0,
            "sources": set(),
            "qualities": [],
            "active_shortlist_count": 0,
            "passive_bookmark_count": 0,
        }
    )
    for insight in insight_payloads:
        reason = insight["reason_category"]
        bucket = reason_groups[reason]
        bucket["evidence_volume"] += insight["evidence_volume"]
        bucket["sources"].update(insight["sources"])
        bucket["qualities"].append(insight["confidence"] or 0.5)
        if insight["intent_type"] == "active_shortlist":
            bucket["active_shortlist_count"] += insight["evidence_volume"]
        else:
            bucket["passive_bookmark_count"] += insight["evidence_volume"]

    reason_payloads: list[dict[str, Any]] = []
    for reason, bucket in sorted(reason_groups.items()):
        sources = sorted(bucket["sources"])
        avg_quality = sum(bucket["qualities"]) / len(bucket["qualities"])
        reason_payloads.append(
            {
                "reason_category": reason,
                "evidence_volume": bucket["evidence_volume"],
                "confidence": compute_confidence(
                    evidence_volume=bucket["evidence_volume"],
                    sources=set(sources),
                    avg_quality=avg_quality,
                ),
                "sources": sources,
                "active_shortlist_count": bucket["active_shortlist_count"],
                "passive_bookmark_count": bucket["passive_bookmark_count"],
                "run_version": run_version,
            }
        )
    reason_payloads.sort(key=lambda r: r["evidence_volume"], reverse=True)

    theme_results = cluster_themes(analyzed)
    cluster_payloads: list[dict[str, Any]] = []
    for cluster in theme_results:
        sources = set(cluster.sources)
        avg_quality = 0.7
        cluster_payloads.append(
            {
                "cluster_key": cluster.cluster_key,
                "label": cluster.label,
                "reason_category": cluster.reason_category,
                "chunk_ids": [_parse_uuid(cid) for cid in cluster.chunk_ids],
                "evidence_volume": cluster.evidence_volume,
                "confidence": compute_confidence(
                    evidence_volume=cluster.evidence_volume,
                    sources=sources,
                    avg_quality=avg_quality,
                ),
                "sources": cluster.sources,
                "run_version": run_version,
            }
        )

    competitive_payloads = build_competitive_aggregates(competitive_rows, run_version=run_version)
    return insight_payloads, reason_payloads, cluster_payloads, competitive_payloads


def run_semantic_analytics(
    raw_chunks: list[dict[str, Any]],
    *,
    run_version: str | None = None,
) -> AnalyticsResult:
    """Analyze chunks and return structured insight payloads (no DB)."""
    run_version = run_version or _default_run_version()
    analyzed = analyze_chunks(raw_chunks)
    insights, reasons, clusters, competitive = _group_insights(raw_chunks, analyzed, run_version)
    summary = summarize_competitive(competitive)

    return AnalyticsResult(
        run_version=run_version,
        chunks_analyzed=len(raw_chunks),
        insights_created=len(insights),
        reason_aggregates=len(reasons),
        theme_clusters=len(clusters),
        competitive_aggregates=len(competitive),
        insights=insights,
        reasons=reasons,
        clusters=clusters,
        competitive=competitive,
        competitive_summary=summary,
    )


def _clear_run(session: Session, run_version: str) -> None:
    session.execute(delete(Insight).where(Insight.run_version == run_version))
    session.execute(delete(ReasonAggregate).where(ReasonAggregate.run_version == run_version))
    session.execute(delete(ThemeCluster).where(ThemeCluster.run_version == run_version))
    session.execute(delete(CompetitiveAggregate).where(CompetitiveAggregate.run_version == run_version))


def persist_analytics_result(session: Session, result: AnalyticsResult) -> None:
    """Write insight and aggregate records to PostgreSQL."""
    for payload in result.insights:
        session.add(
            Insight(
                reason_category=payload["reason_category"],
                intent_type=IntentType(payload["intent_type"]),
                journey_stage=JourneyStage(payload["journey_stage"]),
                segment=payload["segment"],
                category=payload["category"],
                platforms=payload.get("platforms"),
                wishlist_motive=payload.get("wishlist_motive"),
                comparison_scope=payload.get("comparison_scope"),
                evidence_chunk_ids=payload["evidence_chunk_ids"],
                evidence_volume=payload["evidence_volume"],
                confidence=payload["confidence"],
                sources=payload["sources"],
                run_version=result.run_version,
            )
        )

    for payload in result.reasons:
        session.add(ReasonAggregate(**payload))

    for payload in result.clusters:
        session.add(ThemeCluster(**payload))

    for payload in result.competitive:
        session.add(
            CompetitiveAggregate(
                platform=payload["platform"],
                metric_type=payload["metric_type"],
                label=payload["label"],
                count=payload["count"],
                share=payload["share"],
                evidence_volume=payload["evidence_volume"],
                confidence=payload["confidence"],
                shared_vs_unique=payload["shared_vs_unique"],
                sources=payload.get("sources"),
                run_version=result.run_version,
            )
        )

    session.flush()


def run_semantic_analytics_db(
    session: Session,
    *,
    run_version: str | None = None,
    replace_existing: bool = True,
    json_path: str | Path | None = None,
) -> AnalyticsResult:
    """Load chunks from DB or JSON, analyze, and persist insights."""
    run_version = run_version or _default_run_version()

    if json_path:
        raw_chunks = _load_chunks_from_json(json_path)
    else:
        raw_chunks = _load_chunks_from_session(session)

    if not raw_chunks:
        logger.warning("No chunks available for semantic analytics")
        return AnalyticsResult(run_version=run_version)

    if replace_existing:
        _clear_run(session, run_version)

    result = run_semantic_analytics(raw_chunks, run_version=run_version)
    persist_analytics_result(session, result)
    session.commit()

    logger.info(
        "Semantic analytics %s: chunks=%s insights=%s reasons=%s clusters=%s competitive=%s",
        run_version,
        result.chunks_analyzed,
        result.insights_created,
        result.reason_aggregates,
        result.theme_clusters,
        result.competitive_aggregates,
    )
    return result


def export_analytics_json(result: AnalyticsResult, output_path: str | Path) -> Path:
    """Export analytics result to JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_version": result.run_version,
        "exported_at": datetime.now(UTC).isoformat(),
        "stats": {
            "chunks_analyzed": result.chunks_analyzed,
            "insights_created": result.insights_created,
            "reason_aggregates": result.reason_aggregates,
            "theme_clusters": result.theme_clusters,
            "competitive_aggregates": result.competitive_aggregates,
        },
        "insights": result.insights,
        "reasons": result.reasons,
        "clusters": result.clusters,
        "competitive": result.competitive,
        "competitive_summary": result.competitive_summary,
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path
