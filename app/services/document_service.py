from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
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
        source_type = SourceType(payload.source_type)
        content_hash = self._sha256(payload.content)
        existing_document = await self._find_existing_document(
            source_type=source_type,
            source_url=payload.source_url,
            content_hash=content_hash,
        )
        if existing_document is not None:
            logger.info(
                "document_ingest_skipped_existing",
                document_id=str(existing_document.id),
                content_hash=content_hash,
            )
            return existing_document

        chunks = self._chunk_text(payload.content)
        logger.info("document_chunking_completed", chunk_count=len(chunks))
        embeddings = await self._embedding_service.embed_batch(chunks)
        logger.info("document_embedding_completed", embedding_count=len(embeddings))
        fetched_at = payload.fetched_at or datetime.now(tz=UTC)
        doc_id = uuid.uuid4()

        document = Document(
            id=doc_id,
            source_type=source_type,
            source_url=payload.source_url,
            title=payload.title,
            content_hash=content_hash,
            metadata_json=payload.metadata,
            fetched_at=fetched_at,
        )

        document.chunks = [
            Chunk(
                id=self._deterministic_chunk_id(doc_id=doc_id, chunk_index=index, text=chunk),
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

    async def _find_existing_document(
        self,
        *,
        source_type: SourceType,
        source_url: str | None,
        content_hash: str,
    ) -> Document | None:
        stmt = select(Document).where(
            Document.source_type == source_type,
            Document.content_hash == content_hash,
        )
        if source_url is None:
            stmt = stmt.where(Document.source_url.is_(None))
        else:
            stmt = stmt.where(Document.source_url == source_url)
        rows = await self._session.scalars(stmt)
        return rows.one_or_none()

    @staticmethod
    def _chunk_text(
        content: str,
        chunk_size_tokens: int = 1000,
        overlap_ratio: float = 0.12,
    ) -> list[str]:
        normalized = " ".join(content.split())
        if not normalized:
            return [content]

        tokens = normalized.split(" ")
        if len(tokens) <= chunk_size_tokens:
            return [normalized]

        overlap_tokens = max(1, int(chunk_size_tokens * overlap_ratio))
        step = max(1, chunk_size_tokens - overlap_tokens)

        chunks: list[str] = []
        for start in range(0, len(tokens), step):
            chunk_tokens = tokens[start : start + chunk_size_tokens]
            if not chunk_tokens:
                break
            chunks.append(" ".join(chunk_tokens))
            if start + chunk_size_tokens >= len(tokens):
                break
        return chunks

    @staticmethod
    def _token_count(text: str) -> int:
        return len(text.split())

    @staticmethod
    def _sha256(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _deterministic_chunk_id(doc_id: uuid.UUID, chunk_index: int, text: str) -> uuid.UUID:
        seed = f"{doc_id}:{chunk_index}:{text}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        return uuid.UUID(hex=digest[:32])
