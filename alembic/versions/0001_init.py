"""Initial schema for documents, chunks, and ingest jobs."""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_init"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    source_type_enum = postgresql.ENUM("url", "md", name="source_type_enum")
    ingest_job_status_enum = postgresql.ENUM(
        "pending",
        "running",
        "success",
        "failure",
        name="ingest_job_status_enum",
    )
    source_type_enum.create(op.get_bind(), checkfirst=True)
    ingest_job_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "source_type",
            postgresql.ENUM("url", "md", name="source_type_enum", create_type=False),
            nullable=False,
            server_default=sa.text("'md'"),
        ),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"], unique=False)
    op.create_index(
        "ix_documents_metadata_gin",
        "documents",
        ["metadata"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("doc_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1536), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["doc_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("doc_id", "chunk_index", name="uq_chunks_doc_id_chunk_index"),
    )
    op.create_index("ix_chunks_doc_id", "chunks", ["doc_id"], unique=False)
    op.create_index("ix_chunks_content_hash", "chunks", ["content_hash"], unique=False)
    op.create_index(
        "ix_chunks_metadata_gin",
        "chunks",
        ["metadata"],
        unique=False,
        postgresql_using="gin",
    )
    op.execute(
        "CREATE INDEX ix_chunks_embedding_ivfflat ON chunks USING ivfflat "
        "(embedding vector_cosine_ops) WITH (lists = 100)"
    )

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
    op.drop_table("ingest_jobs")

    op.drop_index("ix_chunks_embedding_ivfflat", table_name="chunks")
    op.drop_index("ix_chunks_metadata_gin", table_name="chunks")
    op.drop_index("ix_chunks_content_hash", table_name="chunks")
    op.drop_index("ix_chunks_doc_id", table_name="chunks")
    op.drop_table("chunks")

    op.drop_index("ix_documents_metadata_gin", table_name="documents")
    op.drop_index("ix_documents_content_hash", table_name="documents")
    op.drop_table("documents")

    sa.Enum(name="ingest_job_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="source_type_enum").drop(op.get_bind(), checkfirst=True)
