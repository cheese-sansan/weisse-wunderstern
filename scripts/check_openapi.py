"""Compare the FastAPI v1 OpenAPI document with the committed snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from noteforge.api import app

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "tests" / "snapshots" / "openapi_v1.json"


def canonical_document() -> str:
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    current = canonical_document()
    if args.update:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(current, encoding="utf-8")
        print(f"updated {SNAPSHOT}")
        return 0
    if not SNAPSHOT.exists():
        raise SystemExit(f"OpenAPI snapshot missing: {SNAPSHOT}")
    expected = SNAPSHOT.read_text(encoding="utf-8")
    if current != expected:
        raise SystemExit("OpenAPI snapshot changed; review compatibility and run: python scripts/check_openapi.py --update")
    print("OpenAPI v1 snapshot matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
