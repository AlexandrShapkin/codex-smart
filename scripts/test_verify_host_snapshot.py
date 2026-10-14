"""Real disposable inventories; no SSH, tool execution, production writes or models."""
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_repository_workflow as fixtures
import repository_consistency as consistency
import verify_host_snapshot as verify


class HostSnapshotTests(unittest.TestCase):
    setUp = fixtures.RepositoryWorkflowTests.setUp
    git = fixtures.RepositoryWorkflowTests.git
    commit = fixtures.RepositoryWorkflowTests.commit
    export = fixtures.RepositoryWorkflowTests.export
    snapshot_state = fixtures.RepositoryWorkflowTests.snapshot_state

    def runtime(self):
        temporary = tempfile.TemporaryDirectory(prefix="benchmark-runtime-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for role in ("python", "rust", "go", "libraries", "linker", "grader"):
            (root / role).mkdir(mode=0o700)
        (root / "python/tool").write_text("fake; never executed\n")
        contract = copy.deepcopy(verify.grading.load_contract())
        (root / "grader/repository-head.txt").write_text(contract["runtime_repository_head"] + "\n")
        (root / "python/link").symlink_to("tool")
        inventory = self.base / ("inventory-" + root.name)
        inventory.mkdir(mode=0o700)
        files = [p for p in root.rglob("*") if not p.is_symlink() and p.is_file()]
        directories = [p for p in root.rglob("*") if not p.is_symlink() and p.is_dir()]
        (inventory / "runtime-files.tsv").write_text("sha256\tsize\tmode\tpath\n" + "".join(
            f"{verify.grading._sha256(p)}\t{p.stat().st_size}\t{oct(stat.S_IMODE(p.stat().st_mode))}\t{p.relative_to(root)}\n"
            for p in sorted(files)))
        (inventory / "runtime-symlinks.tsv").write_text("mode\tpath\ttarget\n0o777\tpython/link\ttool\n")
        (inventory / "runtime-dirs.tsv").write_text("mode\tpath\n" + "".join(
            f"{oct(stat.S_IMODE(p.stat().st_mode))}\t{p.relative_to(root)}\n" for p in sorted(directories)))
        contract["runtime_inventory"] = {**{
            f"{kind}_manifest_sha256": verify.grading._sha256(inventory / f"runtime-{kind}.tsv")
            for kind in ("files", "symlinks", "dirs")},
            "regular_file_count": len(files), "symlink_count": 1, "directory_count": len(directories)}
        self.candidate = verify.grading.load_candidate_evidence()
        return root, inventory, contract

    def test_source_only_keeps_runtime_unknown_and_permissions_unchanged(self):
        exported = self.export()
        before = self.snapshot_state()
        with patch("subprocess.run", side_effect=AssertionError("no subprocess")), \
                patch("os.chmod", side_effect=AssertionError("no repair")):
            result = verify.inspect(self.snapshot, self.sha, exported["receipt_sha256"])
            self.assertEqual(result, verify.inspect(self.snapshot, self.sha, exported["receipt_sha256"]))
        self.assertEqual(result["exit_code"], 2)
        self.assertEqual(result["runtime"], "NOT VERIFIED")
        self.assertFalse(result["operation_authorized"])
        self.assertEqual(before, self.snapshot_state())

    def test_public_register_cannot_claim_unrecorded_deployments_are_verified(self):
        path = Path(verify.__file__).resolve().parent.parent / "docs/source-register.json"
        with patch.object(consistency.repo, "remote_main", side_effect=AssertionError("offline only")):
            result = consistency.audit(self.root, consistency.load(path), expected_main=self.sha)
        self.assertEqual(result["exit_code"], 2)
        self.assertTrue(result["snapshots"])
        self.assertTrue(all(s["state"] == "missing-deployment-reference" for s in result["snapshots"]))

    def test_missing_source_wrong_sha_and_writable_source_refused(self):
        exported = self.export()
        self.assertEqual(verify.inspect(self.base / "missing", self.sha, exported["receipt_sha256"])["exit_code"], 2)
        self.assertEqual(verify.inspect(self.snapshot, "a" * 40, exported["receipt_sha256"])["exit_code"], 1)
        (self.snapshot / "file.txt").chmod(0o666)
        self.assertEqual(verify.inspect(self.snapshot, self.sha, exported["receipt_sha256"])["exit_code"], 1)
        self.assertEqual((self.snapshot / "file.txt").stat().st_mode & 0o777, 0o666)

    def test_cli_source_only_is_read_only_and_invalid_identity_is_not_echoed(self):
        exported = self.export()
        before = self.snapshot_state()
        result = subprocess.run([sys.executable, "-B", verify.__file__,
            "--snapshot", str(self.snapshot), "--source-sha", self.sha,
            "--receipt-sha256", exported["receipt_sha256"]], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["observed_source"], self.sha)
        self.assertEqual(before, self.snapshot_state())
        invalid = verify.inspect(self.snapshot, "private-invalid-input", exported["receipt_sha256"])
        self.assertEqual(invalid["exit_code"], 1)
        self.assertNotIn("private-invalid-input", json.dumps(invalid))

    def test_runtime_full_bytes_modes_links_and_topology_without_processes(self):
        root, inventory, contract = self.runtime()
        with patch.object(verify.grading, "load_contract", return_value=contract), \
                patch.object(verify.grading, "load_candidate_evidence", return_value=self.candidate), \
                patch("subprocess.run", side_effect=AssertionError("no runtime probes")), \
                patch("os.chmod", side_effect=AssertionError("no repair")):
            result = verify.runtime_identity(root, inventory)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result, verify.runtime_identity(root, inventory))
            (root / "python/tool").write_text("tampered\n")
            with self.assertRaises(ValueError): verify.runtime_identity(root, inventory)

    def test_changed_runtime_manifests_and_symlinked_inventory_refused(self):
        root, inventory, contract = self.runtime()
        with patch.object(verify.grading, "load_contract", return_value=contract):
            path = inventory / "runtime-files.tsv"
            path.write_text(path.read_text() + "\n")
            with self.assertRaises(ValueError): verify.runtime_identity(root, inventory)
            link = self.base / "inventory-link"
            link.symlink_to(inventory)
            with self.assertRaises(ValueError): verify.runtime_identity(root, link)

    def test_runtime_permission_hardlink_and_link_target_drift_refused(self):
        for mutation in ("directory", "hardlink", "link"):
            with self.subTest(mutation=mutation):
                root, inventory, contract = self.runtime()
                if mutation == "directory": (root / "python").chmod(0o777)
                elif mutation == "hardlink": os.link(root / "python/tool", self.base / "extra-link")
                else:
                    (root / "python/link").unlink()  # Disposable fixture only.
                    (root / "python/link").symlink_to("different")
                with patch.object(verify.grading, "load_contract", return_value=contract), self.assertRaises(ValueError):
                    verify.runtime_identity(root, inventory)

    def test_partial_or_untrusted_qualification_cannot_verify_runtime(self):
        exported = self.export()
        result = verify.inspect(self.snapshot, self.sha, exported["receipt_sha256"], runtime_root=str(self.base))
        self.assertEqual(result["exit_code"], 1)
        path = self.base / "qualification.json"
        path.write_text("{}")
        result = verify.inspect(self.snapshot, self.sha, exported["receipt_sha256"],
            runtime_root=str(self.base), inventory_dir=str(self.base), qualification=str(path),
            qualification_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(result["failed_phase"], "qualification")

    def test_saved_qualification_and_runtime_do_not_claim_fresh_host_readiness(self):
        exported = self.export()
        root, inventory, contract = self.runtime()
        qualification = Path(verify.host.__file__).resolve().parent.parent / "benchmarks/qualified-host-receipt-v1.json"
        # Preserve real accepted qualification and implementation checks; only the
        # disposable runtime inventory differs from the production 26,885-file pin.
        actual = verify.runtime_identity
        def runtime(*args):
            with patch.object(verify.grading, "load_contract", return_value=contract), \
                    patch.object(verify.grading, "load_candidate_evidence", return_value=self.candidate):
                return actual(*args)
        with patch.object(verify, "runtime_identity", side_effect=runtime), \
                patch("subprocess.run", side_effect=AssertionError("no process")):
            result = verify.inspect(self.snapshot, self.sha, exported["receipt_sha256"],
                runtime_root=str(root), inventory_dir=str(inventory), qualification=str(qualification),
                qualification_sha256=verify.grading._sha256(qualification))
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["fresh_host_qualification"], "NOT VERIFIED")
        self.assertFalse(result["physical_host_attested"])


if __name__ == "__main__":
    unittest.main()
