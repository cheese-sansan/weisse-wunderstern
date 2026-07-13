"""Transactional v0.2-to-v3 job migration."""

from __future__ import annotations

import json
import os
import shutil
import threading
from pathlib import Path
from typing import Any

from noteforge.errors import ErrorCode, NoteForgeError
from noteforge.models import (
    SCHEMA_VERSION,
    ArtifactSet,
    JobState,
    JobStatus,
    StageRecord,
    StageStatus,
)
from noteforge.storage.state import BASE_STAGES, DEFAULT_OUTPUT_ROOT, now_iso, validate_job_id

TASK_TO_STAGE = {
    "T0": "document_parse", "T1": "keyword_extract", "T2": "literature_search",
    "T3": "synthesis", "T4": "report_generation", "T5": "technical_cases",
    "T6": "policy_assessment",
}
CONTEXT_TO_SEMANTIC = {
    "input": "input", "T0": "document", "T1": "keywords", "T2": "literature",
    "T3": "synthesis", "T4": "report", "T5": "technical_cases",
    "T6": "policy_assessment",
}
LEGACY_STAGE_STATUS = {
    "未开始": StageStatus.PENDING,
    "进行中": StageStatus.RUNNING,
    "完成": StageStatus.COMPLETED,
    "失败": StageStatus.FAILED,
}
_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


def migrate_job(job_id: str, output_root: Path | str = DEFAULT_OUTPUT_ROOT) -> bool:
    job_id = validate_job_id(job_id)
    root = Path(output_root)
    job_dir = root / "jobs" / job_id
    state_path = job_dir / "task_state.json"
    context_path = job_dir / "context_data.json"
    if not state_path.exists() and not context_path.exists():
        return False
    lock_key = str(job_dir.resolve())
    with _locks_guard:
        lock = _locks.setdefault(lock_key, threading.RLock())
    with lock:
        state_existed = state_path.exists()
        context_existed = context_path.exists()
        state_data = _read_json(state_path) if state_path.exists() else None
        context_data = _read_json(context_path) if context_path.exists() else None
        state_current = not state_data or state_data.get("schema_version") == SCHEMA_VERSION
        context_current = not context_data or context_data.get("schema_version") == SCHEMA_VERSION
        if state_current and context_current:
            return False

        state_backup = job_dir / "task_state.v0.2.json"
        context_backup = job_dir / "context_data.v0.2.json"
        _validate_existing_backup(state_backup, state_path)
        _validate_existing_backup(context_backup, context_path)
        legacy_report = job_dir / "report_framework.md"
        report = job_dir / "report.md"
        report_existed = report.exists()
        try:
            if state_path.exists() and not state_backup.exists():
                _exclusive_backup(state_backup, state_path)
            if context_path.exists() and not context_backup.exists():
                _exclusive_backup(context_backup, context_path)
            new_state = _migrate_state(job_id, state_data or {})
            new_context = _migrate_context(context_data or {})
            JobState.from_dict(new_state)
            if new_context.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("context migration validation failed")
            state_temp = state_path.with_suffix(".json.v3tmp")
            context_temp = context_path.with_suffix(".json.v3tmp")
            _write_json(state_temp, new_state)
            _write_json(context_temp, new_context)
            os.replace(state_temp, state_path)
            os.replace(context_temp, context_path)
            if legacy_report.exists() and not report.exists():
                shutil.copy2(legacy_report, report)
            return True
        except Exception as error:
            if state_backup.exists():
                shutil.copy2(state_backup, state_path)
            elif not state_existed:
                state_path.unlink(missing_ok=True)
            if context_backup.exists():
                shutil.copy2(context_backup, context_path)
            elif not context_existed:
                context_path.unlink(missing_ok=True)
            if not report_existed:
                report.unlink(missing_ok=True)
            for temp in (state_path.with_suffix(".json.v3tmp"), context_path.with_suffix(".json.v3tmp")):
                temp.unlink(missing_ok=True)
            if isinstance(error, NoteForgeError):
                raise
            raise NoteForgeError(
                ErrorCode.MIGRATION_FAILED,
                f"job migration failed: {error}",
                details={"job_id": job_id},
            ) from error


