# Release Checklist

Use this checklist before publishing a tagged release.

## Before Tagging

- Confirm `main` is the intended release branch.
- Confirm `README.md`, `README_plan.md`, `CHANGELOG.md`, `SECURITY.md`, and `CONTRIBUTING.md` are current.
- Confirm no private documents, generated reports, `.env` files, cache files, or credentials are tracked.
- Confirm simulated literature output is still labeled as simulated.

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

Optional extras build:

```powershell
$env:INSTALL_EXTRAS="true"
docker compose build api
```

## Tagging

```bash
git checkout main
git pull --ff-only
git tag -a v0.1.0 -m "Weisse Wunderstern v0.1.0"
git push origin v0.1.0
```

## GitHub Release

- Use `docs/releases/v0.1.0.md` as the initial release notes.
- Mark the release as a public prototype.
- Do not upload local generated outputs as release assets.
- Confirm CI passes after publishing the tag.

## After Release

- Move completed items from `README_plan.md` into `CHANGELOG.md`.
- Open issues for the next roadmap items.
- Keep default branch protection lightweight until the project has active contributors.
