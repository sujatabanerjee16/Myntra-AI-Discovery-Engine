"""Phase 7 source refresh scheduling table.

Revision ID: 0006_phase7_scaleout
Revises: 0005_phase6_observability
Create Date: 2026-08-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_phase7_scaleout"
down_revision: Union[str, None] = "0005_phase6_observability"
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
    op.create_table(
        "source_refresh_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", source_type, nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_refresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_version", sa.String(length=64), nullable=True),
        sa.Column("documents_added", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_source_refresh_states_source",
        "source_refresh_states",
        ["source"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_source_refresh_states_source", table_name="source_refresh_states")
    op.drop_table("source_refresh_states")
