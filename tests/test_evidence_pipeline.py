"""Evidence provenance, optional stages, report, and resume regression tests."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noteforge import AnalysisRequest, JobStatus, run_job
from noteforge.models import LiteratureSearchResult, ProviderStatus, StageStatus
from noteforge.stages.policy import run as run_policy
from noteforge.stages.report import run as run_report
from noteforge.stages.synthesis import run as run_synthesis
from noteforge.stages.technical_cases import run as run_cases
from noteforge.storage.context import ContextStore
from noteforge.storage.state import StateManager


def simulated_literature():
    return {
        "provider": "mock", "query": "transformer", "status": "ok",
        "retrieved_at": "2026-01-01T00:00:00+00:00", "warnings": [],
        "literature_results": [{
            "source_id": "L1", "title": "Simulated Transformer Deployment",
            "authors": ["A"], "year": 2026, "doi": None, "url": None,
            "abstract": "", "source_provider": "mock", "source_type": "simulated",
            "retrieved_at": "2026-01-01T00:00:00+00:00",
            "core_method": "Transformer", "datasets": ["demo input"],
            "metrics": ["demo output"], "key_findings": ["simulated result"],
            "limitations": ["simulation"],
        }],
    }


def external_literature(with_policy=False):
    title = "AI Regulation 2026" if with_policy else "A Real Research Paper"
    abstract = "The AI policy was issued by Example Authority." if with_policy else "Controlled evidence."
    return {
        "provider": "crossref", "query": "AI", "status": "ok",
        "retrieved_at": "2026-01-01T00:00:00+00:00", "warnings": [],
        "literature_results": [{
            "source_id": "L1", "title": title, "authors": ["Ada"], "year": 2026,
            "doi": "10.1000/example", "url": "https://doi.org/10.1000/example",
            "abstract": abstract, "source_provider": "crossref", "source_type": "external_api",
            "retrieved_at": "2026-01-01T00:00:00+00:00", "core_method": "",
            "datasets": [], "metrics": [], "key_findings": ["Evidence-backed finding"], "limitations": [],
        }],
    }


class TestEvidenceStages(unittest.TestCase):
    def test_cases_mock_is_structured_and_simulated(self):
        result = run_cases("transformer", simulated_literature())
        self.assertEqual(result["status"], "ok")
        case = result["cases"][0]
        for field in (
            "case_name", "use_scenario", "technical_route", "inputs", "outputs",
            "implementation_conditions", "limitations", "evidence_ids",
            "source_type", "verification_status",
        ):
            self.assertIn(field, case)
        self.assertEqual(case["source_type"], "simulated")
        self.assertEqual(case["evidence_ids"], ["L1"])

    def test_cases_real_without_llm_does_not_fabricate(self):
        with patch("noteforge.llm.chat", return_value=None):
            result = run_cases("AI", external_literature())
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["cases"], [])

    def test_cases_real_llm_output_is_evidence_filtered(self):
        payload = {
            "cases": [{
                "case_name": "Supported case", "use_scenario": "Evaluation",
                "technical_route": "Controlled method", "inputs": ["dataset"],
                "outputs": ["metric"], "implementation_conditions": ["review"],
                "limitations": ["single source"], "evidence_ids": ["L1", "missing"],
            }],
        }
        with patch("noteforge.llm.chat", return_value=json.dumps(payload)):
            result = run_cases("AI", external_literature())
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["cases"][0]["evidence_ids"], ["L1"])
        self.assertEqual(result["cases"][0]["source_type"], "llm_inference")

    def test_policy_requires_policy_evidence(self):
        result = run_policy("AI compliance", external_literature(with_policy=False))
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["policies"], [])
        self.assertTrue(result["warnings"])

    def test_policy_explicit_mock_is_labelled(self):
        result = run_policy("AI compliance", simulated_literature())
        self.assertEqual(result["policies"][0]["source_type"], "simulated")
        self.assertTrue(result["warnings"])

    def test_policy_real_llm_output_is_evidence_filtered(self):
        payload = {
            "policies": [{
                "policy_name": "AI Regulation 2026", "issuing_body": "Example Authority",
                "effective_date": "2026", "scope": "AI", "affected_parties": ["developers"],
                "compliance_requirements": ["document controls"], "risk_level": "high",
                "evidence_ids": ["L1", "missing"],
            }],
        }
        with patch("noteforge.llm.chat", return_value=json.dumps(payload)):
            result = run_policy("AI compliance", external_literature(with_policy=True))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["policies"][0]["evidence_ids"], ["L1"])
        self.assertEqual(result["policies"][0]["verification_status"], "supported")

    def test_synthesis_external_source_has_provenance(self):
        result = run_synthesis(external_literature())
        records = result["extractor_draft"]["claim_records"]
        self.assertEqual(records[0]["evidence_ids"], ["L1"])
        self.assertEqual(records[0]["source_type"], "llm_inference")

    def test_synthesis_extracts_literal_document_result_rows_without_llm(self):
        document = {
            "metadata": {"file_name": "evidence.md"},
            "markdown_text": "## Results\n| Model | Accuracy |\n| --- | --- |\n| A | 0.91 |",
            "raw_text": "",
        }
        result = run_synthesis({
            "provider": "crossref", "status": "ok", "warnings": [], "literature_results": [],
        }, document)
        draft = result["extractor_draft"]
        self.assertEqual(draft["metrics"][0]["value"], "0.91")
        self.assertEqual(draft["claim_records"][0]["evidence_ids"], ["D1"])

    def test_final_report_renders_sources_cases_and_policies(self):
        report = run_report(
            "AI", {"final_report": "Evidence summary"},
            run_cases("AI", simulated_literature()), run_policy("AI", simulated_literature()),
            [{"source_id": "L1", "title": "Simulated", "doi": None, "url": None,
              "source_provider": "mock", "source_type": "simulated"}],
        )
        self.assertIn("[L1]", report)
        self.assertIn("Evidence summary", report)


class TestPipelineV03(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_mock_pipeline_writes_only_canonical_report(self):
        result = run_job(
            AnalysisRequest(topic="transformer deployment", provider="mock", job_id="evidence_mock_job"),
            output_root=self.root,
        )
        job_dir = self.root / "jobs" / result.job_id
        self.assertTrue((job_dir / "report.md").exists())
        self.assertFalse((job_dir / "report_framework.md").exists())
        self.assertIs(result.status, JobStatus.COMPLETED)
        self.assertEqual(ContextStore(result.job_id, self.root).load("keywords")["source_type"], "unverified")

    def test_provider_failure_completes_without_simulated_fallback(self):
        degraded = LiteratureSearchResult(
            provider="crossref", query="evidence", status=ProviderStatus.DEGRADED,
            retrieved_at="2026-01-01T00:00:00+00:00",
            warnings=["Crossref offline"], literature_results=[],
        )
        with patch("noteforge.pipeline.search_literature", return_value=degraded):
            result = run_job(
                AnalysisRequest(topic="bibliographic evidence", provider="crossref", job_id="degraded_job"),
                output_root=self.root,
            )
        self.assertIs(result.status, JobStatus.COMPLETED)
        self.assertIn("Crossref offline", result.warnings)
        self.assertNotIn("Simulated finding", result.report_path.read_text(encoding="utf-8"))

    def test_resume_loads_completed_context_before_rebuilding_report(self):
        request = AnalysisRequest(topic="transformer resume", provider="mock", job_id="resume_job")
        run_job(request, output_root=self.root)
        manager = StateManager("resume_job", self.root)
        state = manager.load_state()
        state.status = JobStatus.RUNNING
        stage = state.stages["report_generation"]
        stage.status = StageStatus.FAILED
        manager.save_state(state)
        (manager.job_dir / "report.md").unlink()

        with patch("noteforge.pipeline.extract_keywords", side_effect=AssertionError("keywords reran")), \
             patch("noteforge.pipeline.search_literature", side_effect=AssertionError("provider reran")):
            result = run_job(AnalysisRequest(job_id="resume_job"), output_root=self.root)
        self.assertTrue(result.report_path.exists())
        self.assertIs(manager.load_state().status, JobStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
