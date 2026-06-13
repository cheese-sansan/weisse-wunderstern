"""
核心管道执行器 — 供 CLI 和 API 共用。

run_job(job_id, topic, file_path, uploaded_file_path)
使用 StateManager / ContextStore 进行 job 级隔离。
"""

import os
import json
from datetime import datetime

from utils.logger import get_logger
from utils.state_manager import StateManager, now_str
from utils.context_manager import ContextStore

log = get_logger(__name__)


def _jlog(job_id, msg):
    """同时输出到控制台和日志。"""
    text = f"[Job {job_id}] {msg}"
    print(text)
    log.info(text)
from tasks.t0_document_parsing import run as t0_run
from tasks.t1_keyword_extraction import run as t1_run
from tasks.t2_literature_search import run as t2_run
from tasks.t3_summary_generation import run as t3_run
from tasks.t4_report_framework import run as t4_run

TASK_ORDER = ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]
TASK_INDEX = {tid: i for i, tid in enumerate(TASK_ORDER)}


def should_run(task_id, next_task_id):
    return TASK_INDEX[task_id] >= TASK_INDEX[next_task_id]


class PipelineError(Exception):
    """管道执行中的可恢复错误。"""
    pass


def run_job(job_id: str, topic: str = "", file_path: str = None, uploaded_file_path: str = None):
    """
    执行完整的任务编排管道。

    参数:
        job_id: 唯一任务标识
        topic: 研究主题（可从文件中自动提取）
        file_path: 外部文件路径（由用户提供的已有路径）
        uploaded_file_path: API 上传保存后的文件路径

    异常:
        PipelineError: 无主题且无文件时抛出
    """
    smgr = StateManager(job_id)
    ctx = ContextStore(job_id)

    output_dir = os.path.join("outputs", "jobs", job_id)
    os.makedirs(output_dir, exist_ok=True)

    # 确定实际使用的文件路径
    effective_file = file_path or uploaded_file_path

    # 断点续跑
    last_done = smgr.get_last_completed_task()
    _log_resume(last_done, output_dir, job_id)

    if last_done is None:
        smgr.init_state()
        next_task = "T0"
    else:
        _ensure_all_tasks(smgr)
        idx = TASK_ORDER.index(last_done)
        next_task = TASK_ORDER[idx + 1] if idx + 1 < len(TASK_ORDER) else None
        if next_task is None:
            print(f"[OK] Job {job_id}: 所有任务已完成，无需重复执行。")
            return

    print(f"[Job {job_id}] 主题: {topic if topic else '(待提取)'}")
    if effective_file:
        print(f"[Job {job_id}] 文件: {effective_file}")

    doc_result = None
    t1_output = {}
    t2_output = {}
    lit_results = []
    summary = ""
    literature_is_empty = True

    # ── T0 ──
    if should_run("T0", next_task) and effective_file:
        print(f"[Job {job_id}] -> T0 文档内容提取...")
        smgr.update_task_status("T0", "进行中")
        doc_result = t0_run(effective_file)
        ctx.save("T0", doc_result)
        smgr.update_task_status("T0", "完成")
        meta = doc_result.get("metadata", {})
        text_len = len(doc_result.get("raw_text", ""))
        print(f"[Job {job_id}] [T0] 文件: {meta.get('file_name')} | 长度: {text_len} 字符")
        if doc_result.get("warnings"):
            for w in doc_result["warnings"]:
                print(f"[Job {job_id}]  [WARNING] {w}")
        if not topic:
            topic = meta.get("file_name", "文档分析")
        next_task = "T1"
    elif should_run("T0", next_task):
        if next_task == "T0":
            smgr.update_task_status("T0", "完成")
            next_task = "T1"

    if not topic and should_run("T1", next_task):
        smgr.set_error("未指定主题且未提供文件，无法继续")
        raise PipelineError("未指定主题且未提供文件，无法继续")

    # ── T1 ──
    if should_run("T1", next_task):
        print(f"[Job {job_id}] -> T1 关键词与学术实体提取...")
        smgr.update_task_status("T1", "进行中")
        t1_output = t1_run(topic)
        ctx.save("T1", t1_output)
        smgr.update_task_status("T1", "完成")
        keywords = t1_output.get("keywords", [])
        entities = t1_output.get("academic_entities", {})
        print(f"[Job {job_id}] [T1] 关键词: {keywords}")
        next_task = "T2"

    # ── T2 ──
    if should_run("T2", next_task):
        print(f"[Job {job_id}] -> T2 文献检索...")
        smgr.update_task_status("T2", "进行中")
        t2_output = t2_run(t1_output)
        ctx.save("T2", t2_output)
        smgr.update_task_status("T2", "完成")
        lit_results = t2_output.get("literature_results", [])
        print(f"[Job {job_id}] [T2] 检索到 {len(lit_results)} 条文献")
        next_task = "T3"

        # 动态路由
        state = smgr.load_state()
        has_t5 = any(t["task_id"] == "T5" for t in state["task_list"])
        has_t6 = any(t["task_id"] == "T6" for t in state["task_list"])
        methods = [m.lower() for m in entities.get("methods", [])]
        domains = [d.lower() for d in entities.get("domains", [])]
        policy_domains = {"policy", "law", "legal", "regulation", "governance", "compliance"}
        need_t5 = bool(methods) or any(
            kw in " ".join(methods + domains)
            for kw in ["transformer", "diffusion", "gan", "rl", "reinforcement"]
        )
        need_t6 = bool(set(domains) & policy_domains) or any(
            kw in str(keywords) for kw in ["政策", "法规", "监管", "合规", "法律", "标准"]
        )

        if need_t5 and not has_t5:
            state["task_list"].append({
                "task_id": "T5", "task_name": "技术案例分析",
                "status": "未开始",
                "status_history": [{"status": "未开始", "timestamp": now_str()}],
            })
            print(f"[Job {job_id}] [动态路由] 追加 T5")
        if need_t6 and not has_t6:
            state["task_list"].append({
                "task_id": "T6", "task_name": "政策影响评估",
                "status": "未开始",
                "status_history": [{"status": "未开始", "timestamp": now_str()}],
            })
            print(f"[Job {job_id}] [动态路由] 追加 T6")
        if need_t5 or need_t6:
            smgr.save_state(state)

    # ── T3 ──
    literature_is_empty = len(lit_results) == 0
    if should_run("T3", next_task):
        if literature_is_empty:
            print(f"[Job {job_id}] [跳过] T3 文献不足")
            next_task = "T4"
        else:
            print(f"[Job {job_id}] -> T3 审稿反思环路...")
            smgr.update_task_status("T3", "进行中")
            t3_output = t3_run(t2_output, doc_result)
            ctx.save("T3", t3_output)
            smgr.update_task_status("T3", "完成")
            summary = t3_output.get("final_report", "")
            critic = t3_output.get("critic_review", {})
            critiques = critic.get("critiques", [])
            print(f"[Job {job_id}] [T3] Extractor: claims | Critic: {len(critiques)} critiques | Report: {len(summary)} 字符")
            next_task = "T4"

    # ── T4 ──
    if should_run("T4", next_task):
        print(f"[Job {job_id}] -> T4 报告框架搭建...")
        smgr.update_task_status("T4", "进行中")
        if literature_is_empty:
            report = "# 报告框架\n\n## 摘要\n文献不足，建议补充检索"
        else:
            report = t4_run(topic, summary)
        report_path = os.path.join(output_dir, "report_framework.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        smgr.update_task_status("T4", "完成")
        print(f"[Job {job_id}] [T4] 报告已保存")
        next_task = "T5"

    # ── T5 ──
    if should_run("T5", next_task):
        state = smgr.load_state()
        if any(t["task_id"] == "T5" and t["status"] == "未开始" for t in state["task_list"]):
            print(f"[Job {job_id}] -> T5 技术案例分析...")
            smgr.update_task_status("T5", "进行中")
            ctx.save("T5", f"针对'{topic}'的技术案例分析完成。")
            smgr.update_task_status("T5", "完成")
        next_task = "T6"

    # ── T6 ──
    if should_run("T6", next_task):
        state = smgr.load_state()
        if any(t["task_id"] == "T6" and t["status"] == "未开始" for t in state["task_list"]):
            print(f"[Job {job_id}] -> T6 政策影响评估...")
            smgr.update_task_status("T6", "进行中")
            ctx.save("T6", f"针对'{topic}'的政策影响评估完成。")
            smgr.update_task_status("T6", "完成")

    smgr.set_completed()
    print(f"[Job {job_id}] 管道执行完毕。")


# ═══════════════════════════════════════════════════════════════════
# 内部辅助
# ═══════════════════════════════════════════════════════════════════

def _log_resume(last_task, output_dir, job_id):
    log_file = os.path.join(output_dir, "resume_log.txt")
    now = now_str()
    mode = "a" if os.path.exists(log_file) else "w"
    with open(log_file, mode, encoding="utf-8") as f:
        if last_task:
            f.write(f"[续跑] {now} | Job: {job_id} | 从 {last_task} 之后开始\n")
        else:
            f.write(f"[启动] {now} | Job: {job_id} | 全新执行\n")


def _ensure_all_tasks(smgr):
    state = smgr.load_state()
    existing_ids = {t["task_id"] for t in state["task_list"]}
    base_tasks = [
        ("T0", "文档内容提取"), ("T1", "关键词提取"), ("T2", "文献检索"),
        ("T3", "摘要生成"), ("T4", "报告框架搭建"),
        ("T5", "技术案例分析"), ("T6", "政策影响评估"),
    ]
    changed = False
    for tid, name in base_tasks:
        if tid not in existing_ids:
            state["task_list"].append({
                "task_id": tid, "task_name": name, "status": "未开始",
                "status_history": [{"status": "未开始", "timestamp": now_str()}],
            })
            changed = True
    if changed:
        smgr.save_state(state)
