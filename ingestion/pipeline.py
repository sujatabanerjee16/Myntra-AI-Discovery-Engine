"""Ingestion pipeline orchestrator."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from common.config import get_settings
from common.models import Chunk, Document, SourceType
from ingestion.connectors.registry import ALL_SOURCES, fetch_source_records
from ingestion.schemas import RawRecord
from ingestion.stages.chunk import TextChunk, chunk_records
from ingestion.stages.clean import clean_records
from ingestion.stages.dedupe import dedupe_records
from ingestion.stages.embed import embed_texts
from ingestion.stages.enrich import EnrichedChunk, enrich_chunks
from ingestion.stages.pii import scrub_records
from ingestion.validation import CorpusValidationReport, validate_corpus
from storage.analytics import refresh_analytical_aggregates

logger = logging.getLogger(__name__)

SUPPORTED_SOURCES = set(ALL_SOURCES)


@dataclass
class PipelineResult:
    run_version: str
    fetched: int = 0
    after_filter: int = 0
    documents_created: int = 0
    documents_skipped: int = 0
    chunks_created: int = 0
    sources: dict[str, int] = field(default_factory=dict)
    sources_created: dict[str, int] = field(default_factory=dict)
    validation: CorpusValidationReport | None = None


def _default_run_version() -> str:
    return datetime.now(UTC).strftime("run-%Y%m%dT%H%M%SZ")


def _serialize_record(record: RawRecord, run_version: str) -> dict:
    return {
        "source": record.source.value,
        "source_ref": record.source_ref,
        "text": record.text,
        "author_hash": record.author_hash,
        "language": record.language,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "run_version": run_version,
        "matched_signals": record.matched_signals,
        "metadata": record.metadata,
    }


def _serialize_chunk(item: EnrichedChunk, vector: list[float] | None) -> dict:
    payload = {
        "chunk_index": item.chunk.chunk_index,
        "text": item.chunk.text,
        "matched_signals": item.signals,
        "category": item.category,
        "occasion": item.occasion,
        "price_band": item.price_band,
        "segment": item.segment,
        "quality_score": item.quality_score,
        "metadata": item.chunk.metadata,
    }
    if vector is not None:
        payload["embedding_dim"] = len(vector)
        payload["embedding"] = vector
    return payload


def prepare_corpus(
    *,
    sources: list[str] | None = None,
    research_excel_path: str | None = None,
    research_excel_paths: list[str] | None = None,
    run_version: str | None = None,
    play_store_limit: int | None = None,
    skip_embed: bool = False,
    include_embeddings: bool = False,
) -> tuple[dict, PipelineResult]:
    """Collect and process records without persisting to the database."""
    settings = get_settings()
    sources = sources or settings.default_source_list
    run_version = run_version or _default_run_version()
    result = PipelineResult(run_version=run_version)

    raw = collect_records(
        sources=sources,
        research_excel_path=research_excel_path,
        research_excel_paths=research_excel_paths,
        play_store_limit=play_store_limit,
    )
    result.fetched = len(raw)

    cleaned = clean_records(raw)
    scrubbed = scrub_records(cleaned)
    deduped = dedupe_records(scrubbed)
    result.after_filter = len(deduped)
    result.validation = validate_corpus(deduped)
    result.documents_created = len(deduped)

    documents: list[dict] = []
    total_chunks = 0

    for record in deduped:
        result.sources[record.source.value] = result.sources.get(record.source.value, 0) + 1
        text_chunks = chunk_records([record])
        enriched = enrich_chunks(text_chunks)

        vectors: list[list[float]] = []
        if not skip_embed and enriched:
            vectors = embed_texts([e.chunk.text for e in enriched])
        elif enriched:
            dim = get_settings().embedding_dim
            vectors = [[0.0] * dim for _ in enriched]

        chunk_payloads = []
        for item, vector in zip(enriched, vectors, strict=True):
            vec = vector if include_embeddings else None
            chunk_payloads.append(_serialize_chunk(item, vec))
        total_chunks += len(chunk_payloads)

        doc = _serialize_record(record, run_version)
        doc["chunks"] = chunk_payloads
        documents.append(doc)

    result.chunks_created = total_chunks

    stats = {
        "fetched": result.fetched,
        "after_filter": result.after_filter,
        "documents": len(documents),
        "chunks": total_chunks,
        "by_source": result.sources,
        "validation": result.validation.to_dict() if result.validation else {},
    }
    payload = {
        "run_version": run_version,
        "exported_at": datetime.now(UTC).isoformat(),
        "sources": sources,
        "stats": stats,
        "documents": documents,
    }
    return payload, result


def collect_records(
    *,
    sources: list[str],
    research_excel_path: str | None = None,
    research_excel_paths: list[str] | None = None,
    play_store_limit: int | None = None,
) -> list[RawRecord]:
    settings = get_settings()
    paths = list(research_excel_paths or [])
    if not paths:
        paths = list(settings.research_excel_path_list)
    if research_excel_path and research_excel_path not in paths:
        paths = [research_excel_path, *[p for p in paths if p != research_excel_path]]

    records: list[RawRecord] = []

    for source in sources:
        source = source.strip().lower()
        batch = fetch_source_records(
            source,
            research_excel_path=research_excel_path or (paths[0] if paths else None),
            research_excel_paths=paths,
            play_store_limit=play_store_limit,
        )
        records.extend(batch)

    return records


def _document_exists(session: Session, source: SourceType, source_ref: str) -> bool:
    stmt = select(Document.id).where(
        Document.source == source,
        Document.source_ref == source_ref,
    )
    return session.execute(stmt).scalar_one_or_none() is not None


def _persist_document(
    session: Session,
    record: RawRecord,
    run_version: str,
) -> Document:
    doc = Document(
        source=record.source,
        source_ref=record.source_ref,
        author_hash=record.author_hash,
        text=record.text,
        language=record.language,
        created_at=record.created_at,
        run_version=run_version,
    )
    session.add(doc)
    session.flush()
    return doc


def _persist_chunks(
    session: Session,
    document: Document,
    enriched: list[EnrichedChunk],
    embeddings: list[list[float]],
) -> int:
    count = 0
    for item, vector in zip(enriched, embeddings, strict=True):
        chunk = Chunk(
            document_id=document.id,
            text=item.chunk.text,
            embedding=vector,
            chunk_index=item.chunk.chunk_index,
            matched_signals=item.signals,
            category=item.category,
            occasion=item.occasion,
            price_band=item.price_band,
            segment=item.segment,
            quality_score=item.quality_score,
        )
        session.add(chunk)
        count += 1
    return count


def run_pipeline(
    session: Session,
    *,
    sources: list[str] | None = None,
    research_excel_path: str | None = None,
    research_excel_paths: list[str] | None = None,
    run_version: str | None = None,
    play_store_limit: int | None = None,
    skip_embed: bool = False,
) -> PipelineResult:
    """Execute the full ingestion pipeline and persist results idempotently."""
    import time

    from common.observability import log_pipeline_run, persist_pipeline_run

    sources = sources or get_settings().default_source_list
    run_version = run_version or _default_run_version()
    result = PipelineResult(run_version=run_version)
    start = time.perf_counter()
    success = True
    error_message: str | None = None

    try:
        raw = collect_records(
            sources=sources,
            research_excel_path=research_excel_path,
            research_excel_paths=research_excel_paths,
            play_store_limit=play_store_limit,
        )
        result.fetched = len(raw)

        cleaned = clean_records(raw)
        scrubbed = scrub_records(cleaned)
        deduped = dedupe_records(scrubbed)
        result.after_filter = len(deduped)
        result.validation = validate_corpus(deduped)

        record_chunks: list[tuple[RawRecord, list[TextChunk]]] = []
        for record in deduped:
            chunks = chunk_records([record])
            if chunks:
                record_chunks.append((record, chunks))

        for record, _ in record_chunks:
            result.sources[record.source.value] = result.sources.get(record.source.value, 0) + 1

        for record, text_chunks in record_chunks:
            if _document_exists(session, record.source, record.source_ref):
                result.documents_skipped += 1
                logger.debug("Skipping existing document: %s", record.source_ref)
                continue

            document = _persist_document(session, record, run_version)
            result.documents_created += 1
            source_key = record.source.value
            result.sources_created[source_key] = result.sources_created.get(source_key, 0) + 1

            enriched = enrich_chunks(text_chunks)
            vectors: list[list[float]] = []
            if not skip_embed:
                vectors = embed_texts([e.chunk.text for e in enriched])
            else:
                dim = get_settings().embedding_dim
                vectors = [[0.0] * dim for _ in enriched]

            created = _persist_chunks(session, document, enriched, vectors)
            result.chunks_created += created

        session.commit()

        if result.documents_created > 0:
            refresh_analytical_aggregates(session, run_version)
            session.commit()
    except Exception as exc:
        success = False
        error_message = str(exc)
        session.rollback()
        raise
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        stats = {
            "fetched": result.fetched,
            "after_filter": result.after_filter,
            "documents_created": result.documents_created,
            "documents_skipped": result.documents_skipped,
            "chunks_created": result.chunks_created,
            "sources": result.sources,
            "sources_created": result.sources_created,
            "validation": result.validation.to_dict() if result.validation else {},
        }
        log_pipeline_run(
            run_type="ingestion",
            run_version=run_version,
            duration_ms=duration_ms,
            success=success,
            stats=stats,
            error=error_message,
        )
        if success:
            persist_pipeline_run(
                session,
                run_type="ingestion",
                run_version=run_version,
                duration_ms=duration_ms,
                success=True,
                stats=stats,
            )
            session.commit()

    logger.info(
        "Pipeline %s complete: %s docs created, %s skipped, %s chunks",
        run_version,
        result.documents_created,
        result.documents_skipped,
        result.chunks_created,
    )
    return result
