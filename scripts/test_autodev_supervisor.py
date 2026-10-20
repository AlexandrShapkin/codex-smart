"""No Codex account, GitHub token, network or service needed for pilot tests."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
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
        (self.source / "scripts").mkdir()
        (self.source / "scripts" / "test_small.py").write_text(
            "import unittest\n"
            "from pathlib import Path\n"
            "class SmallTests(unittest.TestCase):\n"
            "    def test_source(self):\n"
            "        self.assertTrue(Path('small.py').is_file())\n"
        )
        git(self.source, "add", "small.py", "scripts/test_small.py")
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
        self.bwrap = self.base / "fake-bwrap"
        self.bwrap.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "from pathlib import Path\n"
            "args = sys.argv[1:]\n"
            "if '--unshare-all' not in args or '--ro-bind' not in args:\n"
            "    sys.exit(23)\n"
            "try:\n"
            "    source = Path(args[args.index('/workspace') - 1])\n"
            "    text = (source / 'small.py').read_text()\n"
            "except (ValueError, OSError):\n"
            "    sys.exit(24)\n"
            "sys.exit(17 if 'FAIL_PROJECT_VALIDATION' in text else 0)\n"
        )
        self.bwrap.chmod(0o700)

    def write_manifest(self, count=3, prompts=None, paths=None, recipe=None):
        prompts = prompts or [f"Add regression test stage {i}" for i in range(count)]
        body = {
            "schema": 1,
            "repository": "AlexandrShapkin/sandbox",
            "expected_sha": self.head,
            "tasks": [
                {**{"id": f"stage-{i}", "prompt": prompts[i],
                    "paths": paths or ["small.py"]},
                 **({"recipe": recipe} if recipe is not None else {})}
                for i in range(count)
            ]
        }
        self.manifest.write_text(json.dumps(body))

    def args(self, action, *more):
        return [action, "--manifest", str(self.manifest),
                "--repo", str(self.repo), "--state-dir", str(self.state), *more]

    def run_case(self, **kwargs):
        sha = hashlib.sha256(self.codex.read_bytes()).hexdigest()
        bwrap_sha = hashlib.sha256(self.bwrap.read_bytes()).hexdigest()
        return autodev.execute(self.args(
            "run", "--codex", str(self.codex), "--codex-sha256", sha,
            "--test-bwrap", str(self.bwrap),
            "--test-bwrap-sha256", bwrap_sha,
            "--apply", *kwargs.get("extra", [])
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

    def test_project_validation_failure_never_commits_or_advances(self):
        self.write_manifest(prompts=[
            "FAIL_PROJECT_VALIDATION: reject stage zero",
            "Add regression test stage 1", "Add regression test stage 2",
        ])
        with self.assertRaises(autodev.Refused):
            self.run_case()
        state = json.loads((self.state / "state.json").read_text())
        self.assertEqual(state["phase"], "started")
        self.assertEqual(state["index"], 0)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertEqual((self.repo / "small.py").read_text(), "answer = 42\n")

    def test_project_gate_requires_verified_bwrap_before_codex(self):
        sha = hashlib.sha256(self.codex.read_bytes()).hexdigest()
        with self.assertRaises(autodev.Refused):
            autodev.execute(self.args(
                "run", "--codex", str(self.codex), "--codex-sha256", sha,
                "--test-bwrap", str(self.bwrap),
                "--test-bwrap-sha256", "0" * 64, "--apply"
            ))
        self.assertFalse((self.state / "state.json").exists())

    def test_project_gate_never_accepts_unbounded_timeout(self):
        with self.assertRaises(autodev.Refused):
            self.run_case(extra=["--test-seconds", "999"])
        self.assertFalse((self.state / "state.json").exists())

    def test_rust_edit_manifest_requires_cargo_recipe(self):
        self.write_manifest(paths=["lib.rs"])
        with self.assertRaises(autodev.Refused):
            autodev.manifest(self.manifest)
        self.write_manifest(paths=["lib.rs"], recipe="rust-cargo-test")
        data, _ = autodev.manifest(self.manifest)
        self.assertEqual(data["tasks"][0]["recipe"], "rust-cargo-test")
        self.write_manifest(paths=["lib.rs"], recipe="unrestricted-shell")
        with self.assertRaises(autodev.Refused):
            autodev.manifest(self.manifest)

    def test_rust_cargo_gate_uses_fixed_offline_command(self):
        (self.repo / "Cargo.toml").write_text(
            '[package]\nname="sample"\nversion="0.1.0"\nedition="2021"\n'
        )
        expected = hashlib.sha256(self.bwrap.read_bytes()).hexdigest()
        original_is_file = Path.is_file
        def fake_is_file(path):
            if str(path) in ("/usr/bin/cargo", "/usr/bin/rustc", "/usr/bin/gcc"):
                return True
            return original_is_file(path)
        with mock.patch.object(Path, "is_file", fake_is_file), \
             mock.patch.object(autodev, "bounded_codex", return_value=0) as bound:
            autodev.project_test_gate(
                self.repo, self.bwrap, expected, timeout=30,
                recipe="rust-cargo-test",
            )
        invocation = bound.call_args.args[0]
        self.assertIn("--unshare-all", invocation)
        self.assertIn("--offline", invocation)
        self.assertIn("--locked", invocation)
        self.assertIn("--workspace", invocation)
        self.assertIn("/usr/bin/cargo", invocation)
        self.assertNotIn("sh", invocation)

    def test_rejects_cargo_recipe_when_manifest_missing(self):
        expected = hashlib.sha256(self.bwrap.read_bytes()).hexdigest()
        with self.assertRaises(autodev.Refused):
            autodev.project_test_gate(
                self.repo, self.bwrap, expected, timeout=30,
                recipe="rust-cargo-test",
            )

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

    def test_model_timeout_terminates_and_refuses_to_commit(self):
        self.codex.write_text(
            "#!/usr/bin/env python3\n"
            "import time\n"
            "time.sleep(60)\n"
        )
        self.codex.chmod(0o700)
        with self.assertRaises(subprocess.TimeoutExpired):
            autodev.bounded_codex(
                [str(self.codex), "exec", "ignored"],
                cwd=self.repo, env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
                seconds=0.2,
            )
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertFalse((self.state / "state.json").exists())

    def test_explicit_codex_pin_denies_mismatch_before_model_launch(self):
        with self.assertRaises(autodev.Refused):
            autodev.execute(self.args(
                "run", "--codex", str(self.codex),
                "--codex-sha256", "0" * 64, "--apply"
            ))
        self.assertFalse((self.state / "state.json").exists())
        digest = hashlib.sha256(self.codex.read_bytes()).hexdigest()
        self.assertIs(autodev.pinned_executable(self.codex, digest), self.codex)
        self.codex.write_text(self.codex.read_text() + "\n# replaced executable\n")
        with self.assertRaises(autodev.Refused):
            autodev.pinned_executable(self.codex, digest)

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
        self.write_manifest(paths=["lib.rs"], recipe="rust-cargo-test")
        self.codex.write_text(
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            "Path('lib.rs').write_text('fn x() { }\\n')\n"
        )
        self.codex.chmod(0o700)
        with self.assertRaises(autodev.Refused):
            self.run_case()
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        self.assertFalse((self.state / "state.json").exists())

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

    def test_state_directory_must_not_be_checkout_ancestor(self):
        # A 0700 parent can be a valid private directory, but never a
        # supervisor state location when it also contains the worktree.
        with self.assertRaises(autodev.Refused):
            autodev.execute([
                "run", "--apply", "--manifest", str(self.manifest),
                "--repo", str(self.repo), "--state-dir", str(self.base),
                "--codex", str(self.codex),
                "--codex-sha256",
                hashlib.sha256(self.codex.read_bytes()).hexdigest(),
            ])
        self.assertFalse((self.base / "state.json").exists())

    def test_rejects_overlapping_codex_auth_profile(self):
        candidate = self.state / "codex-profile"
        candidate.mkdir(mode=0o700)
        with self.assertRaises(autodev.Refused):
            self.run_case(extra=["--codex-home", str(candidate)])
        self.assertFalse((self.state / "state.json").exists())

    def test_secret_environment_not_forwarded(self):
        # The model subprocess is fake and dumps its inherited environment into
        # an explicitly allowlisted file, which the supervisor then commits.
        self.codex.write_text(
            "#!/usr/bin/env python3\n"
            "from pathlib import Path\n"
            "import os\n"
            "Path('small.py').write_text('# GH='"
            " + str('GH_TOKEN' in os.environ) + ' SSH='"
            " + str('SSH_AUTH_SOCK' in os.environ) + ' CLEANHOME='"
            " + str(Path(os.environ['HOME']) == Path.cwd()) + ' PROFILE='"
            " + str('CODEX_HOME' in os.environ) + '\\n')\n"
        )
        self.codex.chmod(0o700)
        with mock.patch.dict(os.environ, {
            "GH_TOKEN": "private", "GITHUB_TOKEN": "private",
            "SSH_AUTH_SOCK": "/tmp/not-a-real-agent",
            "HOME": "/home/operator-with-private-config",
            "CODEX_HOME": "/home/operator-with-private-config/.codex",
        }):
            with self.assertRaises(autodev.Refused):
                # second stage repeats the same output -> no-change fail closed
                self.run_case()
        output = (self.repo / "small.py").read_text()
        self.assertIn("GH=False SSH=False CLEANHOME=True PROFILE=False", output)


if __name__ == "__main__":
    unittest.main()