def migrate_all(output_root: Path | str = DEFAULT_OUTPUT_ROOT) -> tuple[int, list[str]]:
    jobs_root = Path(output_root) / "jobs"
    if not jobs_root.exists():
        return 0, []
    migrated = 0
    errors = []
    for job_dir in sorted(path for path in jobs_root.iterdir() if path.is_dir()):
        try:
            migrated += int(migrate_job(job_dir.name, output_root))
        except Exception as error:
            errors.append(f"{job_dir.name}: {error}")
    return migrated, errors


def _migrate_state(job_id: str, legacy: dict[str, Any]) -> dict[str, Any]:
    now = now_iso()
    stages = {name: StageRecord(name=name, status=StageStatus.SKIPPED) for name in BASE_STAGES}
    for task in legacy.get("task_list", []):
        task_id = str(task.get("task_id", ""))
        name = TASK_TO_STAGE.get(task_id)
        if not name:
            continue
        status = LEGACY_STAGE_STATUS.get(str(task.get("status") or ""), StageStatus.PENDING)
        stages[name] = StageRecord(
            name=name,
            status=status,
            started_at=task.get("started_at"),
            finished_at=task.get("finished_at"),
            error=_legacy_error(task.get("error")),
            history=[
                {
                    "status": LEGACY_STAGE_STATUS.get(
                        str(item.get("status") or ""), StageStatus.PENDING,
                    ).value,
                    "timestamp": str(item.get("timestamp", "")),
                }
                for item in task.get("status_history", []) if isinstance(item, dict)
            ],
        )
    legacy_status = str(legacy.get("status", "PENDING"))
    status = JobStatus.RUNNING if legacy_status == "PROCESSING" else JobStatus(
        legacy_status if legacy_status in {item.value for item in JobStatus} else JobStatus.PENDING.value
    )
    current_task = legacy.get("current_task")
    current = TASK_TO_STAGE.get(str(current_task)) if current_task else None
    artifacts = legacy.get("artifacts", {}) if isinstance(legacy.get("artifacts"), dict) else {}
    report = artifacts.get("report") or artifacts.get("legacy_report")
    state = JobState(
        job_id=job_id,
        status=status,
        current_stage=current,
        created_at=str(legacy.get("created_at") or now),
        updated_at=str(legacy.get("updated_at") or now),
        error=_legacy_error(legacy.get("error")),
        stages=stages,
        artifacts=ArtifactSet(report=report),
    )
    return state.to_dict()


def _migrate_context(legacy: dict[str, Any]) -> dict[str, Any]:
    migrated: dict[str, Any] = {"schema_version": SCHEMA_VERSION}
    for old_key, new_key in CONTEXT_TO_SEMANTIC.items():
        if old_key not in legacy:
            continue
        value = legacy[old_key]
        if isinstance(value, dict) and set(value) == {"result"}:
            value = value["result"]
        migrated[new_key] = value
    return migrated


def _legacy_error(value: Any) -> dict[str, Any] | None:
    if not value:
        return None
    if isinstance(value, dict) and "code" in value:
        return value
    return {
        "code": ErrorCode.INTERNAL_ERROR.value,
        "message": str(value),
        "retryable": False,
        "details": {"migrated_from": "v0.2"},
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise NoteForgeError(ErrorCode.MIGRATION_FAILED, f"cannot read legacy file: {path.name}") from error
    if not isinstance(data, dict):
        raise NoteForgeError(ErrorCode.MIGRATION_FAILED, f"legacy file is not an object: {path.name}")
    return data


def _exclusive_backup(path: Path, source: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(source.read_bytes())
        handle.flush()
        os.fsync(handle.fileno())


def _validate_existing_backup(backup: Path, current: Path):
    if not backup.exists():
        return
    if not current.exists() or backup.read_bytes() != current.read_bytes():
        raise NoteForgeError(
            ErrorCode.MIGRATION_FAILED,
            "legacy backup conflicts with current legacy data",
            details={"backup": backup.name},
        )


def _write_json(path: Path, data: dict[str, Any]):
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
