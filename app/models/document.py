import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.chunk import Chunk


class SourceType(StrEnum):
    URL = "url"
    MD = "md"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(
            SourceType,
            name="source_type_enum",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=SourceType.MD,
        server_default=SourceType.MD.value,
    )
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )
