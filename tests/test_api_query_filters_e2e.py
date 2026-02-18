from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_retrieval_service
from app.main import app
from app.schemas.query import QueryResult, UsedFilters


@dataclass(frozen=True)
class _DocRecord:
    result: QueryResult
    metadata: dict[str, str]
    fetched_at: datetime


class _FilteringRetrievalService:
    def __init__(self) -> None:
        self._records: list[_DocRecord] = [
            _DocRecord(
                result=QueryResult(
                    chunk_id=uuid4(),
                    document_id=uuid4(),
                    content="English rubber duck debugging note.",
                    title="Duck EN",
                    url="https://example.com/wiki-duck",
                    score=0.9,
                ),
                metadata={"product": "raggy", "version": "1.0", "lang": "en", "source": "wiki"},
                fetched_at=datetime(2026, 2, 10, tzinfo=UTC),
            ),
            _DocRecord(
                result=QueryResult(
                    chunk_id=uuid4(),
                    document_id=uuid4(),
                    content="Spanish rubber duck debugging note.",
                    title="Duck ES",
                    url="https://example.com/blog-duck",
                    score=0.8,
                ),
                metadata={"product": "raggy", "version": "2.0", "lang": "es", "source": "blog"},
                fetched_at=datetime(2026, 2, 16, tzinfo=UTC),
            ),
        ]

    async def search(self, query: str, top_k: int, used_filters: UsedFilters) -> list[QueryResult]:
        _ = query
        candidates = self._records

        if used_filters.product is not None:
            candidates = [
                row
                for row in candidates
                if row.metadata.get("product") == used_filters.product
            ]
        if used_filters.version is not None:
            candidates = [
                row
                for row in candidates
                if row.metadata.get("version") == used_filters.version
            ]
        if used_filters.lang is not None:
            candidates = [
                row for row in candidates if row.metadata.get("lang") == used_filters.lang
            ]
        if used_filters.source is not None:
            candidates = [
                row
                for row in candidates
                if row.metadata.get("source") == used_filters.source
                or (row.result.url and used_filters.source in row.result.url)
            ]
        if used_filters.date_from is not None:
            candidates = [row for row in candidates if row.fetched_at >= used_filters.date_from]
        if used_filters.date_to is not None:
            candidates = [row for row in candidates if row.fetched_at <= used_filters.date_to]

        for key, value in used_filters.extra.items():
            candidates = [row for row in candidates if row.metadata.get(key) == str(value)]

        return [row.result for row in candidates[:top_k]]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    async def _no_op() -> None:
        return None

    monkeypatch.setattr("app.main.init_db", _no_op)
    monkeypatch.setattr("app.main.close_db", _no_op)

    app.dependency_overrides[get_retrieval_service] = lambda: _FilteringRetrievalService()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_query_filters_end_to_end(client: TestClient) -> None:
    payload = {
        "query": "duck debugging",
        "top_k": 5,
        "used_filters": {
            "lang": "es",
            "source": "blog",
            "date_from": "2026-02-15T00:00:00Z",
            "extra": {"product": "raggy"},
        },
    }

    response = client.post("/query", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["used_filters"]["lang"] == "es"
    assert body["used_filters"]["source"] == "blog"
    assert body["answer"].startswith("Spanish")
    assert len(body["citations"]) == 1
    assert body["citations"][0]["title"] == "Duck ES"
