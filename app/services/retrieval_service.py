from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.schemas.query import QueryResult
from app.services.embedding import EmbeddingService


class RetrievalService:
    def __init__(self, session: AsyncSession, embedding_service: EmbeddingService) -> None:
        self._session = session
        self._embedding_service = embedding_service

    async def search(self, query: str, top_k: int) -> list[QueryResult]:
        vector = await self._embedding_service.embed_text(query)
        distance = Chunk.embedding.cosine_distance(vector)

        stmt: Select[tuple[Chunk, float]] = (
            select(Chunk, distance.label("distance")).order_by(distance).limit(top_k)
        )
        rows = (await self._session.execute(stmt)).all()

        results: list[QueryResult] = []
        for chunk, dist in rows:
            score = 1.0 - float(dist)
            results.append(
                QueryResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    score=max(min(score, 1.0), 0.0),
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        return results
