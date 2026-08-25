"""Cost-control caches for embeddings and retrieval results."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from common.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """Hit/miss counters for observability dashboards."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    entries: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total else 0.0

    def to_dict(self) -> dict[str, int | float]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "entries": self.entries,
            "hit_rate": self.hit_rate,
        }


class _LRUCache:
    """Thread-safe TTL LRU cache keyed by string."""

    def __init__(self, *, max_entries: int, ttl_seconds: int) -> None:
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = Lock()
        self.stats = CacheStats()

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                self.stats.misses += 1
                return None

            expires_at, value = item
            if expires_at <= time.monotonic():
                del self._store[key]
                self.stats.misses += 1
                self.stats.entries = len(self._store)
                return None

            self._store.move_to_end(key)
            self.stats.hits += 1
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (time.monotonic() + self._ttl_seconds, value)
            while len(self._store) > self._max_entries:
                self._store.popitem(last=False)
                self.stats.evictions += 1
            self.stats.entries = len(self._store)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self.stats.entries = 0


_embedding_cache: _LRUCache | None = None
_retrieval_cache: _LRUCache | None = None


def _embedding_cache_instance() -> _LRUCache:
    global _embedding_cache
    if _embedding_cache is None:
        settings = get_settings()
        _embedding_cache = _LRUCache(
            max_entries=settings.embedding_cache_max_entries,
            ttl_seconds=settings.embedding_cache_ttl_seconds,
        )
    return _embedding_cache


def _retrieval_cache_instance() -> _LRUCache:
    global _retrieval_cache
    if _retrieval_cache is None:
        settings = get_settings()
        _retrieval_cache = _LRUCache(
            max_entries=settings.retrieval_cache_max_entries,
            ttl_seconds=settings.retrieval_cache_ttl_seconds,
        )
    return _retrieval_cache


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_cached_embedding(text: str) -> list[float] | None:
    """Return a cached embedding vector when caching is enabled."""
    settings = get_settings()
    if not settings.embedding_cache_enabled:
        return None
    return _embedding_cache_instance().get(_hash_text(text))


def set_cached_embedding(text: str, vector: list[float]) -> None:
    """Store an embedding vector in the cache."""
    settings = get_settings()
    if not settings.embedding_cache_enabled:
        return
    _embedding_cache_instance().set(_hash_text(text), vector)


def retrieval_cache_key(
    *,
    query_text: str,
    top_k: int,
    filters: dict[str, Any] | None,
) -> str:
    payload = {"query": query_text, "top_k": top_k, "filters": filters or {}}
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_cached_retrieval(key: str) -> list[dict[str, Any]] | None:
    settings = get_settings()
    if not settings.retrieval_cache_enabled:
        return None
    return _retrieval_cache_instance().get(key)


def set_cached_retrieval(key: str, chunks: list[dict[str, Any]]) -> None:
    settings = get_settings()
    if not settings.retrieval_cache_enabled:
        return
    _retrieval_cache_instance().set(key, chunks)


@dataclass
class CostControlSnapshot:
    embedding_cache: dict[str, int | float] = field(default_factory=dict)
    retrieval_cache: dict[str, int | float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, dict[str, int | float]]:
        return {
            "embedding_cache": self.embedding_cache,
            "retrieval_cache": self.retrieval_cache,
        }


def get_cost_control_snapshot() -> CostControlSnapshot:
    """Return current cache hit/miss stats for dashboards."""
    settings = get_settings()
    snapshot = CostControlSnapshot()

    if settings.embedding_cache_enabled:
        snapshot.embedding_cache = _embedding_cache_instance().stats.to_dict()
    if settings.retrieval_cache_enabled:
        snapshot.retrieval_cache = _retrieval_cache_instance().stats.to_dict()

    return snapshot


def reset_caches() -> None:
    """Clear all caches (useful in tests)."""
    global _embedding_cache, _retrieval_cache
    if _embedding_cache is not None:
        _embedding_cache._store.clear()
        _embedding_cache.stats = CacheStats()
    if _retrieval_cache is not None:
        _retrieval_cache._store.clear()
        _retrieval_cache.stats = CacheStats()
