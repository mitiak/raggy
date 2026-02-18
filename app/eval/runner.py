from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import SessionLocal
from app.models.chunk import Chunk
from app.schemas.query import QueryAnswer, UsedFilters


class EvalQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    query: str
    answerable: bool
    used_filters: UsedFilters = Field(default_factory=UsedFilters)
    expected_title: str | None = None
    expected_substring: str | None = None


class FixtureDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str = "md"
    source_url: str | None = None
    title: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class _EvalOutcome:
    question: EvalQuestion
    response: QueryAnswer
    unknown: bool
    retrieval_hit: bool


def _is_unknown_answer(answer: str) -> bool:
    normalized = answer.strip().lower()
    return any(
        marker in normalized
        for marker in ("i don't know", "i do not know", "not enough information")
    )


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        rows.append(json.loads(stripped))
    return rows


def _http_json(
    *,
    method: str,
    base_url: str,
    path: str,
    payload: dict[str, Any] | None,
    timeout: float,
) -> tuple[int, dict[str, Any]]:
    url = f"{base_url.rstrip('/')}{path if path.startswith('/') else f'/{path}'}"
    body: bytes | None = None
    headers: dict[str, str] = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url=url, data=body, headers=headers, method=method.upper())
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, json.loads(data) if data else {}
    except error.HTTPError as exc:
        data = exc.read().decode("utf-8")
        parsed: dict[str, Any]
        try:
            parsed = json.loads(data) if data else {}
        except json.JSONDecodeError:
            parsed = {"raw": data}
        return exc.code, parsed


def _ingest_fixture_docs(base_url: str, timeout: float, fixture_path: Path) -> None:
    if not fixture_path.exists():
        return
    for raw in _load_jsonl(fixture_path):
        doc = FixtureDoc.model_validate(raw)
        payload = doc.model_dump(mode="json")
        _http_json(
            method="POST",
            base_url=base_url,
            path="/documents",
            payload=payload,
            timeout=timeout,
        )


def _evaluate_retrieval_hit(question: EvalQuestion, response: QueryAnswer) -> bool:
    if question.expected_title is not None:
        return any(c.title == question.expected_title for c in response.citations)

    if question.expected_substring is not None:
        needle = question.expected_substring.lower()
        if needle in response.answer.lower():
            return True
        return any(needle in citation.title.lower() for citation in response.citations)

    if question.answerable:
        return bool(response.citations)
    return True


async def _fetch_cited_chunk_texts(citation_chunk_ids: set[UUID]) -> dict[UUID, str]:
    if not citation_chunk_ids:
        return {}
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Chunk.id, Chunk.text).where(Chunk.id.in_(citation_chunk_ids))
            )
        ).all()
    return {chunk_id: text for chunk_id, text in rows}


def _citation_supported(answer: str, citation_ids: list[UUID], text_map: dict[UUID, str]) -> bool:
    normalized_answer = " ".join(answer.lower().split())
    if not normalized_answer:
        return False
    for citation_id in citation_ids:
        text = text_map.get(citation_id)
        if text is None:
            continue
        normalized_text = " ".join(text.lower().split())
        if normalized_answer in normalized_text:
            return True
    return False


def run_evaluation(
    *,
    base_url: str,
    timeout: float,
    dataset_path: Path,
    fixture_path: Path | None,
    ingest_fixtures: bool,
    limit: int | None,
) -> dict[str, Any]:
    if ingest_fixtures and fixture_path is not None:
        _ingest_fixture_docs(base_url, timeout, fixture_path)

    rows = _load_jsonl(dataset_path)
    questions = [EvalQuestion.model_validate(row) for row in rows]
    if limit is not None:
        questions = questions[: max(0, limit)]

    outcomes: list[_EvalOutcome] = []
    failures: list[dict[str, Any]] = []

    for question in questions:
        payload = {
            "query": question.query,
            "top_k": 5,
            "used_filters": question.used_filters.model_dump(mode="json"),
        }
        status_code, body = _http_json(
            method="POST",
            base_url=base_url,
            path="/query",
            payload=payload,
            timeout=timeout,
        )
        if status_code != 200:
            failures.append(
                {
                    "id": question.id,
                    "status_code": status_code,
                    "error": body,
                }
            )
            continue

        response = QueryAnswer.model_validate(body)
        unknown = _is_unknown_answer(response.answer)
        retrieval_hit = _evaluate_retrieval_hit(question, response)
        outcomes.append(
            _EvalOutcome(
                question=question,
                response=response,
                unknown=unknown,
                retrieval_hit=retrieval_hit,
            )
        )

    answerable_outcomes = [item for item in outcomes if item.question.answerable]
    unanswerable_outcomes = [item for item in outcomes if not item.question.answerable]

    answerable_total = len(answerable_outcomes)
    unanswerable_total = len(unanswerable_outcomes)

    retrieval_hits = sum(1 for item in answerable_outcomes if item.retrieval_hit)
    retrieval_hit_rate = (retrieval_hits / answerable_total) if answerable_total else 0.0

    idk_on_unanswerable = sum(1 for item in unanswerable_outcomes if item.unknown)
    idk_rate = (idk_on_unanswerable / unanswerable_total) if unanswerable_total else 0.0

    citation_checks_total = 0
    citation_checks_supported = 0
    citation_errors: str | None = None
    try:
        citation_ids: set[UUID] = {
            citation.chunk_id
            for item in outcomes
            if not item.unknown
            for citation in item.response.citations
        }
        text_map = asyncio.run(_fetch_cited_chunk_texts(citation_ids))

        for item in outcomes:
            if item.unknown or not item.response.citations:
                continue
            citation_checks_total += 1
            citation_chunk_ids = [citation.chunk_id for citation in item.response.citations]
            if _citation_supported(item.response.answer, citation_chunk_ids, text_map):
                citation_checks_supported += 1
    except (SQLAlchemyError, RuntimeError) as exc:
        citation_errors = str(exc)

    citation_correctness = (
        (citation_checks_supported / citation_checks_total) if citation_checks_total else 0.0
    )

    return {
        "total_questions": len(questions),
        "completed_questions": len(outcomes),
        "failed_questions": len(failures),
        "answerable_questions": answerable_total,
        "unanswerable_questions": unanswerable_total,
        "retrieval_hit_rate": round(retrieval_hit_rate, 4),
        "citation_correctness": round(citation_correctness, 4),
        "idk_rate_unanswerable": round(idk_rate, 4),
        "citation_checks_total": citation_checks_total,
        "citation_checks_supported": citation_checks_supported,
        "citation_errors": citation_errors,
        "failures": failures,
    }
