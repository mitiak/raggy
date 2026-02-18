from __future__ import annotations

import argparse
import asyncio
import json
import shlex
import subprocess
import sys
from collections.abc import Coroutine, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request
from urllib.parse import SplitResult, urlsplit, urlunsplit
from uuid import UUID

from sqlalchemy import Select, func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.eval.runner import run_evaluation
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.ingest_job import IngestJob


def _run_command(command: Sequence[str]) -> int:
    try:
        process = subprocess.run(command, check=False)
        return process.returncode
    except KeyboardInterrupt:
        return 130


def _run_shell_command(command: str) -> int:
    try:
        process = subprocess.run(command, check=False, shell=True)
        return process.returncode
    except KeyboardInterrupt:
        return 130


def _add_common_verbosity(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress command echoing.",
    )


def _echo_command(command: Sequence[str], quiet: bool) -> None:
    if not quiet:
        print(f"$ {' '.join(command)}")


def _run_and_exit(command: Sequence[str], quiet: bool) -> int:
    _echo_command(command, quiet)
    return _run_command(command)


def _run_shell_and_exit(command: str, quiet: bool) -> int:
    if not quiet:
        print(f"$ {command}")
    return _run_shell_command(command)


def _print_response(raw_body: str, pretty: bool) -> None:
    if not raw_body:
        print("<empty response>")
        return

    if pretty:
        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError:
            print(raw_body)
            return
        print(json.dumps(parsed, indent=2, sort_keys=True))
        return

    print(raw_body)


def _db_json_default(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def _run_db_command(coro: Coroutine[Any, Any, int]) -> int:
    try:
        return int(asyncio.run(coro))
    except SQLAlchemyError as exc:
        print(f"Database command failed: {exc}")
        return 1


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True, default=_db_json_default))


def _as_utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _redact_db_url(raw_url: str) -> str:
    split: SplitResult = urlsplit(raw_url)
    if split.password is None:
        return raw_url

    username = split.username or ""
    host = split.hostname or ""
    port_suffix = f":{split.port}" if split.port is not None else ""
    netloc = f"{username}:***@{host}{port_suffix}"
    return urlunsplit((split.scheme, netloc, split.path, split.query, split.fragment))


def _api_request(
    *,
    method: str,
    base_url: str,
    path: str,
    payload: dict[str, Any] | None,
    timeout: float,
    quiet: bool,
    pretty: bool,
) -> int:
    normalized_base = base_url.rstrip("/")
    normalized_path = path if path.startswith("/") else f"/{path}"
    url = f"{normalized_base}{normalized_path}"

    body_bytes: bytes | None = None
    headers: dict[str, str] = {"Accept": "application/json"}
    if payload is not None:
        body_bytes = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    if not quiet:
        print(f"$ {method.upper()} {url}")
        if payload is not None:
            print(json.dumps(payload, indent=2, sort_keys=True))

    req = request.Request(url=url, data=body_bytes, headers=headers, method=method.upper())
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            status_code = resp.status
            response_body = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        status_code = exc.code
        response_body = exc.read().decode("utf-8")
        print(f"HTTP {status_code}")
        _print_response(response_body, pretty)
        return 1
    except error.URLError as exc:
        print(f"Request failed: {exc.reason}")
        return 1

    print(f"HTTP {status_code}")
    _print_response(response_body, pretty)
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    settings = get_settings()
    host = args.host or settings.app_host
    port = args.port or settings.app_port

    command: list[str] = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if args.reload:
        command.append("--reload")

    if args.jq:
        shell_command = (
            "uv run uvicorn app.main:app "
            f"--host {shlex.quote(host)} "
            f"--port {port} "
            f"{'--reload ' if args.reload else ''}"
            "| jq -C -R 'fromjson? // .'"
        )
        return _run_shell_and_exit(shell_command, args.quiet)

    return _run_and_exit(command, args.quiet)


def _cmd_migrate_up(args: argparse.Namespace) -> int:
    command = [sys.executable, "-m", "alembic", "upgrade", args.revision]
    return _run_and_exit(command, args.quiet)


def _cmd_migrate_down(args: argparse.Namespace) -> int:
    command = [sys.executable, "-m", "alembic", "downgrade", args.revision]
    return _run_and_exit(command, args.quiet)


def _cmd_migrate_new(args: argparse.Namespace) -> int:
    command = [sys.executable, "-m", "alembic", "revision", "-m", args.message]
    if args.autogenerate:
        command.append("--autogenerate")
    return _run_and_exit(command, args.quiet)


def _cmd_lint(args: argparse.Namespace) -> int:
    command = [sys.executable, "-m", "ruff", "check", "."]
    return _run_and_exit(command, args.quiet)


