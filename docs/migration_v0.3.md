# Migrating from NoteForge v0.2 to v0.3

## Code and commands

Replace root scripts with the installed command:

```text
python main.py      -> noteforge run
python main_tui.py  -> noteforge tui
python main_api.py  -> noteforge api
```

Replace `core`, `tasks`, and `utils` imports with the top-level `noteforge` SDK or the documented `noteforge.storage` operational modules. Replace requirements files with extras from `pyproject.toml`: `.[api]`, `.[documents]`, and `.[dev]`.

## Job data

Reading a legacy job or running `noteforge jobs migrate --all` performs an in-place, idempotent migration:

1. Acquire the per-job migration lock.
2. Detect missing `schema_version` and legacy `T0…T6` context.
3. Create byte-exact `task_state.v0.2.json` and `context_data.v0.2.json` backups.
4. Map dynamic tasks and Chinese statuses to schema-v3 Job/Stage records.
5. Map context to `input/document/keywords/literature/synthesis/technical_cases/policy_assessment/report`.
6. Validate both temporary documents and atomically replace both current files.
7. Preserve `report_framework.md` and create `report.md` if it is missing.

Any failure restores both originals and raises `MIGRATION_FAILED`. Re-running a completed migration does not rewrite files or backups.
