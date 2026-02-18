from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from collections.abc import Sequence

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
