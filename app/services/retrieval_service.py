from __future__ import annotations

from sqlalchemy import Select, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.chunk import Chunk
from app.models.document import Document
from app.schemas.query import QueryResult
from app.services.embedding import EmbeddingService

logger = get_logger(__name__)


class RetrievalService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService,
        ivfflat_probes: int = 100,
    ) -> None:
        self._session = session
        self._embedding_service = embedding_service
        self._ivfflat_probes = max(1, ivfflat_probes)

    async def search(self, query: str, top_k: int) -> list[QueryResult]:
        logger.info(
            "retrieval_started",
            query=query,
            top_k=top_k,
            ivfflat_probes=self._ivfflat_probes,
        )
        vector = await self._embedding_service.embed_text(query)
        logger.info("retrieval_query_embedding_completed", embedding_dim=len(vector))
        await self._session.execute(text(f"SET LOCAL ivfflat.probes = {self._ivfflat_probes}"))
        distance = Chunk.embedding.cosine_distance(vector)

        stmt: Select[tuple[Chunk, Document, float]] = (
            select(Chunk, Document, distance.label("distance"))
            .join(Document, Chunk.doc_id == Document.id)
            .order_by(distance)
            .limit(top_k)
        )
        rows = (await self._session.execute(stmt)).all()
        logger.info("retrieval_vector_search_completed", candidate_count=len(rows))

        results: list[QueryResult] = []
        for chunk, document, dist in rows:
            score = 1.0 - float(dist)
            results.append(
                QueryResult(
                    chunk_id=chunk.id,
                    document_id=chunk.doc_id,
                    content=chunk.text,
                    title=document.title,
                    url=document.source_url,
                    score=max(min(score, 1.0), 0.0),
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        logger.info("retrieval_completed", result_count=len(results))
        return results
