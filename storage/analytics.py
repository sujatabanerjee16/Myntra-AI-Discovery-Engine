"""Refresh analytical store aggregates from the document/vector stores."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from common.models import Chunk, DimensionAggregate, Document, SignalAggregate, SourceAggregate


def refresh_analytical_aggregates(session: Session, run_version: str) -> dict[str, int]:
    """Recompute dashboard-ready aggregates and replace rows for *run_version*."""
    now = datetime.now(UTC)

    session.execute(delete(DimensionAggregate).where(DimensionAggregate.run_version == run_version))
    session.execute(delete(SignalAggregate).where(SignalAggregate.run_version == run_version))
    session.execute(delete(SourceAggregate).where(SourceAggregate.run_version == run_version))

    source_rows = session.execute(
        select(
            Document.source,
            func.count(func.distinct(Document.id)),
            func.count(Chunk.id),
            func.avg(Chunk.quality_score),
        )
        .join(Chunk, Chunk.document_id == Document.id, isouter=True)
        .group_by(Document.source)
    ).all()

    source_count = 0
    for source, doc_count, chunk_count, avg_quality in source_rows:
        session.add(
            SourceAggregate(
                source=source,
                document_count=int(doc_count or 0),
                chunk_count=int(chunk_count or 0),
                avg_quality_score=float(avg_quality) if avg_quality is not None else None,
                run_version=run_version,
                computed_at=now,
            )
        )
        source_count += 1

    signal_doc_map: dict[str, set] = {}
    signal_chunk_rows = session.execute(
        select(Chunk.id, Chunk.matched_signals, Chunk.document_id).where(
            Chunk.matched_signals.isnot(None)
        )
    ).all()

    signal_chunk_counts: dict[str, int] = {}
    for _chunk_id, signals, doc_id in signal_chunk_rows:
        if not signals:
            continue
        for signal in signals:
            signal_chunk_counts[signal] = signal_chunk_counts.get(signal, 0) + 1
            signal_doc_map.setdefault(signal, set()).add(doc_id)

    signal_count = 0
    for signal, chunk_total in sorted(signal_chunk_counts.items()):
        session.add(
            SignalAggregate(
                signal=signal,
                chunk_count=chunk_total,
                document_count=len(signal_doc_map.get(signal, set())),
                run_version=run_version,
                computed_at=now,
            )
        )
        signal_count += 1

    dimension_rows = session.execute(
        select(
            Chunk.segment,
            Chunk.category,
            Chunk.occasion,
            Chunk.price_band,
            func.count(Chunk.id),
        ).group_by(Chunk.segment, Chunk.category, Chunk.occasion, Chunk.price_band)
    ).all()

    dimension_count = 0
    for segment, category, occasion, price_band, count in dimension_rows:
        session.add(
            DimensionAggregate(
                segment=segment,
                category=category,
                occasion=occasion,
                price_band=price_band,
                chunk_count=int(count or 0),
                run_version=run_version,
                computed_at=now,
            )
        )
        dimension_count += 1

    session.flush()
    return {
        "source_aggregates": source_count,
        "signal_aggregates": signal_count,
        "dimension_aggregates": dimension_count,
    }
