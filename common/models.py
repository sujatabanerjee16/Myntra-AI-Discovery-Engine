"""Core ORM data models.

Implements the conceptual schemas defined in ``doc/Architecture.md`` §5:
``Document``, ``Chunk``, ``Insight``, and ``AnswerTrace``. Enums for source,
intent type, and journey stage keep taxonomy values consistent across layers.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.config import get_settings
from common.db import Base

EMBEDDING_DIM = get_settings().embedding_dim


class SourceType(str, enum.Enum):
    play_store = "play_store"
    reddit = "reddit"
    youtube = "youtube"
    product_review = "product_review"
    social = "social"
    research = "research"


class IntentType(str, enum.Enum):
    active_shortlist = "active_shortlist"
    passive_bookmark = "passive_bookmark"


class JourneyStage(str, enum.Enum):
    discovery = "discovery"
    consideration = "consideration"
    hesitation = "hesitation"
    postponement = "postponement"
    external_comparison = "external_comparison"
    purchase = "purchase"


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Document(Base):
    """Raw source record (post-cleaning) with provenance and lineage."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source: Mapped[SourceType] = mapped_column(Enum(SourceType, name="source_type"), index=True)
    source_ref: Mapped[str | None] = mapped_column(String(1024))
    author_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    run_version: Mapped[str | None] = mapped_column(String(64), index=True)

    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    """Retrieval unit: a chunk of a document plus its embedding and tags."""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    matched_signals: Mapped[list[str] | None] = mapped_column(ARRAY(String(64)))

    category: Mapped[str | None] = mapped_column(String(64), index=True)
    occasion: Mapped[str | None] = mapped_column(String(64), index=True)
    price_band: Mapped[str | None] = mapped_column(String(32), index=True)
    segment: Mapped[str | None] = mapped_column(String(64), index=True)
    platforms: Mapped[list[str] | None] = mapped_column(ARRAY(String(32)))
    wishlist_motives: Mapped[list[str] | None] = mapped_column(ARRAY(String(64)))
    platform_attribution_confidence: Mapped[float | None] = mapped_column(Float)
    quality_score: Mapped[float | None] = mapped_column(Float)

    document: Mapped[Document] = relationship(back_populates="chunks")


