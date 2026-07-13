"""Schema-v3 semantic context tests."""

import json
import tempfile
import threading
import unittest
from pathlib import Path

from noteforge.errors import NoteForgeError
from noteforge.storage.context import SEMANTIC_KEYS, ContextStore


class TestContextStore(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = ContextStore("test_job_cs", self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_save_and_load(self):
        self.store.save("keywords", {"keywords": ["AI"]})
        self.assertEqual(self.store.load("keywords"), {"keywords": ["AI"]})

    def test_load_missing_key(self):
        self.assertIsNone(self.store.load("report"))

    def test_load_all_has_schema_version(self):
        self.store.save("input", {"topic": "AI"})
        data = self.store.load_all()
        self.assertEqual(data["schema_version"], 3)
        self.assertIn("input", data)

    def test_context_file_path(self):
        self.assertEqual(self.store.context_file, self.root / "jobs" / "test_job_cs" / "context_data.json")

    def test_job_isolation(self):
        first = ContextStore("job_a", self.root)
        second = ContextStore("job_b", self.root)
        first.save("input", "a")
        second.save("input", "b")
        self.assertEqual(first.load("input"), "a")
        self.assertEqual(second.load("input"), "b")

    def test_rejects_t_keys_and_unknown_keys(self):
        for key in ("T0", "T6", "unknown"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.store.save(key, {})

    def test_semantic_key_contract(self):
        self.assertEqual(SEMANTIC_KEYS, {
            "input", "document", "keywords", "literature", "synthesis",
            "technical_cases", "policy_assessment", "report",
        })

    def test_corrupt_context_raises_structured_error(self):
        self.store.save("input", {"topic": "AI"})
        self.store.context_file.write_text("{bad", encoding="utf-8")
        with self.assertRaises(NoteForgeError):
            self.store.load_all()

    def test_invalid_job_ids_rejected(self):
        for bad_id in ("", "..", "../escape", "bad job", "bad.job", "-bad"):
            with self.subTest(job_id=bad_id), self.assertRaises(ValueError):
                ContextStore(bad_id, self.root)

    def test_multiple_stores_same_job_preserve_keys(self):
        first = ContextStore("test_job_cs", self.root)
        second = ContextStore("test_job_cs", self.root)
        errors = []

        def save_many(store, keys):
            try:
                for key in keys:
                    store.save(key, {"owner": key})
            except Exception as error:  # pragma: no cover - asserted below
                errors.append(error)

        keys = list(SEMANTIC_KEYS)
        threads = [
            threading.Thread(target=save_many, args=(first, keys[:4])),
            threading.Thread(target=save_many, args=(second, keys[4:])),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertTrue(SEMANTIC_KEYS.issubset(self.store.load_all()))

    def test_json_contains_no_legacy_task_keys(self):
        self.store.save("literature", {"status": "ok"})
        payload = json.loads(self.store.context_file.read_text(encoding="utf-8"))
        self.assertFalse(any(key.startswith("T") for key in payload))


if __name__ == "__main__":
    unittest.main()
