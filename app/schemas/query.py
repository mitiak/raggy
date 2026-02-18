from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    used_filters: UsedFilters = Field(default_factory=lambda: UsedFilters())


class UsedFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: str | None = None
    version: str | None = None
    lang: str | None = None
    source: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: uuid.UUID
    chunk_id: uuid.UUID
    title: str
    url: str | None
    page: int | None = None
    score: float = Field(ge=0.0, le=1.0)


class QueryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    title: str
    url: str | None
    score: float = Field(ge=0.0, le=1.0)


class QueryAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[Citation]
    used_filters: UsedFilters
    confidence: float = Field(ge=0.0, le=1.0)
    retrieve_ms: float = Field(ge=0.0)
    gen_ms: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_claims_have_citations(self) -> QueryAnswer:
        normalized = self.answer.strip().lower()
        unknown_markers = (
            "i don't know",
            "i do not know",
            "not enough information",
        )
        if any(marker in normalized for marker in unknown_markers):
            return self
        if not self.citations:
            raise ValueError("Claims must include at least one citation.")
        return self
