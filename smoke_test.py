"""Smoke test — 验证完整管道、结构化 schema 和 T3 三角色审稿环路。"""
import subprocess
import sys
import tempfile
import os
import json
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
MAIN_PY = str(PROJECT_ROOT / "main.py")
TUI_PY = str(PROJECT_ROOT / "main_tui.py")
FAILED = 0
SUBPROCESS_ENV = {
    **os.environ,
    "PYTHONIOENCODING": "utf-8",
    "LITERATURE_PROVIDER": "mock",
}


def configure_stdio():
    """Keep captured UTF-8 output printable on Windows legacy consoles."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


configure_stdio()


def run_pipeline(args, label):
    global FAILED
    print(f"\n{'='*50}")
    print(f" Smoke: {label}")
    print(f" 命令: python main.py {' '.join(args)}")
    print(f"{'='*50}")
    result = subprocess.run(
        [sys.executable, MAIN_PY] + args,
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        env=SUBPROCESS_ENV,
        cwd=str(PROJECT_ROOT),
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"[FAIL] 进程退出码 {result.returncode}")
        if result.stderr:
            print(result.stderr)
        FAILED += 1
        return None

    output_dir = None
    for i, arg in enumerate(args):
        if arg in ("--output", "-o") and i + 1 < len(args):
            output_dir = args[i + 1]
            break
        if arg.startswith("--output="):
            output_dir = arg.split("=", 1)[1]
            break
    if output_dir is None:
        output_dir = "outputs"

    output_path = PROJECT_ROOT / output_dir
    job_dir = Path("outputs") / "jobs" / os.path.basename(output_dir.rstrip("/\\"))
    full_job_dir = PROJECT_ROOT / job_dir

    # 验证 state file
    state_file = full_job_dir / "task_state.json"
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        task_ids = {t["task_id"] for t in state.get("task_list", [])}
        for tid in ("T0", "T1", "T2"):
            if tid not in task_ids:
                print(f"[FAIL] 状态文件缺少 {tid}")
                FAILED += 1
    else:
        print(f"[WARN] 状态文件未在预期路径: {state_file}")

    # 验证报告文件（位于 job 目录下）
    report_path = full_job_dir / "report.md"
    if report_path.exists():
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()
        if content.strip():
            print(f"[ OK ] 报告已生成 ({len(content)} 字符)")
        else:
            print(f"[FAIL] 报告文件为空")
            FAILED += 1
    else:
        print(f"[FAIL] 未生成报告文件")
        FAILED += 1

    # 验证 context_data.json
    ctx_path = full_job_dir / "context_data.json"
    if ctx_path.exists():
        with open(ctx_path, "r", encoding="utf-8") as f:
            ctx = json.load(f)

        # T1 schema
        t1_data = ctx.get("T1", {}).get("result", {})
        if isinstance(t1_data, dict) and "academic_entities" in t1_data:
            print(f"[ OK ] T1: keywords={len(t1_data.get('keywords', []))}")

        # T2 schema
        t2_data = ctx.get("T2", {}).get("result", {})
        if isinstance(t2_data, dict):
            lr = t2_data.get("literature_results", [])
            all_sim = all(r.get("source_type") == "simulated" for r in lr if isinstance(r, dict))
            if t2_data.get("provider") == "mock" and all_sim:
                print(f"[ OK ] T2: explicit mock, {len(lr)} simulated results")
            else:
                print(f"[FAIL] T2 provider/source contract invalid: {t2_data.get('provider')}")
                FAILED += 1

        # T3 triple-role schema
        t3_data = ctx.get("T3", {}).get("result", {})
        if isinstance(t3_data, dict):
            for key in ("extractor_draft", "critic_review", "final_report"):
                if key in t3_data:
                    print(f"[ OK ] T3: {key} present")
                else:
                    print(f"[FAIL] T3 缺少 {key}")
                    FAILED += 1

            # 验证 Critic 至少 2 条质疑
            critic = t3_data.get("critic_review", {})
            critiques = critic.get("critiques", [])
            if len(critiques) >= 2:
                print(f"[ OK ] T3 Critic: {len(critiques)} critiques")
            else:
                print(f"[FAIL] T3 Critic 不足 2 条质疑 (got {len(critiques)})")
                FAILED += 1

            # 验证 final_report 包含 5 个必要章节
            report = t3_data.get("final_report", "")
            sections = ["核心共识", "学术冲突", "方法局限", "高价值定量指标", "证据与不确定性"]
            missing = [s for s in sections if s not in report]
            if missing:
                print(f"[FAIL] T3 报告缺少章节: {missing}")
                FAILED += 1
            else:
                print(f"[ OK ] T3 报告包含全部 5 个章节")

            # 验证不把 simulated 表述为真实
            if "simulated" in report.lower() or "模拟生成" in report:
                print(f"[ OK ] T3 报告标注了模拟来源声明")
            else:
                print(f"[WARN] T3 报告未明确标注模拟来源")

        print(f"[ OK ] 上下文键: {list(ctx.keys())}")
    else:
        print(f"[FAIL] context_data.json 缺失")
        FAILED += 1

    return output_dir


def clean_job(output_dir):
    """清理指定 smoke job，避免历史 outputs 影响验证结果。"""
    job_id = os.path.basename(output_dir.rstrip("/\\"))
    job_dir = PROJECT_ROOT / "outputs" / "jobs" / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)


def assert_rerun_is_noop(output_dir):
    """已完成 job 再运行时应直接返回，不追加动态任务或改写状态。"""
    global FAILED
    job_id = os.path.basename(output_dir.rstrip("/\\"))
    state_file = PROJECT_ROOT / "outputs" / "jobs" / job_id / "task_state.json"
    with open(state_file, "r", encoding="utf-8") as f:
        before = json.load(f)

    result = subprocess.run(
        [sys.executable, MAIN_PY, "--topic", "rerun should be noop", "--output", output_dir],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        env=SUBPROCESS_ENV,
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        print(f"[FAIL] 已完成 job 重跑失败: {result.returncode}")
        FAILED += 1
        return

    with open(state_file, "r", encoding="utf-8") as f:
        after = json.load(f)

    before_tasks = [(t["task_id"], t["status"]) for t in before.get("task_list", [])]
    after_tasks = [(t["task_id"], t["status"]) for t in after.get("task_list", [])]
    if before_tasks == after_tasks and after.get("status") == "COMPLETED":
        print(f"[ OK ] 已完成 job 重跑保持幂等")
    else:
        print(f"[FAIL] 已完成 job 重跑改写了任务状态")
        print(f"  before={before_tasks}")
        print(f"  after={after_tasks}")
        FAILED += 1


# ── Test 1: Topic 模式 ──
clean_job("test_output_topic")
run_pipeline(["--topic", "transformer model evaluation for NLP", "--output", "test_output_topic"], "Topic 模式")
assert_rerun_is_noop("test_output_topic")

# ── Test 2: TXT 文件模式 ──
with tempfile.NamedTemporaryFile(
    mode="w", suffix=".txt", prefix="smoke_test_", delete=False, encoding="utf-8"
) as f:
    f.write("# Benchmarking Large Language Models\n\n")
    f.write("This paper evaluates GPT, BERT, and T5 on MMLU and GLUE benchmarks.\n\n")
    f.write("## Methods\n")
    f.write("We fine-tuned each model using LoRA and measured accuracy and F1 scores.\n\n")
    f.write("## Results\n")
    f.write("GPT-4 achieved 86.4% accuracy, outperforming BERT (79.2%) and T5 (81.1%).\n")
    tmp_file = f.name

try:
    clean_job("test_output_file")
    run_pipeline(
        ["--file", tmp_file, "--topic", "LLM benchmark evaluation", "--output", "test_output_file"],
        "TXT 文件模式",
    )
finally:
    os.unlink(tmp_file)


# ── Test 3: T3 triple-role standalone ──
print(f"\n{'='*50}")
print(" Smoke: T3 三角色审稿环路验证")
print(f"{'='*50}")
from tasks.t3_summary_generation import run as t3_run

t2_mock = {
    "literature_results": [
        {
            "title": "Test Paper 1", "source_type": "simulated",
            "core_method": "SVM", "datasets": ["MNIST"],
            "metrics": ["Accuracy=0.95"],
            "key_findings": ["SVM outperforms baseline on MNIST"],
            "limitations": ["Small sample size (n=100)"],
            "authors": ["Author A"], "year": 2024,
        },
        {
            "title": "Test Paper 2", "source_type": "simulated",
            "core_method": "CNN", "datasets": ["CIFAR-10"],
            "metrics": ["Accuracy=0.88"],
            "key_findings": ["CNN achieves state-of-art on CIFAR-10"],
            "limitations": ["High computational cost"],
            "authors": ["Author B"], "year": 2023,
        },
    ]
}
result = t3_run(t2_mock)

for key in ("extractor_draft", "critic_review", "final_report"):
    assert key in result, f"T3 缺少 {key}"
    print(f"[ OK ] {key} present")

critiques = result["critic_review"].get("critiques", [])
assert len(critiques) >= 2, f"Critic 需要 >=2 条质疑，得到 {len(critiques)}"
print(f"[ OK ] Critic: {len(critiques)} critiques")
for c in critiques:
    print(f"  - [{c.get('severity', '?')}] {c.get('point', '')}")

report = result["final_report"]
sections = ["核心共识", "学术冲突", "方法局限", "高价值定量指标", "证据与不确定性"]
for s in sections:
    assert s in report, f"报告缺少章节: {s}"
print(f"[ OK ] 报告包含全部 5 个章节 ({len(report)} chars)")
assert "模拟生成" in report or "simulated" in report.lower(), "缺少模拟来源声明"
print(f"[ OK ] 报告包含模拟来源声明")
print(f"[ OK ] T3 三角色审稿环路验证通过")


# ── Test 4: TUI one-shot and report viewing ──
print(f"\n{'='*50}")
print(" Smoke: TUI 一次性分析与报告查看")
print(f"{'='*50}")
clean_job("test_tui_topic")
tui_run = subprocess.run(
    [sys.executable, TUI_PY, "--topic", "TUI smoke transformer analysis", "--job-id", "test_tui_topic"],
    capture_output=True, text=True,
    encoding="utf-8", errors="replace",
    env=SUBPROCESS_ENV,
    cwd=str(PROJECT_ROOT),
)
if tui_run.returncode != 0:
    print(f"[FAIL] TUI one-shot failed: {tui_run.returncode}")
    print(tui_run.stdout)
    print(tui_run.stderr)
    FAILED += 1
else:
    report_path = PROJECT_ROOT / "outputs" / "jobs" / "test_tui_topic" / "report.md"
    if report_path.exists():
        print("[ OK ] TUI one-shot generated report")
    else:
        print("[FAIL] TUI one-shot did not generate report")
        FAILED += 1

tui_report = subprocess.run(
    [sys.executable, TUI_PY, "--report", "test_tui_topic"],
    capture_output=True, text=True,
    encoding="utf-8", errors="replace",
    env=SUBPROCESS_ENV,
    cwd=str(PROJECT_ROOT),
)
if tui_report.returncode == 0 and "Report: test_tui_topic" in tui_report.stdout:
    print("[ OK ] TUI report viewer works")
else:
    print("[FAIL] TUI report viewer failed")
    print(tui_report.stdout)
    print(tui_report.stderr)
    FAILED += 1


# ── Test 5: 并发 job 隔离 ──
print(f"\n{'='*50}")
print(" Smoke: 并发 job 隔离")
print(f"{'='*50}")
clean_job("test_isolation_a")
clean_job("test_isolation_b")
t1_r = subprocess.run(
    [sys.executable, MAIN_PY, "--topic", "AI ethics", "--output", "test_isolation_a"],
    capture_output=True, text=True,
    encoding="utf-8", errors="replace",
    env=SUBPROCESS_ENV,
    cwd=str(PROJECT_ROOT),
)
t2_r = subprocess.run(
    [sys.executable, MAIN_PY, "--topic", "climate change", "--output", "test_isolation_b"],
    capture_output=True, text=True,
    encoding="utf-8", errors="replace",
    env=SUBPROCESS_ENV,
    cwd=str(PROJECT_ROOT),
)
if t1_r.returncode != 0 or t2_r.returncode != 0:
    print(f"[FAIL] 并发任务执行失败")
    FAILED += 1
else:
    state_a = PROJECT_ROOT / "outputs" / "jobs" / "test_isolation_a" / "task_state.json"
    state_b = PROJECT_ROOT / "outputs" / "jobs" / "test_isolation_b" / "task_state.json"
    if state_a.exists() and state_b.exists():
        with open(state_a, encoding="utf-8") as f:
            sa = json.load(f)
        with open(state_b, encoding="utf-8") as f:
            sb = json.load(f)
        if sa.get("job_id") != sb.get("job_id"):
            print(f"[ OK ] job 隔离通过 (a={sa['job_id']}, b={sb['job_id']})")
        else:
            print(f"[FAIL] job_id 相同")
            FAILED += 1
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