def _cmd_typecheck(args: argparse.Namespace) -> int:
    command = [sys.executable, "-m", "mypy", "app"]
    return _run_and_exit(command, args.quiet)


def _cmd_test(args: argparse.Namespace) -> int:
    command = [sys.executable, "-m", "pytest"]
    return _run_and_exit(command, args.quiet)


def _cmd_check(args: argparse.Namespace) -> int:
    for command in (
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "mypy", "app"],
    ):
        exit_code = _run_and_exit(command, args.quiet)
        if exit_code != 0:
            return exit_code
    return 0


def _cmd_eval_run(args: argparse.Namespace) -> int:
    report = run_evaluation(
        base_url=args.base_url,
        timeout=args.timeout,
        dataset_path=Path(args.dataset),
        fixture_path=Path(args.fixtures) if args.fixtures is not None else None,
        ingest_fixtures=args.ingest_fixtures,
        limit=args.limit,
    )

    if args.json:
        _print_json(report)
    else:
        print("Evaluation report:")
        print(f"- total_questions: {report['total_questions']}")
        print(f"- completed_questions: {report['completed_questions']}")
        print(f"- failed_questions: {report['failed_questions']}")
        print(f"- answerable_questions: {report['answerable_questions']}")
        print(f"- unanswerable_questions: {report['unanswerable_questions']}")
        print(f"- retrieval_hit_rate: {report['retrieval_hit_rate']}")
        print(f"- citation_correctness: {report['citation_correctness']}")
        print(f"- idk_rate_unanswerable: {report['idk_rate_unanswerable']}")
        print(
            f"- citation_checks: {report['citation_checks_supported']}/"
            f"{report['citation_checks_total']}"
        )
        if report["citation_errors"] is not None:
            print(f"- citation_errors: {report['citation_errors']}")
        if report["failures"]:
            print("- failures:")
            for failure in report["failures"]:
                print(
                    f"  - {failure['id']} status={failure['status_code']} "
                    f"error={json.dumps(failure['error'])}"
                )

    return 0 if report["failed_questions"] == 0 else 1


async def _doctor_db_payload() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "documents": 0,
        "chunks": 0,
        "ingest_jobs": 0,
        "missing_tables": [],
        "error": None,
    }
    try:
        missing_tables = await _db_missing_tables("documents", "chunks", "ingest_jobs")
        payload["missing_tables"] = missing_tables
        if missing_tables:
            payload["ok"] = False
            return payload

        payload["documents"] = int(
            await _db_fetch_scalar(select(func.count()).select_from(Document)) or 0
        )
        payload["chunks"] = int(
            await _db_fetch_scalar(select(func.count()).select_from(Chunk)) or 0
        )
        payload["ingest_jobs"] = int(
            await _db_fetch_scalar(select(func.count()).select_from(IngestJob)) or 0
        )
        return payload
    except SQLAlchemyError as exc:
        payload["ok"] = False
        payload["error"] = str(exc)
        return payload


def _doctor_api_payload(base_url: str, timeout: float) -> dict[str, Any]:
    normalized_base = base_url.rstrip("/")
    url = f"{normalized_base}/health"
    req = request.Request(url=url, method="GET")

    payload: dict[str, Any] = {
        "ok": False,
        "url": url,
        "status_code": None,
        "body": None,
        "error": None,
    }
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            payload["status_code"] = resp.status
            payload["body"] = body
            payload["ok"] = resp.status == 200
            return payload
    except error.HTTPError as exc:
        payload["status_code"] = exc.code
        payload["body"] = exc.read().decode("utf-8")
        payload["error"] = "http_error"
        return payload
    except error.URLError as exc:
        payload["error"] = str(exc.reason)
        return payload


def _cmd_doctor(args: argparse.Namespace) -> int:
    settings = get_settings()
    db_payload = asyncio.run(_doctor_db_payload())
    api_payload = _doctor_api_payload(args.base_url, args.timeout)

    payload = {
        "database_url": _redact_db_url(settings.database_url),
        "database": db_payload,
        "api": api_payload,
    }

    if args.json:
        _print_json(payload)
    else:
        print("Doctor report:")
        print(f"- database_url: {payload['database_url']}")
        print(f"- db_ok: {db_payload['ok']}")
        print(
            f"- db_counts: documents={db_payload['documents']}, "
            f"chunks={db_payload['chunks']}, ingest_jobs={db_payload['ingest_jobs']}"
        )
        if db_payload["missing_tables"]:
            print(f"- db_missing_tables: {', '.join(db_payload['missing_tables'])}")
        if db_payload["error"] is not None:
            print(f"- db_error: {db_payload['error']}")

        print(f"- api_health_url: {api_payload['url']}")
        print(f"- api_ok: {api_payload['ok']}")
        print(f"- api_status_code: {api_payload['status_code']}")
        if api_payload["error"] is not None:
            print(f"- api_error: {api_payload['error']}")

    db_ok = bool(db_payload["ok"])
    api_ok = bool(api_payload["ok"])
    return 0 if db_ok and api_ok else 1


