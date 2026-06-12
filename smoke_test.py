"""最小 smoke test — 验证 Topic 模式和 TXT 文件模式均能跑通完整管道。"""
import subprocess
import sys
import tempfile
import os
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
        print(result.stderr)
        FAILED += 1
        return

    output_dir = None
    for i, arg in enumerate(args):
        if arg == "--output" and i + 1 < len(args):
            output_dir = args[i + 1]
            break
        if arg.startswith("--output="):
            output_dir = arg.split("=", 1)[1]
            break
    if output_dir is None:
        print("[FAIL] 无法确定输出目录")
        FAILED += 1
        return

    report_path = os.path.join(PROJECT_ROOT, output_dir, "report_framework.md")
    if not os.path.exists(report_path):
        print(f"[FAIL] 未生成报告文件: {report_path}")
        FAILED += 1
        return

    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()
    if len(content.strip()) == 0:
        print(f"[FAIL] 报告文件为空: {report_path}")
        FAILED += 1
        return

    print(f"[ OK ] 报告已生成 ({len(content)} 字符)")


# ── Test 1: Topic 模式 ──
run_pipeline(["--topic", "AI safety", "--output", "test_output_topic"], "Topic 模式")

# ── Test 2: TXT 文件模式 ──
with tempfile.NamedTemporaryFile(
    mode="w", suffix=".txt", prefix="smoke_test_", delete=False, encoding="utf-8"
) as f:
    f.write("This is a test document about artificial intelligence safety.\n")
    f.write("It covers topics such as alignment, robustness, and interpretability.\n")
    tmp_file = f.name

try:
    run_pipeline(
        ["--file", tmp_file, "--topic", "AI safety analysis", "--output", "test_output_file"],
        "TXT 文件模式",
    )
finally:
    os.unlink(tmp_file)


# ── Summary ──
print(f"\n{'='*50}")
if FAILED:
    print(f"{FAILED} smoke test(s) FAILED.")
    sys.exit(1)
else:
    print("All smoke tests PASSED.")
