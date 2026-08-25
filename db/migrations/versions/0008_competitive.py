"""Competitive analysis columns and aggregates.

Revision ID: 0008_competitive
Revises: 0007_phase8_internal
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_competitive"
down_revision: Union[str, None] = "0007_phase8_internal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chunks", sa.Column("platforms", postgresql.ARRAY(sa.String(length=32)), nullable=True))
    op.add_column(
        "chunks",
        sa.Column("wishlist_motives", postgresql.ARRAY(sa.String(length=64)), nullable=True),
    )
    op.add_column("chunks", sa.Column("platform_attribution_confidence", sa.Float(), nullable=True))

    op.add_column("insights", sa.Column("platforms", postgresql.ARRAY(sa.String(length=32)), nullable=True))
    op.add_column("insights", sa.Column("wishlist_motive", sa.String(length=64), nullable=True))
    op.add_column("insights", sa.Column("comparison_scope", sa.String(length=32), nullable=True))
    op.create_index("ix_insights_wishlist_motive", "insights", ["wishlist_motive"])

    op.create_table(
        "competitive_aggregates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("metric_type", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("share", sa.Float(), nullable=True),
        sa.Column("evidence_volume", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("shared_vs_unique", sa.String(length=32), nullable=True),
        sa.Column("sources", postgresql.ARRAY(sa.String(length=32)), nullable=True),
        sa.Column("run_version", sa.String(length=64), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_competitive_aggregates_platform", "competitive_aggregates", ["platform"])
    op.create_index("ix_competitive_aggregates_metric_type", "competitive_aggregates", ["metric_type"])
    op.create_index("ix_competitive_aggregates_label", "competitive_aggregates", ["label"])
    op.create_index("ix_competitive_aggregates_run_version", "competitive_aggregates", ["run_version"])


def downgrade() -> None:
    op.drop_index("ix_competitive_aggregates_run_version", table_name="competitive_aggregates")
    op.drop_index("ix_competitive_aggregates_label", table_name="competitive_aggregates")
    op.drop_index("ix_competitive_aggregates_metric_type", table_name="competitive_aggregates")
    op.drop_index("ix_competitive_aggregates_platform", table_name="competitive_aggregates")
    op.drop_table("competitive_aggregates")

    op.drop_index("ix_insights_wishlist_motive", table_name="insights")
    op.drop_column("insights", "comparison_scope")
    op.drop_column("insights", "wishlist_motive")
    op.drop_column("insights", "platforms")

    op.drop_column("chunks", "platform_attribution_confidence")
    op.drop_column("chunks", "wishlist_motives")
    op.drop_column("chunks", "platforms")
