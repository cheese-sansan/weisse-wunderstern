"""Schema-v3 state machine tests."""

import json
import tempfile
import threading
import unittest
from pathlib import Path

from noteforge.errors import InvalidStateTransition, NoteForgeError
from noteforge.models import JobStatus, StageStatus
from noteforge.storage.state import BASE_STAGES, StateManager, validate_job_id


class TestStateManager(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manager = StateManager("test_job_sm", self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_init_creates_state(self):
        self.manager.init_state()
        self.assertTrue(self.manager.state_file.exists())

    def test_job_id_in_state(self):
        self.assertEqual(self.manager.init_state().job_id, "test_job_sm")

    def test_initial_status_pending(self):
        self.assertIs(self.manager.init_state().status, JobStatus.PENDING)

    def test_stage_list_has_seven_semantic_stages(self):
        state = self.manager.init_state()
        self.assertEqual(tuple(state.stages), BASE_STAGES)
        self.assertNotIn("T1", state.stages)

    def test_update_stage_status(self):
        self.manager.init_state()
        self.manager.transition_stage("keyword_extract", StageStatus.RUNNING)
        self.assertIs(self.manager.load_state().stages["keyword_extract"].status, StageStatus.RUNNING)

    def test_status_history_timestamp_is_iso8601(self):
        self.manager.init_state()
        self.manager.transition_stage("keyword_extract", StageStatus.RUNNING)
        timestamp = self.manager.load_state().stages["keyword_extract"].history[-1]["timestamp"]
        self.assertRegex(timestamp, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00$")

    def test_set_completed(self):
        self.manager.init_state()
        self.manager.transition_stage("keyword_extract", StageStatus.RUNNING)
        self.manager.transition_stage("keyword_extract", StageStatus.COMPLETED)
        self.manager.set_completed()
        self.assertIs(self.manager.load_state().status, JobStatus.COMPLETED)

    def test_set_error(self):
        self.manager.init_state()
        self.manager.set_error("test error")
        state = self.manager.load_state()
        self.assertIs(state.status, JobStatus.FAILED)
        self.assertEqual(state.error["message"], "test error")

    def test_job_isolation(self):
        first = StateManager("job_a", self.root)
        second = StateManager("job_b", self.root)
        first.init_state()
        second.init_state()
        self.assertNotEqual(first.state_file, second.state_file)

    def test_thread_safety(self):
        self.manager.init_state()
        errors = []

        def update(stage):
            try:
                self.manager.transition_stage(stage, StageStatus.RUNNING)
                self.manager.transition_stage(stage, StageStatus.COMPLETED)
            except Exception as error:  # pragma: no cover - asserted below
                errors.append(error)

        threads = [threading.Thread(target=update, args=(stage,)) for stage in BASE_STAGES[:4]]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertTrue(all(
            self.manager.load_state().stages[stage].status is StageStatus.COMPLETED
            for stage in BASE_STAGES[:4]
        ))

    def test_empty_state_file_is_storage_error(self):
        self.manager.init_state()
        self.manager.state_file.write_text("", encoding="utf-8")
        with self.assertRaises(NoteForgeError):
            self.manager.load_state()

    def test_corrupt_state_file_is_migration_error_and_preserved(self):
        self.manager.init_state()
        self.manager.state_file.write_text("{bad json", encoding="utf-8")
        with self.assertRaises(NoteForgeError):
            self.manager.load_state()
        self.assertEqual(self.manager.state_file.read_text(encoding="utf-8"), "{bad json")

    def test_illegal_stage_transition_rejected(self):
        self.manager.init_state()
        with self.assertRaises(InvalidStateTransition):
            self.manager.transition_stage("synthesis", StageStatus.COMPLETED)

    def test_illegal_job_transition_rejected(self):
        self.manager.init_state()
        with self.assertRaises(InvalidStateTransition):
            self.manager.transition_job(JobStatus.COMPLETED)

    def test_persisted_schema_version_is_three(self):
        self.manager.init_state()
        payload = json.loads(self.manager.state_file.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 3)

    def test_invalid_job_ids_rejected(self):
        for bad_id in ("", "..", "../escape", "bad job", "bad.job", "-bad"):
            with self.subTest(job_id=bad_id), self.assertRaises(ValueError):
                StateManager(bad_id, self.root)

    def test_validate_job_id_accepts_safe_ids(self):
        self.assertEqual(validate_job_id("job_20260613-a"), "job_20260613-a")


if __name__ == "__main__":
    unittest.main()
