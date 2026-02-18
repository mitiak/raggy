from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.chunk import Chunk
from app.models.document import Document, SourceType
from app.schemas.document import DocumentIngestRequest
from app.services.embedding import EmbeddingService

logger = get_logger(__name__)


class DocumentService:
    def __init__(self, session: AsyncSession, embedding_service: EmbeddingService) -> None:
        self._session = session
        self._embedding_service = embedding_service

    async def ingest_document(self, payload: DocumentIngestRequest) -> Document:
        logger.info(
            "document_ingest_started",
            title=payload.title,
            source_type=payload.source_type,
            source_url=payload.source_url,
        )
        chunks = self._chunk_text(payload.content)
        logger.info("document_chunking_completed", chunk_count=len(chunks))
        embeddings = await self._embedding_service.embed_batch(chunks)
        logger.info("document_embedding_completed", embedding_count=len(embeddings))
        content_hash = self._sha256(payload.content)
        source_type = SourceType(payload.source_type)
        fetched_at = payload.fetched_at or datetime.now(tz=UTC)

        document = Document(
            source_type=source_type,
            source_url=payload.source_url,
            title=payload.title,
            content_hash=content_hash,
            metadata_json=payload.metadata,
            fetched_at=fetched_at,
        )

        document.chunks = [
            Chunk(
                chunk_index=index,
                text=chunk,
                token_count=self._token_count(chunk),
                metadata_json={"source_type": source_type.value, "chunk_index": index},
                embedding=embeddings[index],
                content_hash=self._sha256(chunk),
            )
            for index, chunk in enumerate(chunks)
        ]

        self._session.add(document)
        await self._session.commit()
        await self._session.refresh(document)
        logger.info(
            "document_ingest_completed",
            document_id=str(document.id),
            chunk_count=len(chunks),
        )
        return document

    @staticmethod
    def _chunk_text(content: str, chunk_size: int = 800) -> list[str]:
        normalized = " ".join(content.split())
        if not normalized:
            return [content]
        return [normalized[i : i + chunk_size] for i in range(0, len(normalized), chunk_size)]

    @staticmethod
    def _token_count(text: str) -> int:
        return len(text.split())

    @staticmethod
    def _sha256(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
