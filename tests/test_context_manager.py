"""ContextStore 单元测试。"""
import unittest
import os
import shutil
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


if __name__ == "__main__":
    unittest.main()
