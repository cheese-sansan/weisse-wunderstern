# Contributing

Thank you for considering a contribution to Lite Agent Orchestrator.

## Setup

```bash
git clone <repo-url>
cd lite-agent-orchestrator
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Linux/macOS:

```bash
source .venv/bin/activate
```

## Checks

Run before opening a pull request:

```bash
python check_all.py
python smoke_test.py
```

Run when API or deployment code changes:

```bash
python test_api_client.py
docker compose config
```

Run before a public release:

```bash
python scripts/privacy_audit.py --history
python scripts/privacy_audit.py --include-outputs
```

## Contribution Rules

- Keep Mock mode usable without external API keys.
- Do not commit `.env`, credentials, generated outputs, cache files, IDE metadata, or local-only documents.
- Do not include real API keys, tokens, private paths, phone numbers, or generated reports in code, tests, docs, issues, or pull requests.
- Keep simulated literature clearly labeled with `source_type: simulated`.
- Add tests for behavior changes when practical.
- Keep unrelated refactors out of focused bug fixes.

## Pull Request Checklist

- Describe the problem and solution.
- List validation commands that passed.
- Note any known limitations.
- Confirm `python scripts/privacy_audit.py` passes.