def _cmd_api_list(_: argparse.Namespace) -> int:
    print("Available API endpoints:")
    print("- GET /health")
    print("- POST /documents")
    print("- POST /query")
    print("Use 'raggy api request' for custom method/path payload calls.")
    return 0


def _cmd_api_health(args: argparse.Namespace) -> int:
    return _api_request(
        method="GET",
        base_url=args.base_url,
        path="/health",
        payload=None,
        timeout=args.timeout,
        quiet=args.quiet,
        pretty=not args.raw,
    )


def _cmd_api_ingest(args: argparse.Namespace) -> int:
    try:
        metadata_obj = json.loads(args.metadata_json)
    except json.JSONDecodeError as exc:
        print(f"Invalid --metadata-json: {exc}")
        return 2

    if not isinstance(metadata_obj, dict):
        print("--metadata-json must be a JSON object")
        return 2

    payload: dict[str, Any] = {
        "source_type": args.source_type,
        "source_url": args.source_url,
        "title": args.title,
        "content": args.content,
        "metadata": metadata_obj,
    }
    if args.fetched_at is not None:
        payload["fetched_at"] = args.fetched_at

    return _api_request(
        method="POST",
        base_url=args.base_url,
        path="/documents",
        payload=payload,
        timeout=args.timeout,
        quiet=args.quiet,
        pretty=not args.raw,
    )


def _cmd_api_query(args: argparse.Namespace) -> int:
    payload = {"query": args.query, "top_k": args.top_k}
    return _api_request(
        method="POST",
        base_url=args.base_url,
        path="/query",
        payload=payload,
        timeout=args.timeout,
        quiet=args.quiet,
        pretty=not args.raw,
    )


def _cmd_api_request(args: argparse.Namespace) -> int:
    payload_obj: dict[str, Any] | None = None
    if args.body_json is not None:
        try:
            parsed = json.loads(args.body_json)
        except json.JSONDecodeError as exc:
            print(f"Invalid --body-json: {exc}")
            return 2

        if not isinstance(parsed, dict):
            print("--body-json must be a JSON object")
            return 2
        payload_obj = parsed

    return _api_request(
        method=args.method,
        base_url=args.base_url,
        path=args.path,
        payload=payload_obj,
        timeout=args.timeout,
        quiet=args.quiet,
        pretty=not args.raw,
    )


async def _db_fetch_rows(statement: Select[Any]) -> list[Any]:
    async with SessionLocal() as session:
        rows = await session.execute(statement)
        return list(rows)


async def _db_fetch_scalars(statement: Select[Any]) -> list[Any]:
    async with SessionLocal() as session:
        rows = await session.scalars(statement)
        return list(rows)


async def _db_fetch_scalar(
    statement: Any,
    params: dict[str, Any] | None = None,
) -> Any:
    async with SessionLocal() as session:
        return await session.scalar(statement, params or {})


