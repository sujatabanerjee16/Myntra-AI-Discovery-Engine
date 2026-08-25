"""Tests for embedding and retrieval caches."""

from common.cache import (
    get_cached_embedding,
    get_cached_retrieval,
    get_cost_control_snapshot,
    reset_caches,
    retrieval_cache_key,
    set_cached_embedding,
    set_cached_retrieval,
)


def test_embedding_cache_roundtrip():
    reset_caches()
    text = "sample chunk for embedding cache"
    vector = [0.1, 0.2, 0.3]
    assert get_cached_embedding(text) is None
    set_cached_embedding(text, vector)
    assert get_cached_embedding(text) == vector


def test_retrieval_cache_roundtrip():
    reset_caches()
    key = retrieval_cache_key(query_text="why price", top_k=5, filters={"source": "research"})
    payload = [{"chunk_id": "abc", "text": "waiting for sale"}]
    assert get_cached_retrieval(key) is None
    set_cached_retrieval(key, payload)
    assert get_cached_retrieval(key) == payload


def test_cost_control_snapshot_tracks_hits():
    reset_caches()
    text = "another cached text"
    set_cached_embedding(text, [0.5, 0.6])
    get_cached_embedding(text)
    get_cached_embedding("missing")
    snapshot = get_cost_control_snapshot()
    assert snapshot.embedding_cache["hits"] == 1
    assert snapshot.embedding_cache["misses"] == 1
