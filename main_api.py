"""
NoteForge — FastAPI 异步服务入口

端点：
  POST /api/v1/jobs/submit       提交任务（可选上传文件 + topic）
  GET  /api/v1/jobs/status/{id}  查询任务状态
  GET  /api/v1/jobs/result/{id}  获取结果报告
"""

import os
import sys
import re
import threading
import secrets
import time
from pathlib import PurePath, PureWindowsPath
from datetime import datetime, timezone, timedelta

try:
    from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
    from fastapi.responses import JSONResponse
    import uvicorn
except ImportError:
    print("错误：FastAPI 服务需要安装 fastapi 和 uvicorn。")
    print("  pip install fastapi uvicorn python-multipart")
    sys.exit(1)

from utils.env_loader import load_env
from utils.logger import get_logger
from utils.state_manager import StateManager, validate_job_id
from utils.context_manager import ContextStore
from core.pipeline import run_job, PipelineError
from core.version import __version__
from tasks.t2_literature_search import DEFAULT_PROVIDER, PROVIDER_NAMES

log = get_logger(__name__)

load_env()

app = FastAPI(
    title="NoteForge API",
    version=__version__,
    description="学术文献提炼引擎 — 提交-轮询-获取结果接口",
)

TZ = timezone(timedelta(hours=8))
JOBS_OUTPUT_DIR = os.path.join("outputs", "jobs")

# ── 配置 ──
API_TOKEN = os.environ.get("API_TOKEN", "").strip()
MAX_UPLOAD_SIZE_MB = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "50"))
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".pdf", ".docx", ".json",
    ".csv", ".html", ".htm", ".xml", ".epub", ".rtf",
    ".tex", ".rst", ".log", ".ini", ".yaml", ".yml",
}
SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")

# ── 鉴权中间件 ──

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """简单 token 鉴权。未配置 API_TOKEN 时跳过。"""
    if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)
    if not API_TOKEN:
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    expected = f"Bearer {API_TOKEN}"
    if auth != expected:
        return JSONResponse(status_code=401, content={"detail": "未授权：需要有效的 API Token"})
    return await call_next(request)


# ── 文件验证 ──

def _validate_upload(file: UploadFile):
    """验证上传文件的扩展名和内容。"""
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件")
    safe_name = _sanitize_filename(file.filename)
    _, ext = os.path.splitext(safe_name)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型 '{ext}'。允许的类型: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    return safe_name


def _sanitize_filename(filename: str) -> str:
    """将上传文件名规整为安全的单文件名，兼容 Windows 和 POSIX 路径。"""
    raw_name = str(filename or "").strip()
    leaf_name = PurePath(PureWindowsPath(raw_name).name).name
    leaf_name = SAFE_FILENAME_PATTERN.sub("_", leaf_name).strip("._")
    if not leaf_name:
        leaf_name = "upload"
    if len(leaf_name) > 128:
        stem, ext = os.path.splitext(leaf_name)
        leaf_name = f"{stem[:128 - len(ext)]}{ext}"
    return leaf_name


def _validate_api_job_id(job_id: str) -> str:
    """校验 API 路径中的 job_id，非法时返回 400。"""
    try:
        return validate_job_id(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── 定期清理 ──

def _schedule_cleanup(interval_hours: int = 1):
    """后台线程定期清理过期 job。"""
    def _run():
        while True:
            time.sleep(interval_hours * 3600)
            try:
                from utils.job_cleanup import cleanup_old_jobs
                deleted, total = cleanup_old_jobs()
                if deleted > 0:
                    log.info("定期清理: 删除 %d/%d 个过期 job", deleted, total)
            except Exception as e:
                log.warning("定期清理失败: %s", e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    log.info("定期清理已启动 (间隔 %d 小时)", interval_hours)


def _generate_job_id() -> str:
    now = datetime.now(TZ).strftime("%Y%m%d")
    suffix = secrets.token_hex(3)
    return f"{now}-{suffix}"


def _run_job_background(job_id: str, topic: str, file_path: str = None,
                        provider: str | None = None):
    """在后台线程中执行管道，捕获异常写入状态。"""
    try:
        run_job(job_id, topic=topic, file_path=file_path, provider=provider)
    except Exception as e:
        log.error("Job %s 执行失败: %s", job_id, e)
        try:
            smgr = StateManager(job_id)
            smgr.set_error(f"{type(e).__name__}: {e}")
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
# POST /api/v1/jobs/submit
# ═══════════════════════════════════════════════════════════════════

@app.post("/api/v1/jobs/submit")
async def submit_job(
    file: UploadFile = File(None),
    topic: str = Form(""),
    provider: str = Form(""),
):
    """提交一个分析任务。提供 file 或 topic 至少其一。"""
    if not topic and (file is None or file.filename == ""):
        raise HTTPException(status_code=400, detail="请提供 topic 或上传文件")

    provider = provider.strip().lower().replace("_", "-")
    if provider and provider not in PROVIDER_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文献 Provider；可选值: {', '.join(PROVIDER_NAMES)}",
        )
    selected_provider = (
        provider or os.environ.get("LITERATURE_PROVIDER", DEFAULT_PROVIDER)
    ).strip().lower().replace("_", "-")
    if selected_provider not in PROVIDER_NAMES:
        raise HTTPException(status_code=500, detail="服务端 LITERATURE_PROVIDER 配置无效")

    # 文件验证
    if file and file.filename:
        safe_name = _validate_upload(file)
    else:
        safe_name = None

    job_id = _generate_job_id()
    job_dir = os.path.join(JOBS_OUTPUT_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    uploaded_path = None

    # 保存上传文件
    if file and file.filename:
        # 读取并检查大小
        content = await file.read()
        size_mb = len(content) / (1024 * 1024)
        if size_mb > MAX_UPLOAD_SIZE_MB:
            raise HTTPException(
                status_code=413,
                detail=f"文件过大 ({size_mb:.1f}MB)。最大允许: {MAX_UPLOAD_SIZE_MB}MB",
            )
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="文件为空")

        input_dir = os.path.join(job_dir, "input")
        os.makedirs(input_dir, exist_ok=True)
        uploaded_path = os.path.join(input_dir, safe_name)
        with open(uploaded_path, "wb") as f:
            f.write(content)

    # 初始化状态为 PENDING
    smgr = StateManager(job_id)
    smgr.init_state()

    # 后台执行
    t = threading.Thread(
        target=_run_job_background,
        args=(job_id, topic, uploaded_path, selected_provider),
        daemon=True,
    )
    t.start()

    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "status": "PENDING", "provider": selected_provider},
    )


