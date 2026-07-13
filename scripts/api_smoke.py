"""Dependency-light FastAPI v1 smoke test used by CI."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import noteforge.api as api


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        output_root = Path(directory)
        with patch.object(api, "OUTPUT_ROOT", output_root), \
             patch.object(api, "JOBS_OUTPUT_DIR", output_root / "jobs"), \
             patch.object(api, "_run_background", return_value=None), \
             TestClient(api.create_app()) as client:
            health = client.get("/health")
            submit = client.post(
                "/api/v1/jobs/submit",
                data={"topic": "API smoke", "provider": "mock"},
            )
            if health.status_code != 200 or health.json() != {"status": "ok"}:
                raise RuntimeError(f"health smoke failed: {health.status_code} {health.text}")
            if submit.status_code != 202 or set(submit.json()) != {"job_id", "status", "provider"}:
                raise RuntimeError(f"submit smoke failed: {submit.status_code} {submit.text}")
    print("API smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
