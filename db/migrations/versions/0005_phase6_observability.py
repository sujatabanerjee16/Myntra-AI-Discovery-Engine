"""Phase 6 observability tables and AnswerTrace extensions.

Revision ID: 0005_phase6_observability
Revises: 0004_phase3_semantic
Create Date: 2026-08-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_phase6_observability"
down_revision: Union[str, None] = "0004_phase3_semantic"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("answer_traces", sa.Column("duration_ms", sa.Float(), nullable=True))
    op.add_column(
        "answer_traces",
        sa.Column("insufficient_evidence", sa.Boolean(), nullable=True, server_default="false"),
    )

    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_type", sa.String(length=32), nullable=False),
        sa.Column("run_version", sa.String(length=64), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("stats", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_pipeline_runs_run_type", "pipeline_runs", ["run_type"])
    op.create_index("ix_pipeline_runs_run_version", "pipeline_runs", ["run_version"])

    op.create_table(
        "eval_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_version", sa.String(length=64), nullable=False),
        sa.Column("retrieval_hit_at_k", sa.Float(), nullable=True),
        sa.Column("retrieval_mrr", sa.Float(), nullable=True),
        sa.Column("faithfulness_score", sa.Float(), nullable=True),
        sa.Column("taxonomy_accuracy", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("report", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_eval_runs_run_version", "eval_runs", ["run_version"])


def downgrade() -> None:
    op.drop_index("ix_eval_runs_run_version", table_name="eval_runs")
    op.drop_table("eval_runs")
    op.drop_index("ix_pipeline_runs_run_version", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_run_type", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
    op.drop_column("answer_traces", "insufficient_evidence")
    op.drop_column("answer_traces", "duration_ms")
