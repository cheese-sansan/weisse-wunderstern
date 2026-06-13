"""StateManager 单元测试。"""
import unittest
import os
import shutil
import threading
from utils.state_manager import StateManager


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


if __name__ == "__main__":
    unittest.main()
