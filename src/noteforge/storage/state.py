"""Schema-v3 job state machine with atomic persistence."""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from noteforge.errors import ErrorCode, InvalidStateTransition, NoteForgeError
from noteforge.models import ArtifactSet, JobState, JobStatus, StageRecord, StageStatus

DEFAULT_OUTPUT_ROOT = Path("outputs")
TZ = timezone(timedelta(hours=8))
JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
BASE_STAGES = (
    "document_parse",
    "keyword_extract",
    "literature_search",
    "synthesis",
    "technical_cases",
    "policy_assessment",
    "report_generation",
)
ALLOWED_TRANSITIONS = {
    StageStatus.PENDING: {StageStatus.RUNNING, StageStatus.SKIPPED},
    StageStatus.RUNNING: {StageStatus.COMPLETED, StageStatus.FAILED},
    StageStatus.COMPLETED: set(),
    StageStatus.SKIPPED: set(),
    StageStatus.FAILED: {StageStatus.RUNNING},
}
ALLOWED_JOB_TRANSITIONS = {
    JobStatus.PENDING: {JobStatus.RUNNING, JobStatus.FAILED},
    JobStatus.RUNNING: {JobStatus.COMPLETED, JobStatus.FAILED},
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: {JobStatus.RUNNING},
}


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def validate_job_id(job_id: str) -> str:
    normalized = str(job_id or "").strip()
    if not normalized:
        raise ValueError("job_id 不能为空")
    if not JOB_ID_PATTERN.fullmatch(normalized):
        raise ValueError(
            "job_id 只能包含英文字母、数字、下划线和连字符，"
            "必须以字母或数字开头，长度不超过 64"
        )
    return normalized


class StateManager:
    _locks: dict[str, threading.RLock] = {}
    _locks_guard = threading.Lock()

    def __init__(self, job_id: str, output_root: Path | str = DEFAULT_OUTPUT_ROOT):
        self.job_id = validate_job_id(job_id)
        self.output_root = Path(output_root)
        self._job_dir = self.output_root / "jobs" / self.job_id
        self._state_file = self._job_dir / "task_state.json"
        lock_key = str(self._state_file.resolve())
        with self._locks_guard:
            self._lock = self._locks.setdefault(lock_key, threading.RLock())

    @property
    def job_dir(self) -> Path:
        return self._job_dir

    @property
    def state_file(self) -> Path:
        return self._state_file

    def _new_state(self) -> JobState:
        now = now_iso()
        return JobState(
            job_id=self.job_id,
            created_at=now,
            updated_at=now,
            stages={name: StageRecord(name=name) for name in BASE_STAGES},
            artifacts=ArtifactSet(),
        )

    def init_state(self, force: bool = False) -> JobState:
        with self._lock:
            self._job_dir.mkdir(parents=True, exist_ok=True)
            if self._state_file.exists() and not force:
                return self.load_state()
            state = self._new_state()
            self.save_state(state)
            return state

    def load_state(self) -> JobState:
        with self._lock:
            if not self._state_file.exists():
                return self.init_state()
            from noteforge.storage.migration import migrate_job

            migrate_job(self.job_id, self.output_root)
            try:
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                state = JobState.from_dict(data)
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
                raise NoteForgeError(
                    ErrorCode.STORAGE_FAILED,
                    f"无法读取 Job 状态: {error}",
                    details={"job_id": self.job_id},
                ) from error
            if state.schema_version != 3:
                raise NoteForgeError(ErrorCode.STORAGE_FAILED, "不支持的 Job schema_version")
            return state

    def save_state(self, state: JobState):
        with self._lock:
            state.updated_at = now_iso()
            self._job_dir.mkdir(parents=True, exist_ok=True)
            _atomic_json_write(self._state_file, state.to_dict())

    def completed_stages(self) -> set[str]:
        return {
            name for name, stage in self.load_state().stages.items()
            if stage.status in (StageStatus.COMPLETED, StageStatus.SKIPPED)
        }

    def transition_stage(self, name: str, target: StageStatus):
        with self._lock:
            state = self.load_state()
            if name not in state.stages:
                state.stages[name] = StageRecord(name=name)
            stage = state.stages[name]
            if stage.status == target:
                return
            if target not in ALLOWED_TRANSITIONS[stage.status]:
                raise InvalidStateTransition(stage.status.value, target.value)
            now = now_iso()
            stage.status = target
            stage.history.append({"status": target.value, "timestamp": now})
            if target is StageStatus.RUNNING:
                stage.started_at = now
                stage.finished_at = None
                stage.error = None
                _transition_job(state, JobStatus.RUNNING)
                state.current_stage = name
            elif target in (StageStatus.COMPLETED, StageStatus.SKIPPED):
                stage.finished_at = now
            elif target is StageStatus.FAILED:
                stage.finished_at = now
                _transition_job(state, JobStatus.FAILED)
                state.current_stage = name
            self.save_state(state)

    def set_error(self, error: NoteForgeError | str, stage_name: str | None = None):
        with self._lock:
            state = self.load_state()
            structured = error.to_dict() if isinstance(error, NoteForgeError) else {
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": str(error),
                "retryable": False,
                "details": {},
            }
            state.error = structured
            _transition_job(state, JobStatus.FAILED)
            if stage_name and stage_name in state.stages:
                stage = state.stages[stage_name]
                stage.error = structured
                if stage.status is StageStatus.RUNNING:
                    stage.status = StageStatus.FAILED
                    stage.finished_at = now_iso()
            self.save_state(state)

    def set_completed(self):
        with self._lock:
            state = self.load_state()
            _transition_job(state, JobStatus.COMPLETED)
            state.current_stage = None
            self.save_state(state)

    def transition_job(self, target: JobStatus):
        with self._lock:
            state = self.load_state()
            _transition_job(state, target)
            self.save_state(state)


def _transition_job(state: JobState, target: JobStatus):
    if state.status is target:
        return
    if target not in ALLOWED_JOB_TRANSITIONS[state.status]:
        raise InvalidStateTransition(state.status.value, target.value)
    state.status = target


def _atomic_json_write(path: Path, data: dict):
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
