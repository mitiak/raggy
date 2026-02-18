from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_retrieval_service
from app.main import app
from app.schemas.query import QueryResult, UsedFilters


class _CapturingRetrievalService:
    def __init__(self, results: list[QueryResult]) -> None:
        self.results = results
        self.last_query: str | None = None
        self.last_top_k: int | None = None
        self.last_filters: UsedFilters | None = None

    async def search(self, query: str, top_k: int, used_filters: UsedFilters) -> list[QueryResult]:
        self.last_query = query
        self.last_top_k = top_k
        self.last_filters = used_filters
        return self.results[:top_k]


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, _CapturingRetrievalService]]:
    async def _no_op() -> None:
        return None

    monkeypatch.setattr("app.main.init_db", _no_op)
    monkeypatch.setattr("app.main.close_db", _no_op)

    results = [
        QueryResult(
            chunk_id=uuid4(),
            document_id=uuid4(),
            content=f"Chunk content {idx}",
            title=f"Doc {idx}",
            url=f"https://example.com/doc-{idx}",
            score=max(0.1, 0.95 - (idx * 0.05)),
        )
        for idx in range(12)
    ]
    fake_retrieval = _CapturingRetrievalService(results=results)
    app.dependency_overrides[get_retrieval_service] = lambda: fake_retrieval

    with TestClient(app) as test_client:
        yield test_client, fake_retrieval

    app.dependency_overrides.clear()


def test_query_uses_rag_service_and_returns_grounded_answer(
    client: tuple[TestClient, _CapturingRetrievalService],
) -> None:
    test_client, fake_retrieval = client
    payload = {
        "query": "why does duck debugging help?",
        "top_k": 5,
        "used_filters": {"lang": "en", "source": "guide"},
    }

    response = test_client.post("/query", json=payload)

    assert response.status_code == 200
    body = response.json()

    # RagService policy: retrieval fan-out should use at least 20 candidates.
    assert fake_retrieval.last_top_k == 20
    assert fake_retrieval.last_query == "why does duck debugging help?"
    assert fake_retrieval.last_filters is not None
    assert fake_retrieval.last_filters.lang == "en"
    assert fake_retrieval.last_filters.source == "guide"

    # RagService policy: with request top_k=5, select 6 citations minimum.
    assert len(body["citations"]) == 6
    assert body["answer"] == "Chunk content 0"
    assert body["used_filters"]["lang"] == "en"
    assert body["confidence"] == pytest.approx(0.825)


def test_query_unknown_when_retrieval_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_op() -> None:
        return None

    monkeypatch.setattr("app.main.init_db", _no_op)
    monkeypatch.setattr("app.main.close_db", _no_op)

    fake_retrieval = _CapturingRetrievalService(results=[])
    app.dependency_overrides[get_retrieval_service] = lambda: fake_retrieval

    with TestClient(app) as test_client:
        response = test_client.post(
            "/query",
            json={"query": "no data", "top_k": 5, "used_filters": {"lang": "zz"}},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["answer"].lower().startswith("i don't know")
    assert body["citations"] == []
    assert body["confidence"] == 0.0
