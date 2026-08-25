"""Phase 3 semantic analytics: insight run_version, reason aggregates, theme clusters."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_phase3_semantic"
down_revision: Union[str, None] = "0003_phase2_storage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("insights", sa.Column("run_version", sa.String(length=64), nullable=True))
    op.create_index("ix_insights_run_version", "insights", ["run_version"])

    op.create_table(
        "reason_aggregates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("reason_category", sa.String(length=64), nullable=False),
        sa.Column("evidence_volume", sa.Integer(), server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("sources", postgresql.ARRAY(sa.String(length=32)), nullable=True),
        sa.Column("active_shortlist_count", sa.Integer(), server_default="0"),
        sa.Column("passive_bookmark_count", sa.Integer(), server_default="0"),
        sa.Column("run_version", sa.String(length=64), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_reason_aggregates_reason_category", "reason_aggregates", ["reason_category"])
    op.create_index("ix_reason_aggregates_run_version", "reason_aggregates", ["run_version"])

    op.create_table(
        "theme_clusters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cluster_key", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=256), nullable=False),
        sa.Column("reason_category", sa.String(length=64), nullable=True),
        sa.Column("chunk_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column("evidence_volume", sa.Integer(), server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("sources", postgresql.ARRAY(sa.String(length=32)), nullable=True),
        sa.Column("run_version", sa.String(length=64), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_theme_clusters_cluster_key", "theme_clusters", ["cluster_key"])
    op.create_index("ix_theme_clusters_run_version", "theme_clusters", ["run_version"])


def downgrade() -> None:
    op.drop_table("theme_clusters")
    op.drop_table("reason_aggregates")
    op.drop_index("ix_insights_run_version", table_name="insights")
    op.drop_column("insights", "run_version")
