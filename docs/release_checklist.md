# Release Checklist

## Before Tagging

- Confirm `main` is the intended release branch and all v0.2 changes are reviewed.
- Confirm no `.env`, generated jobs, private documents, credentials, caches, or local samples are staged.
- Confirm real, document, inferred, simulated, and unverified data remain distinguishable.
- Confirm `core.version`, FastAPI, Changelog, README, and release notes all identify `0.2.0`.

## Validation

```bash
python check_all.py
python smoke_test.py
python test_api_client.py
python scripts/privacy_audit.py --history
python scripts/privacy_audit.py --include-outputs
docker compose config
docker compose build api
```

Run one opt-in real retrieval check separately from deterministic CI:

```bash
python main.py --topic "transformer model evaluation" --provider crossref --output release_crossref_check
```

Verify the report lists `crossref/external_api`, contains no automatic simulated fallback, and handles missing abstracts without fabricated findings.

## Tagging

```bash
git checkout main
git pull --ff-only
git tag -a v0.2.0 -m "NoteForge v0.2.0"
git push origin v0.2.0
```

Use `docs/releases/v0.2.0.md` as the GitHub release notes. Do not upload generated jobs as release assets.
