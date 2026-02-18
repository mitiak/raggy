from __future__ import annotations

from typing import Any

import pytest

from app import cli


def test_db_preferred_column_returns_first_match() -> None:
    columns = {"created_at", "title", "content_hash"}

    result = cli._db_preferred_column(columns, "fetched_at", "created_at")

    assert result == "created_at"


@pytest.mark.asyncio
async def test_db_chunks_doc_fk_column_prefers_doc_id(monkeypatch: Any) -> None:
    async def fake_table_columns(_: str) -> set[str]:
        return {"doc_id", "document_id"}

    monkeypatch.setattr(cli, "_db_table_columns", fake_table_columns)

    result = await cli._db_chunks_doc_fk_column()

    assert result == "doc_id"


@pytest.mark.asyncio
async def test_db_chunks_doc_fk_column_returns_none_when_missing(monkeypatch: Any) -> None:
    async def fake_table_columns(_: str) -> set[str]:
        return {"id", "chunk_index"}

    monkeypatch.setattr(cli, "_db_table_columns", fake_table_columns)

    result = await cli._db_chunks_doc_fk_column()

    assert result is None
