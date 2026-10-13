import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import benchmark_grading_backend as backend
import benchmark_host as host
import benchmark_submission_grading as grading


def verified_host():
    return host.qualify(host.HostQualificationEvidence(
        "benchmark-qualified-host-v1",
        tuple(host.ComponentEvidence(name, "verified", "1" * 64) for name in host.COMPONENTS),
    ))


class SubmissionGradingTests(unittest.TestCase):
    def setUp(self):
        receipt = patch.object(host, "_receipt_reviewed", return_value=True)
        receipt.start()
        self.addCleanup(receipt.stop)

    def test_contract_is_review_required_and_pins_trusted_code(self):
        contract = grading.load_contract()
        self.assertEqual(contract["accepted_evidence_sha256"], [])
        self.assertEqual(contract["qualified_host_receipt"], grading.QUALIFIED_HOST_RECEIPT)
        self.assertEqual(contract["grading_backend_reference"], grading.GRADING_BACKEND_REFERENCE)
        self.assertEqual(contract["trusted_controller_sha256"], grading._sha256(grading.CONTROLLER))
        self.assertEqual(contract["grading_supervisor_sha256"], grading._sha256(grading.SUPERVISOR))
        self.assertEqual(contract["mount_policy"]["verdict_channel"], "private-unix-socket")
        self.assertTrue(contract["submission_copy_policy"]["descriptor_relative"])
        self.assertTrue(contract["submission_copy_policy"]["no_follow"])
        self.assertTrue(contract["submission_copy_policy"]["hardlinks_rejected"])

    def test_public_contract_cannot_verify_before_separate_review(self):
        q = verified_host()
        with patch.object(backend, "representative_contract_verified", return_value=True):
            self.assertFalse(grading.contract_verified(q))

    def test_production_mount_plan_has_one_untrusted_final_bind_and_private_channel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / "runtime"
            controller = root / "controller.py"
            verdict = root / "verdict.sock"
            workspace = root / "work"
            runtime.mkdir()
            workspace.mkdir()
            controller.write_text("pass\n")
            verdict.write_text("")
            ops = backend.production_mount_plan(runtime, controller, verdict, workspace)
        self.assertTrue(backend.validate_mount_plan(ops))
        untrusted = [op for op in ops if op.trust == "untrusted"]
        self.assertEqual(len(untrusted), 1)
        self.assertEqual(untrusted[0].destination, "/work")
        self.assertIs(ops[-1], untrusted[0])
        self.assertTrue(any(op.destination == "/verdict.sock" for op in ops))
        self.assertFalse(any(op.source == "/usr" for op in ops if op.source))

    def test_candidate_rejects_unprepared_runtime_and_bad_policy_without_execution(self):
        q = verified_host()
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(backend, "representative_contract_verified", return_value=True), \
             patch.object(grading, "_execute_isolated_grade") as execute:
            result = grading.grade_candidate_for_review(
                "python-billing", Path(tmp), q, None,
                SimpleNamespace(task_files_immutable=False, allowed_answer_artifacts=()),
            )
            self.assertEqual(result.reason, "grading-runtime-not-prepared")
            runtime = grading.PreparedRuntime(
                Path("/tmp/benchmark-runtime-test"), "1" * 64, (1, 2), ())
            with patch.object(grading, "_runtime_identity_matches", return_value=True):
                result = grading.grade_candidate_for_review(
                    "python-billing", Path(tmp), q, runtime,
                    SimpleNamespace(task_files_immutable="no", allowed_answer_artifacts=()),
                )
            self.assertEqual(result.reason, "submission-policy-mismatch")
            execute.assert_not_called()

    def test_runtime_identity_rejects_replacement(self):
        with tempfile.TemporaryDirectory(dir="/tmp", prefix="benchmark-runtime-test-") as tmp:
            root = Path(tmp)
            for role in ("python", "rust", "go", "libraries", "linker", "grader"):
                (root / role).mkdir()
            info = root.stat()
            roles = tuple(
                (role, (root / role).stat().st_dev, (root / role).stat().st_ino)
                for role in ("python", "rust", "go", "libraries", "linker", "grader"))
            prepared = grading.PreparedRuntime(
                root, "1" * 64, (info.st_dev, info.st_ino), roles)
            self.assertTrue(grading._runtime_identity_matches(prepared))
            old = root / "python"
            retained = root / "python-retained-old-inode"
            old.rename(retained)
            old.mkdir()
            self.assertFalse(grading._runtime_identity_matches(prepared))

    def test_manifest_parsers_reject_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "files.tsv"
            path.write_text("sha256\tsize\tmode\tpath\n" + "0" * 64
                            + "\t1\t0o644\t../escape\n")
            with self.assertRaises(ValueError):
                grading._parse_file_manifest(path)
            path.write_text("sha256\tsize\tmode\tpath\n" + "0" * 64
                            + "\t1\t0o644\ta.txt\n")
            self.assertEqual(set(grading._parse_file_manifest(path)), {"a.txt"})

    def test_user_manager_environment_is_allowlisted(self):
        env = grading._user_manager_env()
        self.assertEqual(set(env), {"PATH", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"})
        self.assertEqual(env["PATH"], "/usr/bin:/bin")
        self.assertTrue(env["XDG_RUNTIME_DIR"].endswith(str(os.getuid())))

    def test_candidate_evidence_validates_and_tamper_is_rejected(self):
        record = grading.load_candidate_evidence()
        self.assertEqual(
            record["evidence_reference"],
            "38da26664d2bf8868677ec96c3875214b84da875ef0058f0faeae62bb15db019",
        )
        self.assertEqual(record["candidate"]["references_passed"], 10)
        self.assertEqual(record["candidate"]["wrong_controls_rejected"], 20)
        self.assertIn("forged-verdict-rejected",
                      record["candidate"]["security_controls_passed"])
        record = json.loads(json.dumps(record))
        record["candidate"]["references_passed"] = 9
        record["evidence_reference"] = grading.evidence_reference(record["candidate"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.json"
            path.write_text(json.dumps(record))
            with self.assertRaises(ValueError):
                grading.load_candidate_evidence(path)


if __name__ == "__main__":
    unittest.main()
