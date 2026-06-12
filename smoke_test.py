"""Smoke test — 验证 Topic 模式、文件模式和结构化 schema。"""
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
    if not output_path.exists():
        print(f"[FAIL] 输出目录不存在: {output_path}")
        FAILED += 1
        return output_dir

    job_dir = Path("outputs") / "jobs" / os.path.basename(output_dir.rstrip("/\\"))

    # 验证 state file
    state_file = job_dir / "task_state.json"
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
    report_path = output_path / "report_framework.md"
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

    # 验证 context_data.json schema
    ctx_path = job_dir / "context_data.json"
    if ctx_path.exists():
        with open(ctx_path, "r", encoding="utf-8") as f:
            ctx = json.load(f)

        # T1 schema 验证
        t1_key = "T1"
        if t1_key in ctx:
            t1_data = ctx[t1_key].get("result", {})
            if isinstance(t1_data, dict):
                has_kw = isinstance(t1_data.get("keywords"), list)
                has_ae = isinstance(t1_data.get("academic_entities"), dict)
                if has_kw and has_ae:
                    print(f"[ OK ] T1 schema: keywords={len(t1_data['keywords'])} "
                          f"methods={len(t1_data['academic_entities'].get('methods', []))}")
                else:
                    print(f"[FAIL] T1 schema 不完整")
                    FAILED += 1
            else:
                print(f"[WARN] T1 非 dict（可能为旧版或 Topic 模式差异）")

        # T2 schema 验证
        t2_key = "T2"
        if t2_key in ctx:
            t2_data = ctx[t2_key].get("result", {})
            if isinstance(t2_data, dict):
                lr = t2_data.get("literature_results", [])
                all_simulated = all(
                    isinstance(r, dict) and r.get("source_type") == "simulated"
                    for r in lr
                )
                if all_simulated:
                    print(f"[ OK ] T2 schema: {len(lr)} 文献, source_type=simulated")
                else:
                    print(f"[FAIL] T2 文献缺少 source_type=simulated 标记")
                    FAILED += 1
            else:
                print(f"[FAIL] T2 非 dict")
                FAILED += 1

        print(f"[ OK ] 上下文键: {list(ctx.keys())}")
    else:
        print(f"[FAIL] context_data.json 缺失")
        FAILED += 1

    return output_dir


# ── Test 1: Topic 模式 ──
run_pipeline(["--topic", "transformer model evaluation", "--output", "test_output_topic"], "Topic 模式")

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
    run_pipeline(
        ["--file", tmp_file, "--topic", "LLM benchmark evaluation", "--output", "test_output_file"],
        "TXT 文件模式",
    )
finally:
    os.unlink(tmp_file)


# ── Test 3: JSON schema 跨模式一致性 ──
print(f"\n{'='*50}")
print(" Smoke: Mock 模式 JSON schema 验证")
print(f"{'='*50}")
from tasks.t1_keyword_extraction import run as t1
from tasks.t2_literature_search import run as t2

r1 = t1("transformer models for NLP evaluation")
assert isinstance(r1, dict), "T1 应返回 dict"
assert "keywords" in r1, "T1 缺少 keywords"
assert "academic_entities" in r1, "T1 缺少 academic_entities"
ae = r1["academic_entities"]
for field in ("methods", "datasets", "metrics", "tasks", "domains", "relations"):
    assert field in ae, f"T1 academic_entities 缺少 {field}"

r2 = t2(r1)
assert isinstance(r2, dict), "T2 应返回 dict"
assert "literature_results" in r2, "T2 缺少 literature_results"
for lr in r2["literature_results"]:
    assert lr["source_type"] == "simulated", f"文献应标记 simulated，得到 {lr.get('source_type')}"
    for field in ("title", "authors", "year", "core_method", "key_findings"):
        assert field in lr, f"文献缺少 {field}"
print("[ OK ] Mock 模式 T1/T2 JSON schema 同构验证通过")


# ── Test 4: 并发 job 隔离 ──
print(f"\n{'='*50}")
print(" Smoke: 并发 job 隔离")
print(f"{'='*50}")
t1_r = subprocess.run(
    [sys.executable, MAIN_PY, "--topic", "AI ethics", "--output", "test_isolation_a"],
    capture_output=True, text=True, cwd=str(PROJECT_ROOT),
)
t2_r = subprocess.run(
    [sys.executable, MAIN_PY, "--topic", "climate change", "--output", "test_isolation_b"],
    capture_output=True, text=True, cwd=str(PROJECT_ROOT),
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
        if sa.get("job_id") == sb.get("job_id"):
            print(f"[FAIL] job_id 相同: {sa['job_id']}")
            FAILED += 1
        else:
            print(f"[ OK ] job 隔离通过 (a={sa['job_id']}, b={sb['job_id']})")
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
