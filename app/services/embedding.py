from __future__ import annotations

import hashlib
from typing import Protocol


class EmbeddingService(Protocol):
    async def embed_text(self, text: str) -> list[float]:
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...


class HashEmbeddingService:
    def __init__(self, dimension: int = 1536) -> None:
        self.dimension = dimension

    async def embed_text(self, text: str) -> list[float]:
        digest = hashlib.sha512(text.encode("utf-8")).digest()
        values = [((digest[i % len(digest)] / 255.0) * 2.0) - 1.0 for i in range(self.dimension)]
        return values

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed_text(text) for text in texts]
