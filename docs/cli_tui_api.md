# CLI, TUI, and API

## CLI

```bash
noteforge run --topic "transformer evaluation" --provider crossref
noteforge run --file ./examples/sample_paper_abstract.md --provider mock --job-id paper-demo
noteforge run --job-id paper-demo                 # resume persisted input
noteforge jobs list --limit 20
noteforge jobs migrate --all
noteforge report paper-demo
```

Use `--output-root` on `run`, `jobs list`, `jobs migrate`, and `report` when artifacts should not use `outputs/`.

## TUI

```bash
noteforge tui
```

The TUI runs topic/file analysis, lists jobs, and displays canonical reports through the same SDK used by the CLI and API.

## API

```bash
python -m pip install ".[api]"
noteforge api --host 0.0.0.0 --port 8000
```

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/v1/jobs/submit \
  -F "topic=AI safety" -F "provider=crossref"
curl http://localhost:8000/api/v1/jobs/status/{job_id}
curl http://localhost:8000/api/v1/jobs/result/{job_id}
```

The v1 result retains `report`, `context_summary`, `provider_status`, `sources`, `tech_cases`, `policy_assessment`, and `warnings`. Status retains the legacy `T0…T6` presentation fields for HTTP compatibility even though persisted v3 data uses semantic stage names. Structured failures may add `error_code` without removing `detail` or `error`.

Set `API_TOKEN` to require `Authorization: Bearer ...` on `/api/v1/jobs/*`. Keep secrets in environment variables or an untracked `.env` file.
