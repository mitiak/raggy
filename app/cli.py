from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from collections.abc import Sequence
from typing import Any
from urllib import error, request

from app.core.config import get_settings


def _run_command(command: Sequence[str]) -> int:
    process = subprocess.run(command, check=False)
    return process.returncode


def _run_shell_command(command: str) -> int:
    process = subprocess.run(command, check=False, shell=True)
    return process.returncode


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
            "| jq -R 'fromjson? // .'"
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
