"""Job-isolated NoteForge pipeline shared by CLI, TUI, API, and SDK."""

from __future__ import annotations

import os

from tasks.t0_document_parsing import run as t0_run
from tasks.t1_keyword_extraction import run as t1_run
from tasks.t2_literature_search import DEFAULT_PROVIDER, run as t2_run
from tasks.t3_summary_generation import run as t3_run
from tasks.t4_report_framework import run as t4_run
from tasks.t5_technical_case_analysis import run as t5_run
from tasks.t6_policy_assessment import run as t6_run
from utils.context_manager import ContextStore
from utils.logger import get_logger
from utils.state_manager import StateManager, now_str


log = get_logger(__name__)
EXECUTION_ORDER = ["T0", "T1", "T2", "T3", "T5", "T6", "T4"]


class PipelineError(Exception):
    """Recoverable error caused by invalid pipeline input."""


def _jlog(job_id: str, message: str):
    text = f"[Job {job_id}] {message}"
    print(text)
    log.info(text)


def run_job(job_id: str, topic: str = "", file_path: str | None = None,
            uploaded_file_path: str | None = None,
            provider: str | None = None):
    """Run or resume an evidence-aware analysis job."""
    smgr = StateManager(job_id)
    ctx = ContextStore(job_id)
    output_dir = smgr.job_dir
    os.makedirs(output_dir, exist_ok=True)

    state = smgr.load_state()
    if state.get("status") == "COMPLETED":
        _jlog(job_id, "所有任务已完成，无需重复执行。")
        return

    _ensure_base_tasks(smgr)
    completed = _completed_tasks(smgr)
    last_done = next((task for task in reversed(EXECUTION_ORDER) if task in completed), None)
    _log_resume(last_done, output_dir, job_id)

    stored_input = ctx.load("input")
    stored_file = None
    if isinstance(stored_input, dict):
        topic = topic or str(stored_input.get("topic", ""))
        provider = provider or stored_input.get("provider")
        stored_file = stored_input.get("file_path")
    provider = provider or os.environ.get("LITERATURE_PROVIDER", DEFAULT_PROVIDER)
    effective_file = file_path or uploaded_file_path or stored_file
    ctx.save("input", {
        "topic": topic,
        "file_path": effective_file,
        "provider": provider,
    })

    _jlog(job_id, f"主题: {topic if topic else '(待提取)'}")
    if effective_file:
        _jlog(job_id, f"文件: {effective_file}")

    # T0 — document parsing. Topic-only jobs complete T0 without an artifact.
    doc_result = ctx.load("T0")
    if "T0" not in completed or (effective_file and not isinstance(doc_result, dict)):
        smgr.update_task_status("T0", "进行中")
        if effective_file:
            _jlog(job_id, "-> T0 文档内容提取...")
            doc_result = t0_run(effective_file)
            doc_result["source_id"] = "D1"
            doc_result["source_type"] = "source_document"
            doc_result["source_provider"] = "local-file"
            ctx.save("T0", doc_result)
            metadata = doc_result.get("metadata", {})
            _jlog(job_id, f"[T0] 文件: {metadata.get('file_name')} | 长度: {len(doc_result.get('raw_text', ''))} 字符")
            if not topic:
                topic = metadata.get("file_name", "文档分析")
        smgr.update_task_status("T0", "完成")
        completed.add("T0")

    if not topic and isinstance(doc_result, dict):
        topic = doc_result.get("metadata", {}).get("file_name", "文档分析")
    if not topic:
        smgr.set_error("未指定主题且未提供文件，无法继续")
        raise PipelineError("未指定主题且未提供文件，无法继续")

    # T1 — keywords and academic entities.
    t1_output = ctx.load("T1")
    if "T1" not in completed or not isinstance(t1_output, dict):
        _jlog(job_id, "-> T1 关键词与学术实体提取...")
        smgr.update_task_status("T1", "进行中")
        t1_output = t1_run(topic)
        t1_output["source_id"] = "D1" if isinstance(doc_result, dict) else "INPUT1"
        t1_output["source_type"] = "source_document" if isinstance(doc_result, dict) else "unverified"
        ctx.save("T1", t1_output)
        smgr.update_task_status("T1", "完成")
        completed.add("T1")
    _jlog(job_id, f"[T1] 关键词: {t1_output.get('keywords', [])}")

    # T2 — explicit retrieval provider.
    t2_output = ctx.load("T2")
    if "T2" not in completed or not isinstance(t2_output, dict):
        _jlog(job_id, "-> T2 文献检索...")
        smgr.update_task_status("T2", "进行中")
        t2_output = t2_run(t1_output, provider=provider)
        ctx.save("T2", t2_output)
        smgr.update_task_status("T2", "完成")
        completed.add("T2")
    literature = t2_output.get("literature_results", [])
    _jlog(
        job_id,
        f"[T2] Provider={t2_output.get('provider', 'unknown')} | 状态={t2_output.get('status', 'unknown')} | 文献={len(literature)}",
    )
    for warning in t2_output.get("warnings", []):
        _jlog(job_id, f"[WARNING] {warning}")

    # Dynamic routing is based on T1 semantics, not provider availability.
    need_t5, need_t6 = _route_tasks(t1_output)
    if need_t5:
        smgr.ensure_task_in_state("T5", "技术案例分析")
        _jlog(job_id, "[动态路由] 启用 T5")
    if need_t6:
        smgr.ensure_task_in_state("T6", "政策影响评估")
        _jlog(job_id, "[动态路由] 启用 T6")
    completed = _completed_tasks(smgr)

    # T3 — extraction, critique, and synthesis even when evidence is empty.
    t3_output = ctx.load("T3")
    if "T3" not in completed or not isinstance(t3_output, dict):
        _jlog(job_id, "-> T3 审稿反思环路...")
        smgr.update_task_status("T3", "进行中")
        t3_output = t3_run(t2_output, doc_result)
        ctx.save("T3", t3_output)
        smgr.update_task_status("T3", "完成")
        completed.add("T3")
    critiques = t3_output.get("critic_review", {}).get("critiques", [])
    _jlog(job_id, f"[T3] Critic={len(critiques)} | Report={len(t3_output.get('final_report', ''))} 字符")

    # T5/T6 — evidence-gated dynamic branches.
    task_ids = {task.get("task_id") for task in smgr.load_state().get("task_list", [])}
    t5_output = ctx.load("T5")
    if "T5" in task_ids and ("T5" not in completed or not isinstance(t5_output, dict)):
        _jlog(job_id, "-> T5 技术案例分析...")
        smgr.update_task_status("T5", "进行中")
        t5_output = t5_run(topic, t2_output, t3_output, doc_result)
        ctx.save("T5", t5_output)
        smgr.update_task_status("T5", "完成")
        completed.add("T5")
        _jlog(job_id, f"[T5] 案例={len(t5_output.get('cases', []))} | 状态={t5_output.get('status')}")
    if not isinstance(t5_output, dict):
        t5_output = {"status": "not_requested", "warnings": [], "cases": []}

    t6_output = ctx.load("T6")
    if "T6" in task_ids and ("T6" not in completed or not isinstance(t6_output, dict)):
        _jlog(job_id, "-> T6 政策影响评估...")
        smgr.update_task_status("T6", "进行中")
        t6_output = t6_run(topic, t2_output, doc_result)
        ctx.save("T6", t6_output)
        smgr.update_task_status("T6", "完成")
        completed.add("T6")
        _jlog(job_id, f"[T6] 政策={len(t6_output.get('policies', []))} | 状态={t6_output.get('status')}")
    if not isinstance(t6_output, dict):
        t6_output = {"status": "not_requested", "warnings": [], "policies": []}

    # T4 — always rebuild the final report after dynamic branches.
    sources = _source_registry(literature, doc_result)
    warnings = _collect_warnings(doc_result, t2_output, t3_output, t5_output, t6_output)
    _jlog(job_id, "-> T4 最终报告生成...")
    smgr.update_task_status("T4", "进行中")
    report = t4_run(topic, t3_output, t5_output, t6_output, sources, warnings)
    report_path = os.path.join(output_dir, "report.md")
    legacy_report_path = os.path.join(output_dir, "report_framework.md")
    for path in (report_path, legacy_report_path):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(report)
    ctx.save("T4", {
        "report_path": report_path,
        "legacy_report_path": legacy_report_path,
        "sources": sources,
        "warnings": warnings,
    })
    smgr.update_task_status("T4", "完成")
    state = smgr.load_state()
    state.setdefault("artifacts", {}).update({
        "report": report_path,
        "legacy_report": legacy_report_path,
    })
    smgr.save_state(state)
    _jlog(job_id, f"[T4] 报告已保存: {report_path}")

    smgr.set_completed()
    _jlog(job_id, "管道执行完毕。")


