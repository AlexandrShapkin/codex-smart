import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

import benchmark_submission_grader as grader
import benchmark_grading_supervisor as supervisor


class SubmissionGraderTests(unittest.TestCase):
    def test_descriptor_read_rejects_symlink_and_hardlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "normal.py").write_text("print('ok')\n")
            (root / "target.py").write_text("print('target')\n")
            (root / "link.py").symlink_to("target.py")
            os.link(root / "target.py", root / "hard.py")
            fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                self.assertEqual(grader._read_regular(fd, "normal.py"), "print('ok')\n")
                with self.assertRaises(grader.SubmissionRejected):
                    grader._read_regular(fd, "link.py")
                with self.assertRaises(grader.SubmissionRejected):
                    grader._read_regular(fd, "hard.py")
            finally:
                os.close(fd)

    def test_copy_expected_ignores_unrelated_build_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            sanitized = root / "sanitized"
            work.mkdir()
            (work / "src").mkdir()
            (work / "src" / "lib.py").write_text("VALUE = 7\n")
            (work / "target").mkdir()
            (work / "target" / "large-cache").write_text("untrusted-build-output")
            fixture = {
                "files": {"src/lib.py": "VALUE = 1\n"},
                "reference": {"src/lib.py": "VALUE = 7\n", "new.py": "NEW = True\n"},
            }
            with patch.object(grader, "WORKSPACE", work), patch.object(grader, "SANITIZED", sanitized):
                grader._copy_expected(fixture)
            self.assertEqual((sanitized / "src" / "lib.py").read_text(), "VALUE = 7\n")
            self.assertFalse((sanitized / "target").exists())
            self.assertFalse((sanitized / "new.py").exists())

    def test_exploration_policy_rejects_extra_artifact_and_symlink(self):
        fixture = {"files": {"service.py": "pass\n"}, "reference": {"answer.json": "{}\n"}}
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "work"
            work.mkdir()
            (work / "service.py").write_text("pass\n")
            (work / "answer.json").write_text("{}\n")
            with patch.object(grader, "WORKSPACE", work):
                grader._exploration_policy(fixture)
                (work / "notes.txt").write_text("extra")
                with self.assertRaisesRegex(grader.SubmissionRejected, "extra-artifact"):
                    grader._exploration_policy(fixture)
                (work / "notes.txt").unlink()
                (work / "escape").symlink_to("/tmp")
                with self.assertRaisesRegex(grader.SubmissionRejected, "symlink"):
                    grader._exploration_policy(fixture)

    def test_unsafe_relative_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            fd = os.open(tmp, os.O_RDONLY | os.O_DIRECTORY)
            try:
                for name in ["../escape", "/absolute", "a/../b"]:
                    with self.subTest(name=name), self.assertRaises(grader.SubmissionRejected):
                        grader._read_regular(fd, name)
            finally:
                os.close(fd)


    def test_main_sends_verdict_only_over_private_unix_socket(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "verdict.sock"
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(str(path))
                listener.listen(1)
                with patch.object(grader, "VERDICT_SOCKET", str(path)),                      patch.object(grader, "grade", return_value=True):
                    grader.main(["python-billing"])
                connection, _ = listener.accept()
                with connection:
                    payload = connection.recv(4096)
        self.assertEqual(
            json.loads(payload.decode()),
            {"quality_pass": True, "status": "verified"},
        )

    def test_supervisor_anchors_service_until_bwrap_exits(self):
        child = unittest.mock.Mock()
        child.wait.return_value = 7
        with patch.object(supervisor.subprocess, "Popen", return_value=child) as popen:
            self.assertEqual(supervisor.main(["--", "/usr/bin/bwrap", "--version"]), 7)
        argv = popen.call_args.args[0]
        self.assertEqual(argv, ["/usr/bin/bwrap", "--version"])
        self.assertEqual(popen.call_args.kwargs["stdin"], supervisor.subprocess.DEVNULL)
        self.assertEqual(popen.call_args.kwargs["stdout"], supervisor.subprocess.DEVNULL)
        self.assertEqual(popen.call_args.kwargs["stderr"], supervisor.subprocess.DEVNULL)
        self.assertTrue(popen.call_args.kwargs["close_fds"])

if __name__ == "__main__":
    unittest.main()
