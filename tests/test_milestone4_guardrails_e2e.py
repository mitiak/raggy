from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_rag_service
from app.main import app, reset_runtime_state, settings
from app.schemas.query import QueryAnswer, UsedFilters


class _FakeRagService:
    async def answer(self, query: str, top_k: int, used_filters: UsedFilters) -> QueryAnswer:
        _ = (query, top_k, used_filters)
        return QueryAnswer(
            answer="I don't know based on the provided documents.",
            citations=[],
            used_filters=UsedFilters(),
            confidence=0.0,
        )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    async def _no_op() -> None:
        return None

    monkeypatch.setattr("app.main.init_db", _no_op)
    monkeypatch.setattr("app.main.close_db", _no_op)
    app.dependency_overrides[get_rag_service] = lambda: _FakeRagService()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_request_size_limit_returns_413(client: TestClient) -> None:
    reset_runtime_state()
    original_max_bytes = settings.max_request_bytes
    settings.max_request_bytes = 100
    try:
        payload = {"query": "x" * 500, "top_k": 5}
        response = client.post("/query", json=payload)
    finally:
        settings.max_request_bytes = original_max_bytes

    assert response.status_code == 413
    assert response.json()["detail"] == "Request payload too large"


def test_rate_limit_returns_429(client: TestClient) -> None:
    reset_runtime_state()
    original_limit = settings.rate_limit_requests
    original_window = settings.rate_limit_window_seconds
    settings.rate_limit_requests = 2
    settings.rate_limit_window_seconds = 60
    try:
        first = client.get("/health")
        second = client.get("/health")
        third = client.get("/health")
    finally:
        settings.rate_limit_requests = original_limit
        settings.rate_limit_window_seconds = original_window

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["detail"] == "Rate limit exceeded"
