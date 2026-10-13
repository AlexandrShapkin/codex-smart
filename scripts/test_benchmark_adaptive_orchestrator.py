"""Fake-only operational integration: no real Codex, SSH, runtimes or submissions execute."""
from contextlib import ExitStack, redirect_stdout
import copy
import io
import json
import os
import shlex
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import benchmark_adaptive_orchestrator as operation

live = operation.live


def resolver(adapter, policy, events=()):
    profile = "strong" if policy["risk"] == "high" else "economy" if policy["task"] == "inspect" else "standard"
    key = {"economy": 10, "standard": 20, "strong": 30}[profile]
    if events == ("quality-pass",):
        return {"schema_version": 1, "state": "completed", "profile": profile,
                "reasoning": "high", "model_key": None, "attempts_started": 1,
                "retries_used": 0, "delegations_used": 0}
    if events:
        key = min(30, key + 10)
        profile = {20: "standard", 30: "strong"}[key]
    return {"schema_version": 1, "state": "ready", "profile": profile,
            "reasoning": "medium" if profile == "economy" else "high", "model_key": key,
            "attempts_started": int(bool(events)), "retries_used": int(bool(events)), "delegations_used": 0}


class FakeBackend(operation.Backend):
    def preflight(self, plan):
        return {"runtime_reference": live.split.RUNTIME_INVENTORY_REFERENCE,
                "adapter_sha256": plan["config"]["agent"]["adapter_sha256"]}


