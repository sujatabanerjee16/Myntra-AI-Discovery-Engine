"""Generate BGE embeddings for text chunks."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from common.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embedding_model() -> Any:
    # Lazy import: keep API boot working on lean deploys without torch/ST.
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    logger.info("Loading embedding model: %s", settings.embedding_model)
    return SentenceTransformer(settings.embedding_model)


def embed_texts(texts: list[str], *, batch_size: int = 16) -> list[list[float]]:
    if not texts:
        return []

    from common.cache import get_cached_embedding, set_cached_embedding

    results: list[list[float] | None] = [None] * len(texts)
    pending_indices: list[int] = []
    pending_texts: list[str] = []

    for index, text in enumerate(texts):
        cached = get_cached_embedding(text)
        if cached is not None:
            results[index] = cached
        else:
            pending_indices.append(index)
            pending_texts.append(text)

    if pending_texts:
        model = get_embedding_model()
        vectors = model.encode(
            pending_texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(pending_texts) > 32,
        )
        for idx, vector in zip(pending_indices, vectors, strict=True):
            as_list = vector.tolist()
            set_cached_embedding(texts[idx], as_list)
            results[idx] = as_list

    return results  # type: list[list[float]]
