"""T3 Extractor-Critic-Synthesizer 单元测试。"""
import unittest
from tasks.t3_summary_generation import (
    run, _mock_extract, _mock_critic, _mock_synthesize,
)


class TestT3Report(unittest.TestCase):

    def setUp(self):
        self.t2_mock = {
            "literature_results": [
                {
                    "title": "Paper A", "source_type": "simulated",
                    "core_method": "SVM", "datasets": ["MNIST"],
                    "metrics": ["Accuracy=0.95"],
                    "key_findings": ["SVM excels on MNIST"],
                    "limitations": ["Small sample (n=100)"],
                    "authors": ["A"], "year": 2024,
                },
                {
                    "title": "Paper B", "source_type": "simulated",
                    "core_method": "CNN", "datasets": ["CIFAR-10"],
                    "metrics": ["Accuracy=0.88"],
                    "key_findings": ["CNN achieves SOTA"],
                    "limitations": ["High cost"],
                    "authors": ["B"], "year": 2023,
                },
            ]
        }

    def test_run_returns_three_outputs(self):
        result = run(self.t2_mock)
        self.assertIn("extractor_draft", result)
        self.assertIn("critic_review", result)
        self.assertIn("final_report", result)

    def test_critic_has_at_least_two_critiques(self):
        result = run(self.t2_mock)
        critiques = result["critic_review"].get("critiques", [])
        self.assertGreaterEqual(len(critiques), 2)

    def test_final_report_has_five_sections(self):
        result = run(self.t2_mock)
        report = result["final_report"]
        sections = ["核心共识", "学术冲突", "方法局限", "高价值定量指标", "证据与不确定性"]
        for s in sections:
            self.assertIn(s, report, f"Missing section: {s}")

    def test_report_contains_simulated_declaration(self):
        result = run(self.t2_mock)
        report = result["final_report"]
        self.assertTrue("simulated" in report.lower() or "模拟生成" in report)

    def test_mock_extract_produces_claims(self):
        extract = _mock_extract(self.t2_mock["literature_results"])
        self.assertIn("claims", extract)
        self.assertGreater(len(extract["claims"]), 0)

    def test_mock_critic_produces_critiques(self):
        extract = _mock_extract(self.t2_mock["literature_results"])
        critic = _mock_critic(extract, self.t2_mock["literature_results"])
        self.assertIn("critiques", critic)
        self.assertGreaterEqual(len(critic["critiques"]), 2)

    def test_empty_literature_handled(self):
        result = run({"literature_results": []})
        self.assertIn("final_report", result)
        self.assertIn("文献不足", result["final_report"])


if __name__ == "__main__":
    unittest.main()
