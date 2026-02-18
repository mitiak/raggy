# Milestone 5 Verification (Evaluation Harness)

## 1) Start services

```bash
docker compose up -d db
uv run raggy migrate up
uv run raggy run --no-reload
```

## 2) Run evaluation (default dataset + fixtures)

```bash
uv run raggy eval run
```

Expected output includes:

- `total_questions`
- `retrieval_hit_rate`
- `citation_correctness`
- `idk_rate_unanswerable`

## 3) JSON output mode

```bash
uv run raggy eval run --json
```

## 4) Run subset for quick smoke

```bash
uv run raggy eval run --limit 3 --json
```

## 5) Disable fixture ingest (evaluate existing corpus only)

```bash
uv run raggy eval run --no-ingest-fixtures --json
```

## 6) Run automated e2e test for milestone 5

```bash
uv run pytest -q tests/test_milestone5_eval_e2e.py
```
