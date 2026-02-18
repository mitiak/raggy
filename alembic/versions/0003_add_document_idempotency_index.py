"""Add document idempotency unique index for upsert/dedup behavior."""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_doc_idempotency"
down_revision: str | None = "0002_add_ingest_jobs_if_missing"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_idempotency "
        "ON documents (source_type, COALESCE(source_url, ''), content_hash)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_documents_idempotency")