class Insight(Base):
    """Structured, confidence-scored analysis produced by the semantic layer."""

    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    reason_category: Mapped[str] = mapped_column(String(64), index=True)
    intent_type: Mapped[IntentType | None] = mapped_column(Enum(IntentType, name="intent_type"))
    journey_stage: Mapped[JourneyStage | None] = mapped_column(
        Enum(JourneyStage, name="journey_stage")
    )
    segment: Mapped[str | None] = mapped_column(String(64), index=True)
    category: Mapped[str | None] = mapped_column(String(64), index=True)
    platforms: Mapped[list[str] | None] = mapped_column(ARRAY(String(32)))
    wishlist_motive: Mapped[str | None] = mapped_column(String(64), index=True)
    comparison_scope: Mapped[str | None] = mapped_column(String(32))
    evidence_chunk_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    evidence_volume: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float | None] = mapped_column(Float)
    sources: Mapped[list[str] | None] = mapped_column(ARRAY(String(32)))
    run_version: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReasonAggregate(Base):
    """Analytical store: ranked non-conversion reason categories."""

    __tablename__ = "reason_aggregates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    reason_category: Mapped[str] = mapped_column(String(64), index=True)
    evidence_volume: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float | None] = mapped_column(Float)
    sources: Mapped[list[str] | None] = mapped_column(ARRAY(String(32)))
    active_shortlist_count: Mapped[int] = mapped_column(Integer, default=0)
    passive_bookmark_count: Mapped[int] = mapped_column(Integer, default=0)
    run_version: Mapped[str] = mapped_column(String(64), index=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CompetitiveAggregate(Base):
    """Analytical store: wishlist motives / barriers by fashion platform."""

    __tablename__ = "competitive_aggregates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    metric_type: Mapped[str] = mapped_column(String(16), index=True)  # motive | barrier
    label: Mapped[str] = mapped_column(String(64), index=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    share: Mapped[float | None] = mapped_column(Float)
    evidence_volume: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float | None] = mapped_column(Float)
    shared_vs_unique: Mapped[str | None] = mapped_column(String(32))
    sources: Mapped[list[str] | None] = mapped_column(ARRAY(String(32)))
    run_version: Mapped[str] = mapped_column(String(64), index=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ThemeCluster(Base):
    """Analytical store: emerging theme clusters from semantic grouping."""

    __tablename__ = "theme_clusters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    cluster_key: Mapped[str] = mapped_column(String(32), index=True)
    label: Mapped[str] = mapped_column(String(256))
    reason_category: Mapped[str | None] = mapped_column(String(64), index=True)
    chunk_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    evidence_volume: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float | None] = mapped_column(Float)
    sources: Mapped[list[str] | None] = mapped_column(ARRAY(String(32)))
    run_version: Mapped[str] = mapped_column(String(64), index=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SourceAggregate(Base):
    """Analytical store: evidence volume and quality by source."""

    __tablename__ = "source_aggregates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source: Mapped[SourceType] = mapped_column(Enum(SourceType, name="source_type"), index=True)
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_quality_score: Mapped[float | None] = mapped_column(Float)
    run_version: Mapped[str] = mapped_column(String(64), index=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SignalAggregate(Base):
    """Analytical store: chunk/document counts by priority signal."""

    __tablename__ = "signal_aggregates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    signal: Mapped[str] = mapped_column(String(64), index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    run_version: Mapped[str] = mapped_column(String(64), index=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DimensionAggregate(Base):
    """Analytical store: heatmap-style counts by segment/category/occasion/price."""

    __tablename__ = "dimension_aggregates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    segment: Mapped[str | None] = mapped_column(String(64), index=True)
    category: Mapped[str | None] = mapped_column(String(64), index=True)
    occasion: Mapped[str | None] = mapped_column(String(64), index=True)
    price_band: Mapped[str | None] = mapped_column(String(32), index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    run_version: Mapped[str] = mapped_column(String(64), index=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AnswerTrace(Base):
    """Audit record for a grounded assistant answer (evidence + caveats)."""

    __tablename__ = "answer_traces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    question: Mapped[str] = mapped_column(Text)
    retrieved_chunk_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    answer: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    confidence: Mapped[float | None] = mapped_column(Float)
    limitations: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[float | None] = mapped_column(Float)
    insufficient_evidence: Mapped[bool | None] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PipelineRun(Base):
    """Observability record for ingestion or analytics pipeline executions."""

    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    run_type: Mapped[str] = mapped_column(String(32), index=True)
    run_version: Mapped[str] = mapped_column(String(64), index=True)
    success: Mapped[bool] = mapped_column(default=True)
    duration_ms: Mapped[float | None] = mapped_column(Float)
    stats: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvalRun(Base):
    """Persisted evaluation report for quality and cost tracking."""

    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    run_version: Mapped[str] = mapped_column(String(64), index=True)
    retrieval_hit_at_k: Mapped[float | None] = mapped_column(Float)
    retrieval_mrr: Mapped[float | None] = mapped_column(Float)
    faithfulness_score: Mapped[float | None] = mapped_column(Float)
    taxonomy_accuracy: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool] = mapped_column(default=False)
    report: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceRefreshState(Base):
    """Incremental refresh schedule and last-run status per source."""

    __tablename__ = "source_refresh_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type"), unique=True, index=True
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_version: Mapped[str | None] = mapped_column(String(64))
    documents_added: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(default=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FeedbackVerdict(str, enum.Enum):
    validated = "validated"
    flagged = "flagged"
    needs_review = "needs_review"


class WishlistEvent(Base):
    """Internal Myntra wishlist/funnel behavioral event."""

    __tablename__ = "wishlist_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_hash: Mapped[str] = mapped_column(String(128), index=True)
    product_id: Mapped[str] = mapped_column(String(128), index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str | None] = mapped_column(String(64), index=True)
    segment: Mapped[str | None] = mapped_column(String(64), index=True)
    price_band: Mapped[str | None] = mapped_column(String(32))
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event_metadata: Mapped[dict | None] = mapped_column(JSONB)
    run_version: Mapped[str] = mapped_column(String(64), index=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ConversionSnapshot(Base):
    """Computed wishlist-to-purchase conversion metric."""

    __tablename__ = "conversion_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    run_version: Mapped[str] = mapped_column(String(64), index=True)
    window_days: Mapped[int] = mapped_column(Integer, default=30)
    wishlist_users: Mapped[int] = mapped_column(Integer, default=0)
    converted_users: Mapped[int] = mapped_column(Integer, default=0)
    conversion_rate: Mapped[float] = mapped_column(Float)
    cohort_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cohort_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ReasonCorroboration(Base):
    """Join of public-evidence reason with internal conversion behavior."""

    __tablename__ = "reason_corroborations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    reason_category: Mapped[str] = mapped_column(String(64), index=True)
    public_confidence: Mapped[float | None] = mapped_column(Float)
    public_evidence_volume: Mapped[int] = mapped_column(Integer, default=0)
    internal_non_conversion_share: Mapped[float | None] = mapped_column(Float)
    corroboration_score: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), index=True)
    segment_affinity: Mapped[list[str] | None] = mapped_column(ARRAY(String(64)))
    run_version: Mapped[str] = mapped_column(String(64), index=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class InsightFeedback(Base):
    """PM feedback validating or flagging an insight/reason category."""

    __tablename__ = "insight_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    insight_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insights.id", ondelete="SET NULL"), index=True
    )
    reason_category: Mapped[str] = mapped_column(String(64), index=True)
    verdict: Mapped[FeedbackVerdict] = mapped_column(
        Enum(FeedbackVerdict, name="feedback_verdict"), index=True
    )
    notes: Mapped[str | None] = mapped_column(Text)
    reviewer: Mapped[str] = mapped_column(String(128), default="pm")
    adjusted_confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
