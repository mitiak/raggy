from __future__ import annotations

import asyncio
from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_retrieval_service
from app.main import app
from app.schemas.query import QueryResult, UsedFilters


class _SlowRetrievalService:
    async def search(self, query: str, top_k: int, used_filters: UsedFilters) -> list[QueryResult]:
        _ = (query, top_k, used_filters)
        await asyncio.sleep(0.01)
        return [
            QueryResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                content="Timing test chunk content.",
                title="Timing Doc",
                url="https://example.com/timing",
                score=0.77,
            )
        ]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    async def _no_op() -> None:
        return None

    monkeypatch.setattr("app.main.init_db", _no_op)
    monkeypatch.setattr("app.main.close_db", _no_op)
    app.dependency_overrides[get_retrieval_service] = lambda: _SlowRetrievalService()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_query_returns_retrieve_and_gen_timings(client: TestClient) -> None:
    response = client.post(
        "/query",
        json={"query": "timing check", "top_k": 5, "used_filters": {"lang": "en"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert "retrieve_ms" in body
    assert "gen_ms" in body
    assert body["retrieve_ms"] >= 0.0
    assert body["gen_ms"] >= 0.0
    assert body["confidence"] == pytest.approx(0.77)
