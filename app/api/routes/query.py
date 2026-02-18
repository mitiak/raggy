from fastapi import APIRouter, Depends

from app.api.dependencies import get_retrieval_service
from app.schemas.query import QueryRequest, QueryResponse
from app.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def query(
    payload: QueryRequest,
    service: RetrievalService = Depends(get_retrieval_service),
) -> QueryResponse:
    results = await service.search(query=payload.query, top_k=payload.top_k)
    return QueryResponse(results=results)
