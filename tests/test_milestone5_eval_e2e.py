from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.eval import runner


def test_eval_harness_end_to_end(tmp_path: Path, monkeypatch) -> None:
    chunk_a = uuid4()
    chunk_b = uuid4()

    dataset_path = tmp_path / "golden.jsonl"
    dataset_rows = [
        {
            "id": "q1",
            "query": "What is duck debugging?",
            "answerable": True,
            "used_filters": {"lang": "en"},
            "expected_title": "Duck Debugging EN",
        },
        {
            "id": "q2",
            "query": "Unknown moon winner?",
            "answerable": False,
            "used_filters": {"lang": "en"},
        },
    ]
    dataset_path.write_text("\n".join(json.dumps(row) for row in dataset_rows), encoding="utf-8")

    def fake_http_json(
        *,
        method: str,
        base_url: str,
        path: str,
        payload: dict[str, object] | None,
        timeout: float,
    ) -> tuple[int, dict[str, object]]:
        _ = (method, base_url, path, timeout)
        query = (payload or {}).get("query")
        if query == "What is duck debugging?":
            return (
                200,
                {
                    "answer": "Rubber duck debugging explains code line by line.",
                    "citations": [
                        {
                            "doc_id": str(uuid4()),
                            "chunk_id": str(chunk_a),
                            "title": "Duck Debugging EN",
                            "url": "https://example.com/duck-en",
                            "score": 0.9,
                        }
                    ],
                    "used_filters": {"lang": "en", "extra": {}},
                    "confidence": 0.9,
                },
            )
        return (
            200,
            {
                "answer": "I don't know based on the provided documents.",
                "citations": [],
                "used_filters": {"lang": "en", "extra": {}},
                "confidence": 0.0,
            },
        )

    async def fake_fetch_chunk_texts(_: set) -> dict:
        return {
            chunk_a: "Rubber duck debugging explains code line by line.",
            chunk_b: "unused",
        }

    monkeypatch.setattr(runner, "_http_json", fake_http_json)
    monkeypatch.setattr(runner, "_fetch_cited_chunk_texts", fake_fetch_chunk_texts)

    report = runner.run_evaluation(
        base_url="http://127.0.0.1:8000",
        timeout=3.0,
        dataset_path=dataset_path,
        fixture_path=None,
        ingest_fixtures=False,
        limit=None,
    )

    assert report["total_questions"] == 2
    assert report["failed_questions"] == 0
    assert report["answerable_questions"] == 1
    assert report["unanswerable_questions"] == 1
    assert report["retrieval_hit_rate"] == 1.0
    assert report["citation_correctness"] == 1.0
    assert report["idk_rate_unanswerable"] == 1.0
