"""Offline Git fixtures; no model, SSH, GitHub or deployed snapshot calls."""
import hashlib
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import repository_workflow as workflow


class RepositoryWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Offline test")
        self.git("config", "user.email", "offline@example.invalid")
        self.git("remote", "add", "origin", workflow.CANONICAL)
        (self.root / "file.txt").write_text("accepted\n")
        (self.root / "bin").mkdir()
        (self.root / "bin/tool").write_text("fixture (never executed)\n")
        (self.root / "bin/tool").chmod(0o755)
        self.commit("accepted")
        self.sha = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.sha)
        self.target = self.base / "task"
        self.snapshot = self.base / "snapshot"

    def git(self, *args):
        return workflow.git(self.root, *args)

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "-m", message)

    def preserved(self):
        return (self.git("rev-parse", "HEAD"), self.git("branch", "--show-current"),
                self.git("diff"), self.git("diff", "--cached"), workflow.changes(self.root),
                (self.root / "file.txt").read_bytes())

    def start(self):
        with patch.object(workflow, "remote_main", return_value=self.sha), \
                patch.object(workflow, "fetch_main") as fetch:
            result = workflow.start(self.root, "chore/offline-task", self.target, self.sha)
            fetch.assert_called_once_with(self.root)
            return result

    def export(self):
        return workflow.export(self.root, self.sha, self.snapshot)

    def verify_snapshot(self, result, sha=None):
        return workflow.verify_snapshot(self.snapshot, sha or self.sha, result["receipt_sha256"])

    def snapshot_state(self):
        return {p.relative_to(self.snapshot).as_posix():
                (stat.S_IMODE(p.stat().st_mode), p.stat().st_mtime_ns, p.stat().st_ctime_ns,
                 p.read_bytes() if p.is_file() else None)
                for p in [self.snapshot, *self.snapshot.rglob("*")]}

    def test_inspection_read_only_and_offline(self):
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in self.root.rglob("*") if p.is_file()}
        with patch.object(workflow, "remote_main", side_effect=AssertionError("network")), \
                patch.object(workflow, "fetch_main", side_effect=AssertionError("fetch")):
            first = workflow.inspect(self.root)
            self.assertEqual(first, workflow.inspect(self.root))
        self.assertEqual(first["local_only_main_only"], [0, 0])
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns)
                                 for p in self.root.rglob("*") if p.is_file()})

    def test_git_redirection_hooks_and_fsmonitor_cannot_affect_task(self):
        marker = self.base / "unexpected-execution"
        hook = self.root / ".git/hooks/post-checkout"
        hook.write_text(f"#!/bin/sh\ntouch '{marker}'\n")
        hook.chmod(0o755)
        self.git("config", "core.fsmonitor", str(hook))
        with patch.dict(os.environ, {"GIT_DIR": str(self.base / "missing"),
                                     "GIT_WORK_TREE": str(self.base / "missing"),
                                     "GIT_INDEX_FILE": str(self.base / "private-index")}):
            self.assertEqual(workflow.inspect(self.root)["head"], self.sha)
            self.start()
        self.assertFalse(marker.exists())
        self.assertFalse((self.base / "private-index").exists())

    def test_dirty_diverged_checkout_preserved_by_start(self):
        (self.root / "file.txt").write_text("local branch\n")
        self.commit("local")
        self.git("checkout", "-b", "remote-fixture", self.sha)
        (self.root / "file.txt").write_text("new main\n")
        self.commit("remote")
        self.sha = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.sha)
        self.git("checkout", "main")
        (self.root / "file.txt").write_text("precious staged\n")
        self.git("add", "file.txt")
        (self.root / "file.txt").write_text("precious unstaged\n")
        (self.root / "untracked").write_text("precious untracked\n")
        before = self.preserved()
        self.assertEqual(workflow.inspect(self.root)["local_only_main_only"], [1, 1])
        result = self.start()
        self.assertEqual(result["head"], self.sha)
        self.assertEqual(result["changes"], [])
        self.assertEqual(before, self.preserved())
        self.assertEqual((self.root / "untracked").read_text(), "precious untracked\n")

    def test_existing_destination_and_branch_refused_repeatedly(self):
        self.start()
        before = self.preserved()
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, "Destination"):
                self.start()
        self.target = self.base / "another"
        with self.assertRaisesRegex(ValueError, "branch already exists"):
            self.start()
        self.assertFalse(self.target.exists())
        self.assertEqual(before, self.preserved())

    def test_unexpected_remote_refused_without_fetch_or_write(self):
        self.git("remote", "set-url", "origin", "https://example.invalid/wrong.git")
        with patch.object(workflow, "fetch_main") as fetch, \
                patch.object(workflow, "remote_main") as remote:
            with self.assertRaisesRegex(ValueError, "origin"):
                workflow.start(self.root, "chore/offline-task", self.target, self.sha)
            fetch.assert_not_called()
            remote.assert_not_called()
        self.assertFalse(self.target.exists())

    def test_multiple_origin_urls_refused(self):
        self.git("config", "--add", "remote.origin.url", workflow.CANONICAL)
        with self.assertRaisesRegex(ValueError, "ambiguous origin"):
            self.start()
        self.assertFalse(self.target.exists())

    def test_network_overrides_refused_without_remote_execution(self):
        self.git("config", "url.ext::unsafe.insteadOf", "https://github.com/")
        with self.assertRaisesRegex(ValueError, "overrides"):
            workflow.start(self.root, "chore/offline-task", self.target, self.sha)
        self.assertFalse(self.target.exists())

    def test_real_local_fetch_does_not_move_current_branch(self):
        remote = self.base / "remote.git"
        self.git("clone", "--bare", str(self.root), str(remote))
        (self.root / "file.txt").write_text("dirty remains\n")
        before = self.preserved()
        def local_network(root, *args):
            # Substitute only transport: exercise real ls-remote/fetch offline.
            args = tuple(str(remote) if arg == workflow.CANONICAL else arg for arg in args)
            return workflow.git(root, *args)

        with patch.object(workflow, "network_git", side_effect=local_network):
            result = workflow.start(self.root, "chore/offline-task", self.target, self.sha)
        self.assertEqual(result["head"], self.sha)
        self.assertEqual(before, self.preserved())

    def test_main_changes_before_or_during_fetch(self):
        before = self.preserved()
        for values in [["a" * 40], [self.sha, "a" * 40]]:
            with patch.object(workflow, "remote_main", side_effect=values), \
                    patch.object(workflow, "fetch_main"):
                with self.assertRaisesRegex(ValueError, "main changed"):
                    workflow.start(self.root, "chore/offline-task", self.target, self.sha)
            self.assertFalse(self.target.exists())
            self.assertEqual(before, self.preserved())

    def test_fetch_failure_preserves_checkout(self):
        before = self.preserved()
        with patch.object(workflow, "remote_main", return_value=self.sha), \
                patch.object(workflow, "fetch_main", side_effect=ValueError("interrupted fetch")):
            with self.assertRaisesRegex(ValueError, "interrupted"):
                workflow.start(self.root, "chore/offline-task", self.target, self.sha)
        self.assertEqual(before, self.preserved())
        self.assertFalse(self.target.exists())

    def test_interrupted_worktree_operation_preserved_no_cleanup(self):
        original = workflow.git

        def interrupted(root, *args, **kwargs):
            if args[:2] == ("worktree", "add"):
                self.target.mkdir()
                (self.target / "partial").write_text("retained")
                raise ValueError("interrupted worktree add")
            return original(root, *args, **kwargs)

        with patch.object(workflow, "git", side_effect=interrupted):
            with self.assertRaisesRegex(ValueError, "interrupted"):
                self.start()
        with self.assertRaisesRegex(ValueError, "Destination"):
            self.start()
        self.assertEqual((self.target / "partial").read_text(), "retained")

    def test_unsafe_paths_symlinks_and_branch_states(self):
        link = self.base / "link"
        link.symlink_to(self.base, target_is_directory=True)
        for path in [Path("relative"), Path("/"), self.root / "nested", link / "new",
                     self.base / "missing/new", self.base / ".." / "escape",
                     self.root / ".git/new"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                workflow.start(self.root, "chore/offline-task", path, self.sha)
        for branch in ["main", "-b", "chore/a;touch", "chore/../escape"]:
            with self.subTest(branch=branch), self.assertRaises(ValueError):
                workflow.start(self.root, branch, self.target, self.sha)
        with self.assertRaises(ValueError):
            workflow.inspect(self.root / "bin")
        self.git("checkout", "--detach", self.sha)
        self.assertEqual(self.start()["branch"], "chore/offline-task")

    def test_verify_sha_dirty_untracked_and_ambiguous_sha(self):
        self.assertTrue(workflow.verify(self.root, self.sha)["clean"])
        for sha in ["main", self.sha[:8], "0" * 40]:
            with self.assertRaises(ValueError):
                workflow.verify(self.root, sha)
        (self.root / "untracked").write_text("keep")
        with self.assertRaisesRegex(ValueError, "dirty"):
            workflow.verify(self.root, self.sha)
        (self.root / "untracked").unlink()
        (self.root / "file.txt").write_text("dirty")
        with self.assertRaisesRegex(ValueError, "dirty"):
            workflow.verify(self.root, self.sha)

    def test_export_verify_no_git_dirty_source_excluded_and_idempotent_refusal(self):
        (self.root / "private-untracked").write_text("never copied")
        (self.root / "file.txt").write_text("uncommitted not exported")
        result = self.export()
        self.assertFalse((self.snapshot / ".git").exists())
        self.assertFalse((self.snapshot / "private-untracked").exists())
        self.assertEqual((self.snapshot / "file.txt").read_text(), "accepted\n")
        with patch.object(subprocess, "run", side_effect=AssertionError("external command")):
            first = self.verify_snapshot(result)
            self.assertEqual(first, self.verify_snapshot(result))
        with self.assertRaisesRegex(ValueError, "Destination"):
            self.export()

    def test_source_not_on_main_and_symlink_source_refused_before_writes(self):
        (self.root / "extra").write_text("unaccepted")
        self.commit("unaccepted")
        with self.assertRaises(ValueError):
            workflow.export(self.root, self.git("rev-parse", "HEAD"), self.snapshot)
        (self.root / "linked").symlink_to("file.txt")
        self.commit("linked")
        self.sha = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.sha)
        with self.assertRaisesRegex(ValueError, "Unsafe source"):
            self.export()
        self.assertFalse(self.snapshot.exists())

    def test_submodule_source_refused(self):
        self.git("update-index", "--add", "--cacheinfo", f"160000,{self.sha},module")
        self.git("commit", "-m", "submodule fixture (never fetched)")
        self.sha = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.sha)
        with self.assertRaisesRegex(ValueError, "Unsafe source"):
            self.export()
        self.assertFalse(self.snapshot.exists())

    def test_missing_cached_main_stays_unknown(self):
        self.git("update-ref", "-d", "refs/remotes/origin/main")
        result = workflow.inspect(self.root)
        self.assertIsNone(result["cached_main"])
        self.assertIsNone(result["local_only_main_only"])
        with self.assertRaises(ValueError):
            self.export()
        self.assertFalse(self.snapshot.exists())

    def test_missing_snapshot_and_sha_receipt_mismatches(self):
        with self.assertRaises(ValueError):
            workflow.verify_snapshot(self.snapshot, self.sha, "0" * 64)
        result = self.export()
        with self.assertRaisesRegex(ValueError, "identity"):
            self.verify_snapshot(result, "0" * 40)
        with self.assertRaisesRegex(ValueError, "integrity"):
            workflow.verify_snapshot(self.snapshot, self.sha, "0" * 64)
        with self.assertRaises(ValueError):
            workflow.verify_snapshot(self.snapshot, self.sha, "short")

    def test_snapshot_drift_modes_symlinks_hardlinks_extra_files_and_dirs(self):
        result = self.export()
        original = (self.snapshot / "file.txt").read_bytes()
        (self.snapshot / "file.txt").write_text("changed")
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.verify_snapshot(result)
        (self.snapshot / "file.txt").write_bytes(original)
        (self.snapshot / "bin/tool").chmod(0o644)
        with self.assertRaisesRegex(ValueError, "mode"):
            self.verify_snapshot(result)
        (self.snapshot / "bin/tool").chmod(0o755)
        (self.snapshot / "extra").symlink_to(self.root / "file.txt")
        with self.assertRaisesRegex(ValueError, "symlinked"):
            self.verify_snapshot(result)
        (self.snapshot / "extra").unlink()
        (self.snapshot / "extra").hardlink_to(self.snapshot / "file.txt")
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.verify_snapshot(result)
        (self.snapshot / "extra").unlink()
        for directory in [False, True]:
            extra = self.snapshot / "extra"
            extra.mkdir() if directory else extra.write_text("unexpected")
            with self.assertRaisesRegex(ValueError, "inventory"):
                self.verify_snapshot(result)
            extra.rmdir() if directory else extra.unlink()
        self.verify_snapshot(result)

    def test_receipt_hardlink_refused(self):
        result = self.export()
        (self.base / "receipt-link").hardlink_to(self.snapshot / workflow.RECEIPT)
        with self.assertRaisesRegex(ValueError, "Invalid snapshot receipt"):
            self.verify_snapshot(result)

    def test_snapshot_exact_file_permissions_rejected_without_repair(self):
        result = self.export()
        for name, expected, modes in [
                ("file.txt", 0o644, [0o666, 0o640, 0o600, 0o2644, 0o4644]),
                ("bin/tool", 0o755, [0o777, 0o750, 0o711, 0o4755])]:
            for mode in modes:
                with self.subTest(name=name, mode=oct(mode)):
                    (self.snapshot / name).chmod(mode)
                    before = self.snapshot_state()
                    with patch.object(Path, "chmod", side_effect=AssertionError("permission repair")), \
                            patch.object(subprocess, "run", side_effect=AssertionError("subprocess")):
                        with self.assertRaisesRegex(ValueError, "mode"):
                            self.verify_snapshot(result)
                    self.assertEqual(before, self.snapshot_state())
                    (self.snapshot / name).chmod(expected)
        self.verify_snapshot(result)

    def test_unsafe_snapshot_root_and_subdirectories_refused_read_only(self):
        result = self.export()
        for directory in [self.snapshot, self.snapshot / "bin"]:
            expected = stat.S_IMODE(directory.stat().st_mode)
            for mode in [0o777, 0o770, 0o707]:
                with self.subTest(directory=directory.name, mode=oct(mode)):
                    directory.chmod(mode)
                    before = self.snapshot_state()
                    with patch.object(Path, "chmod", side_effect=AssertionError("permission repair")):
                        with self.assertRaisesRegex(ValueError, "directory permissions"):
                            self.verify_snapshot(result)
                    self.assertEqual(before, self.snapshot_state())
                    directory.chmod(expected)
        self.verify_snapshot(result)

    def test_safe_directory_permission_differences_are_read_only(self):
        result = self.export()
        for mode in [0o700, 0o750, 0o755]:
            self.snapshot.chmod(mode)
            (self.snapshot / "bin").chmod(mode)
            before = self.snapshot_state()
            with patch.object(Path, "chmod", side_effect=AssertionError("permission repair")), \
                    patch.object(subprocess, "run", side_effect=AssertionError("subprocess")):
                self.verify_snapshot(result)
            self.assertEqual(before, self.snapshot_state())

    def test_snapshot_receipt_permissions_exact_and_read_only(self):
        result = self.export()
        path = self.snapshot / workflow.RECEIPT
        for mode in [0o666, 0o600, 0o640, 0o4644]:
            with self.subTest(mode=oct(mode)):
                path.chmod(mode)
                before = self.snapshot_state()
                with patch.object(Path, "chmod", side_effect=AssertionError("permission repair")):
                    with self.assertRaisesRegex(ValueError, "Invalid snapshot receipt"):
                        self.verify_snapshot(result)
                self.assertEqual(before, self.snapshot_state())
                path.chmod(0o644)

    def test_export_modes_match_verifier_under_permissive_and_restrictive_umasks(self):
        nested = self.root / "nested/deep/file.txt"
        nested.parent.mkdir(parents=True)
        nested.write_text("nested fixture\n")
        self.commit("nested fixture")
        self.sha = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.sha)
        for mask in [0o000, 0o022, 0o077, 0o777]:
            with self.subTest(umask=oct(mask)):
                self.snapshot = self.base / f"snapshot-{mask:o}"
                previous = os.umask(mask)
                try:
                    result = self.export()
                    self.verify_snapshot(result)
                finally:
                    os.umask(previous)
                for path in [self.snapshot, self.snapshot / "bin", self.snapshot / "nested",
                             self.snapshot / "nested/deep"]:
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
                for name, mode in [("file.txt", 0o644), ("bin/tool", 0o755),
                                   ("nested/deep/file.txt", 0o644), (workflow.RECEIPT, 0o644)]:
                    self.assertEqual(stat.S_IMODE((self.snapshot / name).stat().st_mode), mode)

    def test_interrupted_receipt_permission_normalization_preserved(self):
        original = Path.chmod

        def interrupted(path, *args, **kwargs):
            if path.name == workflow.RECEIPT:
                raise OSError("interrupted receipt permissions")
            return original(path, *args, **kwargs)

        previous = os.umask(0o077)
        try:
            with patch.object(Path, "chmod", interrupted), self.assertRaises(OSError):
                self.export()
        finally:
            os.umask(previous)
        raw = (self.snapshot / workflow.RECEIPT).read_bytes()
        result = {"receipt_sha256": hashlib.sha256(raw).hexdigest()}
        before = self.snapshot_state()
        with self.assertRaisesRegex(ValueError, "Invalid snapshot receipt"):
            self.verify_snapshot(result)
        with self.assertRaisesRegex(ValueError, "Destination"):
            self.export()
        self.assertEqual(before, self.snapshot_state())

    def test_interrupted_export_never_overwritten(self):
        original = Path.open

        def interrupted(path, *args, **kwargs):
            if path.name == workflow.RECEIPT:
                raise OSError("interrupted before receipt")
            return original(path, *args, **kwargs)

        with patch.object(Path, "open", interrupted), self.assertRaises(OSError):
            self.export()
        self.assertTrue((self.snapshot / "file.txt").is_file())
        self.assertFalse((self.snapshot / workflow.RECEIPT).exists())
        with self.assertRaises(ValueError):
            workflow.verify_snapshot(self.snapshot, self.sha, "0" * 64)
        with self.assertRaisesRegex(ValueError, "Destination"):
            self.export()

    def test_unsafe_receipt_entry_refused(self):
        result = self.export()
        path = self.snapshot / workflow.RECEIPT
        manifest = json.loads(path.read_bytes())
        manifest["files"]["../escape"] = manifest["files"].pop("file.txt")
        raw = workflow.encode(manifest)
        path.write_bytes(raw)
        result["receipt_sha256"] = hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(ValueError, "Unsafe snapshot"):
            self.verify_snapshot(result)


if __name__ == "__main__":
    unittest.main()
