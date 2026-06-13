# Roadmap And Release Checklist

This file records the current public roadmap for Weisse Wunderstern. It intentionally avoids local-only documents, private sample names, and development-chat history.

## Current Status

The project is ready as a lightweight public prototype with:

- CLI topic/file analysis.
- Zero-dependency TUI.
- FastAPI submit/status/result service.
- Docker Compose deployment.
- Mock mode without required API keys.
- Optional OpenAI-compatible LLM mode.
- Job-isolated artifacts under `outputs/jobs/{job_id}/`.
- Atomic state/context writes.
- Unit tests, smoke tests, API tests, Docker validation, privacy audit, and CI.

## Release Readiness

Before publishing, run:

```bash
python check_all.py
python smoke_test.py
python test_api_client.py
python scripts/privacy_audit.py --history
python scripts/privacy_audit.py --include-outputs
docker compose config
docker compose build api
```

Optional:

```powershell
$env:INSTALL_EXTRAS="true"
docker compose build api
```

## Near-Term Priorities

### P0: Public Release Hygiene

- Confirm no `.env`, generated reports, local sample documents, IDE metadata, or cache files are staged.
- Review `git diff --cached` before the first public push.
- Confirm CI passes on the first GitHub run.
- Add a first Git tag after CI succeeds.

### P1: Parser Quality

- Add public synthetic PDF fixtures.
- Cover PDF text extraction, tables, headings, and formula-like text.
- Keep parser warnings explicit; never fabricate missing formulas, metrics, or citations.

### P1: API Robustness

- Add tests for oversized files, empty uploads, wrong tokens, and result requests before completion.
- Consider structured error codes in API responses.
- Keep upload filenames sanitized and job IDs validated.

### P2: Data Contracts

- Gradually migrate context keys from task IDs (`T1`, `T2`, `T3`) to semantic keys while preserving compatibility.
- Add lightweight schema validation helpers for T0/T1/T2/T3 outputs.

### P2: Real Literature Provider

Current T2 providers generate simulated candidates. A future real provider should:

- Preserve `source_type`.
- Include provider metadata such as `source_provider`, `url`, `doi`, `title`, `authors`, and `year`.
- Fall back gracefully when external retrieval fails.
- Avoid blocking the core pipeline on provider outages.

### P2: T5/T6 Upgrades

T5/T6 are currently lightweight dynamic branches. Future versions can turn them into structured outputs such as:

- Technical case matrices.
- Policy/compliance impact matrices.
- Evidence quality summaries.

## Not Planned For The First Public Release

- Heavy vector databases.
- Full GraphRAG.
- Multi-tenant permission systems.
- A complex frontend.
- Claims of verified real literature search before a real provider exists.
