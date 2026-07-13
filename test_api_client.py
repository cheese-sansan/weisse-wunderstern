"""Backward-friendly launcher for the v0.3 API smoke test."""

from scripts.api_smoke import main


if __name__ == "__main__":
    raise SystemExit(main())
