"""项目质量检查脚本 — 编译检查 + 单元测试。

用法:
  python check_all.py              # 编译检查 + 测试
  python check_all.py --compile    # 仅编译检查
  python check_all.py --test       # 仅运行测试
"""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
MODULES = [
    "main.py", "main_api.py",
    "check_all.py", "smoke_test.py", "test_api_client.py",
]
TASK_FILES = sorted((PROJECT_ROOT / "tasks").glob("*.py"))
UTIL_FILES = sorted((PROJECT_ROOT / "utils").glob("*.py"))
CORE_FILES = sorted((PROJECT_ROOT / "core").glob("*.py"))


def run_compile_check():
    """编译检查所有 Python 源文件。"""
    all_files = (
        [str(PROJECT_ROOT / m) for m in MODULES]
        + [str(f) for f in TASK_FILES + UTIL_FILES + CORE_FILES]
    )
    failed = 0
    for filepath in all_files:
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
    else:
        print(f"All {len(all_files)} file(s) passed compilation.")
    return failed == 0


def run_tests():
    """运行单元测试套件。"""
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "tests", "-v"],
        capture_output=True, text=True,
        cwd=str(PROJECT_ROOT),
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode == 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="项目质量检查")
    parser.add_argument("--compile", action="store_true", help="仅编译检查")
    parser.add_argument("--test", action="store_true", help="仅运行测试")
    args = parser.parse_args()

    run_both = not args.compile and not args.test
    all_ok = True

    if run_both or args.compile:
        print("=" * 50)
        print(" 编译检查")
        print("=" * 50)
        if not run_compile_check():
            all_ok = False
        print()

    if run_both or args.test:
        print("=" * 50)
        print(" 单元测试")
        print("=" * 50)
        if not run_tests():
            all_ok = False

    if not all_ok:
        sys.exit(1)
