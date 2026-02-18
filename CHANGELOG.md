# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Established changelog management with Keep a Changelog format.
- Expanded README with detailed instructions for setup, development, Docker usage, migrations, and quality checks.
- Added `raggy` development CLI for running the API, migrations, linting, type-checking, and tests from terminal.
- Added `raggy run --jq` option to run `uvicorn` through `jq -R 'fromjson? // .'` for readable log output.
- Expanded DB schema with `documents` source metadata/hash fields, richer `chunks` fields, and a new `ingest_jobs` model plus vector/GIN indexes.
- Added `raggy api` CLI commands to trigger available API endpoints (`/health`, `/documents`, `/query`) and custom requests from terminal.
- Added `raggy db` CLI commands to explore DB contents (`stats`, `documents`, `chunks`, `jobs`, `document`) from terminal.
- Added fun real-document CLI exploration examples using Rubber Duck Debugging in `/Users/dimako/src/raggy/examples/fun-doc-rubber-duck.md`.
- Fixed enum migration re-run failures (`source_type_enum` already exists) and added forward migration `0002_add_ingest_jobs_if_missing`.
- Added pytest coverage for document ingestion service logic and CLI API/db helper behavior.

## [0.1.0] - 2026-02-18

### Added

- Initial production-ready RAG backend scaffold.
- FastAPI application with layered architecture (`api`, `services`, `db`, `models`, `schemas`).
- Async SQLAlchemy 2.0 integration with dependency-injected DB sessions.
- PostgreSQL + pgvector setup via Docker Compose.
- Alembic migration configuration and initial schema for `documents` and `chunks`.
- Document ingestion and vector retrieval service flows.
- Structured JSON logging and request middleware instrumentation.
- Worker-ready protocol/types in `app/workers` for future background processing.
- Strict typing/lint tooling (`mypy`, `ruff`) and project packaging configuration.
