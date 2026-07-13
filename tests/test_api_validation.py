"""FastAPI v1 validation, compatibility, and safety tests."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

import noteforge.api as api
from noteforge import AnalysisRequest, run_job


class TestApiHelpers(unittest.TestCase):
    def test_sanitize_filename_strips_posix_and_windows_paths(self):
        self.assertEqual(api._sanitize_filename("../../paper.md"), "paper.md")
        self.assertEqual(api._sanitize_filename(r"C:\tmp\paper.md"), "paper.md")
        self.assertEqual(api._sanitize_filename("my paper (final).md"), "my_paper_final_.md")

    def test_validate_api_job_id_rejects_unsafe_ids(self):
        for bad_id in ("..", "bad.job", "bad job", "-bad"):
            with self.subTest(job_id=bad_id), self.assertRaises(HTTPException):
                api._validate_api_job_id(bad_id)


class TestApiValidation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [
            patch.object(api, "OUTPUT_ROOT", self.root),
            patch.object(api, "JOBS_OUTPUT_DIR", self.root / "jobs"),
        ]
        for item in self.patches:
            item.start()
        self.client = TestClient(api.create_app())

    def tearDown(self):
        self.client.close()
        api.API_TOKEN = ""
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_invalid_job_id_returns_400(self):
        self.assertEqual(self.client.get("/api/v1/jobs/status/bad.job").status_code, 400)

    def test_missing_job_returns_404_for_valid_id(self):
        self.assertEqual(self.client.get("/api/v1/jobs/status/not_found_job").status_code, 404)

    def test_result_invalid_job_id_returns_400(self):
        self.assertEqual(self.client.get("/api/v1/jobs/result/bad%20job").status_code, 400)

    def test_unsupported_upload_extension_rejected(self):
        response = self.client.post(
            "/api/v1/jobs/submit", data={"topic": "AI safety"},
            files={"file": ("payload.exe", b"not allowed", "application/octet-stream")},
        )
        self.assertEqual(response.status_code, 400)

    def test_empty_submit_rejected(self):
        self.assertEqual(self.client.post("/api/v1/jobs/submit", data={"topic": ""}).status_code, 400)

    def test_unknown_provider_rejected(self):
        response = self.client.post(
            "/api/v1/jobs/submit", data={"topic": "AI safety", "provider": "unknown"},
        )
        self.assertEqual(response.status_code, 400)

    def test_token_auth_blocks_missing_token(self):
        api.API_TOKEN = "tok"
        self.assertEqual(self.client.get("/api/v1/jobs/status/not_found_job").status_code, 401)

    def test_token_auth_allows_valid_token(self):
        api.API_TOKEN = "tok"
        response = self.client.get(
            "/api/v1/jobs/status/not_found_job", headers={"Authorization": "Bearer tok"},
        )
        self.assertEqual(response.status_code, 404)

    def test_health_is_compatible(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})

    def test_submit_response_keeps_v1_fields(self):
        with patch.object(api, "_run_background", return_value=None):
            response = self.client.post(
                "/api/v1/jobs/submit", data={"topic": "AI safety", "provider": "mock"},
            )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(set(response.json()), {"job_id", "status", "provider"})

    def test_status_and_result_keep_v1_response_fields(self):
        run_job(
            AnalysisRequest(topic="transformer API", provider="mock", job_id="api_result_job"),
            output_root=self.root,
        )
        status = self.client.get("/api/v1/jobs/status/api_result_job")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(set(status.json()), {
            "job_id", "status", "current_task", "created_at", "updated_at",
            "error", "error_code", "task_list",
        })
        result = self.client.get("/api/v1/jobs/result/api_result_job")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(set(result.json()), {
            "job_id", "status", "report", "context_summary", "provider_status",
            "sources", "tech_cases", "policy_assessment", "warnings",
        })


if __name__ == "__main__":
    unittest.main()
