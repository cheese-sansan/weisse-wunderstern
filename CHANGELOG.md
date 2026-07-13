# Changelog

All notable changes to NoteForge are documented here.

## Unreleased

No unreleased changes yet.

## v0.3.0 - 2026-07-11

### Added

- Installable `src/noteforge` package, unified `noteforge` command, typed dataclass SDK, and provider protocol.
- Schema-v3 semantic context, strict Job/Stage state machines, and structured error records.
- Transactional, idempotent v0.2 job migration with byte-exact backups and rollback.
- Wheel-first CI, Ruff, Pyright, 80% coverage gate, OpenAPI snapshot, API smoke, privacy audit, and Docker build.

### Changed

- CLI, TUI, API, and Docker now share `AnalysisRequest` and `run_job`.
- New jobs write only canonical `report.md`; HTTP API v1 paths and response fields remain compatible.
- Dependencies are expressed as `api`, `documents`, and `dev` extras in `pyproject.toml`.

### Removed

- Root launch scripts, `run.sh`, legacy `core/tasks/utils` imports, and all `requirements-*.txt` files.

## v0.2.0 - 2026-07-10

### Added

- Real Crossref literature retrieval with bounded retry and no required API key.
- Explicit `crossref`, `mock`, and `llm-simulated` provider selection across CLI, TUI, API, and SDK.
- Source registry, provider status, retrieval warnings, and evidence-aware claim records.
- Structured T5 technical cases and strict T6 policy evidence assessment.
- Canonical `report.md`, real-provider sample output, and Mock-versus-real documentation.

### Changed

- Crossref is the default provider; model credentials no longer select a literature source.
- Provider failures complete with empty evidence and warnings instead of simulated fallback.
- T5/T6 run before T4 so dynamic analysis is included in the final report.
- Resume logic reloads completed context before rebuilding downstream artifacts.
- FastAPI and public release version are aligned to `0.2.0`.

### Compatibility

- `report_framework.md`, existing API result fields, and legacy custom-provider record fields remain available during v0.2.

## v0.1.0 - 2026-06-14

### Added

- CLI topic/file analysis pipeline.
- Zero-dependency TUI with interactive and one-shot modes.
- FastAPI service with submit/status/result endpoints.
- Docker Compose deployment with optional extras build.
- Configurable Docker base image through `PYTHON_IMAGE`.
- Public Python integration surface through `core.run_job`.
- Privacy audit script and CI integration.
- Unit tests, smoke tests, API tests, and Docker validation.

### Changed

- Job artifacts are isolated under `outputs/jobs/{job_id}/`.
- State and context writes use atomic replacement.
- T1/T2/T3 outputs are normalized into structured schemas.
- Mock mode remains available without external services.

### Security

- Job IDs and upload filenames are validated.
- Generated outputs, local environment files, credentials, cache files, and local samples are ignored by default.
- LLM HTTP error logging avoids recording upstream response bodies.
