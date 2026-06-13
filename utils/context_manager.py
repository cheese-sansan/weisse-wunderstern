"""
上下文管理工具模块 — job 级任务产物持久化。

ContextStore(job_id) 将上下文写入 outputs/jobs/{job_id}/context_data.json。
"""

import json
import os
import threading

from utils.state_manager import validate_job_id

BASE_OUTPUT_DIR = "outputs"

# 建议语义键名映射
CONTEXT_KEYS = {
    "T0": "document_parse",
    "T1": "keyword_entities",
    "T2": "literature_results",
    "T3": "extractor_draft",
    "T4": "report_framework",
    "T5": "tech_case_analysis",
    "T6": "policy_assessment",
}


class ContextStore:
    """Per-job 上下文存储。"""

    _locks: dict[str, threading.RLock] = {}
    _locks_guard = threading.Lock()

    def __init__(self, job_id: str):
        self.job_id = validate_job_id(job_id)
        self._job_dir = os.path.join(BASE_OUTPUT_DIR, "jobs", self.job_id)
        self._ctx_file = os.path.join(self._job_dir, "context_data.json")
        with self._locks_guard:
            if self.job_id not in self._locks:
                self._locks[self.job_id] = threading.RLock()
            self._lock = self._locks[self.job_id]

    def _ensure_dir(self):
        os.makedirs(self._job_dir, exist_ok=True)

    def _write_context_atomic(self, ctx):
        """原子写入上下文 JSON，避免并发读取半截内容。"""
        self._ensure_dir()
        tmp_file = f"{self._ctx_file}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(ctx, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, self._ctx_file)

    def save(self, key: str, data):
        """保存一个键的上下文产物。key 可为 task_id（如 'T1'）或语义键名。"""
        with self._lock:
            self._ensure_dir()
            ctx = {}
            if os.path.exists(self._ctx_file):
                try:
                    with open(self._ctx_file, "r", encoding="utf-8") as f:
                        ctx = json.load(f)
                except (json.JSONDecodeError, OSError):
                    pass
            ctx[key] = {"result": data}
            self._write_context_atomic(ctx)

    def load(self, key: str):
        """加载指定键的上下文产物。"""
        if not os.path.exists(self._ctx_file):
            return None
        try:
            with open(self._ctx_file, "r", encoding="utf-8") as f:
                ctx = json.load(f)
            if key in ctx:
                return ctx[key].get("result")
        except Exception:
            pass
        return None

    def load_all(self):
        """加载全部上下文。"""
        if not os.path.exists(self._ctx_file):
            return {}
        try:
            with open(self._ctx_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}


# ── 模块级兼容代理 ──
_default_cs: ContextStore | None = None


def _get_default_cs(output_dir: str) -> ContextStore:
    global _default_cs
    job_id = os.path.basename(output_dir.rstrip("/\\"))
    if _default_cs is None or _default_cs.job_id != job_id:
        _default_cs = ContextStore(job_id)
    return _default_cs


def save_context(task_id, data, output_dir="outputs"):
    key = CONTEXT_KEYS.get(task_id, f"{task_id}_output")
    _get_default_cs(output_dir).save(key, data)


def load_context(task_id, output_dir="outputs"):
    key = CONTEXT_KEYS.get(task_id, f"{task_id}_output")
    return _get_default_cs(output_dir).load(key)