# ═══════════════════════════════════════════════════════════════════
# GET /api/v1/jobs/status/{job_id}
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/v1/jobs/status/{job_id}")
async def job_status(job_id: str):
    """查询任务状态。"""
    job_id = _validate_api_job_id(job_id)
    state_file = os.path.join(JOBS_OUTPUT_DIR, job_id, "task_state.json")
    if not os.path.exists(state_file):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' 不存在")

    smgr = StateManager(job_id)
    state = smgr.load_state()

    return {
        "job_id": state.get("job_id"),
        "status": state.get("status"),
        "current_task": state.get("current_task"),
        "created_at": state.get("created_at"),
        "updated_at": state.get("updated_at"),
        "error": state.get("error"),
        "task_list": [
            {
                "task_id": t["task_id"],
                "task_name": t["task_name"],
                "status": t["status"],
            }
            for t in state.get("task_list", [])
        ],
    }


# ═══════════════════════════════════════════════════════════════════
# GET /api/v1/jobs/result/{job_id}
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/v1/jobs/result/{job_id}")
async def job_result(job_id: str):
    """获取任务结果（仅 COMPLETED 状态）。"""
    job_id = _validate_api_job_id(job_id)
    state_file = os.path.join(JOBS_OUTPUT_DIR, job_id, "task_state.json")
    if not os.path.exists(state_file):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' 不存在")

    smgr = StateManager(job_id)
    state = smgr.load_state()

    if state.get("status") != "COMPLETED":
        raise HTTPException(
            status_code=409,
            detail=f"任务尚未完成，当前状态: {state.get('status')}",
        )

    # 读取报告
    report_path = os.path.join(JOBS_OUTPUT_DIR, job_id, "report.md")
    if not os.path.exists(report_path):
        report_path = os.path.join(JOBS_OUTPUT_DIR, job_id, "report_framework.md")
    report = ""
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            report = f.read()

    # 读取上下文摘要
    cs = ContextStore(job_id)
    ctx_data = cs.load_all()
    t1_out = _safe_get(ctx_data, "T1", "result")
    t2_out = _safe_get(ctx_data, "T2", "result")
    t3_out = _safe_get(ctx_data, "T3", "result")
    t4_out = _safe_get(ctx_data, "T4", "result")
    t5_out = _safe_get(ctx_data, "T5", "result")
    t6_out = _safe_get(ctx_data, "T6", "result")
    context_summary = {
        "keys": list(ctx_data.keys()),
        "t1_keywords": t1_out.get("keywords", []) if isinstance(t1_out, dict) else [],
        "t2_result_count": len(t2_out.get("literature_results", [])) if isinstance(t2_out, dict) else 0,
        "t3_report_length": len(t3_out.get("final_report", "")) if isinstance(t3_out, dict) else 0,
    }

    return {
        "job_id": state.get("job_id"),
        "status": state.get("status"),
        "report": report,
        "context_summary": context_summary,
        "provider_status": {
            "provider": t2_out.get("provider"),
            "status": t2_out.get("status"),
            "query": t2_out.get("query"),
            "retrieved_at": t2_out.get("retrieved_at"),
        } if isinstance(t2_out, dict) else None,
        "sources": t4_out.get("sources", []) if isinstance(t4_out, dict) else [],
        "tech_cases": t5_out.get("cases", []) if isinstance(t5_out, dict) else [],
        "policy_assessment": t6_out.get("policies", []) if isinstance(t6_out, dict) else [],
        "warnings": t4_out.get("warnings", []) if isinstance(t4_out, dict) else [],
    }


# ═══════════════════════════════════════════════════════════════════
# Health check
# ═══════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {"status": "ok"}


def _safe_get(d, *keys):
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k)
        else:
            return None
    return d


# ═══════════════════════════════════════════════════════════════════
# 开发模式启动
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", "8000"))
    _schedule_cleanup()
    auth_status = "已启用" if API_TOKEN else "未启用（公开访问）"
    print(f"启动 NoteForge API 服务 (端口 {port})...")
    print(f"API 鉴权: {auth_status}")
    print(f"上传限制: {MAX_UPLOAD_SIZE_MB}MB, 允许类型: {len(ALLOWED_EXTENSIONS)} 种")
    uvicorn.run("main_api:app", host="0.0.0.0", port=port, reload=False)
