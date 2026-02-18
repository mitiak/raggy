# raggy

Production-ready RAG backend using FastAPI, Postgres + pgvector, SQLAlchemy async, and Alembic.

## Run locally

```bash
docker compose up --build
```

## Migrations

```bash
alembic upgrade head
```
