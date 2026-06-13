"""Privacy and secret audit for publishable repository files.

The scanner is intentionally conservative and dependency-free. It is meant to
catch high-confidence leaks before committing or publishing the repository.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "env",
    "htmlcov",
    "outputs",
    "venv",
}

TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".csv",
    ".dockerignore",
    ".env",
    ".example",
    ".gitignore",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".rst",
    ".sh",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

PATTERNS = [
    (
        "openai_or_deepseek_key",
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        "OpenAI/DeepSeek-style API key",
    ),
    (
        "aws_access_key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "AWS access key",
    ),
    (
        "google_api_key",
        re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
        "Google API key",
    ),
    (
        "assigned_secret",
        re.compile(
            r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*"
            r"[\"']?(?!$|\$\{|<|your_|example|placeholder|tok\b|os\.environ|os\.getenv)"
            r"[A-Za-z0-9_./+=:@-]{12,}"
        ),
        "assigned secret-like value",
    ),
    (
        "private_windows_path",
        re.compile(r"\b[A-Za-z]:\\(?:Users|AI_Projects|Documents and Settings)\\[^\s`\"']+"),
        "private Windows absolute path",
    ),
    (
        "mainland_phone_like_number",
        re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
        "mainland China phone-like number",
    ),
]


def is_text_file(path: Path) -> bool:
    if path.name in {".env", ".env.example", "Dockerfile"}:
        return True
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    return False


def iter_files(root: Path, include_outputs: bool):
    excluded = set(DEFAULT_EXCLUDED_DIRS)
    if include_outputs:
        excluded.discard("outputs")

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = [name for name in dirnames if name not in excluded]
        for filename in filenames:
            path = current / filename
            if is_text_file(path):
                yield path


def redact(line: str) -> str:
    redacted = line.rstrip("\n")
    for _, pattern, _ in PATTERNS:
        redacted = pattern.sub("<REDACTED>", redacted)
    if len(redacted) > 220:
        redacted = redacted[:217] + "..."
    return redacted


def audit(root: Path, include_outputs: bool = False) -> list[tuple[Path, int, str, str]]:
    findings = []
    for path in iter_files(root, include_outputs=include_outputs):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for line_no, line in enumerate(text.splitlines(), 1):
            for rule_id, pattern, description in PATTERNS:
                if pattern.search(line):
                    findings.append((path, line_no, rule_id, description))
    return findings


def audit_git_history(root: Path) -> list[tuple[str, str, int, str]]:
    """Scan reachable Git history without printing matched secret text."""
    try:
        commits = subprocess.check_output(
            ["git", "rev-list", "--all"],
            cwd=str(root),
            text=True,
            stderr=subprocess.DEVNULL,
        ).splitlines()
    except Exception:
        return []

    findings: list[tuple[str, str, int, str]] = []
    for commit in commits:
        try:
            files = subprocess.check_output(
                ["git", "ls-tree", "-r", "--name-only", commit],
                cwd=str(root),
                text=True,
                stderr=subprocess.DEVNULL,
                errors="replace",
            ).splitlines()
        except subprocess.CalledProcessError:
            continue

        for filename in files:
            try:
                blob = subprocess.check_output(
                    ["git", "show", f"{commit}:{filename}"],
                    cwd=str(root),
                    stderr=subprocess.DEVNULL,
                )
            except subprocess.CalledProcessError:
                continue
            if b"\0" in blob:
                continue
            text = blob.decode("utf-8", errors="replace")
            for line_no, line in enumerate(text.splitlines(), 1):
                for rule_id, pattern, _ in PATTERNS:
                    if pattern.search(line):
                        findings.append((commit[:12], filename, line_no, rule_id))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit repository files for private data and secrets.")
    parser.add_argument("--root", default=".", help="Repository root to scan")
    parser.add_argument(
        "--include-outputs",
        action="store_true",
        help="Also scan generated outputs/ artifacts",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Also scan reachable Git history without printing matched text",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    findings = audit(root, include_outputs=args.include_outputs)
    history_findings = audit_git_history(root) if args.history else []
    if not findings:
        print("Privacy audit passed: no high-confidence leaks found in current files.")
    else:
        print(f"Privacy audit failed: {len(findings)} current-file finding(s).")
        for path, line_no, rule_id, description in findings:
            rel = path.relative_to(root)
            try:
                line = path.read_text(encoding="utf-8", errors="replace").splitlines()[line_no - 1]
            except Exception:
                line = ""
            print(f"- {rel}:{line_no} [{rule_id}] {description}: {redact(line)}")

    if args.history:
        if not history_findings:
            print("Git history privacy audit passed: no high-confidence leaks found.")
        else:
            print(f"Git history privacy audit failed: {len(history_findings)} finding(s).")
            for commit, filename, line_no, rule_id in history_findings[:100]:
                print(f"- {commit} {filename}:{line_no} [{rule_id}]")

    return 1 if findings or history_findings else 0


if __name__ == "__main__":
    sys.exit(main())
