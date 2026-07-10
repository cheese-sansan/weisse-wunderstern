"""Evidence provenance, T5/T6, report, and resume regression tests."""

import os
import shutil
import unittest
from unittest.mock import patch

from core.pipeline import run_job
from tasks.t3_summary_generation import run as run_t3
from tasks.t4_report_framework import run as run_t4
from tasks.t5_technical_case_analysis import run as run_t5
from tasks.t6_policy_assessment import run as run_t6
from utils.context_manager import ContextStore
from utils.state_manager import StateManager


def simulated_t2():
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


def external_t2(with_policy=False):
    title = "AI Regulation 2026" if with_policy else "A Real Research Paper"
    abstract = "The AI policy was issued by Example Authority." if with_policy else "Evidence from a controlled study."
    return {
        "provider": "crossref", "query": "AI", "status": "ok",
        "retrieved_at": "2026-01-01T00:00:00+00:00", "warnings": [],
        "literature_results": [{
            "source_id": "L1", "title": title, "authors": ["Ada"], "year": 2026,
            "doi": "10.1000/example", "url": "https://doi.org/10.1000/example",
            "abstract": abstract, "source_provider": "crossref",
            "source_type": "external_api", "retrieved_at": "2026-01-01T00:00:00+00:00",
            "core_method": "", "datasets": [], "metrics": [],
            "key_findings": ["Evidence-backed finding"], "limitations": [],
        }],
    }


class TestEvidenceStages(unittest.TestCase):

    def test_t5_mock_is_structured_and_simulated(self):
        result = run_t5("transformer", simulated_t2())
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

    def test_t5_real_without_llm_does_not_fabricate(self):
        with patch("utils.llm_client.chat", return_value=None):
            result = run_t5("AI", external_t2())
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["cases"], [])

    def test_t6_requires_policy_evidence(self):
        result = run_t6("AI compliance", external_t2(with_policy=False))
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["policies"], [])
        self.assertIn("权威", result["warnings"][0])

    def test_t6_explicit_mock_is_labelled(self):
        result = run_t6("AI compliance", simulated_t2())
        self.assertEqual(result["policies"][0]["source_type"], "simulated")
        self.assertIn("Mock", result["warnings"][0])

    def test_t3_external_source_has_provenance_not_simulated_declaration(self):
        result = run_t3(external_t2())
        records = result["extractor_draft"]["claim_records"]
        self.assertEqual(records[0]["evidence_ids"], ["L1"])
        self.assertEqual(records[0]["source_type"], "llm_inference")
        self.assertIn("真实外部 API", result["final_report"])
        self.assertNotIn("全部文献为模拟数据", result["final_report"])

    def test_t3_extracts_literal_document_result_rows_without_llm(self):
        document = {
            "metadata": {"file_name": "evidence.md"},
            "markdown_text": (
                "## Methods\n- Controlled evaluation\n\n"
                "## Results\n| Model | Accuracy |\n| --- | --- |\n| A | 0.91 |"
            ),
            "raw_text": "",
        }
        result = run_t3({
            "provider": "crossref", "status": "ok", "warnings": [],
            "literature_results": [],
        }, document)
        draft = result["extractor_draft"]
        self.assertIn("文档结果：A；0.91", draft["claims"])
        self.assertEqual(draft["metrics"][0]["value"], "0.91")
        self.assertEqual(draft["claim_records"][0]["evidence_ids"], ["D1"])
        self.assertIn("原始文档 [D1]", result["final_report"])

    def test_final_report_renders_sources_cases_policies_and_mode(self):
        report = run_t4(
            "AI", {"final_report": "Evidence summary"},
            run_t5("AI", simulated_t2()), run_t6("AI", simulated_t2()),
            [{
                "source_id": "L1", "title": "Simulated", "doi": None, "url": None,
                "source_provider": "mock", "source_type": "simulated",
            }],
        )
        for section in ("学术提炼", "技术案例", "政策影响", "数据来源"):
            self.assertIn(section, report)
        self.assertIn("显式模拟模式", report)
        self.assertIn("[L1]", report)


class TestPipelineV02(unittest.TestCase):

    job_ids = ("evidence_mock_job", "evidence_degraded_job", "evidence_resume_job")

    def tearDown(self):
        for job_id in self.job_ids:
            path = os.path.join("outputs", "jobs", job_id)
            if os.path.exists(path):
                shutil.rmtree(path)

    def test_mock_pipeline_writes_canonical_and_legacy_reports(self):
        job_id = "evidence_mock_job"
        run_job(job_id, topic="transformer deployment", provider="mock")
        job_dir = os.path.join("outputs", "jobs", job_id)
        canonical = os.path.join(job_dir, "report.md")
        legacy = os.path.join(job_dir, "report_framework.md")
        self.assertTrue(os.path.exists(canonical))
        self.assertTrue(os.path.exists(legacy))
        with open(canonical, "r", encoding="utf-8") as handle:
            report = handle.read()
        with open(legacy, "r", encoding="utf-8") as handle:
            self.assertEqual(report, handle.read())
        self.assertIn("技术案例", report)
        self.assertIn("数据来源", report)
        self.assertEqual(ContextStore(job_id).load("T1")["source_type"], "unverified")
        self.assertEqual(StateManager(job_id).load_state()["status"], "COMPLETED")

    def test_provider_failure_completes_without_simulated_fallback(self):
        class FailingProvider:
            def search(self, _query):
                return {
                    "provider": "crossref", "query": "evidence", "status": "degraded",
                    "retrieved_at": "2026-01-01T00:00:00+00:00",
                    "warnings": ["Crossref offline"], "literature_results": [],
                }

        job_id = "evidence_degraded_job"
        with patch("tasks.t2_literature_search._get_provider", return_value=FailingProvider()):
            run_job(job_id, topic="bibliographic evidence", provider="crossref")
        t2_output = ContextStore(job_id).load("T2")
        self.assertEqual(t2_output["status"], "degraded")
        self.assertEqual(t2_output["literature_results"], [])
        with open(os.path.join("outputs", "jobs", job_id, "report.md"), "r", encoding="utf-8") as handle:
            report = handle.read()
        self.assertIn("Crossref offline", report)
        self.assertNotIn("Simulated finding", report)
        self.assertEqual(StateManager(job_id).load_state()["status"], "COMPLETED")

    def test_resume_loads_completed_context_before_rebuilding_report(self):
        job_id = "evidence_resume_job"
        run_job(job_id, topic="transformer resume", provider="mock")
        manager = StateManager(job_id)
        state = manager.load_state()
        state["status"] = "PROCESSING"
        for task in state["task_list"]:
            if task["task_id"] == "T4":
                task["status"] = "未开始"
        manager.save_state(state)
        os.remove(os.path.join("outputs", "jobs", job_id, "report.md"))

        with patch("core.pipeline.t1_run", side_effect=AssertionError("T1 reran")), \
             patch("core.pipeline.t2_run", side_effect=AssertionError("T2 reran")):
            run_job(job_id, topic="transformer resume", provider="mock")
        self.assertTrue(os.path.exists(os.path.join("outputs", "jobs", job_id, "report.md")))
        self.assertEqual(manager.load_state()["status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
