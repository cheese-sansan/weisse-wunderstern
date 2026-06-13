"""
Lite Agent Orchestrator — FastAPI 异步服务入口

端点：
  POST /api/v1/jobs/submit       提交任务（可选上传文件 + topic）
  GET  /api/v1/jobs/status/{id}  查询任务状态
  GET  /api/v1/jobs/result/{id}  获取结果报告
"""

import os
import sys
import json
import threading
import secrets
from datetime import datetime, timezone, timedelta

try:
    from fastapi import FastAPI, UploadFile, File, Form, HTTPException
    from fastapi.responses import JSONResponse
    import uvicorn
except ImportError:
    print("错误：FastAPI 服务需要安装 fastapi 和 uvicorn。")
    print("  pip install fastapi uvicorn python-multipart")
    sys.exit(1)

from utils.env_loader import load_env
from utils.state_manager import StateManager
from utils.context_manager import ContextStore
from core.pipeline import run_job, PipelineError

load_env()

app = FastAPI(
    title="Lite Agent Orchestrator API",
    version="0.4.0",
    description="学术文献提炼引擎 — 提交-轮询-获取结果接口",
)

TZ = timezone(timedelta(hours=8))
JOBS_OUTPUT_DIR = os.path.join("outputs", "jobs")


def _generate_job_id() -> str:
    now = datetime.now(TZ).strftime("%Y%m%d")
    suffix = secrets.token_hex(3)
    return f"{now}-{suffix}"


def _run_job_background(job_id: str, topic: str, file_path: str = None):
    """在后台线程中执行管道，捕获异常写入状态。"""
    try:
        run_job(job_id, topic=topic, file_path=file_path)
    except Exception as e:
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
):
    """提交一个分析任务。提供 file 或 topic 至少其一。"""
    if not topic and (file is None or file.filename == ""):
        raise HTTPException(status_code=400, detail="请提供 topic 或上传文件")

    job_id = _generate_job_id()
    job_dir = os.path.join(JOBS_OUTPUT_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    uploaded_path = None

    # 保存上传文件
    if file and file.filename:
        input_dir = os.path.join(job_dir, "input")
        os.makedirs(input_dir, exist_ok=True)
        safe_name = os.path.basename(file.filename)
        uploaded_path = os.path.join(input_dir, safe_name)
        content = await file.read()
        with open(uploaded_path, "wb") as f:
            f.write(content)

    # 初始化状态为 PENDING
    smgr = StateManager(job_id)
    smgr.init_state()

    # 后台执行
    t = threading.Thread(
        target=_run_job_background,
        args=(job_id, topic, uploaded_path),
        daemon=True,
    )
    t.start()

    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "status": "PENDING"},
    )


# ═══════════════════════════════════════════════════════════════════
# GET /api/v1/jobs/status/{job_id}
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/v1/jobs/status/{job_id}")
async def job_status(job_id: str):
    """查询任务状态。"""
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
    print(f"启动 Lite Agent Orchestrator API 服务 (端口 {port})...")
    uvicorn.run("main_api:app", host="0.0.0.0", port=port, reload=False)
