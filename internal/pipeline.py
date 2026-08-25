"""Internal data integration pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from common.config import get_settings
from common.models import ConversionSnapshot, ReasonAggregate, ReasonCorroboration, WishlistEvent
from internal.connectors.events import load_internal_events
from internal.conversion import compute_wishlist_conversion, segment_non_conversion_rates
from internal.corroboration import compute_corroboration

logger = logging.getLogger(__name__)


@dataclass
class InternalPipelineResult:
    run_version: str
    events_loaded: int = 0
    conversion_rate: float = 0.0
    corroborations: int = 0
    items: list[dict] = field(default_factory=list)


def _default_run_version() -> str:
    return datetime.now(UTC).strftime("internal-%Y%m%dT%H%M%SZ")


def ingest_internal_events(
    session: Session,
    events_path: str,
    *,
    run_version: str | None = None,
    replace_existing: bool = True,
) -> int:
    """Persist internal wishlist/funnel events to the analytical store."""
    run_version = run_version or _default_run_version()
    records = load_internal_events(events_path)

    if replace_existing:
        session.execute(delete(WishlistEvent))

    for record in records:
        session.add(
            WishlistEvent(
                user_hash=record.user_hash,
                product_id=record.product_id,
                event_type=record.event_type,
                category=record.category,
                segment=record.segment,
                price_band=record.price_band,
                event_at=record.event_at,
                event_metadata=record.metadata,
                run_version=run_version,
            )
        )

    session.flush()
    logger.info("Ingested %s internal events for %s", len(records), run_version)
    return len(records)


def _load_events_from_db(session: Session) -> list:
    from internal.schemas import InternalEventRecord

    rows = session.execute(select(WishlistEvent).order_by(WishlistEvent.event_at)).scalars()
    return [
        InternalEventRecord(
            user_hash=row.user_hash,
            product_id=row.product_id,
            event_type=row.event_type,
            category=row.category,
            segment=row.segment,
            price_band=row.price_band,
            event_at=row.event_at,
            metadata=row.event_metadata or {},
        )
        for row in rows
    ]


def run_internal_pipeline(
    session: Session,
    *,
    events_path: str | None = None,
    run_version: str | None = None,
    analytics_run_version: str | None = None,
) -> InternalPipelineResult:
    """Ingest internal events, compute conversion, and corroborate public reasons."""
    settings = get_settings()
    run_version = run_version or _default_run_version()
    path = events_path or settings.internal_events_path

    events_loaded = ingest_internal_events(session, path, run_version=run_version)
    events = _load_events_from_db(session)

    conversion = compute_wishlist_conversion(
        events,
        window_days=settings.conversion_window_days,
    )
    session.execute(delete(ConversionSnapshot))
    session.add(
        ConversionSnapshot(
            run_version=run_version,
            window_days=conversion.window_days,
            wishlist_users=conversion.wishlist_users,
            converted_users=conversion.converted_users,
            conversion_rate=conversion.conversion_rate,
            cohort_start=conversion.cohort_start,
            cohort_end=conversion.cohort_end,
        )
    )

    segment_rates = segment_non_conversion_rates(
        events,
        window_days=settings.conversion_window_days,
    )

    reason_stmt = select(ReasonAggregate)
    if analytics_run_version:
        reason_stmt = reason_stmt.where(ReasonAggregate.run_version == analytics_run_version)
    else:
        reason_stmt = reason_stmt.order_by(ReasonAggregate.computed_at.desc()).limit(50)

    reason_rows = session.execute(reason_stmt).scalars().all()
    reason_payload = [
        {
            "reason_category": row.reason_category,
            "evidence_volume": row.evidence_volume,
            "confidence": row.confidence,
        }
        for row in reason_rows
    ]

    corroboration_rows = compute_corroboration(reason_payload, segment_rates)
    session.execute(delete(ReasonCorroboration))
    for row in corroboration_rows:
        session.add(
            ReasonCorroboration(
                reason_category=row.reason_category,
                public_confidence=row.public_confidence,
                public_evidence_volume=row.public_evidence_volume,
                internal_non_conversion_share=row.internal_non_conversion_share,
                corroboration_score=row.corroboration_score,
                status=row.status,
                segment_affinity=row.segment_affinity,
                run_version=run_version,
            )
        )

    session.flush()
    return InternalPipelineResult(
        run_version=run_version,
        events_loaded=events_loaded,
        conversion_rate=conversion.conversion_rate,
        corroborations=len(corroboration_rows),
        items=[
            {
                "reason_category": row.reason_category,
                "corroboration_score": row.corroboration_score,
                "status": row.status,
            }
            for row in corroboration_rows
        ],
    )
