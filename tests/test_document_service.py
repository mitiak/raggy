from __future__ import annotations

import hashlib
import uuid
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.document import DocumentIngestRequest
from app.services.document_service import DocumentService


class FakeEmbeddingService:
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[float(index), 0.5] for index, _ in enumerate(texts)]


class _FakeScalarsResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def one_or_none(self) -> object | None:
        return self._value


@pytest.mark.asyncio
async def test_ingest_document_persists_document_and_chunks() -> None:
    session = Mock(spec=AsyncSession)
    session.add = Mock()
    session.scalars = AsyncMock(return_value=_FakeScalarsResult(None))
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    service = DocumentService(session=session, embedding_service=FakeEmbeddingService())
    payload = DocumentIngestRequest(
        source_type="url",
        source_url="https://example.com/post",
        title="Post",
        content="alpha beta gamma",
        metadata={"team": "search"},
    )

    document = await service.ingest_document(payload)

    assert document.title == "Post"
    assert document.source_type.value == "url"
    assert document.source_url == "https://example.com/post"
    assert document.metadata_json == {"team": "search"}
    assert document.content_hash == hashlib.sha256(b"alpha beta gamma").hexdigest()

    assert len(document.chunks) == 1
    first_chunk = document.chunks[0]
    assert first_chunk.chunk_index == 0
    assert first_chunk.text == "alpha beta gamma"
    assert first_chunk.token_count == 3
    assert first_chunk.metadata_json == {"source_type": "url", "chunk_index": 0}
    assert first_chunk.embedding == [0.0, 0.5]
    assert first_chunk.id == DocumentService._deterministic_chunk_id(
        doc_id=document.id,
        chunk_index=0,
        text="alpha beta gamma",
    )

    session.add.assert_called_once_with(document)
    session.scalars.assert_awaited_once()
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(document)


def test_chunk_text_normalizes_whitespace() -> None:
    chunked = DocumentService._chunk_text("a   b\n\n c", chunk_size=4)
    assert chunked == ["a b ", "c"]


def test_chunk_text_keeps_original_when_only_whitespace() -> None:
    chunked = DocumentService._chunk_text("   \n\t   ")
    assert chunked == ["   \n\t   "]


def test_token_count_and_hash_helpers() -> None:
    assert DocumentService._token_count("one two three") == 3
    assert DocumentService._sha256("abc") == hashlib.sha256(b"abc").hexdigest()


def test_deterministic_chunk_id_stable() -> None:
    doc_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    first = DocumentService._deterministic_chunk_id(doc_id=doc_id, chunk_index=1, text="duck")
    second = DocumentService._deterministic_chunk_id(doc_id=doc_id, chunk_index=1, text="duck")
    assert first == second


@pytest.mark.asyncio
async def test_ingest_document_returns_existing_without_reinserting() -> None:
    session = Mock(spec=AsyncSession)
    existing_document = Mock()
    existing_document.id = uuid.uuid4()
    session.scalars = AsyncMock(return_value=_FakeScalarsResult(existing_document))
    session.add = Mock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    service = DocumentService(session=session, embedding_service=FakeEmbeddingService())
    payload = DocumentIngestRequest(
        source_type="url",
        source_url="https://example.com/post",
        title="Post",
        content="alpha beta gamma",
        metadata={"team": "search"},
    )

    result = await service.ingest_document(payload)

    assert result is existing_document
    session.add.assert_not_called()
    session.commit.assert_not_awaited()
    session.refresh.assert_not_awaited()
