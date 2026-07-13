"""T1 关键词与学术实体 schema 单元测试。"""
import unittest

from noteforge.stages.keywords import _normalize, run


class TestT1Schema(unittest.TestCase):

    def test_mock_returns_dict(self):
        result = run("transformer models for NLP")
        self.assertIsInstance(result, dict)

    def test_mock_has_required_keys(self):
        result = run("transformer BERT evaluation")
        self.assertIn("keywords", result)
        self.assertIn("academic_entities", result)

    def test_academic_entities_has_all_fields(self):
        result = run("CNN image classification on ImageNet")
        ae = result["academic_entities"]
        for field in ("methods", "datasets", "metrics", "tasks", "domains", "relations"):
            self.assertIn(field, ae, f"Missing field: {field}")

    def test_keywords_non_empty(self):
        result = run("large language model evaluation")
        self.assertGreater(len(result["keywords"]), 0)

    def test_mock_detects_methods(self):
        result = run("transformer attention mechanism")
        methods = result["academic_entities"]["methods"]
        self.assertIn("transformer", methods)

    def test_mock_detects_domains(self):
        result = run("nlp sentiment analysis")
        domains = result["academic_entities"]["domains"]
        self.assertIn("nlp", domains)

    def test_mock_detects_original_chinese_ai_trend(self):
        result = run("2025 Q3 AI行业趋势")
        entities = result["academic_entities"]
        self.assertIn("large model", entities["methods"])
        self.assertIn("compliance", entities["domains"])

    def test_mock_detects_original_chinese_car_safety(self):
        result = run("智能汽车安全技术进展")
        entities = result["academic_entities"]
        self.assertEqual(entities["methods"], [])
        self.assertIn("compliance", entities["domains"])

    def test_mock_detects_original_chinese_llm_deployment(self):
        result = run("大模型轻量化部署方案")
        entities = result["academic_entities"]
        self.assertIn("model compression", entities["methods"])
        self.assertIn("compliance", entities["domains"])

    def test_normalize_empty(self):
        normalized = _normalize({})
        self.assertIn("keywords", normalized)
        self.assertEqual(normalized["academic_entities"]["methods"], [])

    def test_normalize_preserves_data(self):
        data = {
            "keywords": ["AI"],
            "academic_entities": {
                "methods": ["Transformer"],
                "datasets": [],
                "metrics": [],
                "tasks": [],
                "domains": [],
                "relations": []
            }
        }
        normalized = _normalize(data)
        self.assertEqual(normalized["keywords"], ["AI"])
        self.assertEqual(normalized["academic_entities"]["methods"], ["Transformer"])

    def test_relations_are_list(self):
        result = run("AI models")
        self.assertIsInstance(result["academic_entities"]["relations"], list)


if __name__ == "__main__":
    unittest.main()
