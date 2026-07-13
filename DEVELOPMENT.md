# Development Guide

## Architecture

All entry points call `noteforge.run_job(AnalysisRequest, output_root=...)`. The pipeline persists schema-v3 semantic context keys:

```text
input -> document -> keywords -> literature -> synthesis
      -> technical_cases -> policy_assessment -> report
```

Job states are `PENDING`, `RUNNING`, `COMPLETED`, and `FAILED`. Stage states add `SKIPPED`. Invalid transitions raise a structured `NoteForgeError`.

The package uses a `src/noteforge` layout. `core`, `tasks`, and `utils` are deliberately not compatibility packages in v0.3.

## Environment

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install ".[dev,documents]"
```

## Verification

```bash
python -m build --wheel
ruff check src/noteforge tests scripts
pyright src/noteforge
pytest --cov=noteforge --cov-report=term-missing --cov-fail-under=80
python scripts/check_openapi.py
python scripts/api_smoke.py
python scripts/privacy_audit.py
docker compose config
docker compose build api
```

CI builds and installs a wheel before testing. It also installs and exercises the wheel on Python 3.10, 3.11, 3.12, and 3.13. Changes to HTTP v1 require deliberate review of `tests/snapshots/openapi_v1.json`.

## Persistence

`StateManager` and `ContextStore` validate job IDs and use atomic replacement. The migration layer backs up v0.2 files byte-for-byte, validates both v3 documents before replacement, and restores originals if either replacement fails.

Keep mock data visibly simulated, keep provider failures visible, and never commit credentials or generated jobs.
