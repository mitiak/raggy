from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_document_service
from app.core.logging import get_logger
from app.schemas.document import DocumentIngestRequest, DocumentResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger(__name__)


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def ingest_document(
    payload: DocumentIngestRequest,
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    logger.info("documents_endpoint_started", title=payload.title, source_type=payload.source_type)
    document = await service.ingest_document(payload)
    logger.info("documents_endpoint_completed", document_id=str(document.id))
    return DocumentResponse.model_validate(document)
