# Development Guide

This document describes the public architecture and development workflow for Lite Agent Orchestrator.

## Architecture

```text
input topic/file
  -> core.pipeline.run_job
  -> T0 document parsing, when file input exists
  -> T1 keyword and academic entity extraction
  -> T2 structured literature candidates
  -> T3 extractor / critic / synthesizer report loop
  -> T4 Markdown report framework
  -> optional T5/T6 lightweight dynamic branches
```

The CLI, TUI, and API all share `core.pipeline.run_job`.

## Public Entrypoints

- `main.py`: CLI entrypoint.
- `main_tui.py`: zero-dependency text UI.
- `main_api.py`: FastAPI service.
- `core.run_job`: Python integration surface.

## Job Artifacts

Each job writes to `outputs/jobs/{job_id}/`:

```text
task_state.json
context_data.json
resume_log.txt
report_framework.md
```

`StateManager` and `ContextStore` validate `job_id`, isolate per-job state, and write JSON atomically.

## Dependencies

- `requirements.txt`: core note; CLI/Mock mode uses the standard library.
- `requirements-api.txt`: FastAPI service dependencies.
- `requirements-dev.txt`: test/development dependencies.
- `requirements-extras.txt`: optional document parsing dependencies.

## Local Development

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Linux/macOS:

```bash
source .venv/bin/activate
```

## Verification

Run before committing:

```bash
python check_all.py
python smoke_test.py
```

Run when API, upload, authentication, or deployment code changes:

```bash
python test_api_client.py
docker compose config
docker compose build api
```

Run before public release:

```bash
python scripts/privacy_audit.py --history
python scripts/privacy_audit.py --include-outputs
```

## Docker Notes

```bash
docker compose up -d
docker compose down
```

Optional extras image:

```powershell
$env:INSTALL_EXTRAS="true"
docker compose build api
```

Base image override:

```powershell
$env:PYTHON_IMAGE="docker.m.daocloud.io/library/python:3.10-slim"
docker compose build api
```

## Development Principles

- Mock mode must remain fully usable without external services.
- Simulated literature must be labeled with `source_type: simulated`.
- Do not claim real external literature retrieval until a real provider is implemented.
- Do not log or commit credentials, generated reports, private paths, or local-only documents.
- Keep downstream imports stable where practical: `core.run_job`, `PipelineError`, `StateManager`, `ContextStore`, and `read_file`.
