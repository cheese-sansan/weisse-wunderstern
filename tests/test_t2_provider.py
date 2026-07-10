"""T2 provider contract and Crossref integration tests."""

import json
import unittest
from urllib.error import URLError

from tasks.t2_literature_search import (
    CrossrefLiteratureProvider,
    MockLiteratureProvider,
    _get_provider,
    _normalize_results,
    run,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class TestT2Provider(unittest.TestCase):

    def setUp(self):
        self.t1_mock = {
            "keywords": ["transformer", "NLP"],
            "academic_entities": {
                "methods": ["BERT"], "datasets": ["GLUE"],
                "metrics": ["Accuracy"], "tasks": [],
                "domains": ["NLP"], "relations": [],
            },
        }

    def test_mock_provider_returns_simulated_contract(self):
        result = MockLiteratureProvider().search(self.t1_mock)
        self.assertEqual(result["provider"], "mock")
        self.assertEqual(result["status"], "ok")
        self.assertGreater(len(result["literature_results"]), 0)
        for record in result["literature_results"]:
            self.assertEqual(record["source_type"], "simulated")
            self.assertEqual(record["source_provider"], "mock")
            for field in (
                "source_id", "title", "authors", "year", "doi", "url",
                "abstract", "source_provider", "source_type", "retrieved_at",
            ):
                self.assertIn(field, record)

    def test_explicit_mock_backward_compatible_inputs(self):
        for value in (["AI", "ML"], "AI ML"):
            result = run(value, provider="mock")
            self.assertIn("literature_results", result)
            self.assertEqual(result["provider"], "mock")

    def test_normalize_simulated_results(self):
        normalized = _normalize_results({"literature_results": [{"title": "Test"}]})
        self.assertEqual(normalized["literature_results"][0]["source_type"], "simulated")
        self.assertEqual(_normalize_results({"literature_results": []})["literature_results"], [])

    def test_default_provider_is_crossref_and_ignores_llm_key(self):
        self.assertIsInstance(_get_provider(), CrossrefLiteratureProvider)
        self.assertIsInstance(_get_provider("crossref"), CrossrefLiteratureProvider)

    def test_unknown_provider_rejected(self):
        with self.assertRaises(ValueError):
            _get_provider("unknown")

    def test_crossref_mapping_and_query_encoding(self):
        captured = {}
        payload = {
            "message": {"items": [{
                "DOI": "10.1000/example",
                "title": ["A Real Paper"],
                "author": [{"given": "Ada", "family": "Lovelace"}],
                "published-online": {"date-parts": [[2026, 1, 2]]},
                "URL": "https://doi.org/10.1000/example",
                "abstract": "<jats:p>Evidence &amp; results.</jats:p>",
                "type": "journal-article",
            }]},
        }

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            return FakeResponse(payload)

        provider = CrossrefLiteratureProvider(
            max_results=5, timeout=3, opener=opener, sleeper=lambda _value: None,
        )
        result = provider.search(self.t1_mock)
        record = result["literature_results"][0]
        self.assertEqual(result["provider"], "crossref")
        self.assertEqual(result["status"], "ok")
        self.assertIn("query.bibliographic=transformer+NLP+BERT", captured["url"])
        self.assertIn("rows=15", captured["url"])
        self.assertEqual(captured["timeout"], 3)
        self.assertEqual(record["authors"], ["Ada Lovelace"])
        self.assertEqual(record["year"], 2026)
        self.assertEqual(record["abstract"], "Evidence & results.")
        self.assertEqual(record["source_type"], "external_api")
        self.assertEqual(record["core_method"], "")
        self.assertEqual(record["key_findings"], [])

    def test_crossref_filters_components_before_limiting(self):
        payload = {"message": {"items": [
            {"title": ["Table 1"], "type": "component"},
            {"title": ["Actual Article"], "type": "journal-article"},
        ]}}
        provider = CrossrefLiteratureProvider(
            max_results=1, opener=lambda *_args, **_kwargs: FakeResponse(payload),
            sleeper=lambda _value: None,
        )
        result = provider.search(self.t1_mock)
        self.assertEqual([item["title"] for item in result["literature_results"]], ["Actual Article"])

    def test_crossref_network_failure_retries_then_degrades_without_mock(self):
        attempts = []

        def opener(_request, timeout):
            attempts.append(timeout)
            raise URLError("offline")

        provider = CrossrefLiteratureProvider(
            timeout=2, opener=opener, sleeper=lambda _value: None,
        )
        result = provider.search(self.t1_mock)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["literature_results"], [])
        self.assertIn("网络错误", result["warnings"][0])


if __name__ == "__main__":
    unittest.main()
