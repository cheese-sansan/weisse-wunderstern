# NoteForge

NoteForge is a lightweight, evidence-aware topic and document distillation pipeline. It retrieves real scholarly metadata, separates source facts from model inference, and produces structured Markdown research reports through CLI, TUI, FastAPI, Docker, or a small Python integration surface.

## Capabilities

- Topic or document analysis through CLI and zero-dependency TUI.
- Real Crossref literature retrieval by default, without an API key.
- Explicit `mock` and `llm-simulated` modes for offline demonstrations.
- Source labels for external APIs, source documents, LLM inference, simulated data, and unverified content.
- Extractor/Critic/Synthesizer review loop with evidence references.
- Evidence-gated technical case and policy impact outputs.
- FastAPI submit/status/result endpoints and Docker Compose deployment.
- Job-isolated state, context, reports, warnings, and resume support.

NoteForge does not treat metadata retrieval as full-text verification. DOI records, abstracts, generated analysis, and policy conclusions must still be checked against authoritative sources.

## Quick Start

```bash
git clone https://github.com/cheese-sansan/NoteForge.git
cd NoteForge

# Real Crossref retrieval (default)
python main.py --topic "transformer model evaluation"

# Explicit offline demonstration
python main.py --topic "transformer model evaluation" --provider mock

# Analyze a local document
python main.py --file ./examples/sample_paper_abstract.md --provider crossref

python main_tui.py
```

Generated artifacts are written to `outputs/jobs/{job_id}/`:

```text
task_state.json
context_data.json
resume_log.txt
report.md
report_framework.md  # v0.1 compatibility copy
```

## Literature Providers

Provider selection is independent from the LLM configuration:

- `crossref`: real external metadata; default.
- `mock`: deterministic simulated data for tests and offline demos.
- `llm-simulated`: model-generated demonstration records; never presented as retrieval.

Configure through `--provider` or environment variables:

```bash
LITERATURE_PROVIDER=crossref
LITERATURE_MAX_RESULTS=10
LITERATURE_TIMEOUT_SECONDS=10
CROSSREF_MAILTO=research@example.com  # optional polite-pool contact
```

Crossref failures produce an empty evidence set and a visible warning. NoteForge does not silently fall back to simulated literature.

## API Service

```bash
pip install -r requirements-api.txt
python main_api.py
```

```bash
curl -X POST http://localhost:8000/api/v1/jobs/submit \
  -F "topic=AI safety" -F "provider=crossref"
curl http://localhost:8000/api/v1/jobs/status/{job_id}
curl http://localhost:8000/api/v1/jobs/result/{job_id}
```

The result response includes the Markdown report, provider status, source registry, technical cases, policy assessment, and warnings. Set `API_TOKEN` to protect `/api/v1/jobs/*` with bearer authentication.

## Optional LLM Enhancement

Mock analysis is used when no model key is configured. To enable OpenAI-compatible evidence extraction and synthesis:

```bash
cp .env.example .env
# edit OPENAI_API_KEY / OPENAI_API_BASE / LLM_MODEL
```

An LLM key never turns simulated records into real retrieval results.

## Docker

```bash
docker compose up -d --build
docker compose logs -f
```

Set `INSTALL_EXTRAS=true` to include optional PDF, DOCX, spreadsheet, presentation, EPUB, and OCR-related parsers.

## Quality Checks

```bash
python check_all.py
python smoke_test.py
python test_api_client.py
python scripts/privacy_audit.py --history
docker compose config
```

## Documentation

- [CLI, TUI, and API usage](docs/cli_tui_api.md)
- [Developer integration](docs/developer_integration.md)
- [Mock vs real provider behavior](docs/mock_vs_real_provider.md)
- [Real Crossref report sample](examples/sample_crossref_report.md)
- [Document analysis report sample](examples/sample_document_report.md)
- [Development guide](DEVELOPMENT.md)
- [Public roadmap](README_plan.md)
- [v0.2.0 release notes](docs/releases/v0.2.0.md)
- [Release checklist](docs/release_checklist.md)

## License

MIT
