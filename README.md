# NoteForge

NoteForge 0.3 is an installable, evidence-aware Python package for topic and document analysis. CLI, TUI, FastAPI, and Python integrations all use the same typed SDK, configuration loader, semantic context, and persisted state machine.

## Install

Python 3.10–3.13 is supported.

```bash
python -m pip install .

# FastAPI service
python -m pip install ".[api]"

# Optional PDF, DOCX, spreadsheet, presentation, EPUB, and OCR parsers
python -m pip install ".[documents]"
```

The core SDK and CLI have no required third-party dependencies.

## CLI

```bash
noteforge run --topic "transformer model evaluation" --provider crossref
noteforge run --file ./examples/sample_paper_abstract.md --provider mock --job-id demo
noteforge tui
noteforge jobs list
noteforge jobs migrate --all
noteforge report demo
noteforge api --host 0.0.0.0 --port 8000
```

New jobs write only these canonical artifacts under `outputs/jobs/{job_id}/`:

```text
task_state.json
context_data.json
resume_log.txt
report.md
```

## Python SDK

```python
from pathlib import Path

from noteforge import AnalysisRequest, run_job

result = run_job(
    AnalysisRequest(
        topic="LLM deployment",
        provider="mock",
        job_id="sdk-demo",
    ),
    output_root=Path("outputs"),
)
print(result.status, result.report_path, result.sources)
```

`AnalysisRequest`, `JobResult`, literature/source/case/policy records, Job/Stage/Artifact models, enums, and structured errors use standard-library dataclasses. `LiteratureProvider.search(LiteratureQuery)` is the stable provider extension contract.

## Providers and evidence

- `crossref` is the default real metadata provider and needs no API key.
- `mock` is deterministic simulated data for tests and offline demos.
- `llm-simulated` is explicitly simulated model output.

Crossref failures return an empty evidence set with warnings; NoteForge never silently substitutes simulated citations. Metadata and generated analysis still require verification against authoritative sources.

## API and Docker

The HTTP v1 paths and existing response fields remain compatible:

```bash
curl -X POST http://localhost:8000/api/v1/jobs/submit \
  -F "topic=AI safety" -F "provider=crossref"
curl http://localhost:8000/api/v1/jobs/status/{job_id}
curl http://localhost:8000/api/v1/jobs/result/{job_id}
```

```bash
docker compose up -d --build
```

Set `INSTALL_EXTRAS=true` during the Docker build to install the `documents` extra. The image installs `.[api]` and starts with `noteforge api`.

## Upgrading from v0.2

Version 0.3 intentionally removes `main.py`, `main_tui.py`, `main_api.py`, `core`, `tasks`, `utils`, and all `requirements-*.txt` entry points. Import from `noteforge` and use the `noteforge` command.

On first read, a v0.2 job is migrated in its own job lock. Original state and context are retained as `task_state.v0.2.json` and `context_data.v0.2.json`; legacy `report_framework.md` remains and is copied to canonical `report.md` when needed. Use `noteforge jobs migrate --all` for explicit pre-migration.

## Quality gates

```bash
python -m build --wheel
ruff check src/noteforge tests scripts
pyright src/noteforge
pytest --cov=noteforge --cov-fail-under=80
python scripts/check_openapi.py
python scripts/api_smoke.py
python scripts/privacy_audit.py
docker compose build api
```

See [CLI/TUI/API usage](docs/cli_tui_api.md), [SDK integration](docs/developer_integration.md), [migration guide](docs/migration_v0.3.md), and [v0.3.0 release notes](docs/releases/v0.3.0.md).

## License

MIT
