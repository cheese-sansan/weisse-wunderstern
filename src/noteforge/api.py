"""FastAPI v1 compatibility surface backed by the typed SDK."""

from __future__ import annotations

import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePath, PureWindowsPath
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from noteforge.config import load_env
from noteforge.logging import get_logger
from noteforge.models import AnalysisRequest, JobStatus, ProviderName, StageStatus
from noteforge.pipeline import run_job
from noteforge.storage.context import ContextStore
from noteforge.storage.state import StateManager, validate_job_id
from noteforge.version import __version__

load_env()
log = get_logger(__name__)
TZ = timezone(timedelta(hours=8))
OUTPUT_ROOT = Path(os.environ.get("NOTEFORGE_OUTPUT_ROOT", "outputs"))
JOBS_OUTPUT_DIR = OUTPUT_ROOT / "jobs"
API_TOKEN = os.environ.get("API_TOKEN", "").strip()
MAX_UPLOAD_SIZE_MB = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "50"))
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".pdf", ".docx", ".json", ".csv", ".html",
    ".htm", ".xml", ".epub", ".rtf", ".tex", ".rst", ".log", ".ini",
    ".yaml", ".yml",
}
SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
STAGE_TO_TASK = {
    "document_parse": ("T0", "文档内容提取"),
    "keyword_extract": ("T1", "关键词提取"),
    "literature_search": ("T2", "文献检索"),
    "synthesis": ("T3", "学术提炼"),
    "report_generation": ("T4", "最终报告生成"),
    "technical_cases": ("T5", "技术案例分析"),
    "policy_assessment": ("T6", "政策影响评估"),
}
STAGE_STATUS_TO_V1 = {
    StageStatus.PENDING: "未开始", StageStatus.RUNNING: "进行中",
    StageStatus.COMPLETED: "完成", StageStatus.SKIPPED: "未开始",
    StageStatus.FAILED: "失败",
}


class SubmitResponse(BaseModel):
    job_id: str
    status: str
    provider: str


class TaskStatusResponse(BaseModel):
    task_id: str
    task_name: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    current_task: str | None = None
    created_at: str
    updated_at: str
    error: str | None = None
    error_code: str | None = None
    task_list: list[TaskStatusResponse] = Field(default_factory=list)


class ContextSummaryResponse(BaseModel):
    keys: list[str] = Field(default_factory=list)
    t1_keywords: list[str] = Field(default_factory=list)
    t2_result_count: int
    t3_report_length: int


class ProviderStatusResponse(BaseModel):
    provider: str | None = None
    status: str | None = None
    query: str | None = None
    retrieved_at: str | None = None


class JobResultResponse(BaseModel):
    job_id: str
    status: str
    report: str
    context_summary: ContextSummaryResponse
    provider_status: ProviderStatusResponse | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    tech_cases: list[dict[str, Any]] = Field(default_factory=list)
    policy_assessment: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def create_app() -> FastAPI:
    application = FastAPI(
        title="NoteForge API",
        version=__version__,
        description="学术文献提炼引擎 — 提交-轮询-获取结果接口",
    )

    @application.middleware("http")
    async def auth_middleware(request: Request, call_next):
        if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc") or not API_TOKEN:
            return await call_next(request)
        if request.headers.get("Authorization", "") != f"Bearer {API_TOKEN}":
            return JSONResponse(status_code=401, content={"detail": "未授权：需要有效的 API Token"})
        return await call_next(request)

    application.add_api_route(
        "/api/v1/jobs/submit", submit_job, methods=["POST"],
        response_model=SubmitResponse, status_code=202,
    )
    application.add_api_route(
        "/api/v1/jobs/status/{job_id}", job_status, methods=["GET"],
        response_model=JobStatusResponse,
    )
    application.add_api_route(
        "/api/v1/jobs/result/{job_id}", job_result, methods=["GET"],
        response_model=JobResultResponse,
    )
    application.add_api_route("/health", health, methods=["GET"])
    return application


async def submit_job(
    file: Annotated[UploadFile | None, File()] = None,
    topic: Annotated[str, Form()] = "",
    provider: Annotated[str, Form()] = "",
):
    if not topic and (file is None or file.filename == ""):
        raise HTTPException(status_code=400, detail="请提供 topic 或上传文件")
    provider_text = provider.strip().lower().replace("_", "-") or os.environ.get("LITERATURE_PROVIDER", "crossref")
    try:
        provider_name = ProviderName(provider_text)
    except ValueError as error:
        raise HTTPException(
            status_code=400 if provider else 500,
            detail="不支持的文献 Provider" if provider else "服务端 LITERATURE_PROVIDER 配置无效",
        ) from error
    safe_name = _validate_upload(file) if file and file.filename else None
    job_id = _generate_job_id()
    job_dir = JOBS_OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    uploaded_path = None
    if file and file.filename:
        assert safe_name is not None
        content = await file.read()
        if len(content) > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"文件过大。最大允许: {MAX_UPLOAD_SIZE_MB}MB")
        if not content:
            raise HTTPException(status_code=400, detail="文件为空")
        input_dir = job_dir / "input"
        input_dir.mkdir(exist_ok=True)
        uploaded_path = input_dir / safe_name
        uploaded_path.write_bytes(content)
    StateManager(job_id, OUTPUT_ROOT).init_state()
    thread = threading.Thread(
        target=_run_background,
        args=(AnalysisRequest(topic=topic, file_path=uploaded_path, provider=provider_name, job_id=job_id),),
        daemon=True,
    )
    thread.start()
    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "status": "PENDING", "provider": provider_name.value},
    )


