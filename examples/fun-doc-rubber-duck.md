# CLI Exploration Examples (Fun Real Document)

This walkthrough uses a real (and fun) document from Wikipedia:

- Source: https://en.wikipedia.org/wiki/Rubber_duck_debugging
- API text source: https://en.wikipedia.org/api/rest_v1/page/summary/Rubber_duck_debugging
- Topic: Explaining bugs to a rubber duck

## 1) Start services

In one terminal:

```bash
docker compose up --build
```

In another terminal (optional health check):

```bash
uv run raggy api health
```

## 2) Fetch a fun real document excerpt and ingest it

```bash
DOC_URL="https://en.wikipedia.org/wiki/Rubber_duck_debugging"
DOC_TITLE="Rubber Duck Debugging (Wikipedia summary)"
DOC_CONTENT="$(curl -fsSL 'https://en.wikipedia.org/api/rest_v1/page/summary/Rubber_duck_debugging' | jq -r '.extract')"

uv run raggy api ingest \
  --source-type url \
  --source-url "$DOC_URL" \
  --title "$DOC_TITLE" \
  --content "$DOC_CONTENT" \
  --metadata-json '{"source":"wikipedia","topic":"rubber_duck_debugging","mood":"fun"}'
```

Expected result: `HTTP 201` and JSON containing document identifiers and metadata.

## 3) Query the ingested content

```bash
uv run raggy api query --query "Why does talking to a rubber duck help debugging?" --top-k 5
```

Expected result: `HTTP 200` and non-empty `results`.

## 4) Ask playful questions

```bash
uv run raggy api query --query "Is this duck a real software engineer?" --top-k 3
uv run raggy api query --query "What behavior does this debugging method encourage?" --top-k 3
```

## 5) Explore validation behavior (intentional invalid request)

`top_k` must be between `1` and `20`. This command triggers a validation error:

```bash
uv run raggy api query --query "quack" --top-k 50
```

Expected result: `HTTP 422` with validation details.

## 6) Explore unknown endpoint behavior

```bash
uv run raggy api request --method GET --path /does-not-exist
```

Expected result: `HTTP 404`.

## 7) Raw output mode

If you want exact response payload without pretty formatting:

```bash
uv run raggy api query --query "duck" --top-k 3 --raw
```

## 8) Non-default API URL

If API is running elsewhere:

```bash
uv run raggy api health --base-url http://localhost:8080
```
