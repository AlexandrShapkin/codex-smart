import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import benchmark_grading_backend as backend


class GradingBackendTests(unittest.TestCase):
    def test_contract_is_exact_and_known_vulnerability_is_explicit(self):
        contract = backend.load_contract()
        self.assertEqual(contract["backend_id"], "ubuntu-bubblewrap-0.11.1-constrained-v1")
        self.assertEqual(contract["version"], "bubblewrap 0.11.1")
        self.assertTrue(contract["known_upstream_issue"]["affected"])
        self.assertEqual(contract["known_upstream_issue"]["id"], "CVE-2026-87766")
        self.assertFalse(contract["known_upstream_issue"]["untrusted_root_bind_allowed"])
        self.assertFalse(contract["known_upstream_issue"]["filesystem_ops_after_untrusted_bind_allowed"])
        self.assertEqual(contract["accepted_evidence_sha256"], ["af25f5138a442a8ea1e52f09c81458a16f57e756f6502af8b49fc1be1b93dbec"])

    def test_probe_plan_places_untrusted_workspace_last(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            probe = root / "probe.py"
            probe.write_text("pass\n")
            work = root / "work"
            work.mkdir()
            ops = backend.probe_mount_plan(probe, work)
            self.assertTrue(backend.validate_mount_plan(ops))
            self.assertEqual(ops[-1].trust, "untrusted")
            self.assertEqual(ops[-1].option, "--bind")
            self.assertEqual(ops[-1].destination, "/work")
            argv = backend.render_mount_plan(ops)
            self.assertEqual(argv[-3:], ["--bind", str(work), "/work"])
            tmpfs_index = argv.index("--tmpfs")
            self.assertEqual(argv[tmpfs_index - 2:tmpfs_index], ["--size", "16777216"])

    def test_untrusted_root_bind_is_rejected(self):
        ops = [backend.MountOp("--bind", "/", "/synthetic", "untrusted")]
        with self.assertRaises(ValueError):
            backend.validate_mount_plan(ops)

    def test_filesystem_operation_after_untrusted_bind_is_rejected(self):
        ops = [
            backend.MountOp("--bind", "/work", "/synthetic", "untrusted"),
            backend.MountOp("--dir", "/work/after"),
        ]
        with self.assertRaises(ValueError):
            backend.validate_mount_plan(ops)

    def test_untrusted_destination_drift_is_rejected(self):
        ops = [backend.MountOp("--bind", "/workspace", "/synthetic", "untrusted")]
        with self.assertRaises(ValueError):
            backend.validate_mount_plan(ops)

    def test_untrusted_read_only_bind_is_rejected(self):
        ops = [backend.MountOp("--ro-bind", "/work", "/synthetic", "untrusted")]
        with self.assertRaises(ValueError):
            backend.validate_mount_plan(ops)

    def test_unreviewed_mount_operation_is_rejected(self):
        ops = [backend.MountOp("--overlay", "/work", "/synthetic", "untrusted")]
        with self.assertRaises(ValueError):
            backend.validate_mount_plan(ops)

    def test_evidence_reference_is_typed_and_identity_pinned(self):
        c = backend.load_contract()
        payload = {
            "backend_id": c["backend_id"],
            "executable_sha256": c["executable_sha256"],
            "package_version": c["package_version"],
            "apparmor_profile_sha256": c["apparmor_profile_sha256"],
            "apparmor_userns_restriction_enabled": True,
            "setuid_present": False,
            "unsafe_control_host_escape_observed": True,
            "constrained_control_host_escape_observed": False,
            "constrained_control_completed": True,
            "mount_plan_static_guard": True,
        }
        ref = backend.evidence_reference(payload)
        self.assertEqual(len(ref), 64)
        self.assertEqual(ref, hashlib.sha256(
            __import__("json").dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest())
        bad = dict(payload, constrained_control_host_escape_observed=1)
        with self.assertRaises(ValueError):
            backend.evidence_reference(bad)

    def test_candidate_evidence_requires_security_outcomes(self):
        record = backend.load_candidate_evidence()
        self.assertEqual(
            record["evidence_reference"],
            "af25f5138a442a8ea1e52f09c81458a16f57e756f6502af8b49fc1be1b93dbec",
        )
        import json
        broken = json.loads(backend.CANDIDATE_EVIDENCE.read_text())
        broken["candidate"]["constrained_control_host_escape_observed"] = True
        broken["evidence_reference"] = backend.evidence_reference(broken["candidate"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.json"
            path.write_text(json.dumps(broken))
            with self.assertRaises(ValueError):
                backend.load_candidate_evidence(path)

    def test_candidate_evidence_does_not_verify_without_host_receipt(self):
        fake = type("Qualification", (), {})()
        self.assertFalse(backend.representative_contract_verified(fake))


if __name__ == "__main__":
    unittest.main()
