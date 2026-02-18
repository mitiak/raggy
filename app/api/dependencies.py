from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.services.document_service import DocumentService
from app.services.embedding import EmbeddingService, HashEmbeddingService
from app.services.retrieval_service import RetrievalService

_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        settings = get_settings()
        _embedding_service = HashEmbeddingService(dimension=settings.embedding_dim)
    return _embedding_service


def get_document_service(
    session: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> DocumentService:
    return DocumentService(session=session, embedding_service=embedding_service)


def get_retrieval_service(
    session: AsyncSession = Depends(get_db_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> RetrievalService:
    return RetrievalService(session=session, embedding_service=embedding_service)
