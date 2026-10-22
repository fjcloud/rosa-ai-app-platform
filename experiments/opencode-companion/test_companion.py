import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import companion


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "progress.json"
        self.patch = patch.object(companion, "STATE", self.state)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def run_action(self, *args):
        output = io.StringIO()
        with patch("sys.argv", ["companion.py", *args]), contextlib.redirect_stdout(output):
            companion.main()
        return json.loads(output.getvalue())

    def test_next_requires_live_evidence_even_after_correct_quiz(self):
        self.run_action("answer", "B")
        self.assertIn("blocked", self.run_action("next"))
        self.assertEqual(self.run_action("status")["step"], 1)

    def test_live_check_alone_does_not_complete_lesson(self):
        with patch.object(companion, "verify", return_value={"gpu_allocatable": True}):
            self.run_action("check")
        self.assertIn("blocked", self.run_action("next"))

    def test_wrong_answer_stays_and_supplies_hint(self):
        result = self.run_action("answer", "A")
        self.assertFalse(result["correct"])
        self.assertIn("Try again", result["feedback"])
        self.assertEqual(self.run_action("status")["step"], 1)

    def test_correct_answer_waits_for_explicit_next_and_survives_resume(self):
        with patch.object(companion, "verify", return_value={"gpu_allocatable": True}):
            self.run_action("check")
        self.run_action("answer", "B")
        self.assertEqual(self.run_action("status")["step"], 1)
        self.run_action("next")
        self.assertEqual(self.run_action("status")["step"], 2)
        self.assertEqual(json.loads(self.state.read_text())["completed"], [0])

    def test_failed_recheck_invalidates_old_success(self):
        with patch.object(companion, "verify", return_value={}):
            self.run_action("check")
        self.run_action("answer", "B")
        with patch.object(companion, "verify", side_effect=RuntimeError("GPU not ready")):
            result = self.run_action("check")
        self.assertFalse(result["check_passed"])
        self.assertIn("blocked", self.run_action("next"))

    def test_credentials_in_unexpected_error_are_not_printed(self):
        with patch.object(companion, "verify", side_effect=ValueError("sk-oai-private-test-value")):
            result = self.run_action("check")
        self.assertEqual(result["error"], "ValueError")
        self.assertNotIn("sk-oai", json.dumps(result))

    def test_finished_course_remains_finished_on_resume(self):
        self.state.write_text(json.dumps({"step": 5, "checks": {"5": True}, "quizzes": {"5": True}, "completed": list(range(5))}))
        self.assertTrue(self.run_action("next")["finished"])
        self.assertTrue(self.run_action("status")["finished"])
        self.run_action("next")
        self.assertEqual(self.run_action("status")["completed"], list(range(6)))


if __name__ == "__main__":
    unittest.main()
