"""No Codex account, GitHub token, network or service needed for pilot tests."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

MODULE = Path(__file__).with_name("autodev_supervisor.py")
spec = importlib.util.spec_from_file_location("autodev_supervisor", MODULE)
autodev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(autodev)


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args],
                                   stderr=subprocess.DEVNULL).decode().strip()


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base / "primary-checkout"
        self.source.mkdir()
        git(self.source, "init", "-q")
        git(self.source, "config", "user.name", "Sandbox")
        git(self.source, "config", "user.email", "sandbox@example.invalid")
        (self.source / "small.py").write_text("answer = 42\n")
        git(self.source, "add", "small.py")
        git(self.source, "commit", "-qm", "initial")
        git(self.source, "remote", "add", "origin",
            "https://github.com/AlexandrShapkin/sandbox.git")
        self.repo = self.base / "isolated-worktree"
        git(self.source, "worktree", "add", "-q", "-b",
            "autodev/safe-pilot", str(self.repo), "HEAD")
        self.assertTrue((self.repo / ".git").is_file())
        self.head = git(self.repo, "rev-parse", "HEAD")
        self.state = self.base / "private-state"
        self.state.mkdir(mode=0o700)
        self.manifest = self.base / "queue.json"
        self.write_manifest()
        self.codex = self.base / "fake-codex"
        self.codex.write_text(
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            "import sys\n"
            "text = sys.argv[-1]\n"
            "if 'simulate-crash' in text: sys.exit(3)\n"
            "path = Path('small.py')\n"
            "path.write_text(path.read_text() + '# '"
            " + text.split('Task: ')[-1] + '\\n')\n"
            "if 'out-of-scope' in text:\n"
            "  Path('private.txt').write_text('leak')\n"
        )
        self.codex.chmod(0o700)

    def write_manifest(self, count=3, prompts=None, paths=None):
        prompts = prompts or [f"Add regression test stage {i}" for i in range(count)]
        body = {
            "schema": 1,
            "repository": "AlexandrShapkin/sandbox",
            "expected_sha": self.head,
            "tasks": [
                {"id": f"stage-{i}", "prompt": prompts[i],
                 "paths": paths or ["small.py"]}
                for i in range(count)
            ]
        }
        self.manifest.write_text(json.dumps(body))

    def args(self, action, *more):
        return [action, "--manifest", str(self.manifest),
                "--repo", str(self.repo), "--state-dir", str(self.state), *more]

    def run_case(self, **kwargs):
        return autodev.execute(self.args(
            "run", "--codex", str(self.codex), "--apply",
            *kwargs.get("extra", [])
        ))

    def test_plan_is_readonly_without_credential_or_state(self):
        with mock.patch.dict(os.environ, {"GH_TOKEN": "private"}, clear=False):
            self.assertEqual(autodev.execute(
                ["plan", "--manifest", str(self.manifest),
                 "--repo", str(self.repo)]), 0)
        self.assertFalse((self.state / "state.json").exists())

    def test_completes_three_stages_with_commits_and_private_ledger(self):
        self.assertEqual(self.run_case(), 0)
        result = json.loads((self.state / "state.json").read_text())
        self.assertEqual(result["index"], 3)
        self.assertEqual(result["phase"], "complete")
        self.assertEqual(len(result["commits"]), 3)
        self.assertEqual(result["head"], git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(len(git(self.repo, "log", "--pretty=%s").splitlines()), 4)
        self.assertEqual((self.state / "state.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.state / "supervisor.lock").stat().st_mode & 0o777, 0o600)
        self.assertNotIn("Add regression test", (self.state / "state.json").read_text())
        with self.assertRaises(autodev.Refused):
            self.run_case()

    def test_resume_from_verified_checkpoint_without_duplicate_stage(self):
        self.assertEqual(self.run_case(extra=["--max-stages", "1"]), 0)
        first = json.loads((self.state / "state.json").read_text())
        self.assertEqual(first["index"], 1)
        self.assertEqual(first["phase"], "ready")
        self.assertEqual(len(first["commits"]), 1)
        first_sha = first["commits"][0]["sha"]
        self.assertEqual(self.run_case(extra=["--max-stages", "2"]), 0)
        last = json.loads((self.state / "state.json").read_text())
        self.assertEqual(last["index"], 3)
        self.assertEqual(last["phase"], "complete")
        self.assertEqual(len(last["commits"]), 3)
        self.assertEqual(last["commits"][0]["sha"], first_sha)
        self.assertEqual(len(git(self.repo, "log", "--pretty=%s").splitlines()), 4)

    def test_stage_budget_does_not_skip_or_publish_pending_tasks(self):
        with self.assertRaises(autodev.Refused):
            self.run_case(extra=["--max-stages", "0"])
        self.assertFalse((self.state / "state.json").exists())
        with self.assertRaises(autodev.Refused):
            self.run_case(extra=["--max-stages", "6"])
        self.assertFalse((self.state / "state.json").exists())
        with self.assertRaises(autodev.Refused):
            self.run_case(extra=["--max-stages", "1", "--publish-draft"])
        partial = json.loads((self.state / "state.json").read_text())
        self.assertEqual(partial["index"], 1)
        self.assertEqual(partial["phase"], "ready")

    def test_started_attempt_never_retried_after_failure(self):
        self.write_manifest(prompts=[
            "Add regression test stage 0", "simulate-crash at stage one",
            "Add regression test stage 2",
        ])
        with self.assertRaises(autodev.Refused):
            self.run_case()
        receipt = json.loads((self.state / "state.json").read_text())
        self.assertEqual(receipt["index"], 1)
        self.assertEqual(receipt["phase"], "started")
        self.assertEqual(len(receipt["commits"]), 1)
        with self.assertRaises(autodev.Refused):
            self.run_case()

    def test_source_scope_cannot_change_untracked_secret(self):
        self.write_manifest(prompts=[
            "out-of-scope modification attempt", "Add regression test stage 1",
            "Add regression test stage 2",
        ])
        # Scratch may contain private.txt produced by the fake agent, but
        # the real checkout must remain clean of such source mutations.
        with self.assertRaises(autodev.Refused):
            self.run_case()
        self.assertFalse((self.repo / "private.txt").exists())
        receipt = json.loads((self.state / "state.json").read_text())
        self.assertEqual(receipt["phase"], "started")
        self.assertEqual(receipt["index"], 0)

    def test_rejects_invalid_schema_and_hidden_file_scope(self):
        for count in [0, 1, 2, 6]:
            self.write_manifest(count=count)
            with self.assertRaises(autodev.Refused):
                autodev.manifest(self.manifest)
        self.write_manifest(count=3, paths=[".github/unsafe.yml"])
        with self.assertRaises(autodev.Refused):
            autodev.manifest(self.manifest)
        self.write_manifest(count=3, paths=["deploy/run.sh"])
        with self.assertRaises(autodev.Refused):
            autodev.manifest(self.manifest)
        self.write_manifest(count=3, paths=["../escape.py"])
        with self.assertRaises(autodev.Refused):
            autodev.manifest(self.manifest)

    def test_rejects_untrusted_checkout_and_private_dir(self):
        self.write_manifest()
        git(self.repo, "switch", "-qc", "unrelated")
        with self.assertRaises(autodev.Refused):
            self.run_case()
        git(self.repo, "switch", "-q", "autodev/safe-pilot")
        self.state.chmod(0o755)
        with self.assertRaises(autodev.Refused):
            self.run_case()
        self.state.chmod(0o700)

    def test_requires_explicit_execution_and_codex_binary(self):
        with self.assertRaises(autodev.Refused):
            autodev.execute(self.args("run", "--codex", str(self.codex)))
        with self.assertRaises(autodev.Refused):
            autodev.execute(self.args("run", "--codex", "/does/not/exist", "--apply"))
        self.assertFalse((self.state / "state.json").exists())

    def test_python_syntax_gate_denies_before_worktree_mutation(self):
        self.codex.write_text(
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            "Path('small.py').write_text('def broken(:\\n')\n"
        )
        self.codex.chmod(0o700)
        with self.assertRaises(autodev.Refused):
            self.run_case()
        self.assertEqual((self.repo / "small.py").read_text(), "answer = 42\n")
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        receipt = json.loads((self.state / "state.json").read_text())
        self.assertEqual(receipt["phase"], "started")
        self.assertEqual(receipt["index"], 0)

    def test_unsafe_checkpoint_symlink_and_permissions_refuse(self):
        receipt = self.state / "state.json"
        outside = self.base / "outside"
        outside.write_text('{"schema":1}')
        receipt.symlink_to(outside)
        with self.assertRaises(autodev.Refused):
            autodev.load_state(self.state)
        receipt.unlink()
        receipt.write_text('{"schema":1}')
        receipt.chmod(0o644)
        with self.assertRaises(autodev.Refused):
            autodev.load_state(self.state)

    def test_rust_tasks_require_explicit_formatter(self):
        (self.repo / "lib.rs").write_text("fn x() {}")
        git(self.repo, "add", "lib.rs")
        git(self.repo, "commit", "-qm", "add Rust fixture")
        self.head = git(self.repo, "rev-parse", "HEAD")
        self.write_manifest(paths=["lib.rs"])
        self.codex.write_text(
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            "Path('lib.rs').write_text('fn x() { }\\n')\n"
        )
        self.codex.chmod(0o700)
        with self.assertRaises(autodev.Refused):
            self.run_case()
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual(json.loads((self.state / "state.json").read_text())["phase"],
                         "started")

    def test_manifest_swap_blocks_resuming_or_publishing(self):
        self.assertEqual(self.run_case(), 0)
        self.write_manifest(prompts=[
            "Replaced prompt one", "Replaced prompt two", "Replaced prompt three",
        ])
        with self.assertRaises(autodev.Refused):
            autodev.execute(self.args("publish", "--apply"))
        with self.assertRaises(autodev.Refused):
            self.run_case()

    def test_lock_contention_does_not_launch(self):
        fd = os.open(self.state / "supervisor.lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(autodev.Refused):
                self.run_case()
        finally:
            os.close(fd)

    def test_secret_environment_not_forwarded(self):
        # The model subprocess is fake and dumps its inherited environment into
        # an explicitly allowlisted file, which the supervisor then commits.
        self.codex.write_text(
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            "import os\n"
            "Path('small.py').write_text('# GH='"
            " + str('GH_TOKEN' in os.environ) + ' SSH='"
            " + str('SSH_AUTH_SOCK' in os.environ) + '\\n')\n"
        )
        self.codex.chmod(0o700)
        with mock.patch.dict(os.environ, {
            "GH_TOKEN": "private", "GITHUB_TOKEN": "private",
            "SSH_AUTH_SOCK": "/tmp/not-a-real-agent",
        }):
            with self.assertRaises(autodev.Refused):
                # second stage repeats the same output -> no-change fail closed
                self.run_case()
        output = (self.repo / "small.py").read_text()
        self.assertIn("GH=False SSH=False", output)


if __name__ == "__main__":
    unittest.main()
