"""Typed job-isolated pipeline shared by CLI, TUI, API, and SDK."""

from __future__ import annotations

import os
import secrets
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from noteforge.errors import ErrorCode, NoteForgeError
from noteforge.logging import get_logger
from noteforge.models import (
    AnalysisRequest,
    ArtifactSet,
    JobResult,
    JobStatus,
    PolicyRecord,
    ProviderName,
    SourceRecord,
    TechnicalCase,
)
from noteforge.providers.literature import (
    DEFAULT_PROVIDER,
    query_from_keyword_output,
    search_literature,
)
from noteforge.stages.document import run as parse_document
from noteforge.stages.keywords import run as extract_keywords
from noteforge.stages.policy import run as assess_policy
from noteforge.stages.report import run as assemble_report
from noteforge.stages.synthesis import run as synthesize
from noteforge.stages.technical_cases import run as analyze_technical_cases
from noteforge.storage.context import ContextStore
from noteforge.storage.state import StageStatus, StateManager, now_iso, validate_job_id

log = get_logger(__name__)
EXECUTION_ORDER = (
    "document_parse", "keyword_extract", "literature_search", "synthesis",
    "technical_cases", "policy_assessment", "report_generation",
)


def run_job(request: AnalysisRequest, *, output_root: Path = Path("outputs")) -> JobResult:
    """Run or resume one job and return a typed SDK result."""
    if not isinstance(request, AnalysisRequest):
        raise TypeError("run_job requires AnalysisRequest")
    job_id = validate_job_id(request.job_id or _generate_job_id())
    manager = StateManager(job_id, output_root)
    context = ContextStore(job_id, output_root)
    state = manager.load_state()
    if state.status is JobStatus.COMPLETED:
        return _build_result(job_id, output_root, context, state.status)

    stored_input = context.load("input") or {}
    topic = request.topic or str(stored_input.get("topic", ""))
    file_value = request.file_path or stored_input.get("file_path")
    file_path = Path(file_value) if file_value else None
    provider = request.provider or _provider_from_value(stored_input.get("provider")) or _configured_provider()
    context.save("input", {
        "topic": topic,
        "file_path": str(file_path) if file_path else None,
        "provider": provider.value,
        "job_id": job_id,
    })
    _write_resume_log(manager.job_dir, manager.completed_stages(), job_id)

    current_stage: str | None = None
    try:
        document = context.load("document")
        current_stage = "document_parse"
        if current_stage not in manager.completed_stages():
            if file_path:
                document = _execute(manager, current_stage, lambda: parse_document(str(file_path)))
                document.update({
                    "source_id": "D1",
                    "source_type": "source_document",
                    "source_provider": "local-file",
                })
                context.save("document", document)
                if not topic:
                    topic = document.get("metadata", {}).get("file_name", "文档分析")
            else:
                manager.transition_stage(current_stage, StageStatus.SKIPPED)

        if not topic and isinstance(document, dict):
            topic = document.get("metadata", {}).get("file_name", "文档分析")
        if not topic:
            raise NoteForgeError(ErrorCode.INPUT_INVALID, "未指定主题且未提供文件")
        context.save("input", {
            "topic": topic,
            "file_path": str(file_path) if file_path else None,
            "provider": provider.value,
            "job_id": job_id,
        })

        keywords = context.load("keywords")
        current_stage = "keyword_extract"
        if current_stage not in manager.completed_stages():
            keywords = _execute(manager, current_stage, lambda: extract_keywords(topic))
            keywords.update({
                "source_id": "D1" if document else "INPUT1",
                "source_type": "source_document" if document else "unverified",
            })
            context.save("keywords", keywords)

        literature = context.load("literature")
        current_stage = "literature_search"
        if current_stage not in manager.completed_stages():
            typed_literature = _execute(
                manager, current_stage,
                lambda: search_literature(query_from_keyword_output(keywords), provider=provider),
            )
            literature = typed_literature.to_dict()
            context.save("literature", literature)

        synthesis = context.load("synthesis")
        current_stage = "synthesis"
        if current_stage not in manager.completed_stages():
            synthesis = _execute(manager, current_stage, lambda: synthesize(literature, document))
            context.save("synthesis", synthesis)

        need_cases, need_policy = _route_stages(keywords)
        technical = context.load("technical_cases")
        current_stage = "technical_cases"
        if current_stage not in manager.completed_stages():
            if need_cases:
                technical = _execute(
                    manager, current_stage,
                    lambda: analyze_technical_cases(topic, literature, synthesis, document),
                )
                context.save("technical_cases", technical)
            else:
                manager.transition_stage(current_stage, StageStatus.SKIPPED)
                technical = {"status": "not_requested", "warnings": [], "cases": []}

        policy = context.load("policy_assessment")
        current_stage = "policy_assessment"
        if current_stage not in manager.completed_stages():
            if need_policy:
                policy = _execute(manager, current_stage, lambda: assess_policy(topic, literature, document))
                context.save("policy_assessment", policy)
            else:
                manager.transition_stage(current_stage, StageStatus.SKIPPED)
                policy = {"status": "not_requested", "warnings": [], "policies": []}

        sources = _source_registry(literature.get("literature_results", []), document)
        warnings = _collect_warnings(document, literature, synthesis, technical, policy)
        current_stage = "report_generation"
        report_path = manager.job_dir / "report.md"
        if current_stage not in manager.completed_stages():
            report = _execute(
                manager, current_stage,
                lambda: assemble_report(topic, synthesis, technical, policy, sources, warnings),
            )
            report_path.write_text(report, encoding="utf-8")
            context.save("report", {
                "report_path": str(report_path), "sources": sources, "warnings": warnings,
            })
        state = manager.load_state()
        state.artifacts = ArtifactSet(report=str(report_path))
        manager.save_state(state)
        manager.set_completed()
        return _build_result(job_id, output_root, context, JobStatus.COMPLETED)
    except NoteForgeError as error:
        manager.set_error(error, current_stage)
        raise
    except Exception as error:
        structured = NoteForgeError(
            ErrorCode.INTERNAL_ERROR,
            f"{type(error).__name__}: {error}",
            details={"stage": current_stage},
        )
        manager.set_error(structured, current_stage)
        raise structured from error


