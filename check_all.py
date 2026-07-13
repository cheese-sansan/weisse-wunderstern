"""Convenience wrapper for the v0.3 quality checks."""

from __future__ import annotations

import compileall
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> int:
    if not compileall.compile_dir(ROOT / "src", quiet=1):
        return 1
    commands = (
        [sys.executable, "-m", "pytest", "-q"],
        [sys.executable, str(ROOT / "scripts" / "check_openapi.py")],
        [sys.executable, str(ROOT / "scripts" / "privacy_audit.py")],
    )
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
