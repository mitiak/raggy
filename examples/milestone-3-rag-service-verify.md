# Milestone 3 Verification (RagService Layer)

These commands verify that `/query` is served through the dedicated RAG layer and returns grounded structured output.

## 1) Start DB and apply migrations

```bash
docker compose up -d db
uv run raggy migrate up
```

## 2) Start API

```bash
uv run raggy run --no-reload
```

## 3) Ingest sample docs

```bash
uv run raggy api ingest \
  --source-type md \
  --title "Duck Notes 1" \
  --content "Rubber duck debugging helps developers explain logic clearly." \
  --metadata-json '{"product":"raggy","lang":"en","source":"guide"}'

uv run raggy api ingest \
  --source-type md \
  --title "Duck Notes 2" \
  --content "Talking through code exposes hidden assumptions and edge cases." \
  --metadata-json '{"product":"raggy","lang":"en","source":"guide"}'
```

## 4) Query and inspect structured response

```bash
uv run raggy api request \
  --method POST \
  --path /query \
  --body-json '{"query":"why does duck debugging help?","top_k":5,"used_filters":{"lang":"en","source":"guide"}}'
```

Expected:
- HTTP 200
- response keys: `answer`, `citations`, `used_filters`, `confidence`
- `citations` is non-empty when `answer` is a claim

## 5) Unknown-path behavior

```bash
uv run raggy api request \
  --method POST \
  --path /query \
  --body-json '{"query":"question with no matching docs","top_k":5,"used_filters":{"lang":"zz"}}'
```

Expected:
- HTTP 200
- `answer` indicates unknown/not enough information
- `citations` can be empty

## 6) Automated tests for milestone 3

```bash
uv run pytest -q tests/test_api_rag_service_e2e.py
uv run pytest -q
```