def _execute(manager: StateManager, stage: str, action: Callable[[], Any]) -> Any:
    manager.transition_stage(stage, StageStatus.RUNNING)
    result = action()
    manager.transition_stage(stage, StageStatus.COMPLETED)
    return result


def _build_result(job_id: str, output_root: Path, context: ContextStore,
                  status: JobStatus) -> JobResult:
    report_data = context.load("report") or {}
    sources = [SourceRecord.from_dict(item) for item in report_data.get("sources", [])]
    technical = context.load("technical_cases") or {}
    policy = context.load("policy_assessment") or {}
    report_path = Path(report_data.get("report_path") or output_root / "jobs" / job_id / "report.md")
    return JobResult(
        job_id=job_id,
        status=status,
        report_path=report_path,
        sources=sources,
        warnings=list(report_data.get("warnings", [])),
        tech_cases=[TechnicalCase.from_dict(item) for item in technical.get("cases", [])],
        policies=[PolicyRecord.from_dict(item) for item in policy.get("policies", [])],
    )


def _provider_from_value(value: Any) -> ProviderName | None:
    if not value:
        return None
    try:
        return ProviderName(str(value))
    except ValueError:
        return None


def _configured_provider() -> ProviderName:
    value = os.environ.get("LITERATURE_PROVIDER", DEFAULT_PROVIDER)
    try:
        return ProviderName(value)
    except ValueError as error:
        raise NoteForgeError(ErrorCode.INPUT_INVALID, "LITERATURE_PROVIDER 配置无效") from error


def _generate_job_id() -> str:
    return f"{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3)}"


def _route_stages(keyword_output: dict[str, Any]) -> tuple[bool, bool]:
    keywords = [str(value).casefold() for value in keyword_output.get("keywords", [])]
    entities = keyword_output.get("academic_entities", {})
    methods = [str(value).casefold() for value in entities.get("methods", [])]
    domains = [str(value).casefold() for value in entities.get("domains", [])]
    combined = " ".join(keywords + methods + domains)
    need_cases = bool(methods) or any(marker in combined for marker in (
        "transformer", "diffusion", "gan", "reinforcement", "模型", "部署",
    ))
    need_policy = any(marker in combined for marker in (
        "policy", "law", "legal", "regulation", "governance", "compliance",
        "政策", "法规", "监管", "合规", "法律", "标准", "安全",
    ))
    return need_cases, need_policy


def _source_registry(literature: list[dict[str, Any]], document: dict[str, Any] | None) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    if isinstance(document, dict):
        metadata = document.get("metadata", {})
        sources.append({
            "source_id": "D1", "title": metadata.get("file_name", "source document"),
            "authors": [], "year": None, "doi": None, "url": None,
            "source_provider": "local-file", "source_type": "source_document",
            "retrieved_at": None,
        })
    for item in literature:
        if isinstance(item, dict):
            sources.append({
                key: item.get(key) for key in (
                    "source_id", "title", "authors", "year", "doi", "url",
                    "source_provider", "source_type", "retrieved_at",
                )
            })
    return sources


def _collect_warnings(*outputs: Any) -> list[str]:
    warnings: list[str] = []
    for output in outputs:
        if isinstance(output, dict):
            for warning in output.get("warnings", []):
                text = str(warning).strip()
                if text and text not in warnings:
                    warnings.append(text)
    return warnings


def _write_resume_log(job_dir: Path, completed: set[str], job_id: str):
    job_dir.mkdir(parents=True, exist_ok=True)
    mode = "续跑" if completed else "启动"
    with (job_dir / "resume_log.txt").open("a", encoding="utf-8") as handle:
        handle.write(f"[{mode}] {now_iso()} | Job: {job_id} | completed={sorted(completed)}\n")
