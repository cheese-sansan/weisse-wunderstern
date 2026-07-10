"""
NoteForge — zero-dependency TUI.

This is an intentionally small text UI built with the Python standard library.
It is meant for local use and smoke testing, not as a full-screen terminal app.
"""

import argparse
import json
import os
import sys
from datetime import datetime

from utils.env_loader import load_env
from utils.state_manager import StateManager, validate_job_id
from core.pipeline import run_job, PipelineError
from tasks.t2_literature_search import DEFAULT_PROVIDER, PROVIDER_NAMES


JOBS_DIR = os.path.join("outputs", "jobs")


def _configure_stdio():
    """Make report output robust on Windows consoles with legacy encodings."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _default_job_id(prefix: str = "tui") -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _prompt(label: str, default: str = "", input_func=input) -> str:
    suffix = f" [{default}]" if default else ""
    value = input_func(f"{label}{suffix}: ").strip()
    return value or default


def _print_header(print_func=print):
    print_func("=" * 58)
    print_func(" NoteForge TUI")
    print_func(" Lightweight document distillation and report analysis")
    print_func("=" * 58)


def _print_menu(print_func=print):
    print_func("")
    print_func("1. Analyze by topic")
    print_func("2. Analyze by file")
    print_func("3. List jobs")
    print_func("4. View report")
    print_func("5. API service help")
    print_func("0. Exit")


def list_jobs(limit: int = 20):
    """Return latest job summaries from outputs/jobs."""
    if not os.path.isdir(JOBS_DIR):
        return []

    jobs = []
    for job_id in os.listdir(JOBS_DIR):
        job_dir = os.path.join(JOBS_DIR, job_id)
        state_file = os.path.join(job_dir, "task_state.json")
        if not os.path.isfile(state_file):
            continue
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            jobs.append({
                "job_id": state.get("job_id", job_id),
                "status": state.get("status", "UNKNOWN"),
                "current_task": state.get("current_task"),
                "updated_at": state.get("updated_at", ""),
            })
        except Exception:
            jobs.append({
                "job_id": job_id,
                "status": "UNREADABLE",
                "current_task": None,
                "updated_at": "",
            })

    jobs.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return jobs[:limit]


def print_jobs(print_func=print):
    jobs = list_jobs()
    if not jobs:
        print_func("No jobs found.")
        return
    print_func("")
    print_func("Recent jobs:")
    for item in jobs:
        current = item.get("current_task") or "-"
        print_func(f"- {item['job_id']} | {item['status']} | current={current} | updated={item['updated_at']}")


def read_report(job_id: str) -> str:
    job_id = validate_job_id(job_id)
    report_path = os.path.join(JOBS_DIR, job_id, "report.md")
    if not os.path.exists(report_path):
        report_path = os.path.join(JOBS_DIR, job_id, "report_framework.md")
    if not os.path.exists(report_path):
        return ""
    with open(report_path, "r", encoding="utf-8") as f:
        return f.read()


def print_report(job_id: str, max_chars: int = 4000, print_func=print):
    try:
        report = read_report(job_id)
    except ValueError as e:
        print_func(f"Invalid job_id: {e}")
        return
    if not report:
        print_func(f"No report found for job: {job_id}")
        return
    print_func("")
    print_func(f"Report: {job_id}")
    print_func("-" * 58)
    if len(report) > max_chars:
        print_func(report[:max_chars])
        print_func(f"\n... truncated ({len(report)} chars total)")
    else:
        print_func(report)


def _run_analysis(topic: str = "", file_path: str = None, job_id: str = "",
                  provider: str | None = None, print_func=print) -> bool:
    try:
        job_id = validate_job_id(job_id or _default_job_id())
    except ValueError as e:
        print_func(f"Invalid job_id: {e}")
        return False

    if file_path and not os.path.exists(file_path):
        print_func(f"File not found: {file_path}")
        return False

    try:
        run_job(job_id, topic=topic, file_path=file_path, provider=provider)
        print_func("")
        print_func(f"Done. job_id={job_id}")
        print_func(f"Report: {os.path.join(JOBS_DIR, job_id, 'report.md')}")
        return True
    except PipelineError as e:
        print_func(f"Pipeline error: {e}")
    except Exception as e:
        print_func(f"Fatal error: {type(e).__name__}: {e}")
    return False


def run_tui(input_func=input, print_func=print):
    """Run the interactive text UI."""
    load_env()
    _print_header(print_func)
    while True:
        _print_menu(print_func)
        choice = _prompt("Choose", input_func=input_func)
        if choice == "0":
            print_func("Bye.")
            return 0
        if choice == "1":
            topic = _prompt("Topic", input_func=input_func)
            job_id = _prompt("Job ID", _default_job_id("topic"), input_func=input_func)
            provider = _prompt(
                "Provider (crossref/mock/llm-simulated)",
                os.environ.get("LITERATURE_PROVIDER", DEFAULT_PROVIDER),
                input_func=input_func,
            )
            if not topic:
                print_func("Topic is required.")
                continue
            _run_analysis(topic=topic, job_id=job_id, provider=provider, print_func=print_func)
        elif choice == "2":
            file_path = _prompt("File path", input_func=input_func)
            topic = _prompt("Optional topic", input_func=input_func)
            job_id = _prompt("Job ID", _default_job_id("file"), input_func=input_func)
            provider = _prompt(
                "Provider (crossref/mock/llm-simulated)",
                os.environ.get("LITERATURE_PROVIDER", DEFAULT_PROVIDER),
                input_func=input_func,
            )
            if not file_path:
                print_func("File path is required.")
                continue
            _run_analysis(
                topic=topic, file_path=file_path, job_id=job_id,
                provider=provider, print_func=print_func,
            )
        elif choice == "3":
            print_jobs(print_func)
        elif choice == "4":
            job_id = _prompt("Job ID", input_func=input_func)
            print_report(job_id, print_func=print_func)
        elif choice == "5":
            print_func("")
            print_func("Start API service:")
            print_func("  pip install -r requirements-api.txt")
            print_func("  python main_api.py")
            print_func("")
            print_func("Endpoints:")
            print_func("  POST /api/v1/jobs/submit")
            print_func("  GET  /api/v1/jobs/status/{job_id}")
            print_func("  GET  /api/v1/jobs/result/{job_id}")
        else:
            print_func("Unknown choice.")


def main(argv=None):
    _configure_stdio()
    parser = argparse.ArgumentParser(description="NoteForge TUI")
    parser.add_argument("--topic", default="", help="Run one topic analysis and exit")
    parser.add_argument("--file", default=None, help="Run one file analysis and exit")
    parser.add_argument("--job-id", default="", help="Job id for one-shot analysis")
    parser.add_argument("--provider", choices=PROVIDER_NAMES, default=None, help="Literature provider")
    parser.add_argument("--list", action="store_true", help="List recent jobs and exit")
    parser.add_argument("--report", default="", help="Print report for a job and exit")
    args = parser.parse_args(argv)

    if args.list:
        print_jobs()
        return 0
    if args.report:
        print_report(args.report)
        return 0
    if args.topic or args.file:
        ok = _run_analysis(
            topic=args.topic, file_path=args.file, job_id=args.job_id,
            provider=args.provider,
        )
        return 0 if ok else 1
    return run_tui()


if __name__ == "__main__":
    sys.exit(main())
