"""Installed-command-style smoke test for a local checkout."""

from __future__ import annotations

import tempfile
from pathlib import Path

from noteforge.cli import main


def smoke() -> int:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        if main([
            "run", "--topic", "transformer smoke", "--provider", "mock",
            "--job-id", "smoke_job", "--output-root", str(root),
        ]):
            return 1
        if main(["jobs", "list", "--output-root", str(root)]):
            return 1
        if main(["report", "smoke_job", "--output-root", str(root)]):
            return 1
    print("CLI smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(smoke())
