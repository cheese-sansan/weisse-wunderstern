"""Schema-v3 semantic context persistence."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from noteforge.errors import ErrorCode, NoteForgeError
from noteforge.models import SCHEMA_VERSION, JsonModel
from noteforge.storage.state import DEFAULT_OUTPUT_ROOT, validate_job_id

SEMANTIC_KEYS = {
    "input", "document", "keywords", "literature", "synthesis",
    "technical_cases", "policy_assessment", "report",
}


class ContextStore:
    _locks: dict[str, threading.RLock] = {}
    _locks_guard = threading.Lock()

    def __init__(self, job_id: str, output_root: Path | str = DEFAULT_OUTPUT_ROOT):
        self.job_id = validate_job_id(job_id)
        self.output_root = Path(output_root)
        self._job_dir = self.output_root / "jobs" / self.job_id
        self._ctx_file = self._job_dir / "context_data.json"
        lock_key = str(self._ctx_file.resolve())
        with self._locks_guard:
            self._lock = self._locks.setdefault(lock_key, threading.RLock())

    @property
    def context_file(self) -> Path:
        return self._ctx_file

    def save(self, key: str, data: Any):
        if key not in SEMANTIC_KEYS:
            raise ValueError(f"unknown semantic context key: {key}")
        with self._lock:
            context = self.load_all()
            context[key] = data.to_dict() if isinstance(data, JsonModel) else data
            _atomic_write(self._ctx_file, context)

    def load(self, key: str) -> Any:
        if key not in SEMANTIC_KEYS:
            raise ValueError(f"unknown semantic context key: {key}")
        return self.load_all().get(key)

    def load_all(self) -> dict[str, Any]:
        with self._lock:
            self._job_dir.mkdir(parents=True, exist_ok=True)
            from noteforge.storage.migration import migrate_job

            migrate_job(self.job_id, self.output_root)
            if not self._ctx_file.exists():
                return {"schema_version": SCHEMA_VERSION}
            try:
                context = json.loads(self._ctx_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise NoteForgeError(
                    ErrorCode.STORAGE_FAILED,
                    f"cannot read context data: {error}",
                    details={"job_id": self.job_id},
                ) from error
            if context.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("unsupported context schema_version")
            return context


def _atomic_write(path: Path, data: dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
