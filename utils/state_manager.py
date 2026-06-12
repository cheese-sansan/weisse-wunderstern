"""
状态管理工具模块 — job 级任务状态持久化。

StateManager(job_id) 将状态写入 outputs/jobs/{job_id}/task_state.json，
使用 threading.Lock 保证单进程多线程下的写入安全。
"""

import json
import os
import threading
from datetime import datetime, timezone, timedelta

BASE_OUTPUT_DIR = "outputs"
TZ = timezone(timedelta(hours=8))


def now_iso():
    """返回当前 UTC+8 时间的 ISO 8601 字符串。"""
    return datetime.now(TZ).isoformat(timespec="seconds")


class StateManager:
    """Per-job 任务状态管理器。"""

    def __init__(self, job_id: str):
        if not job_id or not job_id.strip():
            raise ValueError("job_id 不能为空")
        self.job_id = job_id.strip()
        self._job_dir = os.path.join(BASE_OUTPUT_DIR, "jobs", self.job_id)
        self._state_file = os.path.join(self._job_dir, "task_state.json")
        self._lock = threading.RLock()

    @property
    def job_dir(self):
        return self._job_dir

    @property
    def state_file(self):
        return self._state_file

    def _ensure_dir(self):
        os.makedirs(self._job_dir, exist_ok=True)

    def init_state(self):
        """初始化 job 状态文件（幂等）。"""
        with self._lock:
            self._ensure_dir()
            if os.path.exists(self._state_file):
                return
            now = now_iso()
            state = {
                "job_id": self.job_id,
                "status": "PENDING",
                "current_task": None,
                "created_at": now,
                "updated_at": now,
                "error": None,
                "task_list": [
                    {"task_id": tid, "task_name": name, "status": "未开始",
                     "started_at": None, "finished_at": None, "error": None,
                     "status_history": [{"status": "未开始", "timestamp": now}]}
                    for tid, name in [
                        ("T0", "文档内容提取"), ("T1", "关键词提取"),
                        ("T2", "文献检索"), ("T3", "摘要生成"),
                        ("T4", "报告框架搭建"),
                    ]
                ],
                "artifacts": {},
            }
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)

    def load_state(self):
        """加载当前 job 状态（不存在时初始化）。"""
        with self._lock:
            self.init_state()
            with open(self._state_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    self.init_state()
                    with open(self._state_file, "r", encoding="utf-8") as f2:
                        content = f2.read()
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                self.init_state()
                with open(self._state_file, "r", encoding="utf-8") as f2:
                    return json.loads(f2.read())

    def save_state(self, state):
        """持久化状态。"""
        with self._lock:
            state["updated_at"] = now_iso()
            self._ensure_dir()
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)

    def update_task_status(self, task_id, new_status):
        """更新指定任务的状态并记录时间戳。"""
        with self._lock:
            state = self.load_state()
            for task in state["task_list"]:
                if task["task_id"] == task_id:
                    if task["status"] != new_status:
                        task["status"] = new_status
                        task["status_history"].append(
                            {"status": new_status, "timestamp": now_iso()}
                        )
                        if new_status == "进行中":
                            task["started_at"] = now_iso()
                        elif new_status in ("完成", "失败"):
                            task["finished_at"] = now_iso()
            state["current_task"] = task_id
            state["status"] = "PROCESSING"
            self.save_state(state)

    def set_error(self, error_message):
        """设置 job 级别的错误信息并将状态置为 FAILED。"""
        with self._lock:
            state = self.load_state()
            state["error"] = error_message
            state["status"] = "FAILED"
            self.save_state(state)

    def set_completed(self):
        """标记整个 job 为 COMPLETED。"""
        with self._lock:
            state = self.load_state()
            state["status"] = "COMPLETED"
            state["current_task"] = None
            self.save_state(state)

    def ensure_task_in_state(self, task_id, task_name):
        """如果指定任务不在 task_list 中，则追加。"""
        with self._lock:
            state = self.load_state()
            if not any(t["task_id"] == task_id for t in state["task_list"]):
                state["task_list"].append({
                    "task_id": task_id,
                    "task_name": task_name,
                    "status": "未开始",
                    "started_at": None,
                    "finished_at": None,
                    "error": None,
                    "status_history": [{"status": "未开始", "timestamp": now_iso()}],
                })
                self.save_state(state)

    def get_last_completed_task(self):
        """获取最后一个已完成的任务 ID（用于断点续跑）。"""
        state = self.load_state()
        last = None
        for t in state["task_list"]:
            if t["status"] == "完成":
                last = t["task_id"]
        return last


# ── 模块级兼容代理（单 job 场景，减少 main.py 改动）──
_default_sm: StateManager | None = None


def _get_default_sm(output_dir: str) -> StateManager:
    global _default_sm
    job_id = os.path.basename(output_dir.rstrip("/\\"))
    if _default_sm is None or _default_sm.job_id != job_id:
        _default_sm = StateManager(job_id)
    return _default_sm


def ensure_output_dir(output_dir: str = "outputs"):
    job_id = os.path.basename(output_dir.rstrip("/\\"))
    os.makedirs(os.path.join(BASE_OUTPUT_DIR, "jobs", job_id), exist_ok=True)


def init_state(output_dir: str = "outputs"):
    _get_default_sm(output_dir).init_state()


def load_state(output_dir: str = "outputs"):
    return _get_default_sm(output_dir).load_state()


def save_state(state, output_dir: str = "outputs"):
    _get_default_sm(output_dir).save_state(state)


def update_task_status(task_id, new_status, output_dir: str = "outputs"):
    _get_default_sm(output_dir).update_task_status(task_id, new_status)


def now_str():
    return now_iso()
