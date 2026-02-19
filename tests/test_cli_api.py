from __future__ import annotations

from argparse import Namespace
from typing import Any

import pytest

from app import cli


def test_api_ingest_rejects_invalid_metadata_json(capsys: Any) -> None:
    args = Namespace(
        metadata_json="{",
        source_type="url",
        source_url="https://example.com",
        title="t",
        content="c",
        fetched_at=None,
        base_url="http://127.0.0.1:8000",
        timeout=10.0,
        quiet=True,
        raw=False,
    )

    code = cli._cmd_api_ingest(args)

    assert code == 2
    assert "Invalid --metadata-json" in capsys.readouterr().out


def test_api_ingest_rejects_non_object_metadata(capsys: Any) -> None:
    args = Namespace(
        metadata_json='["x"]',
        source_type="url",
        source_url="https://example.com",
        title="t",
        content="c",
        fetched_at=None,
        base_url="http://127.0.0.1:8000",
        timeout=10.0,
        quiet=True,
        raw=False,
    )

    code = cli._cmd_api_ingest(args)

    assert code == 2
    assert "--metadata-json must be a JSON object" in capsys.readouterr().out


def test_api_ingest_builds_expected_payload(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_api_request(**kwargs: Any) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(cli, "_api_request", fake_api_request)
    args = Namespace(
        metadata_json='{"mood":"fun"}',
        source_type="url",
        source_url="https://example.com",
        title="Duck",
        content="Quack",
        fetched_at="2026-02-18T12:00:00Z",
        base_url="http://127.0.0.1:8000",
        timeout=10.0,
        quiet=False,
        raw=False,
    )

    code = cli._cmd_api_ingest(args)

    assert code == 0
    assert captured["method"] == "POST"
    assert captured["path"] == "/documents"
    assert captured["payload"] == {
        "source_type": "url",
        "source_url": "https://example.com",
        "title": "Duck",
        "content": "Quack",
        "metadata": {"mood": "fun"},
        "fetched_at": "2026-02-18T12:00:00Z",
    }
    assert captured["pretty"] is True


def test_api_request_rejects_invalid_body_json(capsys: Any) -> None:
    args = Namespace(
        method="POST",
        path="/query",
        body_json="{",
        base_url="http://127.0.0.1:8000",
        timeout=10.0,
        quiet=True,
        raw=False,
    )

    code = cli._cmd_api_request(args)

    assert code == 2
    assert "Invalid --body-json" in capsys.readouterr().out


def test_api_query_builds_payload(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_api_request(**kwargs: Any) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(cli, "_api_request", fake_api_request)
    args = Namespace(
        query="duck",
        top_k=3,
        base_url="http://127.0.0.1:8000",
        timeout=10.0,
        quiet=True,
        raw=True,
    )

    code = cli._cmd_api_query(args)

    assert code == 0
    assert captured["method"] == "POST"
    assert captured["path"] == "/query"
    assert captured["payload"] == {"query": "duck", "top_k": 3}
    assert captured["pretty"] is False


def test_parser_supports_api_query_command() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["api", "query", "--query", "hello", "--top-k", "2"])

    assert args.command == "api"
    assert args.api_command == "query"
    assert args.query == "hello"
    assert args.top_k == 2


def test_run_uses_logster_pipeline(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def fake_run_shell_and_exit(command: str, quiet: bool) -> int:
        captured["command"] = command
        captured["quiet"] = quiet
        return 0

    monkeypatch.setattr(cli, "_run_shell_and_exit", fake_run_shell_and_exit)
    args = Namespace(
        host="0.0.0.0",
        port=8000,
        reload=True,
        jq=False,
        logster=True,
        quiet=False,
    )

    code = cli._cmd_run(args)

    assert code == 0
    assert "| uv run logster" in captured["command"]
    assert captured["quiet"] is False


def test_parser_rejects_jq_and_logster_together() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["run", "--jq", "--logster"])
