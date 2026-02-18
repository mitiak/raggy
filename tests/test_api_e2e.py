from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_document_service, get_retrieval_service
from app.db.session import get_db
from app.main import app
from app.models.document import SourceType
from app.schemas.document import DocumentIngestRequest
from app.schemas.query import QueryResult


class _FakeDbSession:
    async def execute(self, _: object) -> object:
        return SimpleNamespace()


class _FakeDocumentService:
    async def ingest_document(self, payload: DocumentIngestRequest) -> object:
        return SimpleNamespace(
            id=uuid4(),
            source_type=SourceType.URL,
            source_url="https://example.com/fun",
            title=payload.title,
            content_hash="a" * 64,
            metadata_json=payload.metadata,
            fetched_at=datetime(2026, 2, 18, tzinfo=UTC),
        )


class _FakeRetrievalService:
    async def search(self, query: str, top_k: int) -> list[QueryResult]:
        _ = (query, top_k)
        return [
            QueryResult(
                chunk_id=uuid4(),
                document_id=uuid4(),
                content="Rubber duck debugging helps by forcing clear reasoning.",
                score=0.87,
            )
        ]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    async def _no_op() -> None:
        return None

    monkeypatch.setattr("app.main.init_db", _no_op)
    monkeypatch.setattr("app.main.close_db", _no_op)

    async def _fake_get_db() -> Iterator[_FakeDbSession]:
        yield _FakeDbSession()

    app.dependency_overrides[get_db] = _fake_get_db
    app.dependency_overrides[get_document_service] = lambda: _FakeDocumentService()
    app.dependency_overrides[get_retrieval_service] = lambda: _FakeRetrievalService()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ingest_document_endpoint(client: TestClient) -> None:
    payload = {
        "source_type": "url",
        "source_url": "https://example.com/fun",
        "title": "Rubber duck debugging",
        "content": "Explain code to a duck.",
        "metadata": {"mood": "fun"},
    }

    response = client.post("/documents", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == "url"
    assert body["title"] == "Rubber duck debugging"
    assert body["source_url"] == "https://example.com/fun"
    assert body["metadata"] == {"mood": "fun"}


def test_query_endpoint_returns_results(client: TestClient) -> None:
    response = client.post("/query", json={"query": "duck debugging", "top_k": 5})

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 1
    assert "Rubber duck debugging" in body["results"][0]["content"]


def test_query_endpoint_validation_error(client: TestClient) -> None:
    response = client.post("/query", json={"query": "duck debugging", "top_k": 50})

    assert response.status_code == 422