def _completed_tasks(smgr: StateManager) -> set[str]:
    return {
        str(task.get("task_id"))
        for task in smgr.load_state().get("task_list", [])
        if task.get("status") == "完成"
    }


def _route_tasks(t1_output: dict) -> tuple[bool, bool]:
    keywords = [str(value).casefold() for value in t1_output.get("keywords", [])]
    entities = t1_output.get("academic_entities", {})
    methods = [str(value).casefold() for value in entities.get("methods", [])]
    domains = [str(value).casefold() for value in entities.get("domains", [])]
    combined = " ".join(keywords + methods + domains)
    need_t5 = bool(methods) or any(marker in combined for marker in (
        "transformer", "diffusion", "gan", "reinforcement", "模型", "部署",
    ))
    need_t6 = any(marker in combined for marker in (
        "policy", "law", "legal", "regulation", "governance", "compliance",
        "政策", "法规", "监管", "合规", "法律", "标准", "安全",
    ))
    return need_t5, need_t6


def _source_registry(literature: list, document: dict | None) -> list[dict]:
    sources = []
    if isinstance(document, dict):
        metadata = document.get("metadata", {})
        sources.append({
            "source_id": "D1",
            "title": metadata.get("file_name", "source document"),
            "authors": [], "year": None, "doi": None, "url": None,
            "source_provider": "local-file",
            "source_type": "source_document",
            "retrieved_at": None,
        })
    for item in literature:
        if not isinstance(item, dict):
            continue
        sources.append({
            key: item.get(key) for key in (
                "source_id", "title", "authors", "year", "doi", "url",
                "source_provider", "source_type", "retrieved_at",
            )
        })
    return sources


def _collect_warnings(*outputs) -> list[str]:
    warnings = []
    for output in outputs:
        if not isinstance(output, dict):
            continue
        for warning in output.get("warnings", []):
            text = str(warning).strip()
            if text and text not in warnings:
                warnings.append(text)
    return warnings


def _log_resume(last_task: str | None, output_dir: str, job_id: str):
    log_file = os.path.join(output_dir, "resume_log.txt")
    mode = "a" if os.path.exists(log_file) else "w"
    with open(log_file, mode, encoding="utf-8") as handle:
        if last_task:
            handle.write(f"[续跑] {now_str()} | Job: {job_id} | 已完成至 {last_task}\n")
        else:
            handle.write(f"[启动] {now_str()} | Job: {job_id} | 全新执行\n")


def _ensure_base_tasks(smgr: StateManager):
    for task_id, task_name in (
        ("T0", "文档内容提取"), ("T1", "关键词与实体提取"),
        ("T2", "文献检索"), ("T3", "学术提炼"), ("T4", "最终报告生成"),
    ):
        smgr.ensure_task_in_state(task_id, task_name)
