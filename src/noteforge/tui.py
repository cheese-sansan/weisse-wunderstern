"""Small interactive text UI backed by the installed SDK."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from noteforge.models import AnalysisRequest, ProviderName
from noteforge.pipeline import run_job
from noteforge.storage.state import StateManager, validate_job_id
from noteforge.version import __version__


def run_tui(input_func=input, print_func=print, output_root: Path = Path("outputs")) -> int:
    print_func(f"NoteForge TUI {__version__}")
    while True:
        print_func("\n1. Analyze topic\n2. Analyze file\n3. List jobs\n4. View report\n0. Exit")
        choice = input_func("Choose: ").strip()
        if choice == "0":
            return 0
        if choice in ("1", "2"):
            topic = input_func("Topic (optional for file): ").strip()
            file_path = Path(input_func("File path: ").strip()) if choice == "2" else None
            provider_text = input_func("Provider [crossref]: ").strip() or "crossref"
            job_id = input_func("Job ID [auto]: ").strip() or None
            result = run_job(
                AnalysisRequest(
                    topic=topic, file_path=file_path,
                    provider=ProviderName(provider_text), job_id=job_id,
                ),
                output_root=output_root,
            )
            print_func(f"Done: {result.job_id}\nReport: {result.report_path}")
        elif choice == "3":
            _print_jobs(output_root, print_func)
        elif choice == "4":
            job_id = validate_job_id(input_func("Job ID: ").strip())
            StateManager(job_id, output_root).load_state()
            report = output_root / "jobs" / job_id / "report.md"
            print_func(report.read_text(encoding="utf-8") if report.exists() else "Report not found")
        else:
            print_func("Unknown choice")


def _print_jobs(output_root: Path, print_func=print):
    jobs_root = output_root / "jobs"
    if not jobs_root.exists():
        print_func("No jobs found")
        return
    for job_dir in sorted(jobs_root.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True)[:20]:
        if job_dir.is_dir():
            state = StateManager(job_dir.name, output_root).load_state()
            print_func(f"{state.job_id} | {state.status.value} | {state.current_stage or '-'}")


def default_job_id() -> str:
    return f"tui-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
