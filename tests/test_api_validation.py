"""FastAPI validation and safety tests."""
import unittest

try:
    import main_api
except SystemExit:  # main_api exits when FastAPI dependencies are missing.
    main_api = None
except ImportError:
    main_api = None

try:
    from fastapi.testclient import TestClient
except (ImportError, RuntimeError):
    TestClient = None


@unittest.skipIf(main_api is None, "FastAPI runtime dependencies are not installed")
class TestApiHelpers(unittest.TestCase):

    def test_sanitize_filename_strips_posix_and_windows_paths(self):
        self.assertEqual(main_api._sanitize_filename("../../paper.md"), "paper.md")
        self.assertEqual(main_api._sanitize_filename(r"C:\tmp\paper.md"), "paper.md")
        self.assertEqual(main_api._sanitize_filename("my paper (final).md"), "my_paper_final_.md")

    def test_validate_api_job_id_rejects_unsafe_ids(self):
        for bad_id in ("..", "bad.job", "bad job", "-bad"):
            with self.subTest(job_id=bad_id):
                with self.assertRaises(main_api.HTTPException):
                    main_api._validate_api_job_id(bad_id)


@unittest.skipIf(
    main_api is None or TestClient is None,
    "FastAPI TestClient dependencies are not installed",
)
class TestApiValidation(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(main_api.app)

    def tearDown(self):
        main_api.API_TOKEN = ""

    def test_invalid_job_id_returns_400(self):
        res = self.client.get("/api/v1/jobs/status/bad.job")
        self.assertEqual(res.status_code, 400)

    def test_missing_job_returns_404_for_valid_id(self):
        res = self.client.get("/api/v1/jobs/status/not_found_job")
        self.assertEqual(res.status_code, 404)

    def test_result_invalid_job_id_returns_400(self):
        res = self.client.get("/api/v1/jobs/result/bad%20job")
        self.assertEqual(res.status_code, 400)

    def test_unsupported_upload_extension_rejected(self):
        res = self.client.post(
            "/api/v1/jobs/submit",
            data={"topic": "AI safety"},
            files={"file": ("payload.exe", b"not allowed", "application/octet-stream")},
        )
        self.assertEqual(res.status_code, 400)

    def test_empty_submit_rejected(self):
        res = self.client.post("/api/v1/jobs/submit", data={"topic": ""})
        self.assertEqual(res.status_code, 400)

    def test_token_auth_blocks_missing_token(self):
        main_api.API_TOKEN = "tok"
        res = self.client.get("/api/v1/jobs/status/not_found_job")
        self.assertEqual(res.status_code, 401)

    def test_token_auth_allows_valid_token(self):
        main_api.API_TOKEN = "tok"
        res = self.client.get(
            "/api/v1/jobs/status/not_found_job",
            headers={"Authorization": "Bearer tok"},
        )
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
