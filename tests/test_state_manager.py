"""StateManager 单元测试。"""
import unittest
import os
import shutil
import threading
import re
from utils.state_manager import StateManager, validate_job_id


class TestStateManager(unittest.TestCase):

    def setUp(self):
        self.job_id = "test_job_sm"
        self.sm = StateManager(self.job_id)
        self._clean()

    def tearDown(self):
        self._clean()

    def _clean(self):
        d = os.path.join("outputs", "jobs", self.job_id)
        if os.path.exists(d):
            shutil.rmtree(d)

    def test_init_creates_state(self):
        self.sm.init_state()
        self.assertTrue(os.path.exists(self.sm.state_file))

    def test_job_id_in_state(self):
        self.sm.init_state()
        state = self.sm.load_state()
        self.assertEqual(state["job_id"], self.job_id)

    def test_initial_status_pending(self):
        self.sm.init_state()
        state = self.sm.load_state()
        self.assertEqual(state["status"], "PENDING")

    def test_task_list_has_five_base_tasks(self):
        self.sm.init_state()
        state = self.sm.load_state()
        self.assertEqual(len(state["task_list"]), 5)

    def test_update_task_status(self):
        self.sm.init_state()
        self.sm.update_task_status("T1", "进行中")
        state = self.sm.load_state()
        t1 = [t for t in state["task_list"] if t["task_id"] == "T1"][0]
        self.assertEqual(t1["status"], "进行中")

    def test_status_history_timestamp_uses_original_format(self):
        self.sm.init_state()
        self.sm.update_task_status("T1", "进行中")
        state = self.sm.load_state()
        t1 = [t for t in state["task_list"] if t["task_id"] == "T1"][0]
        timestamp = t1["status_history"][-1]["timestamp"]
        self.assertRegex(timestamp, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    def test_set_completed(self):
        self.sm.init_state()
        self.sm.set_completed()
        state = self.sm.load_state()
        self.assertEqual(state["status"], "COMPLETED")

    def test_set_error(self):
        self.sm.init_state()
        self.sm.set_error("test error")
        state = self.sm.load_state()
        self.assertEqual(state["status"], "FAILED")
        self.assertEqual(state["error"], "test error")

    def test_job_isolation(self):
        sm1 = StateManager("job_a")
        sm2 = StateManager("job_b")
        sm1.init_state()
        sm2.init_state()
        self.assertNotEqual(sm1.state_file, sm2.state_file)
        self.assertTrue(os.path.exists(sm1.state_file))
        self.assertTrue(os.path.exists(sm2.state_file))
        # clean
        for d in [os.path.join("outputs", "jobs", j) for j in ("job_a", "job_b")]:
            if os.path.exists(d):
                shutil.rmtree(d)

    def test_thread_safety(self):
        self.sm.init_state()
        errors = []

        def update():
            try:
                for i in range(20):
                    self.sm.update_task_status("T1", "进行中")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=update) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(errors), 0)

    def test_empty_state_file_recovers(self):
        self.sm.init_state()
        with open(self.sm.state_file, "w", encoding="utf-8") as f:
            f.write("")
        state = self.sm.load_state()
        self.assertEqual(state["job_id"], self.job_id)
        self.assertEqual(state["status"], "PENDING")

    def test_corrupt_state_file_recovers(self):
        self.sm.init_state()
        with open(self.sm.state_file, "w", encoding="utf-8") as f:
            f.write("{bad json")
        state = self.sm.load_state()
        self.assertEqual(state["job_id"], self.job_id)
        self.assertEqual(state["status"], "PENDING")

    def test_multiple_managers_same_job_share_lock(self):
        self.sm.init_state()
        other = StateManager(self.job_id)
        errors = []

        def update(manager, task_id):
            try:
                for _ in range(20):
                    manager.update_task_status(task_id, "进行中")
                    manager.update_task_status(task_id, "完成")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=update, args=(self.sm, "T1")),
            threading.Thread(target=update, args=(other, "T2")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        state = self.sm.load_state()
        self.assertEqual(state["task_list"][1]["status"], "完成")
        self.assertEqual(state["task_list"][2]["status"], "完成")

    def test_invalid_job_ids_rejected(self):
        for bad_id in ("", "..", "../escape", "bad job", "bad.job", "-bad"):
            with self.subTest(job_id=bad_id):
                with self.assertRaises(ValueError):
                    StateManager(bad_id)

    def test_validate_job_id_accepts_safe_ids(self):
        self.assertEqual(validate_job_id("job_20260613-a"), "job_20260613-a")


if __name__ == "__main__":
    unittest.main()
