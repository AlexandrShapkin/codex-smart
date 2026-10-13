"""Adversarial offline fixtures; never connect SSH or invoke a model."""
import copy
import fcntl
import json
import multiprocessing
import os
from pathlib import Path
import signal
import subprocess
import unittest
from unittest.mock import patch

import test_benchmark_adaptive_orchestrator as fixtures

operation = fixtures.operation
live = operation.live
RUST_RESOLVER = live.adaptive._adapter_output


class AuditTests(unittest.TestCase):
    setUp = fixtures.OrchestratorTests.setUp
    stage = fixtures.OrchestratorTests.stage
    through = fixtures.OrchestratorTests.through

    def corrupt_receipt(self, stage, change):
        path = self.state / "stages" / f"{stage}.json"
        value = operation.read(path)
        change(value)
        path.write_bytes(operation.encoded(value))

    def test_completed_receipt_cannot_drop_execution_hashes(self):
        self.through("initial")
        self.corrupt_receipt("initial", lambda value: value.update(outputs={}))
        with self.assertRaises(ValueError):
            self.campaign.receipt("initial")

    def test_completed_receipt_cannot_replace_result_with_null(self):
        self.stage("preflight")
        self.corrupt_receipt("preflight", lambda value: value.update(result=None))
        with self.assertRaises(ValueError):
            self.campaign.receipt("preflight")

    def test_status_rejects_corrupt_interrupted_stage(self):
        self.stage("preflight")
        operation.write(self.state / "stages/initial.started.json", {"junk": True})
        with self.assertRaises(ValueError):
            self.campaign.status()

    def test_nested_artifact_permission_drift_refused_read_only(self):
        self.through("initial")
        directory = self.state / "agent" / live._job_id(*live.jobs()[0]) / "attempt-1"
        directory.chmod(0o777)
        with self.assertRaises(ValueError):
            self.campaign.receipt("initial")
        self.assertEqual(directory.stat().st_mode & 0o777, 0o777)

    def test_remote_campaign_parent_permission_drift_refused(self):
        self.through("transfer-1")
        root = self.campaign.remote_root()
        root.chmod(0o777)
        with self.assertRaises(ValueError):
            self.transport.request(self.plan, "preflight")
        self.assertEqual(root.stat().st_mode & 0o777, 0o777)

    def test_orphan_retry_grading_row_refused(self):
        self.through("transfer-2")
        request = self.transport.request

        def extra_row(plan, action, **payload):
            result = request(plan, action, **payload)
            if action == "grade" and payload["round"] == 2:
                root = self.campaign.remote_root()
                name = live._job_id(*live.jobs()[0]) + ".json"
                row = operation.read(root / "grades-1" / name)
                row["attempt"] = 2
                live._write_json(root / "grades-2" / name, row)
                summary = operation.read(root / "grades-2/summary.json")
                summary["graded_or_terminal_rows"] = 1
                summary["row_sha256"] = {name: live._sha256(root / "grades-2" / name)}
                (root / "grades-2/summary.json").write_text(json.dumps(summary))
                result["summary_sha256"] = live._sha256(root / "grades-2/summary.json")
            return result

        with patch.object(self.transport, "request", side_effect=extra_row):
            self.stage("grade-2")
        with self.assertRaises(ValueError):
            self.stage("authenticate-2")

    def test_archive_rechecks_source_bytes(self):
        self.through("finalize")
        source = Path(self.config["agent"]["source"]["path"]) / "public-fixture.txt"
        source.write_text("altered after execution\n")
        with self.assertRaises(ValueError):
            self.stage("archive")

    def test_controller_drift_refused_before_first_model_callback(self):
        self.stage("preflight")
        def changed(adapter, policy, events=()):
            value = fixtures.resolver(adapter, policy, events)
            value.update(profile="strong", model_key=30, reasoning="high")
            return value
        initial = live.run_initial
        def drift_after_preflight(*args, **kwargs):
            with patch.object(live.adaptive, "_adapter_output", side_effect=changed):
                return initial(*args, **kwargs)
        # Change only the runner-side resolver AFTER the orchestrator preflight.
        with patch.object(live, "run_initial", side_effect=drift_after_preflight):
            with self.assertRaises(ValueError):
                self.stage("initial")
        self.assertEqual(self.model_calls, 0)

    def test_kill_before_and_after_started_json(self):
        self.stage("preflight")
        context = multiprocessing.get_context("fork")
        for after in (False, True):
            # Separate fresh campaign for each actual SIGKILL boundary.
            with self.subTest(after=after):
                config = copy.deepcopy(self.config)
                config["state"] = str(self.root / f"killed-{after}")
                plan = operation.make_plan(config, resolver=fixtures.resolver)
                state = Path(config["state"])
                operation.initialize(state, plan)
                campaign = operation.Campaign(state, operation.digest(plan),
                    backend=fixtures.FakeBackend(), transport=self.transport)
                campaign.stage("preflight", online=True)
                receiver, sender = context.Pipe(duplex=False)
                original = live._write_json

                def paused(path, value, **kwargs):
                    if Path(path).name == "started.json":
                        if after:
                            original(path, value, **kwargs)
                        sender.send("boundary")
                        signal.pause()
                    return original(path, value, **kwargs)

                def child():
                    with patch.object(live, "_write_json", side_effect=paused):
                        campaign.stage("initial", online=True, authorized=True)

                process = context.Process(target=child)
                process.start()
                try:
                    self.assertTrue(receiver.poll(10), "child did not reach bounded kill boundary")
                    self.assertEqual(receiver.recv(), "boundary")
                    process.kill()
                    process.join(10)
                    self.assertEqual(process.exitcode, -signal.SIGKILL)
                    if after:
                        self.assertEqual(campaign.status()["started_attempts"], 1)
                        campaign.stage("initial", online=True, authorized=True, resume=True)
                        self.assertEqual(live._started_count(state / "agent"), 20)
                        self.assertEqual(self.model_calls, 19)
                    else:
                        with self.assertRaises(ValueError):
                            campaign.stage("initial", online=True, authorized=True, resume=True)
                        self.assertEqual(self.model_calls, 0)
                finally:
                    if process.is_alive():
                        process.kill()
                        process.join(10)
                    receiver.close()
                    sender.close()

    def test_concurrent_operator_process_refused_without_execution(self):
        self.stage("preflight")
        descriptor = os.open(self.state / "campaign.lock", os.O_RDWR)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        context = multiprocessing.get_context("fork")
        receiver, sender = context.Pipe(duplex=False)
        def child():
            os.close(descriptor)  # Do not retain the parent's lock in the child.
            try:
                self.stage("initial")
            except operation.OrchestrationRefusal as error:
                sender.send(str(error))
        process = context.Process(target=child)
        process.start()
        try:
            self.assertTrue(receiver.poll(10))
            self.assertIn("already running", receiver.recv())
            process.join(10)
            self.assertEqual(process.exitcode, 0)
            self.assertEqual(self.model_calls, 0)
        finally:
            if process.is_alive():
                process.kill()
                process.join(10)
            os.close(descriptor)
            receiver.close()
            sender.close()

    def test_artifact_symlink_hardlink_and_stage_directory_refused(self):
        self.through("initial")
        path = self.state / "agent/initial-agent-summary.json"
        saved = path.read_bytes()
        outside = self.root / "outside.json"
        outside.write_bytes(saved)
        path.unlink()  # Disposable fixture only; never repair production evidence.
        path.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.campaign.receipt("initial")
        path.unlink()
        os.link(outside, path)
        with self.assertRaises(ValueError):
            self.campaign.receipt("initial")
        (self.state / "stages").chmod(0o777)
        with self.assertRaises(ValueError):
            self.campaign.status()

    def test_authorization_types_out_of_order_and_malformed_json_refused(self):
        for authority in (None, False, 1, "true", [], {}):
            with self.assertRaises(ValueError):
                self.campaign.stage("initial", online=True, authorized=authority)
        with self.assertRaises(ValueError):
            self.stage("finalize")
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.assertRaises(ValueError):
                operation.decode(raw)
        self.assertEqual(self.model_calls, 0)

    def test_grading_changes_after_authentication_block_retry(self):
        self.fail_quality = True
        self.through("authenticate-1")
        remote = self.campaign.remote_root() / "grades-1/summary.json"
        remote.write_bytes(remote.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            self.stage("escalate")
        self.assertEqual(self.model_calls, 20)

    def test_delayed_and_failed_ssh_remain_explicit_refusals(self):
        with patch.object(operation.handoff, "pinned_srv0_options", return_value=[]):
            for failure in (subprocess.TimeoutExpired("fake-ssh", 120), OSError("fake transport")):
                with patch.object(subprocess, "run", side_effect=failure), self.assertRaises(ValueError):
                    operation.Transport().request(self.plan, "preflight")
        self.assertEqual(self.model_calls, 0)

    def test_remote_source_and_runtime_substitution_refused(self):
        request = self.transport.request
        def bad_runtime(*args, **kwargs):
            value = request(*args, **kwargs)
            value["runtime_reference"] = "a" * 64
            return value
        with patch.object(self.transport, "request", side_effect=bad_runtime):
            with self.assertRaises(ValueError):
                self.stage("preflight")
        source = Path(self.config["grader"]["source"]["path"]) / "public-fixture.txt"
        source.write_text("substituted remote source\n")
        with self.assertRaises(ValueError):
            self.stage("preflight", resume=True)
        self.assertEqual(self.model_calls, 0)

    def test_replay_and_corrupted_start_receipt_do_not_reexecute(self):
        self.through("initial")
        self.stage("initial", resume=True)
        self.assertEqual(self.model_calls, 20)
        start = self.state / "stages/initial.started.json"
        value = operation.read(start)
        value["dependencies"] = {}
        start.write_bytes(operation.encoded(value))
        with self.assertRaises(ValueError):
            self.stage("initial", resume=True)
        self.assertEqual(self.model_calls, 20)

    def test_archive_interruption_after_marker_and_mode_drift(self):
        self.through("finalize")
        write = operation.write
        def interrupted(path, value):
            write(path, value)
            if Path(path).name == "archive-receipt.json":
                raise KeyboardInterrupt("synthetic interrupted archive permission freeze")
        with patch.object(operation, "write", side_effect=interrupted), self.assertRaises(KeyboardInterrupt):
            self.stage("archive")
        self.assertEqual((self.state / "archive").stat().st_mode & 0o777, 0o700)
        self.stage("archive", resume=True)
        self.assertEqual((self.state / "archive").stat().st_mode & 0o777, 0o500)
        self.assertEqual(self.model_calls, 20)
        (self.state / "archive").chmod(0o700)
        with self.assertRaises(ValueError):
            self.campaign.receipt("archive")
        self.assertEqual((self.state / "archive").stat().st_mode & 0o777, 0o700)


def synthetic_campaign(adapter, destination):
    """Explicit offline harness using genuine Rust policy, fake execution and real host logic."""
    case = AuditTests()
    case.fixture_root = destination
    case.setUp()
    try:
        adapter = operation.regular(adapter)
        case.config["agent"]["adapter"] = str(adapter)
        case.config["agent"]["adapter_sha256"] = live._sha256(adapter)
        case.stack.enter_context(patch.object(live, "agent_preflight",
            return_value=(live.representative.load(), case.runtime, adapter)))
        case.stack.enter_context(patch.object(live.adaptive, "_adapter_output", side_effect=RUST_RESOLVER))
        # The fixture's original state is unused; create a distinct, explicitly bound plan.
        case.config["state"] = str(case.root / "rust-state")
        case.plan = operation.make_plan(copy.deepcopy(case.config), resolver=RUST_RESOLVER)
        case.state = Path(case.config["state"])
        operation.initialize(case.state, case.plan)
        case.campaign = operation.Campaign(case.state, operation.digest(case.plan),
            backend=fixtures.FakeBackend(), transport=case.transport)
        case.unknown_tokens = True
        # First attempt of job zero is uncertain. Medium-floor jobs have graded failures;
        # one retry remains failed, others pass. Four Strong/High jobs cannot escalate.
        case.interrupt_agent_at = 1
        case.stage("preflight")
        with case.assertRaises(KeyboardInterrupt):
            case.stage("initial")
        case.stage("initial", resume=True)
        case.stage("transfer-1")
        def grade(scenario, workspace, qualification, runtime, policy):
            case.grade_calls += 1
            failed_first = scenario in {"go-pagination", "go-reservations", "infra-service-policy", "repo-ci-gates"}
            retry = case.model_calls > 20
            return fixtures.SimpleNamespace(status="verified",
                quality_pass=(scenario != "go-reservations" if retry else not failed_first), reason="synthetic-only")
        with patch.object(live.submission_grading, "grade_representative", side_effect=grade):
            case.stage("grade-1")
            case.transport.failure = "receipt"
            with case.assertRaises(ValueError):
                case.stage("authenticate-1")
            case.transport.failure = None
            remote = case.campaign.remote_root() / "grades-1/summary.json"
            original = remote.read_bytes()
            remote.write_bytes(b'{"malformed":true}')
            with case.assertRaises(ValueError):
                case.stage("authenticate-1", resume=True)
            remote.write_bytes(original)  # Only the disposable fault-injection fixture.
            case.stage("authenticate-1", resume=True)
            case.stage("escalate")
            case.stage("transfer-2")
            case.stage("grade-2")
            case.stage("authenticate-2")
            case.stage("finalize")
            case.stage("archive")
        for stage in operation.STAGES:
            case.assertIsNotNone(case.campaign.receipt(stage))
        case.stage("archive")
        final = case.campaign.receipt("finalize")["result"]
        case.assertEqual(final["runs"], 20)
        case.assertIsNone(final["estimated_cost"])
        case.assertIsNone(final["winner"])
        case.assertEqual(final["started_without_result_count"], 1)
        case.assertEqual(final["handoff_count"], 0)
        report = {"label": "synthetic — not accepted performance evidence",
                  "real_model_executions": 0, "real_ssh_connections": 0,
                  "genuine_rust_adapter_sha256": live._sha256(adapter),
                  "plan_sha256": operation.digest(case.plan), "fake_model_callbacks": case.model_calls,
                  "controller_decisions": case.plan["jobs"], "final": final,
                  "archive_sha256": case.campaign.receipt("archive")["result"]["archive_sha256"],
                  "faults": ["uncertain first attempt", "missing SSH receipt", "malformed grading summary"]}
        operation.write(case.root / "synthetic-report.json", report)
        return report
    finally:
        case.doCleanups()


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 4 and sys.argv[1] == "--synthetic":
        print(json.dumps(synthetic_campaign(Path(sys.argv[2]), Path(sys.argv[3])), indent=2))
    else:
        unittest.main()
