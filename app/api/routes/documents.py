from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_document_service
from app.schemas.document import DocumentIngestRequest, DocumentResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def ingest_document(
    payload: DocumentIngestRequest,
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    document = await service.ingest_document(payload)
    return DocumentResponse.model_validate(document)
