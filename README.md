# Weisse Wunderstern

Weisse Wunderstern is a poetic lightweight agent for distilling topics, tracing ideas, and forging structured research reports. It can run as a local CLI/TUI tool, a FastAPI service, a Docker deployment, or a small Python library embedded in another project.

The project focuses on document/topic distillation: parse input, extract keywords and academic entities, generate structured literature candidates, run a lightweight extractor/critic/synthesizer loop, and produce a Markdown report.

## Features

- CLI pipeline for topic or file analysis.
- Zero-dependency TUI for local interactive use.
- FastAPI service with submit/status/result endpoints.
- Docker Compose deployment with optional document parsing extras.
- Mock mode that works without any API key.
- Optional OpenAI-compatible LLM enhancement.
- Job-isolated state and artifacts under `outputs/jobs/{job_id}/`.
- Privacy audit, unit tests, smoke tests, API tests, and GitHub Actions CI.

## Quick Start

```bash
git clone https://github.com/cheese-sansan/weisse-wunderstern.git
cd weisse-wunderstern

python main.py --topic "transformer model evaluation"
python main.py --file ./examples/sample_paper_abstract.md
python main_tui.py
```

Generated artifacts are written to:

```text
outputs/jobs/{job_id}/
├── task_state.json
├── context_data.json
├── resume_log.txt
└── report_framework.md
```

## API Service

```bash
pip install -r requirements-api.txt
python main_api.py
```

```bash
curl -X POST http://localhost:8000/api/v1/jobs/submit -F "topic=AI safety"
curl http://localhost:8000/api/v1/jobs/status/{job_id}
curl http://localhost:8000/api/v1/jobs/result/{job_id}
```

Set `API_TOKEN` to require bearer-token authentication for `/api/v1/jobs/*`.

## Docker

```bash
docker compose up -d
docker compose logs -f
```

Build with optional parsing dependencies:

```powershell
$env:INSTALL_EXTRAS="true"
docker compose up -d --build
```

If Docker Hub is unavailable, override the base image:

```powershell
$env:PYTHON_IMAGE="docker.m.daocloud.io/library/python:3.10-slim"
docker compose build api
```

## Optional LLM Mode

Mock mode is the default and requires no key. To enable an OpenAI-compatible LLM provider:

```bash
cp .env.example .env
# edit OPENAI_API_KEY / OPENAI_API_BASE / LLM_MODEL
```

Never commit `.env` or real credentials.

## Quality Checks

```bash
python check_all.py
python smoke_test.py
python test_api_client.py
python scripts/privacy_audit.py --history
```

`check_all.py` runs privacy auditing, Python compilation, and unit tests.

## Documentation

- [CLI/TUI/API usage](docs/cli_tui_api.md)
- [Developer integration](docs/developer_integration.md)
- [Development guide](DEVELOPMENT.md)
- [Roadmap](README_plan.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Changelog](CHANGELOG.md)

## License

MIT
