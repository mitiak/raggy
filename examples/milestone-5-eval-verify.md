# Milestone 5 Verification (Evaluation Harness) — Planned

## Target command flow after implementation

```bash
uv run raggy eval run
uv run raggy eval run --json
```

## Expected outputs

- citation correctness metric
- retrieval hit rate metric
- "I don't know" rate metric
- clear pass/fail thresholds

## Planned e2e test

```bash
uv run pytest -q tests/test_milestone5_eval_e2e.py
```
