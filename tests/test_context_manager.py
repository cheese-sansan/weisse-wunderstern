"""ContextStore 单元测试。"""
import unittest
import os
import shutil
import threading
from utils.context_manager import ContextStore


class TestContextStore(unittest.TestCase):

    def setUp(self):
        self.job_id = "test_job_cs"
        self.cs = ContextStore(self.job_id)
        self._clean()

    def tearDown(self):
        self._clean()

    def _clean(self):
        d = os.path.join("outputs", "jobs", self.job_id)
        if os.path.exists(d):
            shutil.rmtree(d)

    def test_save_and_load(self):
        self.cs.save("T1", {"keywords": ["AI"]})
        result = self.cs.load("T1")
        self.assertEqual(result, {"keywords": ["AI"]})

    def test_load_missing_key(self):
        result = self.cs.load("nonexistent")
        self.assertIsNone(result)

    def test_load_all(self):
        self.cs.save("T1", "data1")
        self.cs.save("T2", "data2")
        all_data = self.cs.load_all()
        self.assertIn("T1", all_data)
        self.assertIn("T2", all_data)

    def test_ctx_file_path(self):
        expected = os.path.join("outputs", "jobs", self.job_id, "context_data.json")
        self.assertTrue(self.cs._ctx_file.endswith(expected))

    def test_job_isolation(self):
        cs1 = ContextStore("job_a")
        cs2 = ContextStore("job_b")
        cs1.save("T1", "a")
        cs2.save("T1", "b")
        self.assertEqual(cs1.load("T1"), "a")
        self.assertEqual(cs2.load("T1"), "b")
        for j in ("job_a", "job_b"):
            d = os.path.join("outputs", "jobs", j)
            if os.path.exists(d):
                shutil.rmtree(d)

    def test_invalid_job_ids_rejected(self):
        for bad_id in ("", "..", "../escape", "bad job", "bad.job", "-bad"):
            with self.subTest(job_id=bad_id):
                with self.assertRaises(ValueError):
                    ContextStore(bad_id)

    def test_multiple_stores_same_job_preserve_keys(self):
        cs1 = ContextStore(self.job_id)
        cs2 = ContextStore(self.job_id)
        errors = []

        def save_many(store, prefix):
            try:
                for i in range(20):
                    store.save(f"{prefix}_{i}", i)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=save_many, args=(cs1, "a")),
            threading.Thread(target=save_many, args=(cs2, "b")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        data = self.cs.load_all()
        self.assertEqual(len(data), 40)
        self.assertIn("a_0", data)
        self.assertIn("b_19", data)


if __name__ == "__main__":
    unittest.main()
