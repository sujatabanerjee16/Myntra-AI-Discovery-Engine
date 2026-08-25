"""Add unique constraint on documents (source, source_ref) for idempotent ingestion."""

from typing import Sequence, Union

from alembic import op

revision: str = "0002_document_source_ref_unique"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_documents_source_source_ref",
        "documents",
        ["source", "source_ref"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_documents_source_source_ref", "documents", type_="unique")
