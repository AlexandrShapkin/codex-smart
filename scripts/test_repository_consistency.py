"""Offline real-Git/filesystem audit fixtures, never model/SSH/live GitHub calls."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import repository_consistency as consistency
import repository_workflow as repo
import test_repository_workflow as fixtures


class ConsistencyTests(unittest.TestCase):
    setUp = fixtures.RepositoryWorkflowTests.setUp
    git = fixtures.RepositoryWorkflowTests.git
    commit = fixtures.RepositoryWorkflowTests.commit
    export = fixtures.RepositoryWorkflowTests.export
    preserved = fixtures.RepositoryWorkflowTests.preserved
    snapshot_state = fixtures.RepositoryWorkflowTests.snapshot_state

    def config(self):
        return {"schema": 1, "repositories": [str(self.root)], "snapshots": [],
                "pull_requests": [], "remote_branches": []}

    def audit(self, value=None, **kwargs):
        with patch.object(repo, "fetch_main", side_effect=AssertionError("fetch prohibited")):
            return consistency.audit(self.root, value or self.config(), expected_main=self.sha, **kwargs)

    def source(self, exported, pin="current", host="local"):
        return {"name": "owned-source", "host": host, "role": "agent", "pin": pin,
                "path": str(self.snapshot), "sha": exported["source_sha"],
                "receipt_sha256": exported["receipt_sha256"]}

    def test_repeat_audit_is_offline_and_does_not_change_files_or_git(self):
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns, p.stat().st_mode)
                  for p in self.root.rglob("*") if p.is_file()}
        with patch.object(repo, "remote_main", side_effect=AssertionError("network prohibited")):
            first = self.audit()
            self.assertEqual(first, self.audit())
        self.assertEqual(first["exit_code"], 0)
        self.assertEqual(before, {str(p): (p.read_bytes(), p.stat().st_mtime_ns, p.stat().st_mode)
                                for p in self.root.rglob("*") if p.is_file()})

    def test_dirty_diverged_worktree_remains_unchanged(self):
        self.git("worktree", "add", "-b", "feat/unique", str(self.target), self.sha)
        (self.target / "new.txt").write_text("local-only\n")
        repo.git(self.target, "add", ".")
        repo.git(self.target, "commit", "-m", "local-only")
        (self.root / "remote.txt").write_text("remote-only\n")
        self.commit("new accepted main")
        self.sha = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.sha)
        (self.target / "new.txt").write_text("precious unstaged\n")
        (self.target / "untracked.txt").write_text("precious untracked\n")
        before = repo.checkout_state(self.target)
        report = self.audit()
        branch = next(b for b in report["repositories"][0]["branches"] if b["branch"] == "feat/unique")
        self.assertEqual(branch["local_only_main_only"], [1, 1])
        self.assertEqual(report["exit_code"], 1)
        self.assertIn("local/main-only 1/1", consistency.render(report))
        self.assertEqual(before, repo.checkout_state(self.target))

    def test_squash_merge_requires_content_and_accepted_pr_evidence(self):
        self.git("checkout", "-b", "feat/squashed")
        (self.root / "extra.txt").write_text("public fixture\n")
        self.commit("feature")
        head = self.git("rev-parse", "HEAD")
        self.git("checkout", "main")
        self.git("merge", "--squash", "feat/squashed")
        self.commit("accepted squash")
        self.sha = self.git("rev-parse", "HEAD")
        value = self.config()
        value["pull_requests"] = [{"number": 1, "branch": "feat/squashed", "head": head,
                                   "state": "merged", "merge": self.sha}]
        report = self.audit(value)
        branch = next(b for b in report["repositories"][0]["branches"] if b["branch"] == "feat/squashed")
        self.assertEqual(branch["classification"], "merged-content-equivalent")
        self.assertGreater(branch["local_only_main_only"][0], 0)
        self.assertFalse(branch["cleanup_authorized"])
        value["pull_requests"][0].update(state="open", merge=None)
        branch = next(b for b in self.audit(value)["repositories"][0]["branches"] if b["branch"] == "feat/squashed")
        self.assertEqual(branch["classification"], "open-pr")

    def test_missing_main_and_partial_scope_fail_closed(self):
        report = consistency.audit(self.root)
        self.assertEqual(report["exit_code"], 2)
        self.assertIn("selected-main-unknown", report["problems"])
        self.assertIn("snapshot-scope-undeclared", report["problems"])
        report = consistency.audit(self.root, self.config(), expected_main="a" * 40)
        self.assertEqual(report["exit_code"], 2)
        self.assertIn("main-object-unavailable", report["problems"])

    def test_stale_clone_uses_canonical_object_proof_without_writes_or_fetch(self):
        self.git("checkout", "-b", "feat/squashed")
        (self.root / "new.txt").write_text("public fixture\n")
        self.commit("feature")
        head = self.git("rev-parse", "HEAD")
        historical = self.base / "historical"
        self.git("clone", "--no-local", str(self.root), str(historical))
        repo.git(historical, "remote", "set-url", "origin", repo.CANONICAL)
        self.git("checkout", "main")
        self.git("merge", "--squash", "feat/squashed")
        self.commit("accepted")
        self.sha = self.git("rev-parse", "HEAD")
        value = self.config()
        value["repositories"] = [str(historical)]
        value["pull_requests"] = [{"number":1,"branch":"feat/squashed","head":head,"state":"merged","merge":self.sha}]
        before = repo.checkout_state(historical)
        branch = self.audit(value)["repositories"][0]["branches"][0]
        self.assertEqual(branch["classification"], "merged-content-equivalent")
        self.assertEqual(branch["local_only_main_only"], [1,1])
        self.assertEqual(before, repo.checkout_state(historical))

    def test_historical_pin_is_verified_without_update(self):
        exported = self.export()
        value = self.config()
        value["snapshots"] = [self.source(exported, pin="historical")]
        (self.root / "new.txt").write_text("new main\n")
        self.commit("new main")
        self.sha = self.git("rev-parse", "HEAD")
        before = self.snapshot_state()
        report = self.audit(value)
        self.assertEqual(report["snapshots"][0]["state"], "verified-historical-pin")
        self.assertEqual(before, self.snapshot_state())
        value["snapshots"][0]["pin"] = "current"
        report = self.audit(value)
        self.assertEqual(report["snapshots"][0]["state"], "outdated-current-reference")
        self.assertEqual(report["exit_code"], 1)

    def test_bad_receipt_permission_and_missing_snapshot_preserved(self):
        exported = self.export()
        value = self.config()
        value["snapshots"] = [self.source(exported)]
        value["snapshots"][0]["receipt_sha256"] = "a" * 64
        before = self.snapshot_state()
        self.assertEqual(self.audit(value)["snapshots"][0]["state"], "missing-or-integrity-drift")
        self.assertEqual(before, self.snapshot_state())
        value["snapshots"][0] = self.source(exported)
        (self.snapshot / "file.txt").chmod(0o666)
        self.assertEqual(self.audit(value)["exit_code"], 1)
        self.assertEqual((self.snapshot / "file.txt").stat().st_mode & 0o777, 0o666)
        value["snapshots"][0]["path"] = str(self.base / "missing")
        self.assertEqual(self.audit(value)["snapshots"][0]["state"], "missing-or-integrity-drift")

    def test_remote_host_is_unknown_without_ssh_or_assumed_equivalence(self):
        value = self.config()
        value["snapshots"] = [self.source(self.export(), host="srv0")]
        self.assertEqual(self.audit(value)["exit_code"], 2)
        self.assertEqual(self.audit(value)["snapshots"][0]["state"], "unknown-host-side-verification-required")

    def test_missing_deployment_reference_reports_partial_not_invented_identity(self):
        value = self.config()
        source = self.source(self.export())
        source.update(receipt_sha256=None, pin="unknown")
        value["snapshots"] = [source]
        report = self.audit(value)
        self.assertEqual(report["exit_code"], 2)
        self.assertEqual(report["snapshots"][0]["state"], "missing-deployment-reference")

    def test_unaccepted_source_cannot_be_called_historical(self):
        value = self.config()
        source = self.source(self.export(), pin="historical")
        source["sha"] = "a" * 40
        value["snapshots"] = [source]
        self.assertEqual(self.audit(value)["exit_code"], 2)

    def test_unsafe_paths_links_duplicate_keys_and_values_refused(self):
        value = self.config()
        value["repositories"] = [str(self.root / "..")]
        with self.assertRaises(ValueError): self.audit(value)
        link = self.base / "linked-root"
        link.symlink_to(self.root)
        value["repositories"] = [str(link)]
        with self.assertRaises(ValueError): self.audit(value)
        file = self.base / "inventory.json"
        file.write_text('{"schema":1,"schema":1}')
        with self.assertRaises(ValueError): consistency.load(file)
        file.write_text('{"schema":NaN}')
        with self.assertRaises(ValueError): consistency.load(file)
        file.write_text(json.dumps(self.config()))
        link = self.base / "linked-inventory"
        link.symlink_to(file)
        with self.assertRaises(ValueError): consistency.load(link)

    def test_concurrent_modification_partial_and_stale_registration(self):
        actual = consistency._observe
        count = 0
        def interrupted(*args):
            nonlocal count
            count += 1
            value = actual(*args)
            if count == 2: value["cached_main"] = None
            return value
        with patch.object(consistency, "_observe", side_effect=interrupted):
            self.assertEqual(self.audit()["exit_code"], 2)
        with patch.object(consistency, "_observe", side_effect=OSError("fixture interrupted audit")):
            self.assertEqual(self.audit()["exit_code"], 2)
        entries = repo.worktrees(self.root)
        entries.append({"worktree": str(self.base / "missing-worktree"), "HEAD": self.sha})
        with patch.object(repo, "worktrees", return_value=entries):
            self.assertEqual(self.audit()["repositories"][0]["worktrees"][1]["state"], "stale-registration")

    def test_repeated_edit_to_already_dirty_file_is_detected(self):
        (self.root / "file.txt").write_text("dirty first\n")
        actual = consistency._observe
        calls = 0
        def changing(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                (self.root / "file.txt").write_text("dirty second, same status entry\n")
            return actual(*args)
        with patch.object(consistency, "_observe", side_effect=changing):
            self.assertEqual(self.audit()["exit_code"], 2)

    def test_explicit_network_changes_and_failures_never_fetch(self):
        with patch.object(repo, "remote_main", side_effect=[self.sha, "a" * 40]):
            report = self.audit(github=True)
        self.assertEqual(report["exit_code"], 2)
        self.assertIn("github-main-changed-during-audit", report["problems"])
        with patch.object(repo, "remote_main", side_effect=ValueError("fixture connectivity unavailable")):
            report = self.audit(github=True)
        self.assertEqual(report["exit_code"], 2)
        self.assertEqual(report["github_freshness"], "unavailable; no host/source equivalence inferred")

    def test_missing_remote_branch_objects_are_partial_not_clean(self):
        value = self.config()
        value["remote_branches"] = [{"branch": "feat/unknown", "head": "a" * 40}]
        report = self.audit(value)
        self.assertEqual(report["exit_code"], 2)
        self.assertIn("remote-branch-object-unavailable", report["problems"])
        self.assertIsNone(report["remote_branches"][0]["local_only_main_only"])

    def test_unmerged_remote_observation_requires_attention_without_cleanup(self):
        self.git("checkout", "-b", "feat/remote-only")
        (self.root / "extra.txt").write_text("remote fixture\n")
        self.commit("unmerged remote")
        head = self.git("rev-parse", "HEAD")
        self.git("checkout", "main")
        self.git("branch", "-D", "feat/remote-only")  # Disposable fixture only.
        value = self.config()
        value["remote_branches"] = [{"branch": "feat/remote-only", "head": head}]
        report = self.audit(value)
        self.assertEqual(report["exit_code"], 1)
        self.assertFalse(report["remote_branches"][0]["cleanup_authorized"])


if __name__ == "__main__":
    unittest.main()