class FakeTransport(operation.Transport):
    def __init__(self, owner):
        self.owner = owner
        self.calls = []
        self.failure = None

    def request(self, plan, action, **payload):
        self.calls.append(action)
        if self.failure == action:
            self.failure = None
            raise operation.OrchestrationRefusal("fake interrupted transport")
        with patch.object(operation, "ROOT", Path(plan["config"]["grader"]["source"]["path"])):
            return operation.host_request({"plan": plan, "action": action, **payload})

    def summary_digest(self, path):
        if self.failure == "receipt":
            raise operation.OrchestrationRefusal("fake missing SSH receipt")
        return live._sha256(path)


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        if getattr(self, "fixture_root", None) is not None:
            self.root = operation.private_directory(self.fixture_root, create=True)
        else:
            self.temporary = tempfile.TemporaryDirectory(prefix="adaptive-operator-test-", dir="/tmp")
            self.addCleanup(self.temporary.cleanup)
            self.root = Path(self.temporary.name)
        repo = self.root / "repository"
        repo.mkdir()
        for args in [("init", "-b", "main"), ("config", "user.name", "Offline fixture"),
                     ("config", "user.email", "offline@example.invalid"),
                     ("remote", "add", "origin", operation.repository.CANONICAL)]:
            operation.repository.git(repo, *args)
        (repo / "public-fixture.txt").write_text("public offline source fixture\n")
        (repo / "scripts").mkdir()
        (repo / "scripts/benchmark_adaptive_orchestrator.py").write_text(
            "def host_request(request):\n    return {'kind': 'fake-bootstrap-test'}\n")
        operation.repository.git(repo, "add", ".")
        operation.repository.git(repo, "commit", "-m", "fixture")
        sha = operation.repository.git(repo, "rev-parse", "HEAD")
        operation.repository.git(repo, "update-ref", "refs/remotes/origin/main", sha)
        sources = {}
        for role in ("agent", "grader"):
            exported = operation.repository.export(repo, sha, self.root / f"source-{role}")
            sources[role] = {"path": exported["snapshot"], "sha": sha,
                             "receipt_sha256": exported["receipt_sha256"]}
        self.adapter = self.root / "adapter"
        self.adapter.write_text("FAKE; must never execute")
        qualification_path = self.root / "qualification.json"
        qualification_path.write_text("{}")
        for name in ("runtime-agent", "runtime-grader", "inventory"):
            (self.root / name).mkdir()
        self.config = {
            "schema_version": 1, "run_id": "fake-operator", "state": str(self.root / "state"),
            "agent": {"source": sources["agent"], "codex": str(self.root / "fake-codex"),
                      "code_mode_host": str(self.root / "fake-host"), "runtime_root": str(self.root / "runtime-agent"),
                      "inventory_dir": str(self.root / "inventory"), "adapter": str(self.adapter),
                      "adapter_sha256": live._sha256(self.adapter)},
            "grader": {"source": sources["grader"], "runtime_root": str(self.root / "runtime-grader"),
                       "inventory_dir": str(self.root / "inventory"),
                       "qualification_evidence": str(qualification_path),
                       "qualification_sha256": live._sha256(qualification_path),
                       "remote_root": str(self.root / "remote")}}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.qualification = SimpleNamespace(status="verified", reference=live.split.GRADING_HOST_RECEIPT)
        self.runtime = SimpleNamespace(inventory_reference=live.split.RUNTIME_INVENTORY_REFERENCE)
        self.stack.enter_context(patch.object(live.host, "load_evidence", return_value=self.qualification))
        self.stack.enter_context(patch.object(live, "_grading_runtime", return_value=self.runtime))
        self.stack.enter_context(patch.object(live, "agent_preflight", return_value=(live.representative.load(), self.runtime, self.adapter)))
        self.stack.enter_context(patch.object(live.adaptive, "_adapter_output", side_effect=resolver))
        self.stack.enter_context(patch.object(live.representative, "command_plan", return_value=[
            "/fake/codex", "exec", "--model", "fake", "-c", 'model_reasoning_effort="medium"']))
        self.current = None
        self.model_calls = 0
        self.grade_calls = 0
        self.fail_quality = False
        self.interrupt_agent_at = None
        self.interrupt_grade_at = None
        self.unknown_tokens = False

        def setup(scenario, workspace):
            self.current = scenario
            live.b.materialize(live.coverage.fixture(scenario)["files"], workspace)

        def execute(argv, workspace, prompt, **kwargs):
            self.model_calls += 1
            if self.model_calls == self.interrupt_agent_at:
                raise KeyboardInterrupt("fake uncertain model attempt")
            live.b.materialize(live.coverage.fixture(self.current)["reference"], workspace)
            trace = {"type": "turn.completed"}
            if not self.unknown_tokens:
                trace["usage"] = {"input_tokens": 3, "output_tokens": 2}
            return {"stdout": json.dumps(trace) + "\n", "stderr": "LOCAL-ONLY-RAW-STDERR",
                    "exit_status": 0, "timeout": False, "duration": 0.01}

        def grade(*args, **kwargs):
            self.grade_calls += 1
            if self.grade_calls == self.interrupt_grade_at:
                raise KeyboardInterrupt("fake interrupted independent grading")
            return SimpleNamespace(status="verified", quality_pass=not self.fail_quality, reason="fake-only")

        self.stack.enter_context(patch.object(live.b, "setup", side_effect=setup))
        self.stack.enter_context(patch.object(live.b, "execute", side_effect=execute))
        # Existing functions captured b.execute in default arguments: inject at the runner boundary.
        original_initial, original_retry = live.run_initial, live.run_retry
        self.stack.enter_context(patch.object(live, "run_initial", side_effect=lambda *a, **k:
                                             original_initial(*a, **k, execute_fn=execute)))
        self.stack.enter_context(patch.object(live, "run_retry", side_effect=lambda *a, **k:
                                             original_retry(*a, **k, execute_fn=execute)))
        self.stack.enter_context(patch.object(live.submission_grading, "grade_representative", side_effect=grade))
        self.plan = operation.make_plan(copy.deepcopy(self.config), resolver=resolver)
        self.state = Path(self.config["state"])
        operation.initialize(self.state, self.plan)
        self.transport = FakeTransport(self)
        self.campaign = operation.Campaign(self.state, operation.digest(self.plan),
                                          backend=FakeBackend(), transport=self.transport)

    def stage(self, name, **kwargs):
        return self.campaign.stage(name, online=True, authorized=True, grading_authorized=True, **kwargs)

    def through(self, name):
        for stage in operation.STAGES[:operation.STAGES.index(name) + 1]:
            self.stage(stage)

    def test_fresh_plan_deterministic_offline_and_no_authority(self):
        self.assertEqual(self.plan, operation.make_plan(copy.deepcopy(self.config), resolver=resolver))
        self.assertEqual(len(self.plan["jobs"]), 20)
        self.assertEqual(self.plan["budget"]["maximum_codex_executions"], 40)
        with patch.object(subprocess, "run", side_effect=AssertionError("network/model")):
            self.campaign.status()
            self.campaign.preflight()
        for name in ("initial", "escalate"):
            with self.assertRaisesRegex(operation.OrchestrationRefusal, "authorization"):
                self.campaign.stage(name, online=True)
        self.assertEqual(self.model_calls, 0)

    def test_source_sha_receipt_mode_and_adapter_drift(self):
        for field in ("sha", "receipt_sha256"):
            config = copy.deepcopy(self.config)
            config["agent"]["source"][field] = "a" * (40 if field == "sha" else 64)
            with self.assertRaises(ValueError):
                operation.make_plan(config, resolver=resolver)
        file = Path(self.config["agent"]["source"]["path"]) / "public-fixture.txt"
        file.chmod(0o666)
        with self.assertRaises(ValueError):
            self.campaign.preflight()
        file.chmod(0o644)
        self.adapter.write_text("changed")
        with self.assertRaisesRegex(ValueError, "adapter identity"):
            operation.make_plan(self.config, resolver=resolver)
        self.assertEqual(self.model_calls, 0)

    def test_full_matrix_grading_finalization_and_archive_idempotence(self):
        self.through("archive")
        final = self.campaign.receipt("finalize")["result"]
        self.assertEqual((self.model_calls, self.grade_calls, final["runs"], final["quality_passes"]), (20, 20, 20, 20))
        self.assertEqual((final["handoff_count"], final["handoff_overhead_seconds"]), (0, 0.0))
        self.assertIsNone(final["winner"])
        first = self.stage("archive")
        self.assertEqual(first, self.stage("archive"))
        self.assertFalse(first["result"]["evidence_accepted"])
        self.assertEqual(self.model_calls, 20)

    def test_interrupted_agent_spent_never_replayed(self):
        self.stage("preflight")
        self.interrupt_agent_at = 1
        with self.assertRaises(KeyboardInterrupt):
            self.stage("initial")
        self.assertEqual(self.campaign.status()["started_attempts"], 1)
        with self.assertRaisesRegex(operation.OrchestrationRefusal, "resume"):
            self.stage("initial")
        self.stage("initial", resume=True)
        for stage in operation.STAGES[2:]:
            self.stage(stage)
        final = self.campaign.receipt("finalize")["result"]
        self.assertEqual((self.model_calls, final["runs"], final["started_without_result_count"]), (20, 20, 1))
        self.assertEqual(final["quality_passes"], 19)
        self.assertEqual(final["lifecycle_latency_unknown_jobs"], 1)

    def test_interrupted_transfer_resume_never_reexecutes_models(self):
        self.through("initial")
        self.transport.failure = "upload"
        with self.assertRaisesRegex(operation.OrchestrationRefusal, "transport"):
            self.stage("transfer-1")
        self.stage("transfer-1", resume=True)
        self.stage("initial")
        self.assertEqual(self.model_calls, 20)
        remote = self.campaign.remote_root() / "bundle-1"
        self.assertFalse(any(p.name in {"trace.jsonl", "stderr.txt"} for p in remote.rglob("*")))

    def test_interrupted_grading_keeps_completed_rows(self):
        self.through("transfer-1")
        self.interrupt_grade_at = 2
        with self.assertRaises(KeyboardInterrupt):
            self.stage("grade-1")
        self.stage("grade-1", resume=True)
        self.stage("authenticate-1")
        self.assertEqual((self.model_calls, self.grade_calls), (20, 21))

    def test_missing_altered_or_duplicate_grading_receipt_refused(self):
        self.through("grade-1")
        self.transport.failure = "receipt"
        with self.assertRaisesRegex(operation.OrchestrationRefusal, "SSH receipt"):
            self.stage("authenticate-1")
        self.transport.failure = None
        summary = self.campaign.remote_root() / "grades-1/summary.json"
        original = summary.read_bytes()
        summary.write_bytes(original[:-1] + b',"attempt":1}')
        with self.assertRaises(ValueError):
            self.stage("authenticate-1", resume=True)
        summary.write_bytes(original)
        self.stage("authenticate-1", resume=True)
        local = self.state / "grades-1/summary.json"
        local.write_text("{}")
        with self.assertRaises(ValueError):
            self.stage("escalate")
        self.assertEqual(self.model_calls, 20)

    def test_controller_escalation_retry_exhaustion_and_high_risk_floor(self):
        self.fail_quality = True
        self.through("archive")
        final = self.campaign.receipt("finalize")["result"]
        self.assertEqual((self.model_calls, final["retry_count"], final["quality_passes"]), (36, 16, 0))
        self.assertEqual(final["runs"], 20)
        self.stage("escalate")
        self.assertEqual(self.model_calls, 36)
        for row in self.plan["jobs"]:
            if live.adaptive.SCENARIO_POLICY[row["scenario"]]["risk"] == "high":
                self.assertEqual(row["decision"]["model_key"], 30)
                self.assertFalse((self.state / "agent" / row["job_id"] / "attempt-2").exists())

    def test_frozen_40_budget_and_unexpected_ledger_refused(self):
        self.stage("preflight")
        with patch.object(live, "_started_count", return_value=40):
            with self.assertRaisesRegex(ValueError, "budget"):
                self.stage("initial")
        self.assertEqual(self.model_calls, 0)
        (self.state / "agent" / "unexpected-job").mkdir()
        with self.assertRaisesRegex(ValueError, "unexpected"):
            self.campaign.status()

    def test_unknown_tokens_cost_and_zero_delegation_preserved(self):
        self.unknown_tokens = True
        self.through("finalize")
        final = self.campaign.receipt("finalize")["result"]
        self.assertEqual(final["attempt_total_tokens_unknown_jobs"], 20)
        self.assertIsNone(final["estimated_cost"])
        self.assertIsNone(final["savings_claim"])
        self.assertIsNone(final["attempt_total_tokens_median"])
        self.assertEqual(final["handoff_count"], 0)

    def test_plan_tampering_paths_duplicate_start_and_archive_no_overwrite(self):
        with self.assertRaises(ValueError):
            operation.initialize(self.root / "other-state", self.plan)
        with self.assertRaises((ValueError, OSError)):
            operation.initialize(self.state, self.plan)
        with self.assertRaises(ValueError):
            operation.Campaign(self.state, "0" * 64)
        copied = self.root / "copied-state"
        operation.private_directory(copied, create=True)
        operation.write(copied / "plan.json", self.plan)
        with self.assertRaisesRegex(ValueError, "state destination"):
            operation.Campaign(copied, operation.digest(self.plan))
        bad = copy.deepcopy(self.config)
        bad["grader"]["source"]["path"] = "/tmp/../unsafe"
        with self.assertRaises(ValueError):
            operation.make_plan(bad, resolver=resolver)
        self.through("archive")
        file = self.state / "archive/final.json"
        file.chmod(0o600)
        file.write_text("tampered")
        with self.assertRaises(ValueError):
            self.stage("archive")
        self.assertEqual(file.read_text(), "tampered")

    def test_unsafe_transfer_paths_raw_logs_and_partial_copy_resume(self):
        files = {"trace.jsonl": "e30="}
        with self.assertRaises(ValueError):
            operation.unpack(files, self.root / "bad-transfer", allowed=operation.bundle_name,
                             manifest={"trace.jsonl": {"mode": 0o600, "sha256": "a" * 64}})
        self.through("initial")
        self.stage("transfer-1")
        source = self.state / "bundle-1"
        target = self.root / "partial-copy"
        manifest, files = operation.tree(source), operation.pack(source)
        first = next(iter(files))
        operation.unpack({first: files[first]}, target, allowed=operation.bundle_name,
                         manifest={first: manifest[first]})
        before = operation.file_record(target / first)
        operation.unpack(files, target, allowed=operation.bundle_name, manifest=manifest, resume=True)
        self.assertEqual(before, operation.file_record(target / first))
        self.assertEqual(operation.tree(target), manifest)

    def test_default_cli_and_transport_remain_offline_or_explicitly_pinned(self):
        output = io.StringIO()
        with patch.object(subprocess, "run", side_effect=AssertionError("network/model")), redirect_stdout(output):
            operation.main([])
        self.assertFalse(json.loads(output.getvalue())["model_execution_enabled"])
        with patch.object(operation.handoff, "pinned_srv0_options", side_effect=AssertionError("pin lookup")):
            with self.assertRaises(ValueError):
                operation.Transport().request(self.plan, "upload", files={"stderr.txt": "e30="},
                                               manifest={"stderr.txt": {"mode": 0o600, "sha256": "a" * 64}})
        with patch.object(operation.handoff, "pinned_srv0_options", return_value=["-o", "StrictHostKeyChecking=yes"]), \
                patch.object(subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=b'{}')) as run:
            operation.Transport().request(self.plan, "preflight")
            args = run.call_args.args[0]
            self.assertEqual(args[0], operation.handoff.SSH)
            self.assertIn(operation.handoff.TRUSTED_ALIAS, args)
            self.assertIn("StrictHostKeyChecking=yes", args)
            self.assertIn("-I", args[-1])
            self.assertIn("verify_snapshot", args[-1])
            self.assertNotIn("shell", run.call_args.kwargs)

    def test_transport_bootstrap_verifies_source_before_import(self):
        run = subprocess.run

        def fake_ssh(argv, **kwargs):
            self.assertEqual(argv[0], operation.handoff.SSH)
            command = shlex.split(argv[-1])
            self.assertEqual(command[:3], ["/usr/bin/python3", "-I", "-B"])
            reply = run(command, **kwargs)
            if not getattr(self, "tampered_bootstrap", False):
                self.assertEqual(reply.returncode, 0, reply.stderr.decode())
            return reply

        with patch.object(operation.handoff, "pinned_srv0_options", return_value=[]), \
                patch.object(subprocess, "run", side_effect=fake_ssh):
            self.assertEqual(operation.Transport().request(self.plan, "preflight"),
                             {"kind": "fake-bootstrap-test"})
            module = Path(self.config["grader"]["source"]["path"]) / "scripts/benchmark_adaptive_orchestrator.py"
            self.tampered_bootstrap = True
            module.write_text("raise AssertionError('must not import before snapshot verification')\n")
            with self.assertRaisesRegex(ValueError, "host operation refused"):
                operation.Transport().request(self.plan, "preflight")
        self.assertEqual(self.model_calls, 0)

    def test_safety_floor_and_duplicate_json_rejected(self):
        def unsafe(*args):
            return {"schema_version": 1, "state": "ready", "profile": "economy", "reasoning": "medium",
                    "model_key": 10, "attempts_started": 0, "retries_used": 0, "delegations_used": 0}
        with self.assertRaisesRegex(ValueError, "safety floor"):
            operation.make_plan(self.config, resolver=unsafe)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            operation.decode(b'{"job":1,"job":2}')
        self.assertEqual(self.model_calls, 0)

    def test_production_preflight_rejects_model_writable_control_paths(self):
        with patch.object(live, "agent_preflight", side_effect=AssertionError("execution preflight")):
            with self.assertRaisesRegex(ValueError, "model-writable temporary root"):
                operation.Backend().preflight(self.plan)
        self.assertEqual(self.model_calls, 0)

    def test_partial_finalization_and_archive_resume_no_reexecution(self):
        self.through("authenticate-2")
        original = live._write_json
        written = []

        def interrupted(path, value, **kwargs):
            if Path(path).parent == self.state / "final":
                written.append(path)
                if len(written) == 2:
                    raise OSError("fake interrupted finalization")
            return original(path, value, **kwargs)

        with patch.object(live, "_write_json", side_effect=interrupted), self.assertRaises(OSError):
            self.stage("finalize")
        row = next((self.state / "final").iterdir())
        before = operation.file_record(row)
        self.stage("finalize", resume=True)
        self.assertEqual(before, operation.file_record(row))
        archive_write = operation.write

        def interrupted_archive(path, value):
            if Path(path).name == "grading.json":
                raise OSError("fake interrupted archival")
            return archive_write(path, value)

        with patch.object(operation, "write", side_effect=interrupted_archive), self.assertRaises(OSError):
            self.stage("archive")
        self.stage("archive", resume=True)
        self.assertEqual(self.model_calls, 20)

    def test_partial_remote_transfer_resume_preserves_completed_files(self):
        self.through("initial")
        original = operation.unpack
        copied = []

        def interrupted(files, path, **kwargs):
            if Path(path).is_relative_to(self.campaign.remote_root()):
                first = next(iter(files))
                copied.append(first)
                original({first: files[first]}, path, allowed=kwargs["allowed"],
                         manifest={first: kwargs["manifest"][first]})
                raise OSError("fake partial remote upload")
            return original(files, path, **kwargs)

        with patch.object(operation, "unpack", side_effect=interrupted), self.assertRaises(OSError):
            self.stage("transfer-1")
        path = self.campaign.remote_root() / "bundle-1" / copied[0]
        before = operation.file_record(path)
        self.stage("transfer-1", resume=True)
        self.assertEqual(before, operation.file_record(path))
        self.assertEqual(self.model_calls, 20)


if __name__ == "__main__":
    unittest.main()
