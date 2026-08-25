"""Phase 8 internal data, conversion metric, and PM feedback tables.

Revision ID: 0007_phase8_internal
Revises: 0006_phase7_scaleout
Create Date: 2026-08-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_phase8_internal"
down_revision: Union[str, None] = "0006_phase7_scaleout"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

feedback_verdict = postgresql.ENUM(
    "validated",
    "flagged",
    "needs_review",
    name="feedback_verdict",
)


def upgrade() -> None:
    feedback_verdict.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "wishlist_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_hash", sa.String(length=128), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("segment", sa.String(length=64), nullable=True),
        sa.Column("price_band", sa.String(length=32), nullable=True),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("run_version", sa.String(length=64), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_wishlist_events_user_hash", "wishlist_events", ["user_hash"])
    op.create_index("ix_wishlist_events_event_type", "wishlist_events", ["event_type"])
    op.create_index("ix_wishlist_events_run_version", "wishlist_events", ["run_version"])

    op.create_table(
        "conversion_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_version", sa.String(length=64), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("wishlist_users", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("converted_users", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conversion_rate", sa.Float(), nullable=False),
        sa.Column("cohort_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cohort_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_conversion_snapshots_run_version",
        "conversion_snapshots",
        ["run_version"],
    )

    op.create_table(
        "reason_corroborations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("reason_category", sa.String(length=64), nullable=False),
        sa.Column("public_confidence", sa.Float(), nullable=True),
        sa.Column("public_evidence_volume", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("internal_non_conversion_share", sa.Float(), nullable=True),
        sa.Column("corroboration_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("segment_affinity", postgresql.ARRAY(sa.String(length=64)), nullable=True),
        sa.Column("run_version", sa.String(length=64), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_reason_corroborations_reason_category",
        "reason_corroborations",
        ["reason_category"],
    )
    op.create_index(
        "ix_reason_corroborations_run_version",
        "reason_corroborations",
        ["run_version"],
    )

    op.create_table(
        "insight_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("insight_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason_category", sa.String(length=64), nullable=False),
        sa.Column("verdict", feedback_verdict, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reviewer", sa.String(length=128), nullable=False, server_default="pm"),
        sa.Column("adjusted_confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["insight_id"], ["insights.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_insight_feedback_reason_category", "insight_feedback", ["reason_category"])


def downgrade() -> None:
    op.drop_index("ix_insight_feedback_reason_category", table_name="insight_feedback")
    op.drop_table("insight_feedback")
    op.drop_index("ix_reason_corroborations_run_version", table_name="reason_corroborations")
    op.drop_index("ix_reason_corroborations_reason_category", table_name="reason_corroborations")
    op.drop_table("reason_corroborations")
    op.drop_index("ix_conversion_snapshots_run_version", table_name="conversion_snapshots")
    op.drop_table("conversion_snapshots")
    op.drop_index("ix_wishlist_events_run_version", table_name="wishlist_events")
    op.drop_index("ix_wishlist_events_event_type", table_name="wishlist_events")
    op.drop_index("ix_wishlist_events_user_hash", table_name="wishlist_events")
    op.drop_table("wishlist_events")
    feedback_verdict.drop(op.get_bind(), checkfirst=True)
