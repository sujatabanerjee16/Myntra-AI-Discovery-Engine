"""Initial schema: pgvector extension + core tables.

Creates the ``documents``, ``chunks``, ``insights``, and ``answer_traces``
tables from doc/Architecture.md §5, plus the enum types and the pgvector
extension used for embedding similarity search.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from common.config import get_settings

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = get_settings().embedding_dim

source_type = postgresql.ENUM(
    "play_store",
    "reddit",
    "youtube",
    "product_review",
    "social",
    "research",
    name="source_type",
)
intent_type = postgresql.ENUM(
    "active_shortlist",
    "passive_bookmark",
    name="intent_type",
)
journey_stage = postgresql.ENUM(
    "discovery",
    "consideration",
    "hesitation",
    "postponement",
    "external_comparison",
    "purchase",
    name="journey_stage",
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    bind = op.get_bind()
    source_type.create(bind, checkfirst=True)
    intent_type.create(bind, checkfirst=True)
    journey_stage.create(bind, checkfirst=True)

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", source_type, nullable=False),
        sa.Column("source_ref", sa.String(length=1024), nullable=True),
        sa.Column("author_hash", sa.String(length=128), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("run_version", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_documents_source", "documents", ["source"])
    op.create_index("ix_documents_author_hash", "documents", ["author_hash"])
    op.create_index("ix_documents_run_version", "documents", ["run_version"])

    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("occasion", sa.String(length=64), nullable=True),
        sa.Column("price_band", sa.String(length=32), nullable=True),
        sa.Column("segment", sa.String(length=64), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_category", "chunks", ["category"])
    op.create_index("ix_chunks_occasion", "chunks", ["occasion"])
    op.create_index("ix_chunks_price_band", "chunks", ["price_band"])
    op.create_index("ix_chunks_segment", "chunks", ["segment"])

    op.create_table(
        "insights",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("reason_category", sa.String(length=64), nullable=False),
        sa.Column("intent_type", intent_type, nullable=True),
        sa.Column("journey_stage", journey_stage, nullable=True),
        sa.Column("segment", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column(
            "evidence_chunk_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
        ),
        sa.Column("evidence_volume", sa.Integer(), server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("sources", postgresql.ARRAY(sa.String(length=32)), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_insights_reason_category", "insights", ["reason_category"])
    op.create_index("ix_insights_segment", "insights", ["segment"])
    op.create_index("ix_insights_category", "insights", ["category"])

    op.create_table(
        "answer_traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column(
            "retrieved_chunk_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
        ),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("citations", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("limitations", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("answer_traces")
    op.drop_table("insights")
    op.drop_table("chunks")
    op.drop_table("documents")

    bind = op.get_bind()
    journey_stage.drop(bind, checkfirst=True)
    intent_type.drop(bind, checkfirst=True)
    source_type.drop(bind, checkfirst=True)
