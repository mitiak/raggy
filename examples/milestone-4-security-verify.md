# Milestone 4 Verification (Security + Guardrails)

## 1) Start services

```bash
docker compose up -d db
uv run raggy migrate up
uv run raggy run --no-reload
```

## 2) Check baseline health

```bash
uv run raggy doctor --json
uv run raggy api health
```

## 3) Verify request size limit (413)

```bash
BIG_QUERY="$(python - <<'PY'
print('x' * 250000)
PY
)"

uv run raggy api request \
  --method POST \
  --path /query \
  --body-json "{\"query\": \"$BIG_QUERY\", \"top_k\": 5}"
```

Expected: `HTTP 413` with `{"detail":"Request payload too large"}`.

## 4) Verify rate limiting (429)

Use strict limits for local verification in one shell:

```bash
export RATE_LIMIT_REQUESTS=2
export RATE_LIMIT_WINDOW_SECONDS=60
uv run raggy run --no-reload
```

In another shell:

```bash
uv run raggy api health
uv run raggy api health
uv run raggy api health
```

Expected: third request returns `HTTP 429`.

## 5) Run automated e2e guardrail tests

```bash
uv run pytest -q tests/test_milestone4_guardrails_e2e.py
```
