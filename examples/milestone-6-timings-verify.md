# Milestone 6 Verification (retrieve_ms + gen_ms)

## 1) Start services

```bash
docker compose up -d db
uv run raggy migrate up
uv run raggy run --no-reload
```

## 2) Ingest one quick doc

```bash
uv run raggy api ingest \
  --source-type md \
  --title "Timing Doc" \
  --content "Timings should be exposed for retrieval and generation stages." \
  --metadata-json '{"lang":"en","source":"timing"}'
```

## 3) Query and inspect timing fields in response

```bash
uv run raggy api request \
  --method POST \
  --path /query \
  --body-json '{"query":"timing","top_k":5,"used_filters":{"lang":"en"}}'
```

Expected response fields include:

- `retrieve_ms`
- `gen_ms`

## 4) Extract timing fields quickly with jq

```bash
uv run raggy api request \
  --method POST \
  --path /query \
  --body-json '{"query":"timing","top_k":5,"used_filters":{"lang":"en"}}' \
  --raw | jq '{retrieve_ms, gen_ms, confidence}'
```

## 5) Run automated e2e test for milestone 6

```bash
uv run pytest -q tests/test_milestone6_timings_e2e.py
```
