"""Regression tests for semantic dynamic-stage routing."""

import tempfile
import unittest
from pathlib import Path

from noteforge import AnalysisRequest, run_job
from noteforge.models import StageStatus
from noteforge.storage.state import StateManager


class TestProjectRequirementsAlignment(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _run_and_stages(self, job_id, topic):
        run_job(AnalysisRequest(topic=topic, provider="mock", job_id=job_id), output_root=self.root)
        return StateManager(job_id, self.root).load_state().stages

    def test_ai_industry_topic_triggers_technical_and_policy(self):
        stages = self._run_and_stages("align_ai_trend", "2025 Q3 AI industry policy transformer trends")
        self.assertIs(stages["technical_cases"].status, StageStatus.COMPLETED)
        self.assertIs(stages["policy_assessment"].status, StageStatus.COMPLETED)

    def test_plain_research_topic_skips_optional_stages(self):
        stages = self._run_and_stages("align_plain", "bibliographic evidence review")
        self.assertIs(stages["technical_cases"].status, StageStatus.SKIPPED)
        self.assertIs(stages["policy_assessment"].status, StageStatus.SKIPPED)

    def test_llm_deployment_topic_triggers_technical_stage(self):
        stages = self._run_and_stages("align_llm_deploy", "transformer deployment benchmark")
        self.assertIs(stages["technical_cases"].status, StageStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
