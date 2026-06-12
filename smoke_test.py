"""Smoke test — 验证 Topic 模式、文件模式和 job 级状态隔离。"""
import subprocess
import sys
import tempfile
import os
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
MAIN_PY = str(PROJECT_ROOT / "main.py")
FAILED = 0


def run_pipeline(args, label):
    global FAILED
    print(f"\n{'='*50}")
    print(f" Smoke: {label}")
    print(f" 命令: python main.py {' '.join(args)}")
    print(f"{'='*50}")
    result = subprocess.run(
        [sys.executable, MAIN_PY] + args,
        capture_output=True, text=True,
        cwd=str(PROJECT_ROOT),
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"[FAIL] 进程退出码 {result.returncode}")
        if result.stderr:
            print(result.stderr)
        FAILED += 1
        return None

    # 推断输出目录
    output_dir = None
    for i, arg in enumerate(args):
        if arg in ("--output", "-o") and i + 1 < len(args):
            output_dir = args[i + 1]
            break
        if arg.startswith("--output="):
            output_dir = arg.split("=", 1)[1]
            break
        if arg.startswith("-o") and len(arg) > 2 and arg[2] != " ":
            continue  # -oValue form
    if output_dir is None:
        output_dir = "outputs"

    output_path = PROJECT_ROOT / output_dir
    if not output_path.exists():
        print(f"[FAIL] 输出目录不存在: {output_path}")
        FAILED += 1
        return output_dir

    # 状态隔离：检查路径在 outputs/jobs/{job_id}/ 下
    job_dir = Path("outputs") / "jobs" / os.path.basename(output_dir.rstrip("/\\"))
    state_file = job_dir / "task_state.json" if job_dir.exists() else output_path / "task_state.json"
    report_path = output_path / "report_framework.md"

    # 验证 state file
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        task_ids = {t["task_id"] for t in state.get("task_list", [])}
        if "T0" not in task_ids:
            print(f"[FAIL] 状态文件缺少 T0")
            FAILED += 1
    else:
        print(f"[WARN] 状态文件未在预期路径: {state_file}")

    # 验证报告文件
    if not report_path.exists():
        print(f"[FAIL] 未生成报告文件: {report_path}")
        FAILED += 1
        return output_dir

    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()
    if not content.strip():
        print(f"[FAIL] 报告文件为空: {report_path}")
        FAILED += 1
    else:
        print(f"[ OK ] 报告已生成 ({len(content)} 字符)")

    # 验证 context_data.json
    ctx_path = job_dir / "context_data.json" if job_dir.exists() else output_path / "context_data.json"
    if ctx_path.exists():
        with open(ctx_path, "r", encoding="utf-8") as f:
            ctx = json.load(f)
        t0_key = "document_parse"
        if t0_key in ctx:
            t0_data = ctx[t0_key].get("result", {})
            if isinstance(t0_data, dict) and "raw_text" in t0_data:
                print(f"[ OK ] T0 上下文: raw_text={len(t0_data['raw_text'])} chars, "
                      f"metadata={t0_data.get('metadata', {})}")
            else:
                print(f"[ OK ] T0 上下文存在但非字典（Topic 模式）")
        else:
            print(f"[ OK ] 上下文键: {list(ctx.keys())}")

    return output_dir


# ── Test 1: Topic 模式 ──
run_pipeline(["--topic", "AI safety", "--output", "test_output_topic"], "Topic 模式")

# ── Test 2: TXT 文件模式 ──
with tempfile.NamedTemporaryFile(
    mode="w", suffix=".txt", prefix="smoke_test_", delete=False, encoding="utf-8"
) as f:
    f.write("# AI Safety Research\n\n")
    f.write("This document discusses alignment, robustness, and interpretability.\n\n")
    f.write("## Key Metrics\n\n")
    f.write("The model achieved 95% accuracy on benchmark XYZ.\n\n")
    f.write("$$\n")
    f.write("P(y|x) = \\frac{\\exp(f(x, y))}{\\sum_{y'} \\exp(f(x, y'))}\n")
    f.write("$$\n")
    tmp_file = f.name

try:
    run_pipeline(
        ["--file", tmp_file, "--topic", "AI safety analysis", "--output", "test_output_file"],
        "TXT 文件模式",
    )
finally:
    os.unlink(tmp_file)


# ── Test 3: 并发任务隔离验证 ──
print(f"\n{'='*50}")
print(" Smoke: 并发 job 隔离")
print(f"{'='*50}")
t1_result = subprocess.run(
    [sys.executable, MAIN_PY, "--topic", "AI ethics", "--output", "test_isolation_a"],
    capture_output=True, text=True, cwd=str(PROJECT_ROOT),
)
t2_result = subprocess.run(
    [sys.executable, MAIN_PY, "--topic", "climate change", "--output", "test_isolation_b"],
    capture_output=True, text=True, cwd=str(PROJECT_ROOT),
)
if t1_result.returncode != 0 or t2_result.returncode != 0:
    print(f"[FAIL] 并发任务执行失败")
    FAILED += 1
else:
    # 验证两个 job 的状态文件互不交叉
    state_a = PROJECT_ROOT / "outputs" / "jobs" / "test_isolation_a" / "task_state.json"
    state_b = PROJECT_ROOT / "outputs" / "jobs" / "test_isolation_b" / "task_state.json"
    if state_a.exists() and state_b.exists():
        with open(state_a, encoding="utf-8") as f:
            sa = json.load(f)
        with open(state_b, encoding="utf-8") as f:
            sb = json.load(f)
        if sa.get("job_id") == sb.get("job_id"):
            print(f"[FAIL] job_id 相同: {sa['job_id']}")
            FAILED += 1
        elif sa.get("job_id") == "test_isolation_a" and sb.get("job_id") == "test_isolation_b":
            print(f"[ OK ] 两个 job 状态文件互不覆盖 (job_a={sa['job_id']}, job_b={sb['job_id']})")
        else:
            print(f"[ OK ] job_id 不同")
    else:
        print(f"[FAIL] 状态文件缺失")
        FAILED += 1


# ── Summary ──
print(f"\n{'='*50}")
if FAILED:
    print(f"{FAILED} smoke test(s) FAILED.")
    sys.exit(1)
else:
    print("All smoke tests PASSED.")
