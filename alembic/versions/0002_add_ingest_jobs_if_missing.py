"""Add ingest_jobs table when migrating from older 0001 schemas."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_add_ingest_jobs_if_missing"
down_revision: str | None = "0001_init"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    ingest_job_status_enum = postgresql.ENUM(
        "pending",
        "running",
        "success",
        "failure",
        name="ingest_job_status_enum",
    )
    ingest_job_status_enum.create(bind, checkfirst=True)

    if inspector.has_table("ingest_jobs"):
        return

    op.create_table(
        "ingest_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "running",
                "success",
                "failure",
                name="ingest_job_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("docs_processed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("chunks_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("ingest_jobs"):
        op.drop_table("ingest_jobs")

    postgresql.ENUM(name="ingest_job_status_enum").drop(bind, checkfirst=True)
