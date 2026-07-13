"""Unified ``noteforge`` command line interface."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from noteforge.config import load_env
from noteforge.errors import NoteForgeError
from noteforge.models import AnalysisRequest, ProviderName
from noteforge.pipeline import run_job
from noteforge.storage.migration import migrate_all
from noteforge.storage.state import StateManager, validate_job_id
from noteforge.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="noteforge", description="Evidence-aware research report pipeline")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command", required=True)

    run_parser = subcommands.add_parser("run", help="Run or resume an analysis job")
    run_parser.add_argument("--topic", "-t", default="")
    run_parser.add_argument("--file", "-f", type=Path)
    run_parser.add_argument("--provider", choices=[item.value for item in ProviderName])
    run_parser.add_argument("--job-id")
    run_parser.add_argument("--output-root", type=Path, default=Path("outputs"))

    subcommands.add_parser("tui", help="Start the interactive text UI")

    api_parser = subcommands.add_parser("api", help="Start the FastAPI service")
    api_parser.add_argument("--host", default="0.0.0.0")
    api_parser.add_argument("--port", type=int, default=int(os.environ.get("API_PORT", "8000")))

    jobs_parser = subcommands.add_parser("jobs", help="List or migrate persisted jobs")
    jobs_actions = jobs_parser.add_subparsers(dest="jobs_action", required=True)
    jobs_list = jobs_actions.add_parser("list")
    jobs_list.add_argument("--limit", type=int, default=20)
    jobs_list.add_argument("--output-root", type=Path, default=Path("outputs"))
    jobs_migrate = jobs_actions.add_parser("migrate")
    jobs_migrate.add_argument("--all", action="store_true", required=True)
    jobs_migrate.add_argument("--output-root", type=Path, default=Path("outputs"))

    report_parser = subcommands.add_parser("report", help="Print a completed job report")
    report_parser.add_argument("job_id")
    report_parser.add_argument("--output-root", type=Path, default=Path("outputs"))
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    load_env()
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            provider = ProviderName(args.provider) if args.provider else None
            result = run_job(
                AnalysisRequest(
                    topic=args.topic, file_path=args.file, provider=provider, job_id=args.job_id,
                ),
                output_root=args.output_root,
            )
            print(f"job_id={result.job_id}")
            print(f"status={result.status.value}")
            print(f"report={result.report_path}")
            return 0
        if args.command == "tui":
            from noteforge.tui import run_tui

            return run_tui()
        if args.command == "api":
            from noteforge.api import serve

            serve(args.host, args.port)
            return 0
        if args.command == "jobs" and args.jobs_action == "list":
            return _list_jobs(args.output_root, args.limit)
        if args.command == "jobs" and args.jobs_action == "migrate":
            migrated, errors = migrate_all(args.output_root)
            print(f"migrated={migrated}")
            for error in errors:
                print(f"error={error}", file=sys.stderr)
            return 1 if errors else 0
        if args.command == "report":
            return _print_report(args.job_id, args.output_root)
    except (NoteForgeError, ValueError, FileNotFoundError) as error:
        code = error.code.value if isinstance(error, NoteForgeError) else "INPUT_INVALID"
        print(f"{code}: {error}", file=sys.stderr)
        return 1
    return 2


def _configure_stdio():
    """Make generated Unicode reports printable on legacy Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        try:
            reconfigure = getattr(stream, "reconfigure", None)
            if callable(reconfigure):
                reconfigure(encoding="utf-8", errors="replace")
        except OSError:
            pass


def _list_jobs(output_root: Path, limit: int) -> int:
    jobs_root = output_root / "jobs"
    if not jobs_root.exists():
        return 0
    summaries = []
    for job_dir in jobs_root.iterdir():
        if not job_dir.is_dir():
            continue
        try:
            state = StateManager(job_dir.name, output_root).load_state()
            summaries.append((state.updated_at, state.job_id, state.status.value, state.current_stage or "-"))
        except Exception as error:
            summaries.append(("", job_dir.name, "UNREADABLE", str(error)))
    for _, job_id, status, stage in sorted(summaries, reverse=True)[:limit]:
        print(f"{job_id}\t{status}\t{stage}")
    return 0


def _print_report(job_id: str, output_root: Path) -> int:
    job_id = validate_job_id(job_id)
    StateManager(job_id, output_root).load_state()
    report = output_root / "jobs" / job_id / "report.md"
    if not report.exists():
        raise FileNotFoundError(f"report not found for job {job_id}")
    print(report.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
