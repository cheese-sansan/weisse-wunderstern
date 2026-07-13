# v0.3 Release Checklist

- Confirm `src/noteforge/version.py`, package metadata, CLI, TUI, and FastAPI report `0.3.0`.
- Confirm wheel installation works outside the checkout on Python 3.10–3.13.
- Confirm all CLI subcommands and the SDK example run from the installed wheel.
- Confirm no legacy root launch scripts, `core/tasks/utils`, or `requirements-*.txt` files remain.
- Confirm all tests pass with no skips and coverage is at least 80%.
- Run Ruff, Pyright standard, OpenAPI snapshot, API smoke, privacy audit, Compose validation, and Docker build.
- Confirm v0.2 migration success, byte-exact backups, idempotence, rollback, and concurrent first-read tests pass.
- Confirm API v1 paths, request fields, response fields, and status codes match the committed snapshot.

```bash
python -m build --wheel
ruff check src/noteforge tests scripts
pyright src/noteforge
pytest --cov=noteforge --cov-fail-under=80
python scripts/check_openapi.py
python scripts/api_smoke.py
python scripts/privacy_audit.py --history
docker compose config
docker compose build api
```
