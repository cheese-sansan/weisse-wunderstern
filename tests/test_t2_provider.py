"""T2 LiteratureProvider 单元测试。"""
import unittest
from tasks.t2_literature_search import (
    run, MockLiteratureProvider, _normalize_results, _get_provider
)


class TestT2Provider(unittest.TestCase):

    def setUp(self):
        self.t1_mock = {
            "keywords": ["transformer", "NLP"],
            "academic_entities": {
                "methods": ["BERT"],
                "datasets": ["GLUE"],
                "metrics": ["Accuracy"],
                "tasks": [],
                "domains": ["NLP"],
                "relations": [],
            }
        }

    def test_mock_provider_returns_results(self):
        provider = MockLiteratureProvider()
        result = provider.search(self.t1_mock)
        self.assertIn("literature_results", result)
        self.assertGreater(len(result["literature_results"]), 0)

    def test_all_mock_results_simulated(self):
        provider = MockLiteratureProvider()
        result = provider.search(self.t1_mock)
        for lr in result["literature_results"]:
            self.assertEqual(lr["source_type"], "simulated")

    def test_results_have_required_fields(self):
        result = run(self.t1_mock)
        for lr in result["literature_results"]:
            for field in ("title", "authors", "year", "core_method", "key_findings", "limitations"):
                self.assertIn(field, lr, f"Missing field: {field}")

    def test_run_accepts_list_backward_compat(self):
        result = run(["AI", "ML"])
        self.assertIsInstance(result, dict)
        self.assertIn("literature_results", result)

    def test_run_accepts_string_backward_compat(self):
        result = run("AI ML")
        self.assertIsInstance(result, dict)
        self.assertIn("literature_results", result)

    def test_normalize_empty(self):
        normalized = _normalize_results({"literature_results": []})
        self.assertEqual(normalized["literature_results"], [])

    def test_normalize_adds_source_type(self):
        normalized = _normalize_results({
            "literature_results": [{"title": "Test"}]
        })
        self.assertEqual(normalized["literature_results"][0]["source_type"], "simulated")

    def test_get_provider_returns_mock_without_key(self):
        provider = _get_provider()
        self.assertIsInstance(provider, MockLiteratureProvider)


if __name__ == "__main__":
    unittest.main()
