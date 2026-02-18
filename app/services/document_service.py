from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.models.document import Document
from app.schemas.document import DocumentIngestRequest
from app.services.embedding import EmbeddingService


class DocumentService:
    def __init__(self, session: AsyncSession, embedding_service: EmbeddingService) -> None:
        self._session = session
        self._embedding_service = embedding_service

    async def ingest_document(self, payload: DocumentIngestRequest) -> Document:
        chunks = self._chunk_text(payload.content)
        embeddings = await self._embedding_service.embed_batch(chunks)

        document = Document(
            external_id=payload.external_id,
            title=payload.title,
            content=payload.content,
            metadata_json=payload.metadata,
        )

        document.chunks = [
            Chunk(content=chunk, chunk_index=index, embedding=embeddings[index])
            for index, chunk in enumerate(chunks)
        ]

        self._session.add(document)
        await self._session.commit()
        await self._session.refresh(document)
        return document

    @staticmethod
    def _chunk_text(content: str, chunk_size: int = 800) -> list[str]:
        normalized = " ".join(content.split())
        if not normalized:
            return [content]
        return [normalized[i : i + chunk_size] for i in range(0, len(normalized), chunk_size)]
