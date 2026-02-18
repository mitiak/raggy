from fastapi import APIRouter, Depends

from app.api.dependencies import get_retrieval_service
from app.core.logging import get_logger
from app.schemas.query import QueryRequest, QueryResponse
from app.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/query", tags=["query"])
logger = get_logger(__name__)


@router.post("", response_model=QueryResponse)
async def query(
    payload: QueryRequest,
    service: RetrievalService = Depends(get_retrieval_service),
) -> QueryResponse:
    logger.info("query_endpoint_started", query=payload.query, top_k=payload.top_k)
    results = await service.search(query=payload.query, top_k=payload.top_k)
    logger.info("query_endpoint_completed", result_count=len(results))
    return QueryResponse(results=results)
