"""Tests for retrieval filter application (no database)."""

from sqlalchemy import select

from common.models import Chunk, Document, SourceType
from storage.retrieval import RetrievalQuery, apply_retrieval_filters, build_retrieval_statement
from storage.schemas import RetrievalFilters


def test_build_retrieval_statement_has_limit():
    stmt = build_retrieval_statement(RetrievalQuery(embedding=[0.1] * 8, top_k=5, filters=None))
    assert stmt._limit == 5  # noqa: SLF001


def test_apply_source_filter():
    stmt = select(Chunk, Document).join(Document)
    filtered = apply_retrieval_filters(
        stmt,
        RetrievalFilters(source=SourceType.research),
    )
    sql = str(filtered.compile(compile_kwargs={"literal_binds": True}))
    assert "documents.source" in sql
    assert "research" in sql


def test_apply_metadata_filters():
    stmt = select(Chunk, Document).join(Document)
    filtered = apply_retrieval_filters(
        stmt,
        RetrievalFilters(
            category="clothing",
            segment="price_sensitive",
            signals=["price_sensitivity_waiting"],
            min_quality_score=0.5,
        ),
    )
    sql = str(filtered.compile(compile_kwargs={"literal_binds": True}))
    assert "chunks.category" in sql
    assert "chunks.segment" in sql
    assert "matched_signals" in sql
    assert "quality_score" in sql
