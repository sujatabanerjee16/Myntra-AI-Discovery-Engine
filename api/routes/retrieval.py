"""Vector retrieval HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.backend import search_with_fallback
from common.db import get_session
from storage.schemas import RetrievalSearchRequest, RetrievalSearchResponse

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/search", response_model=RetrievalSearchResponse)
def retrieval_search(
    body: RetrievalSearchRequest,
    session: Session = Depends(get_session),
) -> RetrievalSearchResponse:
    """Top-k semantic search over chunk embeddings with metadata filters.

    Embeds *query* with the configured BGE model, then searches pgvector using
    cosine distance. Filter by source, category, occasion, price_band, segment,
    matched priority signals, and minimum quality score.
    """
    results = search_with_fallback(
        session,
        query_text=body.query,
        top_k=body.top_k,
        filters=body.filters,
    )
    return RetrievalSearchResponse(
        query=body.query,
        top_k=body.top_k,
        filters=body.filters,
        results=results,
    )
