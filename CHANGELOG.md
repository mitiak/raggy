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
- Added `/Users/dimako/src/raggy/examples/cli-command-examples.md` with examples for all CLI commands and subcommands.
- Added `raggy doctor` command to diagnose effective DB target, schema/table status, and API health in one step.
- Fixed empty vector search results on small datasets by setting `ivfflat.probes` during retrieval (configurable via `IVFFLAT_PROBES`).
- Added API e2e tests for `/health`, `/documents`, and `/query` (including validation error path).
- Made ingestion idempotent/deterministic by deduping existing documents and generating deterministic chunk UUIDs from `doc_id + chunk_index + text`.
- Added Alembic migration `0003_doc_idempotency` with unique index `uq_documents_idempotency` for dedupe/upsert safety.
- Added dedicated `RagService` generation layer so `/query` answer synthesis is separated from retrieval and routes.
- Implemented milestone-4 guardrails: request size limiting (413) and basic in-memory rate limiting (429).
- Added milestone verification guides for 3/4 and planned guides for 5/6 under `/Users/dimako/src/raggy/examples/`.
- Added e2e tests for milestone 4 guardrails and placeholder pending e2e specs for milestones 5 and 6.
- Implemented milestone-5 evaluation harness with `raggy eval run`, fixture docs, golden QA set, and metrics (citation correctness, retrieval hit rate, IDK rate).
- Added milestone-5 e2e test in `/Users/dimako/src/raggy/tests/test_milestone5_eval_e2e.py`.

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
