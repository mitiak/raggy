from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.document import DocumentIngestRequest
from app.services.document_service import DocumentService


class FakeEmbeddingService:
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[float(index), 0.5] for index, _ in enumerate(texts)]


@pytest.mark.asyncio
async def test_ingest_document_persists_document_and_chunks() -> None:
    session = Mock(spec=AsyncSession)
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

    session.add.assert_called_once_with(document)
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
