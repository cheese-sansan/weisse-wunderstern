"""Configuration, LLM transport, cleanup, document stage, and TUI tests."""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

from noteforge.config import load_env
from noteforge.llm import chat
from noteforge.models import JobStatus
from noteforge.stages.document import run as parse_document
from noteforge.storage.cleanup import cleanup_old_jobs
from noteforge.storage.state import StateManager
from noteforge.tui import _print_jobs, default_job_id, run_tui


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class TestConfigAndLlm(unittest.TestCase):
    def test_load_env_missing_file(self):
        self.assertEqual(load_env("definitely-missing.env"), {})

    def test_load_env_parses_quotes_comments_and_preserves_existing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("# comment\nNF_TEST_A='value a'\nNF_TEST_B=from-file\ninvalid\n", encoding="utf-8")
            with patch.dict(os.environ, {"NF_TEST_B": "existing"}, clear=False):
                loaded = load_env(path)
                self.assertEqual(loaded, {"NF_TEST_A": "value a", "NF_TEST_B": "from-file"})
                self.assertEqual(os.environ["NF_TEST_A"], "value a")
                self.assertEqual(os.environ["NF_TEST_B"], "existing")
            os.environ.pop("NF_TEST_A", None)

    def test_load_env_handles_read_error(self):
        with patch("noteforge.config.os.path.exists", return_value=True), \
             patch("builtins.open", side_effect=OSError("denied")):
            self.assertEqual(load_env("blocked.env"), {})

    def test_chat_without_key_is_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(chat("hello"))

    def test_chat_builds_openai_compatible_request(self):
        payload = {"choices": [{"message": {"content": " answer "}}]}
        captured = {}

        def open_request(request, timeout):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse(payload)

        env = {
            "OPENAI_API_KEY": "test-key", "OPENAI_API_BASE": "https://llm.example/v1",
            "LLM_MODEL": "test-model",
        }
        with patch.dict(os.environ, env, clear=True), patch("urllib.request.urlopen", side_effect=open_request):
            self.assertEqual(chat("hello", "system", 0.2), "answer")
        self.assertEqual(captured["url"], "https://llm.example/v1/chat/completions")
        self.assertEqual(captured["body"]["model"], "test-model")
        self.assertEqual(len(captured["body"]["messages"]), 2)
        self.assertEqual(captured["timeout"], 60)

    def test_chat_transport_errors_degrade_to_none(self):
        error = HTTPError("https://llm.example", 500, "failed", None, None)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), \
             patch("urllib.request.urlopen", side_effect=error):
            self.assertIsNone(chat("hello"))
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), \
             patch("urllib.request.urlopen", side_effect=RuntimeError("offline")):
            self.assertIsNone(chat("hello"))


class TestCleanupDocumentAndTui(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_cleanup_missing_root(self):
        self.assertEqual(cleanup_old_jobs(output_root=self.root), (0, 0))

    def test_cleanup_dry_run_and_delete(self):
        old = self.root / "jobs" / "old"
        fresh = self.root / "jobs" / "fresh"
        old.mkdir(parents=True)
        fresh.mkdir()
        timestamp = time.time() - 10 * 86400
        os.utime(old, (timestamp, timestamp))
        self.assertEqual(cleanup_old_jobs(7, True, self.root), (1, 2))
        self.assertTrue(old.exists())
        self.assertEqual(cleanup_old_jobs(7, False, self.root), (1, 2))
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())

    def test_cleanup_uses_environment_default_and_handles_entry_error(self):
        job = self.root / "jobs" / "job"
        job.mkdir(parents=True)
        with patch.dict(os.environ, {"JOB_RETENTION_DAYS": "1"}), \
             patch("noteforge.storage.cleanup.os.path.getmtime", side_effect=OSError("denied")):
            self.assertEqual(cleanup_old_jobs(output_root=self.root), (0, 1))

    def test_document_stage_parses_text_and_structures_metadata(self):
        path = self.root / "paper.txt"
        path.write_text("Evidence $x^2$", encoding="utf-8")
        with patch("noteforge.llm.chat", return_value=None):
            result = parse_document(str(path))
        self.assertEqual(result["raw_text"], "Evidence $x^2$")
        self.assertEqual(result["metadata"]["file_name"], "paper.txt")
        self.assertTrue(result["contains_latex"])
        self.assertTrue(result["structured_summary"])

    def test_document_stage_raises_structured_parse_error(self):
        from noteforge.errors import ErrorCode, NoteForgeError

        with self.assertRaises(NoteForgeError) as caught:
            parse_document(str(self.root / "missing.txt"))
        self.assertIs(caught.exception.code, ErrorCode.PARSE_FAILED)

    def test_tui_exit_and_unknown_choice(self):
        outputs = []
        choices = iter(["unknown", "0"])
        self.assertEqual(run_tui(lambda _prompt: next(choices), outputs.append, self.root), 0)
        self.assertIn("Unknown choice", outputs)

    def test_tui_topic_routes_to_sdk(self):
        choices = iter(["1", "topic", "mock", "tui-job", "0"])
        result = SimpleNamespace(job_id="tui-job", report_path=self.root / "report.md")
        with patch("noteforge.tui.run_job", return_value=result) as run:
            self.assertEqual(run_tui(lambda _prompt: next(choices), lambda _text: None, self.root), 0)
        self.assertEqual(run.call_args.args[0].topic, "topic")

    def test_tui_lists_and_reads_jobs(self):
        outputs = []
        _print_jobs(self.root, outputs.append)
        self.assertEqual(outputs, ["No jobs found"])
        manager = StateManager("tui_job", self.root)
        manager.init_state()
        report = manager.job_dir / "report.md"
        report.write_text("TUI report", encoding="utf-8")
        outputs.clear()
        _print_jobs(self.root, outputs.append)
        self.assertIn("tui_job | PENDING", outputs[0])
        choices = iter(["4", "tui_job", "0"])
        outputs.clear()
        self.assertEqual(run_tui(lambda _prompt: next(choices), outputs.append, self.root), 0)
        self.assertIn("TUI report", outputs)

    def test_default_job_id_is_safe(self):
        self.assertRegex(default_job_id(), r"^tui-\d{8}-\d{6}$")
        self.assertIs(JobStatus.PENDING.value, "PENDING")


if __name__ == "__main__":
    unittest.main()
