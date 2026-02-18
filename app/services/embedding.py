from __future__ import annotations

import hashlib
from typing import Protocol

from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService(Protocol):
    async def embed_text(self, text: str) -> list[float]:
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...


class HashEmbeddingService:
    def __init__(self, dimension: int = 1536) -> None:
        self.dimension = dimension

    async def embed_text(self, text: str) -> list[float]:
        logger.info("embedding_text_started", input_length=len(text), dimension=self.dimension)
        digest = hashlib.sha512(text.encode("utf-8")).digest()
        values = [((digest[i % len(digest)] / 255.0) * 2.0) - 1.0 for i in range(self.dimension)]
        logger.info("embedding_text_completed", dimension=len(values))
        return values

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        logger.info("embedding_batch_started", item_count=len(texts), dimension=self.dimension)
        embeddings = [await self.embed_text(text) for text in texts]
        logger.info("embedding_batch_completed", item_count=len(embeddings))
        return embeddings
