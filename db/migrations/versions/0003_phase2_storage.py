"""Phase 2 storage layer: chunk metadata, analytical tables, vector index."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_phase2_storage"
down_revision: Union[str, None] = "0002_document_source_ref_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

source_type = postgresql.ENUM(
    "play_store",
    "reddit",
    "youtube",
    "product_review",
    "social",
    "research",
    name="source_type",
    create_type=False,
)


def upgrade() -> None:
    op.add_column(
        "chunks",
        sa.Column("chunk_index", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "chunks",
        sa.Column("matched_signals", postgresql.ARRAY(sa.String(length=64)), nullable=True),
    )

    op.create_table(
        "source_aggregates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", source_type, nullable=False),
        sa.Column("document_count", sa.Integer(), server_default="0"),
        sa.Column("chunk_count", sa.Integer(), server_default="0"),
        sa.Column("avg_quality_score", sa.Float(), nullable=True),
        sa.Column("run_version", sa.String(length=64), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_source_aggregates_source", "source_aggregates", ["source"])
    op.create_index("ix_source_aggregates_run_version", "source_aggregates", ["run_version"])

    op.create_table(
        "signal_aggregates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("signal", sa.String(length=64), nullable=False),
        sa.Column("chunk_count", sa.Integer(), server_default="0"),
        sa.Column("document_count", sa.Integer(), server_default="0"),
        sa.Column("run_version", sa.String(length=64), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_signal_aggregates_signal", "signal_aggregates", ["signal"])
    op.create_index("ix_signal_aggregates_run_version", "signal_aggregates", ["run_version"])

    op.create_table(
        "dimension_aggregates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("segment", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("occasion", sa.String(length=64), nullable=True),
        sa.Column("price_band", sa.String(length=32), nullable=True),
        sa.Column("chunk_count", sa.Integer(), server_default="0"),
        sa.Column("run_version", sa.String(length=64), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_dimension_aggregates_segment", "dimension_aggregates", ["segment"])
    op.create_index("ix_dimension_aggregates_category", "dimension_aggregates", ["category"])
    op.create_index("ix_dimension_aggregates_run_version", "dimension_aggregates", ["run_version"])

    # pgvector cosine index for top-k similarity search
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw
        ON chunks USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    op.drop_table("dimension_aggregates")
    op.drop_table("signal_aggregates")
    op.drop_table("source_aggregates")
    op.drop_column("chunks", "matched_signals")
    op.drop_column("chunks", "chunk_index")
