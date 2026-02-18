from __future__ import annotations

import pytest

from app.schemas.query import QueryAnswer, UsedFilters


def test_query_answer_requires_citation_for_claims() -> None:
    with pytest.raises(ValueError, match="citation"):
        QueryAnswer(
            answer="Rubber duck debugging helps clarify reasoning.",
            citations=[],
            used_filters=UsedFilters(),
            confidence=0.8,
        )


def test_query_answer_allows_no_citations_for_unknown() -> None:
    payload = QueryAnswer(
        answer="I don't know based on the provided documents.",
        citations=[],
        used_filters=UsedFilters(),
        confidence=0.0,
    )

    assert payload.citations == []
