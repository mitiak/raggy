import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentIngestRequest(BaseModel):
    source_type: str = Field(default="md", pattern="^(url|md)$")
    source_url: str | None = Field(default=None, max_length=2048)
    title: str = Field(min_length=1, max_length=512)
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime | None = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: str
    source_url: str | None
    title: str
    content_hash: str
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")
    fetched_at: datetime
