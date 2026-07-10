"""Regression tests for public project requirements and dynamic routing."""

import os
import shutil
import unittest

from core.pipeline import run_job
from utils.state_manager import StateManager


class TestProjectRequirementsAlignment(unittest.TestCase):

    def tearDown(self):
        for job_id in (
            "align_ai_trend",
            "align_car_safety",
            "align_llm_deploy",
        ):
            job_dir = os.path.join("outputs", "jobs", job_id)
            if os.path.exists(job_dir):
                shutil.rmtree(job_dir)

    def _run_and_task_ids(self, job_id, topic):
        job_dir = os.path.join("outputs", "jobs", job_id)
        if os.path.exists(job_dir):
            shutil.rmtree(job_dir)
        run_job(job_id, topic=topic, provider="mock")
        state = StateManager(job_id).load_state()
        return {task["task_id"] for task in state["task_list"]}

    def test_ai_industry_topic_triggers_t5_and_t6(self):
        task_ids = self._run_and_task_ids("align_ai_trend", "2025 Q3 AI行业趋势")
        self.assertIn("T5", task_ids)
        self.assertIn("T6", task_ids)

    def test_car_safety_topic_triggers_t6_only(self):
        task_ids = self._run_and_task_ids("align_car_safety", "智能汽车安全技术进展")
        self.assertNotIn("T5", task_ids)
        self.assertIn("T6", task_ids)

    def test_llm_deployment_topic_triggers_t5_and_t6(self):
        task_ids = self._run_and_task_ids("align_llm_deploy", "大模型轻量化部署方案")
        self.assertIn("T5", task_ids)
        self.assertIn("T6", task_ids)


if __name__ == "__main__":
    unittest.main()