async def _db_fetch_mappings(
    statement: Any,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    async with SessionLocal() as session:
        result = await session.execute(statement, params or {})
        return [dict(row) for row in result.mappings()]


async def _db_table_exists(table_name: str) -> bool:
    statement = text("SELECT to_regclass(:qualified_name)")
    qualified_name = f"public.{table_name}"
    async with SessionLocal() as session:
        result = await session.scalar(statement, {"qualified_name": qualified_name})
    return result is not None


async def _db_missing_tables(*table_names: str) -> list[str]:
    missing: list[str] = []
    for table_name in table_names:
        if not await _db_table_exists(table_name):
            missing.append(table_name)
    return missing


async def _db_table_columns(table_name: str) -> set[str]:
    statement = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :table_name
        """
    )
    async with SessionLocal() as session:
        result = await session.execute(statement, {"table_name": table_name})
        return {str(column_name) for column_name in result.scalars().all()}


async def _db_chunks_doc_fk_column() -> str | None:
    columns = await _db_table_columns("chunks")
    for candidate in ("doc_id", "document_id"):
        if candidate in columns:
            return candidate
    return None


def _db_preferred_column(columns: set[str], *candidates: str) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _print_incompatible_schema_hint(table_name: str, expected_columns: list[str]) -> None:
    cols = ", ".join(expected_columns)
    print(
        f"Table '{table_name}' exists but has an unexpected schema. "
        f"Expected one of these columns: {cols}"
    )
    print("Run migrations: uv run raggy migrate up")


def _print_missing_tables_hint(missing_tables: list[str]) -> None:
    tables = ", ".join(missing_tables)
    print(f"Missing table(s): {tables}")
    print("Run migrations: uv run raggy migrate up")


async def _cmd_db_stats_async(args: argparse.Namespace) -> int:
    missing_tables = await _db_missing_tables("documents", "chunks", "ingest_jobs")

    docs_count = 0
    chunks_count = 0
    jobs_count = 0

    if "documents" not in missing_tables:
        docs_count = int(await _db_fetch_scalar(select(func.count()).select_from(Document)) or 0)
    if "chunks" not in missing_tables:
        chunks_count = int(await _db_fetch_scalar(select(func.count()).select_from(Chunk)) or 0)
    if "ingest_jobs" not in missing_tables:
        jobs_count = int(await _db_fetch_scalar(select(func.count()).select_from(IngestJob)) or 0)

    payload = {
        "documents": docs_count,
        "chunks": chunks_count,
        "ingest_jobs": jobs_count,
        "missing_tables": missing_tables,
    }
    if args.json:
        _print_json(payload)
        return 0

    print("Database stats:")
    print(f"- documents: {docs_count}")
    print(f"- chunks: {chunks_count}")
    print(f"- ingest_jobs: {jobs_count}")
    if missing_tables:
        _print_missing_tables_hint(missing_tables)
    return 0


def _cmd_db_stats(args: argparse.Namespace) -> int:
    return _run_db_command(_cmd_db_stats_async(args))


async def _cmd_db_documents_async(args: argparse.Namespace) -> int:
    missing_required = await _db_missing_tables("documents")
    if missing_required:
        _print_missing_tables_hint(missing_required)
        return 1

    document_columns = await _db_table_columns("documents")
    fetched_at_column = _db_preferred_column(document_columns, "fetched_at", "created_at")
    source_type_expression = "NULL::text AS source_type"
    if "source_type" in document_columns:
        source_type_expression = "d.source_type::text AS source_type"
    source_url_expression = "NULL::text AS source_url"
    if "source_url" in document_columns:
        source_url_expression = "d.source_url AS source_url"
    fetched_at_expression = "NULL::timestamptz AS fetched_at"
    order_by_expression = "d.id DESC"
    if fetched_at_column is not None:
        fetched_at_expression = f"d.{fetched_at_column} AS fetched_at"
        order_by_expression = f"d.{fetched_at_column} DESC"

    chunks_exists = not await _db_missing_tables("chunks")
    chunk_fk_column: str | None = None
    if chunks_exists:
        chunk_fk_column = await _db_chunks_doc_fk_column()
        if chunk_fk_column is None:
            _print_incompatible_schema_hint("chunks", ["doc_id", "document_id"])
            return 1

    if chunks_exists and chunk_fk_column is not None:
        statement = text(
            f"""
            SELECT
                d.id,
                d.title,
                {source_type_expression},
                {source_url_expression},
                {fetched_at_expression},
                COUNT(c.id) AS chunk_count
            FROM documents d
            LEFT JOIN chunks c ON c.{chunk_fk_column} = d.id
            GROUP BY d.id, d.title, source_type, source_url, fetched_at
            ORDER BY {order_by_expression}
            LIMIT :limit
            """
        )
    else:
        statement = text(
            """
            SELECT
                d.id,
                d.title,
                NULL::text AS source_type,
                NULL::text AS source_url,
                NULL::timestamptz AS fetched_at,
                0 AS chunk_count
            FROM documents d
            ORDER BY d.id DESC
            LIMIT :limit
            """
        )
    rows = await _db_fetch_mappings(statement, {"limit": args.limit})
    items = [
        {
            "id": row["id"],
            "title": row["title"],
            "source_type": row["source_type"],
            "source_url": row["source_url"],
            "fetched_at": _as_utc_iso(row["fetched_at"]),
            "chunk_count": int(row.get("chunk_count") or 0),
        }
        for row in rows
    ]

    if args.json:
        _print_json(items)
        return 0

    print(f"Recent documents (limit={args.limit}):")
    if not chunks_exists:
        print("chunks table is missing, chunk counts are shown as 0.")
    if not items:
        print("<no documents>")
        return 0
    for item in items:
        print(
            f"- {item['id']} | {item['title']} | chunks={item['chunk_count']} | "
            f"source={item['source_type']} | fetched_at={item['fetched_at']}"
        )
    return 0


def _cmd_db_documents(args: argparse.Namespace) -> int:
    return _run_db_command(_cmd_db_documents_async(args))


async def _cmd_db_chunks_async(args: argparse.Namespace) -> int:
    missing_required = await _db_missing_tables("chunks")
    if missing_required:
        _print_missing_tables_hint(missing_required)
        return 1

    chunk_fk_column = await _db_chunks_doc_fk_column()
    if chunk_fk_column is None:
        _print_incompatible_schema_hint("chunks", ["doc_id", "document_id"])
        return 1

    chunk_columns = await _db_table_columns("chunks")
    created_at_column = _db_preferred_column(chunk_columns, "created_at")
    token_count_expression = "0 AS token_count"
    if "token_count" in chunk_columns:
        token_count_expression = "c.token_count AS token_count"
    content_hash_expression = "NULL::text AS content_hash"
    if "content_hash" in chunk_columns:
        content_hash_expression = "c.content_hash AS content_hash"
    created_at_expression = "NULL::timestamptz AS created_at"
    order_by_expression = "c.id DESC"
    if created_at_column is not None:
        created_at_expression = f"c.{created_at_column} AS created_at"
        order_by_expression = f"c.{created_at_column} DESC"

    documents_exists = not await _db_missing_tables("documents")
    params: dict[str, Any] = {"limit": args.limit}
    doc_filter = ""
    if args.doc_id is not None:
        doc_filter = f"WHERE c.{chunk_fk_column} = :doc_id"
        params["doc_id"] = args.doc_id

    if documents_exists:
        statement = text(
            f"""
            SELECT
                c.id,
                c.{chunk_fk_column} AS doc_id,
                c.chunk_index,
                {token_count_expression},
                {created_at_expression},
                {content_hash_expression},
                d.title AS document_title
            FROM chunks c
            JOIN documents d ON c.{chunk_fk_column} = d.id
            {doc_filter}
            ORDER BY {order_by_expression}
            LIMIT :limit
            """
        )
    else:
        statement = text(
            f"""
            SELECT
                c.id,
                c.{chunk_fk_column} AS doc_id,
                c.chunk_index,
                {token_count_expression},
                {created_at_expression},
                {content_hash_expression},
                NULL::text AS document_title
            FROM chunks c
            {doc_filter}
            ORDER BY {order_by_expression}
            LIMIT :limit
            """
        )

    rows = await _db_fetch_mappings(statement, params)
    items = [
        {
            "id": row["id"],
            "doc_id": row["doc_id"],
            "document_title": row["document_title"],
            "chunk_index": row["chunk_index"],
            "token_count": row["token_count"],
            "created_at": _as_utc_iso(row["created_at"]),
            "content_hash": row["content_hash"],
        }
        for row in rows
    ]

    if args.json:
        _print_json(items)
        return 0

    print(f"Recent chunks (limit={args.limit}):")
    if not documents_exists:
        print("documents table is missing, document titles are unavailable.")
    if not items:
        print("<no chunks>")
        return 0
    for item in items:
        print(
            f"- {item['id']} | doc={item['doc_id']} | idx={item['chunk_index']} | "
            f"tokens={item['token_count']} | created_at={item['created_at']} | "
            f"title={item['document_title']}"
        )
    return 0


def _cmd_db_chunks(args: argparse.Namespace) -> int:
    return _run_db_command(_cmd_db_chunks_async(args))


async def _cmd_db_jobs_async(args: argparse.Namespace) -> int:
    missing_required = await _db_missing_tables("ingest_jobs")
    if missing_required:
        _print_missing_tables_hint(missing_required)
        return 1

    statement = (
        select(
            IngestJob.id,
            IngestJob.status,
            IngestJob.docs_processed,
            IngestJob.chunks_created,
            IngestJob.started_at,
            IngestJob.finished_at,
            IngestJob.error_message,
        )
        .order_by(IngestJob.started_at.desc())
        .limit(args.limit)
    )
    rows = await _db_fetch_rows(statement)
    items = [
        {
            "id": row.id,
            "status": row.status,
            "docs_processed": row.docs_processed,
            "chunks_created": row.chunks_created,
            "started_at": _as_utc_iso(row.started_at),
            "finished_at": _as_utc_iso(row.finished_at),
            "error_message": row.error_message,
        }
        for row in rows
    ]

    if args.json:
        _print_json(items)
        return 0

    print(f"Recent ingest jobs (limit={args.limit}):")
    if not items:
        print("<no ingest jobs>")
        return 0
    for item in items:
        print(
            f"- {item['id']} | status={item['status']} | docs={item['docs_processed']} | "
            f"chunks={item['chunks_created']} | started_at={item['started_at']} | "
            f"finished_at={item['finished_at']}"
        )
        if item["error_message"]:
            print(f"  error: {item['error_message']}")
    return 0


def _cmd_db_jobs(args: argparse.Namespace) -> int:
    return _run_db_command(_cmd_db_jobs_async(args))


async def _cmd_db_document_async(args: argparse.Namespace) -> int:
    missing_required = await _db_missing_tables("documents")
    if missing_required:
        _print_missing_tables_hint(missing_required)
        return 1

    document_columns = await _db_table_columns("documents")
    source_type_expression = "NULL::text AS source_type"
    if "source_type" in document_columns:
        source_type_expression = "source_type::text AS source_type"
    source_url_expression = "NULL::text AS source_url"
    if "source_url" in document_columns:
        source_url_expression = "source_url AS source_url"
    fetched_at_expression = "NULL::timestamptz AS fetched_at"
    fetched_at_column = _db_preferred_column(document_columns, "fetched_at", "created_at")
    if fetched_at_column is not None:
        fetched_at_expression = f"{fetched_at_column} AS fetched_at"
    content_hash_expression = "NULL::text AS content_hash"
    if "content_hash" in document_columns:
        content_hash_expression = "content_hash AS content_hash"
    metadata_expression = "'{}'::jsonb AS metadata"
    if "metadata" in document_columns:
        metadata_expression = "metadata AS metadata"

    doc_statement = text(
        f"""
        SELECT
            id,
            title,
            {source_type_expression},
            {source_url_expression},
            {fetched_at_expression},
            {content_hash_expression},
            {metadata_expression}
        FROM documents
        WHERE id = :id
        LIMIT 1
        """
    )
    doc_rows = await _db_fetch_mappings(doc_statement, {"id": args.id})
    if not doc_rows:
        print(f"Document not found: {args.id}")
        return 1
    document = doc_rows[0]

    chunks_exists = not await _db_missing_tables("chunks")
    chunk_fk_column: str | None = None
    if chunks_exists:
        chunk_fk_column = await _db_chunks_doc_fk_column()
        if chunk_fk_column is None:
            _print_incompatible_schema_hint("chunks", ["doc_id", "document_id"])
            return 1

    chunk_columns = await _db_table_columns("chunks")
    chunk_text_column = _db_preferred_column(chunk_columns, "text", "content")
    if chunks_exists and chunk_text_column is None:
        _print_incompatible_schema_hint("chunks", ["text", "content"])
        return 1

    chunk_token_expression = "0 AS token_count"
    if "token_count" in chunk_columns:
        chunk_token_expression = "token_count AS token_count"
    chunk_created_at_expression = "NULL::timestamptz AS created_at"
    chunk_created_at_column = _db_preferred_column(chunk_columns, "created_at")
    if chunk_created_at_column is not None:
        chunk_created_at_expression = f"{chunk_created_at_column} AS created_at"

    chunk_count = 0
    chunk_rows: list[dict[str, Any]] = []
    if chunks_exists and chunk_fk_column is not None and chunk_text_column is not None:
        chunk_count_statement = text(
            f"""
            SELECT COUNT(*)
            FROM chunks
            WHERE {chunk_fk_column} = :id
            """
        )
        chunk_count = int(await _db_fetch_scalar(chunk_count_statement, {"id": args.id}) or 0)
        chunk_statement = text(
            f"""
            SELECT
                id,
                chunk_index,
                {chunk_token_expression},
                {chunk_created_at_expression},
                {chunk_text_column} AS text
            FROM chunks
            WHERE {chunk_fk_column} = :id
            ORDER BY chunk_index ASC
            LIMIT :chunks_limit
            """
        )
        chunk_rows = await _db_fetch_mappings(
            chunk_statement,
            {"id": args.id, "chunks_limit": args.chunks_limit},
        )

    payload = {
        "id": document["id"],
        "title": document["title"],
        "source_type": document["source_type"],
        "source_url": document["source_url"],
        "fetched_at": _as_utc_iso(document["fetched_at"]),
        "content_hash": document["content_hash"],
        "metadata": document["metadata"] or {},
        "chunk_count": chunk_count,
        "sample_chunks": [
            {
                "id": row["id"],
                "chunk_index": row["chunk_index"],
                "token_count": row["token_count"],
                "created_at": _as_utc_iso(row["created_at"]),
                "text_preview": row["text"][: args.preview_chars],
            }
            for row in chunk_rows
        ],
    }

    if args.json:
        _print_json(payload)
        return 0

    print(f"Document: {payload['id']}")
    print(f"- title: {payload['title']}")
    print(f"- source_type: {payload['source_type']}")
    print(f"- source_url: {payload['source_url']}")
    print(f"- fetched_at: {payload['fetched_at']}")
    print(f"- content_hash: {payload['content_hash']}")
    print(f"- chunk_count: {payload['chunk_count']}")
    print(f"- metadata: {json.dumps(payload['metadata'], sort_keys=True)}")
    if not chunks_exists:
        print("- chunks table is missing")
    print(f"- sample_chunks (limit={args.chunks_limit}):")
    if not payload["sample_chunks"]:
        print("  <none>")
        return 0
    for item in payload["sample_chunks"]:
        print(
            f"  - {item['id']} | idx={item['chunk_index']} | tokens={item['token_count']} | "
            f"created_at={item['created_at']} | text={item['text_preview']!r}"
        )
    return 0


def _cmd_db_document(args: argparse.Namespace) -> int:
    return _run_db_command(_cmd_db_document_async(args))


def _add_api_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://127.0.0.1:8000",
        help="API base URL.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print raw response body without JSON pretty printing.",
    )
    _add_common_verbosity(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="raggy",
        description="Raggy development CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run FastAPI app with uvicorn.")
    run_parser.add_argument("--host", type=str, default=None, help="Bind host.")
    run_parser.add_argument("--port", type=int, default=None, help="Bind port.")
    run_parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable or disable auto-reload.",
    )
    run_parser.add_argument(
        "--jq",
        action="store_true",
        help="Pipe uvicorn output through jq: jq -R 'fromjson? // .'.",
    )
    _add_common_verbosity(run_parser)
    run_parser.set_defaults(func=_cmd_run)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Diagnose DB/API connectivity and schema status.",
    )
    doctor_parser.add_argument(
        "--base-url",
        type=str,
        default="http://127.0.0.1:8000",
        help="API base URL used for /health probe.",
    )
    doctor_parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="HTTP timeout in seconds for API probe.",
    )
    doctor_parser.add_argument("--json", action="store_true", help="Output JSON.")
    doctor_parser.set_defaults(func=_cmd_doctor)

    api_parser = subparsers.add_parser("api", help="Call service API endpoints.")
    api_subparsers = api_parser.add_subparsers(dest="api_command", required=True)

    api_list_parser = api_subparsers.add_parser("list", help="List supported endpoint shortcuts.")
    api_list_parser.set_defaults(func=_cmd_api_list)

    api_health_parser = api_subparsers.add_parser("health", help="Call GET /health.")
    _add_api_common_options(api_health_parser)
    api_health_parser.set_defaults(func=_cmd_api_health)

    api_ingest_parser = api_subparsers.add_parser("ingest", help="Call POST /documents.")
    api_ingest_parser.add_argument("--source-type", choices=["url", "md"], default="md")
    api_ingest_parser.add_argument("--source-url", default=None)
    api_ingest_parser.add_argument("--title", required=True)
    api_ingest_parser.add_argument("--content", required=True)
    api_ingest_parser.add_argument("--metadata-json", default="{}")
    api_ingest_parser.add_argument(
        "--fetched-at",
        default=None,
        help="Optional ISO timestamp, e.g. 2026-02-18T12:00:00Z",
    )
    _add_api_common_options(api_ingest_parser)
    api_ingest_parser.set_defaults(func=_cmd_api_ingest)

    api_query_parser = api_subparsers.add_parser("query", help="Call POST /query.")
    api_query_parser.add_argument("--query", required=True)
    api_query_parser.add_argument("--top-k", type=int, default=5)
    _add_api_common_options(api_query_parser)
    api_query_parser.set_defaults(func=_cmd_api_query)

    api_request_parser = api_subparsers.add_parser(
        "request",
        help="Call any API path with method and optional JSON body.",
    )
    api_request_parser.add_argument("--method", required=True)
    api_request_parser.add_argument("--path", required=True)
    api_request_parser.add_argument("--body-json", default=None)
    _add_api_common_options(api_request_parser)
    api_request_parser.set_defaults(func=_cmd_api_request)

    db_parser = subparsers.add_parser("db", help="Explore database records from terminal.")
    db_subparsers = db_parser.add_subparsers(dest="db_command", required=True)

    db_stats_parser = db_subparsers.add_parser("stats", help="Show row counts by table.")
    db_stats_parser.add_argument("--json", action="store_true", help="Output JSON.")
    db_stats_parser.set_defaults(func=_cmd_db_stats)

    db_documents_parser = db_subparsers.add_parser("documents", help="List recent documents.")
    db_documents_parser.add_argument("--limit", type=int, default=20)
    db_documents_parser.add_argument("--json", action="store_true", help="Output JSON.")
    db_documents_parser.set_defaults(func=_cmd_db_documents)

    db_chunks_parser = db_subparsers.add_parser("chunks", help="List recent chunks.")
    db_chunks_parser.add_argument("--limit", type=int, default=20)
    db_chunks_parser.add_argument(
        "--doc-id",
        type=UUID,
        default=None,
        help="Filter by document UUID.",
    )
    db_chunks_parser.add_argument("--json", action="store_true", help="Output JSON.")
    db_chunks_parser.set_defaults(func=_cmd_db_chunks)

    db_jobs_parser = db_subparsers.add_parser("jobs", help="List recent ingest jobs.")
    db_jobs_parser.add_argument("--limit", type=int, default=20)
    db_jobs_parser.add_argument("--json", action="store_true", help="Output JSON.")
    db_jobs_parser.set_defaults(func=_cmd_db_jobs)

    db_document_parser = db_subparsers.add_parser("document", help="Inspect a single document.")
    db_document_parser.add_argument("--id", type=UUID, required=True, help="Document UUID.")
    db_document_parser.add_argument("--chunks-limit", type=int, default=5)
    db_document_parser.add_argument(
        "--preview-chars",
        type=int,
        default=140,
        help="Character count for each chunk text preview.",
    )
    db_document_parser.add_argument("--json", action="store_true", help="Output JSON.")
    db_document_parser.set_defaults(func=_cmd_db_document)

    eval_parser = subparsers.add_parser("eval", help="Run evaluation metrics on query quality.")
    eval_subparsers = eval_parser.add_subparsers(dest="eval_command", required=True)

    eval_run_parser = eval_subparsers.add_parser("run", help="Run evaluation on golden questions.")
    eval_run_parser.add_argument(
        "--dataset",
        default="eval/golden_qa.jsonl",
        help="Path to golden QA JSONL dataset.",
    )
    eval_run_parser.add_argument(
        "--fixtures",
        default="eval/fixture_docs.jsonl",
        help="Path to fixture docs JSONL for optional bootstrap ingest.",
    )
    eval_run_parser.add_argument(
        "--ingest-fixtures",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Ingest fixture docs before evaluation.",
    )
    eval_run_parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="API base URL for evaluation requests.",
    )
    eval_run_parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds for each request.",
    )
    eval_run_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of questions to run from the dataset.",
    )
    eval_run_parser.add_argument("--json", action="store_true", help="Output JSON.")
    eval_run_parser.set_defaults(func=_cmd_eval_run)

    migrate_parser = subparsers.add_parser("migrate", help="Run Alembic migrations.")
    migrate_subparsers = migrate_parser.add_subparsers(dest="migrate_command", required=True)

    migrate_up_parser = migrate_subparsers.add_parser("up", help="Upgrade DB schema.")
    migrate_up_parser.add_argument("revision", nargs="?", default="head")
    _add_common_verbosity(migrate_up_parser)
    migrate_up_parser.set_defaults(func=_cmd_migrate_up)

    migrate_down_parser = migrate_subparsers.add_parser("down", help="Downgrade DB schema.")
    migrate_down_parser.add_argument("revision", nargs="?", default="-1")
    _add_common_verbosity(migrate_down_parser)
    migrate_down_parser.set_defaults(func=_cmd_migrate_down)

    migrate_new_parser = migrate_subparsers.add_parser("new", help="Create migration revision.")
    migrate_new_parser.add_argument("message", help="Migration message.")
    migrate_new_parser.add_argument(
        "--autogenerate",
        action="store_true",
        help="Enable Alembic autogeneration.",
    )
    _add_common_verbosity(migrate_new_parser)
    migrate_new_parser.set_defaults(func=_cmd_migrate_new)

    lint_parser = subparsers.add_parser("lint", help="Run ruff linting.")
    _add_common_verbosity(lint_parser)
    lint_parser.set_defaults(func=_cmd_lint)

    typecheck_parser = subparsers.add_parser("typecheck", help="Run mypy type checking.")
    _add_common_verbosity(typecheck_parser)
    typecheck_parser.set_defaults(func=_cmd_typecheck)

    test_parser = subparsers.add_parser("test", help="Run pytest.")
    _add_common_verbosity(test_parser)
    test_parser.set_defaults(func=_cmd_test)

    check_parser = subparsers.add_parser("check", help="Run lint and type-check.")
    _add_common_verbosity(check_parser)
    check_parser.set_defaults(func=_cmd_check)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    exit_code = int(args.func(args))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
