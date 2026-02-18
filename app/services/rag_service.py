from __future__ import annotations

from app.core.logging import get_logger
from app.schemas.query import Citation, QueryAnswer, UsedFilters
from app.services.retrieval_service import RetrievalService

logger = get_logger(__name__)


class RagService:
    def __init__(self, retrieval_service: RetrievalService) -> None:
        self._retrieval_service = retrieval_service

    async def answer(self, query: str, top_k: int, used_filters: UsedFilters) -> QueryAnswer:
        # Week-1 policy: retrieve a larger candidate pool, answer from top context slices.
        retrieval_top_k = max(20, top_k)
        logger.info(
            "rag_answer_started",
            query=query,
            requested_top_k=top_k,
            retrieval_top_k=retrieval_top_k,
            used_filters=used_filters.model_dump(mode="json"),
        )
        results = await self._retrieval_service.search(
            query=query,
            top_k=retrieval_top_k,
            used_filters=used_filters,
        )

        if not results:
            logger.info("rag_answer_completed", result_count=0, confidence=0.0)
            return QueryAnswer(
                answer="I don't know based on the provided documents.",
                citations=[],
                used_filters=used_filters,
                confidence=0.0,
            )

        context_size = min(max(6, top_k), 10)
        selected = results[:context_size]

        citations = [
            Citation(
                doc_id=result.document_id,
                chunk_id=result.chunk_id,
                title=result.title,
                url=result.url,
                score=result.score,
            )
            for result in selected
        ]

        # For now, keep generation extractive to guarantee grounding in provided chunks.
        answer_text = selected[0].content
        confidence = sum(item.score for item in selected) / len(selected)

        logger.info(
            "rag_answer_completed",
            result_count=len(results),
            selected_count=len(selected),
            confidence=round(confidence, 4),
        )
        return QueryAnswer(
            answer=answer_text,
            citations=citations,
            used_filters=used_filters,
            confidence=confidence,
        )
