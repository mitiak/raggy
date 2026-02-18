# CLI Command Examples (All Commands)

Use these from the project root (`/Users/dimako/src/raggy`).

## 0) Setup once

```bash
uv sync --extra dev
docker compose up -d db
uv run raggy migrate up
```

## 1) `run`

Start API:

```bash
uv run raggy run
```

Start API with pretty log output:

```bash
uv run raggy run --jq
```

Custom host/port and no reload:

```bash
uv run raggy run --host 127.0.0.1 --port 8080 --no-reload
```

## 1.1) `doctor`

Run all-in-one diagnostics (DB URL, DB schema/counts, API health):

```bash
uv run raggy doctor
```

Machine-readable diagnostics:

```bash
uv run raggy doctor --json
```

Probe non-default API URL:

```bash
uv run raggy doctor --base-url http://localhost:8080 --timeout 5
```

## 2) `api`

List endpoint shortcuts:

```bash
uv run raggy api list
```

Health check:

```bash
uv run raggy api health
```

Health check against another host:

```bash
uv run raggy api health --base-url http://localhost:8080 --timeout 5
```

Ingest a simple document:

```bash
uv run raggy api ingest \
  --source-type md \
  --title "Debug diary" \
  --content "Today I fixed a bug by talking to a rubber duck." \
  --metadata-json '{"mood":"fun","topic":"debugging"}'
```

Ingest using URL source:

```bash
uv run raggy api ingest \
  --source-type url \
  --source-url "https://en.wikipedia.org/wiki/Rubber_duck_debugging" \
  --title "Rubber duck debugging" \
  --content "A debugging method where the programmer explains code out loud." \
  --metadata-json '{"source":"wikipedia"}' \
  --fetched-at "2026-02-18T12:00:00Z"
```

Query:

```bash
uv run raggy api query --query "why does rubber duck debugging help?" --top-k 5
```

Query raw output:

```bash
uv run raggy api query --query "rubber duck" --top-k 3 --raw
```

Generic API request:

```bash
uv run raggy api request --method POST --path /query --body-json '{"query":"duck","top_k":2}'
```

## 3) `db`

Table counts:

```bash
uv run raggy db stats
```

Table counts as JSON:

```bash
uv run raggy db stats --json
```

Recent documents:

```bash
uv run raggy db documents --limit 10
```

Recent documents as JSON:

```bash
uv run raggy db documents --limit 10 --json
```

Recent chunks:

```bash
uv run raggy db chunks --limit 10
```

Recent chunks for one document:

```bash
uv run raggy db chunks --doc-id <DOCUMENT_UUID> --limit 10
```

Recent ingest jobs:

```bash
uv run raggy db jobs --limit 10
```

Inspect one document:

```bash
uv run raggy db document --id <DOCUMENT_UUID> --chunks-limit 5 --preview-chars 160
```

Inspect one document as JSON:

```bash
uv run raggy db document --id <DOCUMENT_UUID> --json
```

Tip to get a UUID quickly:

```bash
uv run raggy db documents --json | jq -r '.[0].id'
```

## 4) `migrate`

Upgrade to head:

```bash
uv run raggy migrate up
```

Upgrade to a specific revision:

```bash
uv run raggy migrate up 0002_add_ingest_jobs_if_missing
```

Downgrade one step:

```bash
uv run raggy migrate down
```

Downgrade to a specific revision:

```bash
uv run raggy migrate down 0001_init
```

Create a migration:

```bash
uv run raggy migrate new "add_new_table"
```

Create migration with autogenerate:

```bash
uv run raggy migrate new "add_new_table" --autogenerate
```

## 5) Quality commands

Lint:

```bash
uv run raggy lint
```

Type-check:

```bash
uv run raggy typecheck
```

Tests:

```bash
uv run raggy test
```

Lint + type-check:

```bash
uv run raggy check
```

## 6) `eval`

Run golden evaluation with fixture ingest:

```bash
uv run raggy eval run
```

JSON report:

```bash
uv run raggy eval run --json
```

Fast smoke run on first 3 questions:

```bash
uv run raggy eval run --limit 3 --json
```

Evaluate existing corpus only (skip fixture ingest):

```bash
uv run raggy eval run --no-ingest-fixtures --json
```
