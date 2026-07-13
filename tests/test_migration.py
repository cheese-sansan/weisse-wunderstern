"""Transactional v0.2-to-v3 migration tests using a captured v0.2 job fixture."""

import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from noteforge.errors import ErrorCode, NoteForgeError
from noteforge.models import JobStatus, StageStatus
from noteforge.storage.context import ContextStore
from noteforge.storage.migration import migrate_all, migrate_job
from noteforge.storage.state import StateManager

FIXTURE = Path(__file__).parent / "fixtures" / "v0_2_job"


class TestMigration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.job_dir = self.root / "jobs" / "fixture_job"
        shutil.copytree(FIXTURE, self.job_dir)

    def tearDown(self):
        self.temp.cleanup()

    def test_first_state_read_migrates_and_creates_exact_backups(self):
        original_state = (self.job_dir / "task_state.json").read_bytes()
        original_context = (self.job_dir / "context_data.json").read_bytes()
        state = StateManager("fixture_job", self.root).load_state()
        self.assertEqual(state.schema_version, 3)
        self.assertIs(state.status, JobStatus.COMPLETED)
        self.assertEqual((self.job_dir / "task_state.v0.2.json").read_bytes(), original_state)
        self.assertEqual((self.job_dir / "context_data.v0.2.json").read_bytes(), original_context)

    def test_context_uses_semantic_keys_without_t_keys(self):
        context = ContextStore("fixture_job", self.root).load_all()
        self.assertEqual(context["schema_version"], 3)
        self.assertIn("keywords", context)
        self.assertIn("technical_cases", context)
        self.assertFalse(any(key.startswith("T") for key in context))

    def test_dynamic_task_maps_to_semantic_stage(self):
        state = StateManager("fixture_job", self.root).load_state()
        self.assertIs(state.stages["technical_cases"].status, StageStatus.COMPLETED)
        self.assertIs(state.stages["policy_assessment"].status, StageStatus.SKIPPED)

    def test_legacy_report_is_preserved_and_canonical_report_created(self):
        StateManager("fixture_job", self.root).load_state()
        legacy = self.job_dir / "report_framework.md"
        canonical = self.job_dir / "report.md"
        self.assertTrue(legacy.exists())
        self.assertEqual(canonical.read_bytes(), legacy.read_bytes())

    def test_repeated_migration_is_idempotent(self):
        self.assertTrue(migrate_job("fixture_job", self.root))
        state_before = (self.job_dir / "task_state.json").read_bytes()
        context_before = (self.job_dir / "context_data.json").read_bytes()
        self.assertFalse(migrate_job("fixture_job", self.root))
        self.assertEqual((self.job_dir / "task_state.json").read_bytes(), state_before)
        self.assertEqual((self.job_dir / "context_data.json").read_bytes(), context_before)

    def test_migrate_all_reports_count(self):
        migrated, errors = migrate_all(self.root)
        self.assertEqual((migrated, errors), (1, []))

    def test_corrupt_legacy_data_is_preserved_and_returns_migration_failed(self):
        path = self.job_dir / "context_data.json"
        path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(NoteForgeError) as caught:
            migrate_job("fixture_job", self.root)
        self.assertIs(caught.exception.code, ErrorCode.MIGRATION_FAILED)
        self.assertEqual(path.read_text(encoding="utf-8"), "{broken")

    def test_second_replace_failure_rolls_back_both_original_files(self):
        state_path = self.job_dir / "task_state.json"
        context_path = self.job_dir / "context_data.json"
        original_state, original_context = state_path.read_bytes(), context_path.read_bytes()
        from noteforge.storage import migration

        real_replace = migration.os.replace
        calls = 0

        def fail_second(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated context replace failure")
            return real_replace(source, destination)

        with patch("noteforge.storage.migration.os.replace", side_effect=fail_second):
            with self.assertRaises(NoteForgeError) as caught:
                migrate_job("fixture_job", self.root)
        self.assertIs(caught.exception.code, ErrorCode.MIGRATION_FAILED)
        self.assertEqual(state_path.read_bytes(), original_state)
        self.assertEqual(context_path.read_bytes(), original_context)
        self.assertTrue(migrate_job("fixture_job", self.root))
        self.assertEqual(json.loads(state_path.read_text(encoding="utf-8"))["schema_version"], 3)

    def test_concurrent_first_reads_migrate_once_without_errors(self):
        errors = []

        def read_state():
            try:
                StateManager("fixture_job", self.root).load_state()
            except Exception as error:  # pragma: no cover - asserted below
                errors.append(error)

        threads = [threading.Thread(target=read_state) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(json.loads((self.job_dir / "task_state.json").read_text(encoding="utf-8"))["schema_version"], 3)


if __name__ == "__main__":
    unittest.main()
