# Changelog

All notable changes to Lite Agent Orchestrator are documented here.

## Unreleased

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