async def job_status(job_id: str):
    job_id = _validate_api_job_id(job_id)
    state_path = JOBS_OUTPUT_DIR / job_id / "task_state.json"
    if not state_path.exists():
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' 不存在")
    state = StateManager(job_id, OUTPUT_ROOT).load_state()
    task_list = []
    for stage_name, (task_id, task_name) in STAGE_TO_TASK.items():
        stage = state.stages[stage_name]
        if stage_name in ("technical_cases", "policy_assessment") and stage.status is StageStatus.SKIPPED:
            continue
        task_list.append({
            "task_id": task_id,
            "task_name": task_name,
            "status": STAGE_STATUS_TO_V1[stage.status],
        })
    current_task = STAGE_TO_TASK[state.current_stage][0] if state.current_stage in STAGE_TO_TASK else None
    error_message = state.error.get("message") if state.error else None
    return {
        "job_id": state.job_id,
        "status": "PROCESSING" if state.status is JobStatus.RUNNING else state.status.value,
        "current_task": current_task,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
        "error": error_message,
        "error_code": state.error.get("code") if state.error else None,
        "task_list": task_list,
    }


async def job_result(job_id: str):
    job_id = _validate_api_job_id(job_id)
    state_path = JOBS_OUTPUT_DIR / job_id / "task_state.json"
    if not state_path.exists():
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' 不存在")
    state = StateManager(job_id, OUTPUT_ROOT).load_state()
    if state.status is not JobStatus.COMPLETED:
        status = "PROCESSING" if state.status is JobStatus.RUNNING else state.status.value
        raise HTTPException(status_code=409, detail=f"任务尚未完成，当前状态: {status}")
    context = ContextStore(job_id, OUTPUT_ROOT).load_all()
    literature = context.get("literature", {})
    synthesis = context.get("synthesis", {})
    technical = context.get("technical_cases", {})
    policy = context.get("policy_assessment", {})
    report_data = context.get("report", {})
    report_path = Path(report_data.get("report_path") or JOBS_OUTPUT_DIR / job_id / "report.md")
    report = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    keys = ["input"] + [
        task for semantic, task in (
            ("document", "T0"), ("keywords", "T1"), ("literature", "T2"),
            ("synthesis", "T3"), ("report", "T4"), ("technical_cases", "T5"),
            ("policy_assessment", "T6"),
        ) if semantic in context
    ]
    return {
        "job_id": state.job_id,
        "status": state.status.value,
        "report": report,
        "context_summary": {
            "keys": keys,
            "t1_keywords": context.get("keywords", {}).get("keywords", []),
            "t2_result_count": len(literature.get("literature_results", [])),
            "t3_report_length": len(synthesis.get("final_report", "")),
        },
        "provider_status": {
            "provider": literature.get("provider"), "status": literature.get("status"),
            "query": literature.get("query"), "retrieved_at": literature.get("retrieved_at"),
        } if literature else None,
        "sources": report_data.get("sources", []),
        "tech_cases": technical.get("cases", []),
        "policy_assessment": policy.get("policies", []),
        "warnings": report_data.get("warnings", []),
    }


async def health():
    return {"status": "ok"}


def _run_background(request: AnalysisRequest):
    try:
        run_job(request, output_root=OUTPUT_ROOT)
    except Exception as error:
        log.error("Job %s failed: %s", request.job_id, error)


def _validate_upload(file: UploadFile) -> str:
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件")
    safe_name = _sanitize_filename(file.filename)
    extension = Path(safe_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型 '{extension}'")
    return safe_name


def _sanitize_filename(filename: str) -> str:
    leaf = PurePath(PureWindowsPath(str(filename or "").strip()).name).name
    leaf = SAFE_FILENAME_PATTERN.sub("_", leaf).strip("._") or "upload"
    if len(leaf) > 128:
        stem, extension = os.path.splitext(leaf)
        leaf = f"{stem[:128 - len(extension)]}{extension}"
    return leaf


def _validate_api_job_id(job_id: str) -> str:
    try:
        return validate_job_id(job_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _generate_job_id() -> str:
    return f"{datetime.now(TZ).strftime('%Y%m%d')}-{secrets.token_hex(3)}"


def _schedule_cleanup(interval_hours: int = 1):
    def loop():
        while True:
            time.sleep(interval_hours * 3600)
            from noteforge.storage.cleanup import cleanup_old_jobs

            cleanup_old_jobs(output_root=OUTPUT_ROOT)

    threading.Thread(target=loop, daemon=True).start()


def serve(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn

    _schedule_cleanup()
    uvicorn.run("noteforge.api:app", host=host, port=port, reload=False)


app = create_app()
