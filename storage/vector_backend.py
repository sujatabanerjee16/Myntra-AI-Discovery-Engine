"""Vector store backend abstraction (pgvector default, optional Qdrant path)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from common.config import get_settings
from ingestion.stages.embed import embed_texts
from storage.schemas import RetrievalFilters, RetrievedChunk


class VectorBackend(Protocol):
    def search(
        self,
        session: Session,
        *,
        query_text: str,
        top_k: int,
        filters: RetrievalFilters | None,
    ) -> list[RetrievedChunk]: ...


@dataclass(frozen=True, slots=True)
class PgVectorBackend:
    """Default Phase 1–7 backend using PostgreSQL + pgvector."""

    def search(
        self,
        session: Session,
        *,
        query_text: str,
        top_k: int,
        filters: RetrievalFilters | None,
    ) -> list[RetrievedChunk]:
        from storage.retrieval import search_by_embedding

        query_embedding = embed_texts([query_text])[0]
        return search_by_embedding(
            session,
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filters,
        )


@dataclass(frozen=True, slots=True)
class QdrantVectorBackend:
    """Placeholder migration path when corpus volume outgrows pgvector."""

    collection_name: str

    def search(
        self,
        session: Session,
        *,
        query_text: str,
        top_k: int,
        filters: RetrievalFilters | None,
    ) -> list[RetrievedChunk]:
        raise NotImplementedError(
            "Qdrant backend is configured but not enabled in Phase 7. "
            "Install qdrant-client and implement the migration adapter before switching."
        )


def get_vector_backend() -> VectorBackend:
    settings = get_settings()
    backend = settings.vector_backend.lower()
    if backend == "qdrant":
        return QdrantVectorBackend(collection_name=settings.qdrant_collection)
    return PgVectorBackend()
