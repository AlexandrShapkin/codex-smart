import json
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

    def test_contract_is_review_required_and_pins_boundary(self):
        c = grading.load_contract()
        self.assertEqual(c["accepted_evidence_sha256"], [])
        self.assertEqual(c["qualified_host_receipt"], grading.QUALIFIED_HOST_RECEIPT)
        self.assertEqual(c["grading_backend_reference"], grading.GRADING_BACKEND_REFERENCE)
        self.assertTrue(c["mount_policy"]["untrusted_bind_last"])
        self.assertFalse(c["mount_policy"]["host_usr_mounted"])
        self.assertEqual(c["resource_limits"]["kill_mode"], "control-group")
        self.assertEqual(c["entrypoint_sha256"],
                         __import__("hashlib").sha256(grading.ENTRYPOINT_SOURCE.encode()).hexdigest())

    def test_candidate_evidence_validates_but_public_contract_waits_for_review(self):
        record = grading.load_candidate_evidence()
        self.assertEqual(record["evidence_reference"],
                         "b2126d5432a8b167cfa03d6d6f857b536948ddcc2d66e60a4b4e096c78f5d0af")
        self.assertEqual(record["candidate"]["references_passed"], 10)
        self.assertEqual(record["candidate"]["wrong_controls_rejected"], 20)
        self.assertIn("hardlink-rejected", record["candidate"]["security_controls_passed"])
        q = verified_host()
        with patch.object(backend, "representative_contract_verified", return_value=True):
            self.assertFalse(grading.contract_verified(q))

    def test_candidate_evidence_tamper_is_rejected(self):
        record = json.loads(grading.CANDIDATE_EVIDENCE.read_text())
        record["candidate"]["references_passed"] = 9
        record["evidence_reference"] = grading.evidence_reference(record["candidate"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.json"
            path.write_text(json.dumps(record))
            with self.assertRaises(ValueError):
                grading.load_candidate_evidence(path)

    def test_mount_plan_has_one_untrusted_final_bind_and_no_host_usr(self):
        runtime = grading.PreparedRuntime(Path("/tmp/benchmark-runtime-test"), "1" * 64)
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "work"
            workspace.mkdir()
            entry = Path(tmp) / "entry.py"
            entry.write_text("pass\n")
            ops = grading._mount_plan(runtime, workspace, entry)
        self.assertTrue(backend.validate_mount_plan(ops))
        untrusted = [op for op in ops if op.trust == "untrusted"]
        self.assertEqual(len(untrusted), 1)
        self.assertEqual(untrusted[0].destination, "/work")
        self.assertIs(ops[-1], untrusted[0])
        self.assertFalse(any(op.source == "/usr" for op in ops if op.source))

    def test_candidate_launcher_uses_systemd_limits_clearenv_and_final_work_bind(self):
        q = verified_host()
        runtime = grading.PreparedRuntime(Path("/tmp/benchmark-runtime-test"), "1" * 64)
        response = SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"schema_version": 1, "quality_pass": True,
                               "policy_or_grader_refusal": False}),
            stderr="",
        )
        original_exists = Path.exists

        def exists(path):
            if str(path).endswith("/bus"):
                return True
            return original_exists(path)

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(backend, "representative_contract_verified", return_value=True), \
             patch.object(backend, "runtime_preflight"), \
             patch.object(Path, "exists", exists), \
             patch.object(grading.subprocess, "run", return_value=response) as run:
            result = grading.grade_candidate_for_review(
                "python-billing", Path(tmp), q, runtime,
                SimpleNamespace(task_files_immutable=False, allowed_answer_artifacts=()),
            )

        self.assertEqual((result.status, result.quality_pass),
                         ("verified", True))
        argv = run.call_args.args[0]
        self.assertEqual(argv[:6],
                         ["/usr/bin/systemd-run", "--user", "--wait", "--collect", "--pipe", "--quiet"])
        self.assertIn("MemoryMax=3G", argv)
        self.assertIn("MemorySwapMax=0", argv)
        self.assertIn("TasksMax=256", argv)
        self.assertIn("RuntimeMaxSec=120s", argv)
        self.assertIn("KillMode=control-group", argv)
        self.assertIn("--clearenv", argv)
        bind = max(i for i, value in enumerate(argv) if value == "--bind")
        self.assertEqual(argv[bind:bind+3], ["--bind", str(Path(tmp)), "/work"])
        filesystem_options = {"--bind", "--ro-bind", "--dir", "--tmpfs", "--proc", "--dev", "--symlink"}
        self.assertFalse(any(value in filesystem_options for value in argv[bind+3:]))
        self.assertEqual(run.call_args.kwargs["env"],
                         {"PATH": "/usr/bin",
                          "XDG_RUNTIME_DIR": f"/run/user/{__import__('os').getuid()}",
                          "DBUS_SESSION_BUS_ADDRESS":
                              f"unix:path=/run/user/{__import__('os').getuid()}/bus"})

    def test_candidate_rejects_unprepared_runtime_and_bad_policy_without_execution(self):
        q = verified_host()
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(backend, "representative_contract_verified", return_value=True), \
             patch.object(grading.subprocess, "run") as run:
            result = grading.grade_candidate_for_review(
                "python-billing", Path(tmp), q, None,
                SimpleNamespace(task_files_immutable=False, allowed_answer_artifacts=()),
            )
            self.assertEqual(result.reason, "grading-runtime-not-prepared")
            result = grading.grade_candidate_for_review(
                "python-billing", Path(tmp), q,
                grading.PreparedRuntime(Path("/tmp/benchmark-runtime-test"), "1"*64),
                SimpleNamespace(task_files_immutable="no", allowed_answer_artifacts=()),
            )
            self.assertEqual(result.reason, "submission-policy-mismatch")
            run.assert_not_called()

    def test_entrypoint_enforces_exploration_immutability_and_special_nodes(self):
        source = grading.ENTRYPOINT_SOURCE
        self.assertIn("immutable task file changed", source)
        self.assertIn("unsafe submission node", source)
        self.assertIn("hardlinked submission file rejected", source)
        self.assertIn("files != expected_all", source)
        self.assertIn("representative_graders", source)

    def test_manifest_parsers_reject_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "files.tsv"
            p.write_text("sha256\tsize\tmode\tpath\n" + "0"*64 + "\t1\t0o644\t../escape\n")
            with self.assertRaises(ValueError):
                grading._parse_file_manifest(p)
            p.write_text("sha256\tsize\tmode\tpath\n" + "0"*64 + "\t1\t0o644\ta.txt\n")
            self.assertEqual(set(grading._parse_file_manifest(p)), {"a.txt"})


if __name__ == "__main__":
    unittest.main()
