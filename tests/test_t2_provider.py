"""Typed provider contract and Crossref integration tests."""

import json
import unittest
from urllib.error import URLError

from noteforge.models import LiteratureQuery, ProviderStatus, SourceType
from noteforge.providers.literature import (
    CrossrefLiteratureProvider,
    LiteratureProvider,
    MockLiteratureProvider,
    _normalize_simulated,
    get_provider,
    query_from_keyword_output,
    search_literature,
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
        self.keyword_output = {
            "keywords": ["transformer", "NLP"],
            "academic_entities": {
                "methods": ["BERT"], "datasets": ["GLUE"],
                "metrics": ["Accuracy"], "tasks": [], "domains": ["NLP"], "relations": [],
            },
        }
        self.query = query_from_keyword_output(self.keyword_output)

    def test_provider_protocol_is_abstract(self):
        self.assertTrue(issubclass(MockLiteratureProvider, LiteratureProvider))
        with self.assertRaises(TypeError):
            LiteratureProvider()

    def test_query_conversion(self):
        self.assertEqual(self.query, LiteratureQuery(
            keywords=["transformer", "NLP"], methods=["BERT"], domains=["NLP"],
        ))

    def test_mock_provider_returns_simulated_contract(self):
        result = MockLiteratureProvider().search(self.query)
        self.assertEqual(result.provider, "mock")
        self.assertIs(result.status, ProviderStatus.OK)
        self.assertGreater(len(result.literature_results), 0)
        for record in result.literature_results:
            self.assertIs(record.source_type, SourceType.SIMULATED)
            self.assertEqual(record.source_provider, "mock")
            self.assertTrue(record.source_id)

    def test_search_literature_accepts_explicit_mock(self):
        result = search_literature(LiteratureQuery(keywords=["AI", "ML"]), provider="mock")
        self.assertEqual(result.provider, "mock")

    def test_normalize_simulated_results(self):
        normalized = _normalize_simulated({"literature_results": [{"title": "Test"}]}, "mock", "AI")
        self.assertIs(normalized.literature_results[0].source_type, SourceType.SIMULATED)
        self.assertEqual(_normalize_simulated({"literature_results": []}, "mock", "AI").literature_results, [])

    def test_default_provider_is_crossref(self):
        self.assertIsInstance(get_provider(), CrossrefLiteratureProvider)
        self.assertIsInstance(get_provider("crossref"), CrossrefLiteratureProvider)

    def test_unknown_provider_rejected(self):
        with self.assertRaises(ValueError):
            get_provider("unknown")

    def test_crossref_mapping_and_query_encoding(self):
        captured = {}
        payload = {"message": {"items": [{
            "DOI": "10.1000/example", "title": ["A Real Paper"],
            "author": [{"given": "Ada", "family": "Lovelace"}],
            "published-online": {"date-parts": [[2026, 1, 2]]},
            "URL": "https://doi.org/10.1000/example",
            "abstract": "<jats:p>Evidence &amp; results.</jats:p>",
            "type": "journal-article",
        }]}}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            return FakeResponse(payload)

        provider = CrossrefLiteratureProvider(
            max_results=5, timeout=3, opener=opener, sleeper=lambda _value: None,
        )
        result = provider.search(self.query)
        record = result.literature_results[0]
        self.assertEqual(result.provider, "crossref")
        self.assertIs(result.status, ProviderStatus.OK)
        self.assertIn("query.bibliographic=transformer+NLP+BERT", captured["url"])
        self.assertIn("rows=15", captured["url"])
        self.assertEqual(captured["timeout"], 3)
        self.assertEqual(record.authors, ["Ada Lovelace"])
        self.assertEqual(record.year, 2026)
        self.assertEqual(record.abstract, "Evidence & results.")
        self.assertIs(record.source_type, SourceType.EXTERNAL_API)

    def test_crossref_filters_components_before_limiting(self):
        payload = {"message": {"items": [
            {"title": ["Table 1"], "type": "component"},
            {"title": ["Actual Article"], "type": "journal-article"},
        ]}}
        provider = CrossrefLiteratureProvider(
            max_results=1, opener=lambda *_args, **_kwargs: FakeResponse(payload),
            sleeper=lambda _value: None,
        )
        result = provider.search(self.query)
        self.assertEqual([item.title for item in result.literature_results], ["Actual Article"])

    def test_crossref_network_failure_retries_then_degrades_without_mock(self):
        attempts = []

        def opener(_request, timeout):
            attempts.append(timeout)
            raise URLError("offline")

        provider = CrossrefLiteratureProvider(timeout=2, opener=opener, sleeper=lambda _value: None)
        result = provider.search(self.query)
        self.assertEqual(len(attempts), 2)
        self.assertIs(result.status, ProviderStatus.DEGRADED)
        self.assertEqual(result.literature_results, [])
        self.assertTrue(result.warnings)


if __name__ == "__main__":
    unittest.main()
