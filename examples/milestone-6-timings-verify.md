# Milestone 6 Verification (retrieve_ms + gen_ms) — Planned

## Target command flow after implementation

```bash
uv run raggy api request --method POST --path /query --body-json '{"query":"duck debugging","top_k":5}'
```

## Expected behavior

- response metadata includes `retrieve_ms` and `gen_ms` (if exposed in API)
- structured logs include `retrieve_ms` and `gen_ms` per request

## Planned e2e test

```bash
uv run pytest -q tests/test_milestone6_timings_e2e.py
```
