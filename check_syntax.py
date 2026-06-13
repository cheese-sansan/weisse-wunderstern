"""编译检查脚本 — 验证所有 Python 源文件可被正确解析。"""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
MODULES = [
    "main.py",
    "main_api.py",
    "check_syntax.py",
    "smoke_test.py",
    "test_api_client.py",
]

TASK_FILES = sorted((PROJECT_ROOT / "tasks").glob("*.py"))
UTIL_FILES = sorted((PROJECT_ROOT / "utils").glob("*.py"))
CORE_FILES = sorted((PROJECT_ROOT / "core").glob("*.py"))
ALL_FILES = [str(PROJECT_ROOT / m) for m in MODULES] + [str(f) for f in TASK_FILES + UTIL_FILES + CORE_FILES]

failed = 0
for filepath in ALL_FILES:
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", filepath],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"[FAIL] {filepath}")
        print(result.stderr)
        failed += 1
    else:
        print(f"[ OK ] {filepath}")

print(f"\n{'='*40}")
if failed:
    print(f"{failed} file(s) failed compilation.")
    sys.exit(1)
else:
    print(f"All {len(ALL_FILES)} file(s) passed compilation.")
