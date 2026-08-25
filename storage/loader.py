"""Load a Phase 1 JSON corpus export into the PostgreSQL storage layer."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from common.config import get_settings
from common.models import SourceType
from storage.analytics import refresh_analytical_aggregates
from storage.repository import create_chunk, create_document, document_exists

logger = logging.getLogger(__name__)


@dataclass
class LoadResult:
    run_version: str
    documents_created: int = 0
    documents_skipped: int = 0
    chunks_created: int = 0
    aggregates: dict[str, int] = field(default_factory=dict)


def _parse_created_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def load_corpus_json(
    session: Session,
    json_path: str | Path,
    *,
    skip_existing: bool = True,
    refresh_aggregates: bool = True,
) -> LoadResult:
    """Load exported corpus JSON into documents/chunks tables."""
    path = Path(json_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    run_version = payload.get("run_version") or "manual-load"
    documents = payload.get("documents", [])

    result = LoadResult(run_version=run_version)
    settings = get_settings()
    dim = settings.embedding_dim

    for doc in documents:
        source = SourceType(doc["source"])
        source_ref = doc["source_ref"]

        if skip_existing and document_exists(session, source, source_ref):
            result.documents_skipped += 1
            continue

        document = create_document(
            session,
            source=source,
            source_ref=source_ref,
            text=doc["text"],
            run_version=doc.get("run_version") or run_version,
            author_hash=doc.get("author_hash"),
            language=doc.get("language"),
            created_at=_parse_created_at(doc.get("created_at")),
        )
        result.documents_created += 1

        doc_signals = doc.get("matched_signals") or []
        for chunk_data in doc.get("chunks", []):
            embedding = chunk_data.get("embedding")
            if embedding is None:
                embedding = [0.0] * dim

            signals = chunk_data.get("matched_signals") or doc_signals
            create_chunk(
                session,
                document_id=document.id,
                text=chunk_data["text"],
                embedding=embedding,
                chunk_index=int(chunk_data.get("chunk_index", 0)),
                matched_signals=signals,
                category=chunk_data.get("category"),
                occasion=chunk_data.get("occasion"),
                price_band=chunk_data.get("price_band"),
                segment=chunk_data.get("segment"),
                quality_score=chunk_data.get("quality_score"),
            )
            result.chunks_created += 1

    if refresh_aggregates and result.documents_created > 0:
        result.aggregates = refresh_analytical_aggregates(session, run_version)

    session.commit()
    logger.info(
        "Loaded corpus %s: docs=%s skipped=%s chunks=%s",
        run_version,
        result.documents_created,
        result.documents_skipped,
        result.chunks_created,
    )
    return result
