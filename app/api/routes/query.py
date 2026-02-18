from fastapi import APIRouter, Depends

from app.api.dependencies import get_retrieval_service
from app.core.logging import get_logger
from app.schemas.query import Citation, QueryAnswer, QueryRequest
from app.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/query", tags=["query"])
logger = get_logger(__name__)


@router.post("", response_model=QueryAnswer)
async def query(
    payload: QueryRequest,
    service: RetrievalService = Depends(get_retrieval_service),
) -> QueryAnswer:
    logger.info("query_endpoint_started", query=payload.query, top_k=payload.top_k)
    results = await service.search(
        query=payload.query,
        top_k=payload.top_k,
        used_filters=payload.used_filters,
    )
    logger.info("query_endpoint_completed", result_count=len(results))
    if not results:
        return QueryAnswer(
            answer="I don't know based on the provided documents.",
            citations=[],
            used_filters=payload.used_filters,
            confidence=0.0,
        )

    top_result = results[0]
    citations = [
        Citation(
            doc_id=result.document_id,
            chunk_id=result.chunk_id,
            title=result.title,
            url=result.url,
            score=result.score,
        )
        for result in results
    ]
    return QueryAnswer(
        answer=top_result.content,
        citations=citations,
        used_filters=payload.used_filters,
        confidence=top_result.score,
    )
