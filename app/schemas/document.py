import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentIngestRequest(BaseModel):
    external_id: str | None = Field(default=None, max_length=255)
    title: str = Field(min_length=1, max_length=512)
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_id: str | None
    title: str
    content: str
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")
    created_at: datetime
