from __future__ import annotations

from datetime import datetime

import pytest

from app.schemas.query import QueryAnswer, QueryRequest, UsedFilters


def test_query_answer_requires_citation_for_claims() -> None:
    with pytest.raises(ValueError, match="citation"):
        QueryAnswer(
            answer="Rubber duck debugging helps clarify reasoning.",
            citations=[],
            used_filters=UsedFilters(),
            confidence=0.8,
            retrieve_ms=1.0,
            gen_ms=1.0,
        )


def test_query_answer_allows_no_citations_for_unknown() -> None:
    payload = QueryAnswer(
        answer="I don't know based on the provided documents.",
        citations=[],
        used_filters=UsedFilters(),
        confidence=0.0,
        retrieve_ms=0.5,
        gen_ms=0.0,
    )

    assert payload.citations == []


def test_query_request_rejects_extra_fields() -> None:
    with pytest.raises(ValueError, match="extra"):
        QueryRequest.model_validate(
            {
                "query": "duck",
                "top_k": 5,
                "unexpected": "field",
            }
        )


def test_used_filters_parses_dates() -> None:
    request = QueryRequest.model_validate(
        {
            "query": "duck",
            "top_k": 5,
            "used_filters": {
                "product": "raggy",
                "date_from": "2026-02-01T00:00:00Z",
            },
        }
    )

    assert request.used_filters.product == "raggy"
    assert isinstance(request.used_filters.date_from, datetime)
