# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Established changelog management with Keep a Changelog format.
- Expanded README with detailed instructions for setup, development, Docker usage, migrations, and quality checks.

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
