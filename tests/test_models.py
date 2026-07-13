"""Stable SDK dataclass and structured-error tests."""

import json
import unittest
from pathlib import Path

from noteforge import AnalysisRequest, JobResult
from noteforge.errors import ErrorCode, NoteForgeError
from noteforge.models import (
    JobStatus,
    LiteratureQuery,
    LiteratureRecord,
    LiteratureSearchResult,
    ProviderStatus,
    SourceType,
    TechnicalCase,
)


class TestModels(unittest.TestCase):
    def test_analysis_request_round_trip(self):
        request = AnalysisRequest(topic=" AI ", file_path=Path("paper.md"), provider="mock", job_id="job_1")
        restored = AnalysisRequest.from_json(request.to_json())
        self.assertEqual(restored, AnalysisRequest(topic="AI", file_path=Path("paper.md"), provider="mock", job_id="job_1"))

    def test_analysis_request_allows_resume_by_job_id(self):
        self.assertEqual(AnalysisRequest(job_id="resume_job").job_id, "resume_job")

    def test_analysis_request_rejects_empty_new_request(self):
        with self.assertRaises(ValueError):
            AnalysisRequest()

    def test_invalid_provider_enum_rejected(self):
        with self.assertRaises(ValueError):
            AnalysisRequest(topic="AI", provider="unknown")

    def test_incoming_schema_version_is_validated(self):
        with self.assertRaises(ValueError):
            AnalysisRequest.from_dict({"topic": "AI", "schema_version": 2})

    def test_literature_result_recursive_round_trip(self):
        result = LiteratureSearchResult(
            provider="crossref", query="AI", status=ProviderStatus.OK,
            retrieved_at="2026-01-01T00:00:00+00:00",
            literature_results=[LiteratureRecord(
                source_id="L1", title="Paper", source_provider="crossref",
                source_type=SourceType.EXTERNAL_API, authors=["Ada"], year=2026,
            )],
        )
        restored = LiteratureSearchResult.from_json(result.to_json())
        self.assertEqual(restored, result)
        self.assertIs(restored.literature_results[0].source_type, SourceType.EXTERNAL_API)

    def test_job_result_path_and_nested_models_round_trip(self):
        result = JobResult(
            job_id="job", status=JobStatus.COMPLETED, report_path=Path("report.md"),
            tech_cases=[TechnicalCase(case_name="Case", source_type=SourceType.SIMULATED)],
        )
        restored = JobResult.from_dict(result.to_dict())
        self.assertEqual(restored, result)
        self.assertIsInstance(restored.report_path, Path)

    def test_literature_query_defaults_are_isolated(self):
        first, second = LiteratureQuery(), LiteratureQuery()
        first.keywords.append("AI")
        self.assertEqual(second.keywords, [])

    def test_json_is_utf8_friendly(self):
        payload = AnalysisRequest(topic="人工智能").to_json()
        self.assertIn("人工智能", payload)
        self.assertEqual(json.loads(payload)["topic"], "人工智能")

    def test_structured_error_contract(self):
        error = NoteForgeError(
            ErrorCode.PROVIDER_UNAVAILABLE, "offline", retryable=True, details={"provider": "crossref"},
        )
        self.assertEqual(error.to_dict(), {
            "code": "PROVIDER_UNAVAILABLE", "message": "offline", "retryable": True,
            "details": {"provider": "crossref"},
        })

    def test_all_required_error_domains_exist(self):
        self.assertTrue({
            "INPUT_INVALID", "PARSE_FAILED", "PROVIDER_UNAVAILABLE", "PROVIDER_RESPONSE_INVALID",
            "ANALYSIS_FAILED", "STORAGE_FAILED", "MIGRATION_FAILED", "INTERNAL_ERROR",
        }.issubset({item.value for item in ErrorCode}))


if __name__ == "__main__":
    unittest.main()
