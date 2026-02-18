from fastapi import APIRouter, Depends

from app.api.dependencies import get_rag_service
from app.core.logging import get_logger
from app.schemas.query import QueryAnswer, QueryRequest
from app.services.rag_service import RagService

router = APIRouter(prefix="/query", tags=["query"])
logger = get_logger(__name__)


@router.post("", response_model=QueryAnswer)
async def query(
    payload: QueryRequest,
    service: RagService = Depends(get_rag_service),
) -> QueryAnswer:
    logger.info("query_endpoint_started", query=payload.query, top_k=payload.top_k)
    answer = await service.answer(
        query=payload.query,
        top_k=payload.top_k,
        used_filters=payload.used_filters,
    )
    logger.info(
        "query_endpoint_completed",
        citation_count=len(answer.citations),
        retrieve_ms=answer.retrieve_ms,
        gen_ms=answer.gen_ms,
    )
    return answer
