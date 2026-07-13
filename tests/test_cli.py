"""Unified CLI routing tests."""

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from noteforge.cli import build_parser, main


class TestCli(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_parser_exposes_all_commands(self):
        parser = build_parser()
        for argv, command in (
            (["run", "--topic", "AI"], "run"), (["tui"], "tui"),
            (["api"], "api"), (["jobs", "list"], "jobs"),
            (["jobs", "migrate", "--all"], "jobs"), (["report", "job"], "report"),
        ):
            with self.subTest(argv=argv):
                self.assertEqual(parser.parse_args(argv).command, command)

    def test_run_list_report_and_migrate(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(main([
                "run", "--topic", "transformer CLI", "--provider", "mock",
                "--job-id", "cli_job", "--output-root", str(self.root),
            ]), 0)
            self.assertEqual(main(["jobs", "list", "--output-root", str(self.root)]), 0)
            self.assertEqual(main(["report", "cli_job", "--output-root", str(self.root)]), 0)
            self.assertEqual(main(["jobs", "migrate", "--all", "--output-root", str(self.root)]), 0)
        output = stdout.getvalue()
        self.assertIn("job_id=cli_job", output)
        self.assertIn("cli_job\tCOMPLETED", output)
        self.assertIn("migrated=0", output)

    def test_tui_routes_to_shared_entrypoint(self):
        with patch("noteforge.tui.run_tui", return_value=0) as run_tui:
            self.assertEqual(main(["tui"]), 0)
        run_tui.assert_called_once_with()

    def test_api_routes_to_shared_entrypoint(self):
        with patch("noteforge.api.serve") as serve:
            self.assertEqual(main(["api", "--host", "127.0.0.1", "--port", "8123"]), 0)
        serve.assert_called_once_with("127.0.0.1", 8123)

    def test_invalid_request_returns_nonzero_with_error_code(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(main(["run", "--job-id", "missing", "--output-root", str(self.root)]), 1)
        self.assertIn("INPUT_INVALID", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
