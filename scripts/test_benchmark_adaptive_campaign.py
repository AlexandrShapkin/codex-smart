"""Offline tests only: every execution and grading boundary is replaced by a fake."""

from contextlib import ExitStack, redirect_stderr
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import benchmark_adaptive_campaign as live


JOB = ("explore-notification", 0, 14)
TRACE = json.dumps({
    "type": "turn.completed",
    "usage": {
        "input_tokens": 3, "cached_input_tokens": 1,
        "output_tokens": 2, "reasoning_tokens": 1,
    },
}) + "\n"


def decision(profile="economy", ordinal=1):
    key = {"economy": 10, "standard": 20, "strong": 30}[profile]
    return {
        "schema_version": 1, "state": "ready", "profile": profile,
        "reasoning": "medium" if profile == "economy" else "high",
        "model_key": key, "attempts_started": ordinal - 1,
        "retries_used": ordinal - 1, "delegations_used": 0,
    }


class AdaptiveCampaignTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir="/tmp")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.artifacts = self.root / "agent"
        self.artifacts.mkdir()
        self.campaign = {"timeout_seconds": 1}
        self.scenario = {"id": JOB[0]}

    def fakes(self, stack, *, adapter=None):
        stack.enter_context(patch.object(live, "jobs", return_value=[JOB]))
        stack.enter_context(patch.object(live, "agent_preflight", return_value=(
            self.campaign, object(), Path("/fake/adapter"))))
        stack.enter_context(patch.object(live, "_artifact_root", return_value=self.artifacts))
        stack.enter_context(patch.object(live, "_scenario", return_value=self.scenario))
        stack.enter_context(patch.object(live.adaptive, "_adapter_output",
                                         side_effect=adapter or (lambda *a: decision())))
        stack.enter_context(patch.object(live.b, "setup"))
        stack.enter_context(patch.object(live.representative, "command_plan",
                                         return_value=["/fake/codex", "exec", "--model", "x",
                                                       "-c", 'model_reasoning_effort="medium"']))
        stack.enter_context(patch.object(live.primitives, "prompt", return_value="fake prompt"))
        stack.enter_context(patch.object(live.split, "export_submission", return_value={
            "schema_version": 1, "campaign_sha256": live.adaptive.CAMPAIGN_SHA256,
            "scenario_id": JOB[0], "files": {},
        }))

    def execute(self, *args, **kwargs):
        self.assertTrue((self.artifacts / live._job_id(*JOB) /
                         "attempt-1" / "started.json").is_file())
        return {"stdout": TRACE, "stderr": "", "exit_status": 0,
                "timeout": False, "duration": 0.1}

    def initial(self, *, execute=None):
        return live.run_initial("/fake/codex", "/fake/host", "/tmp/runtime",
                                "/tmp/inventory", "/fake/adapter", "a" * 64,
                                "fake-run", authorized=True, execute_fn=execute or self.execute)

    def attempt_dir(self, ordinal=1):
        return self.artifacts / live._job_id(*JOB) / f"attempt-{ordinal}"

    def grade_row(self, result, *, attempt=1, quality=True):
        return {
            "schema_version": 1, "measurement_id": live.adaptive.load_contract()["measurement_id"],
            "job_id": live._job_id(*JOB), "scenario_id": JOB[0],
            "repetition": JOB[1], "seed": JOB[2], "attempt": attempt,
            "profile": result["profile"] if result else None,
            "reasoning": result["reasoning"] if result else None,
            "model_key": result["model_key"] if result else None,
            "model": result["model"] if result else None,
            "agent_success": result is not None and result["failure_reason"] is None,
            "quality_pass": quality if result else False,
            "failure_reason": (None if quality else "quality-failure") if result else "interrupted-no-result",
            "grader_reason": None, "grading_seconds": 0.2 if result else 0.0,
            "trace_sha256": result["trace_sha256"] if result else None,
            "submission_sha256": result["submission_sha256"] if result else None,
            "host_qualification_reference": live.split.GRADING_HOST_RECEIPT,
            "production_grading_reference": live.split.PRODUCTION_GRADING_REFERENCE,
            "runtime_inventory_reference": live.split.RUNTIME_INVENTORY_REFERENCE,
        }

    def grades(self, ordinal, row=None):
        root = self.root / f"grades-{ordinal}"
        root.mkdir()
        hashes = {}
        if row is not None:
            file = root / f"{live._job_id(*JOB)}.json"
            live._write_json(file, row)
            hashes[file.name] = live._sha256(file)
        live._write_json(root / "summary.json", {
            "schema_version": 1, "kind": "adaptive-lifecycle-grade-round",
            "measurement_id": live.adaptive.load_contract()["measurement_id"],
            "attempt": ordinal, "graded_or_terminal_rows": len(hashes),
            "missing_jobs": [] if row or ordinal == 2 else [live._job_id(*JOB)],
            "row_sha256": hashes,
            "host_qualification_reference": live.split.GRADING_HOST_RECEIPT,
            "production_grading_reference": live.split.PRODUCTION_GRADING_REFERENCE,
            "runtime_inventory_reference": live.split.RUNTIME_INVENTORY_REFERENCE,
        })
        return root

    def digest(self, root):
        return live._sha256(root / "summary.json")

    def result(self, ordinal=1):
        return live._load_attempt_result(self.attempt_dir(ordinal), *JOB, ordinal)

    def test_shared_boundary_durable_identity_and_tamper_refusal(self):
        with ExitStack() as stack:
            self.fakes(stack)
            sync = stack.enter_context(patch.object(live.runner, "sync_ledger",
                                                     wraps=live.runner.sync_ledger))
            self.initial()
            sync.assert_called_once_with(self.attempt_dir() / "started.json")
        result = self.result()
        started = live._load_started(self.attempt_dir(), *JOB, 1)
        grade = self.grade_row(result)
        live._match_grade(grade, started, result)
        for key, value in (("seed", 15), ("attempt", 2), ("job_id", "static-control")):
            with self.subTest(key=key), self.assertRaisesRegex(
                    live.AdaptiveCampaignRefusal, "adaptive grade/started identity mismatch"):
                live._match_grade(grade | {key: value}, started, result)
        with self.assertRaisesRegex(live.AdaptiveCampaignRefusal, "adaptive grade/agent evidence mismatch"):
            live._match_grade(grade | {"trace_sha256": "0" * 64}, started, result)
        marker = self.attempt_dir() / "started.json"
        for key, value in (("measurement_id", "static-control"), ("attempt", True),
                           ("repetition", False), ("schema_version", True)):
            with self.subTest(ledger_key=key):
                marker.write_text(json.dumps(started | {key: value}))
                with self.assertRaisesRegex(live.AdaptiveCampaignRefusal, "started ledger identity mismatch"):
                    self.result()
        marker.write_text(json.dumps(started))
        result_path = self.attempt_dir() / "agent-result.json"
        for key, value in (("measurement_id", "static-control"), ("attempt", True)):
            with self.subTest(result_key=key):
                result_path.write_text(json.dumps(result | {key: value}))
                with self.assertRaisesRegex(live.AdaptiveCampaignRefusal, "adaptive attempt identity mismatch"):
                    self.result()

    def test_shared_boundary_ledger_sync_failure_blocks_execution(self):
        with ExitStack() as stack:
            self.fakes(stack)
            stack.enter_context(patch.object(live.runner, "sync_ledger", side_effect=OSError("fake sync")))
            execute = stack.enter_context(patch.object(live.b, "execute"))
            with self.assertRaisesRegex(OSError, "fake sync"):
                self.initial(execute=execute)
            execute.assert_not_called()
            live.run_initial("a", "b", "c", "d", "e", "f", "fake-run",
                             authorized=True, resume=True, execute_fn=execute)
            execute.assert_not_called()

    def test_shared_boundary_launch_failure_and_interruption_not_replayed(self):
        with ExitStack() as stack:
            self.fakes(stack)
            launch = stack.enter_context(patch.object(live.b, "execute", side_effect=OSError("fake")))
            self.initial(execute=launch)
            self.assertEqual(self.result()["failure_reason"], "launch-failure")
            live.run_initial("a", "b", "c", "d", "e", "f", "fake-run",
                             authorized=True, resume=True, execute_fn=launch)
            self.assertEqual(launch.call_count, 1)
        interrupted = self.grade_row(None)
        started = live._load_started(self.attempt_dir(), *JOB, 1)
        live._match_grade(interrupted, started, None)
        with self.assertRaisesRegex(live.AdaptiveCampaignRefusal, "adaptive interrupted grade mismatch"):
            live._match_grade(interrupted | {"quality_pass": True}, started, None)

    def test_shared_boundary_path_errors_and_preflight_refusal_preserved(self):
        for path, message in ((None, "invalid adaptive artifact path"),
                              ("relative", "symlink or relative adaptive artifact path")):
            with self.subTest(path=path), self.assertRaisesRegex(live.AdaptiveCampaignRefusal, message):
                live._safe_path(path)
        link = self.root / "link"
        link.symlink_to(self.artifacts, target_is_directory=True)
        with self.assertRaisesRegex(live.AdaptiveCampaignRefusal, "symlink or relative"):
            live._regular_file(link / "started.json")
        with patch.object(live.adaptive, "profile_mapping_verified", return_value=True), \
                patch.object(live.split, "agent_preflight", side_effect=ValueError("fake drift")):
            with self.assertRaisesRegex(live.AdaptiveCampaignRefusal, "split-host agent preflight refused"):
                live.agent_preflight("/fake/codex", "/fake/host", "/fake/runtime",
                                     "/fake/inventory", "/fake/adapter", "0" * 64)

    def test_plan_and_authorization_before_any_preflight(self):
        plan = live.plan()
        self.assertEqual((plan["jobs"], plan["maximum_codex_executions"]), (20, 40))
        self.assertFalse(plan["model_execution_enabled"])
        self.assertTrue(plan["sanitized_grading_bundle_required"])
        self.assertTrue(plan["trusted_grade_summary_digest_required"])
        self.assertEqual(len(live.jobs()), 20)
        self.assertEqual(len(set(live.jobs())), 20)
        with patch.object(live, "agent_preflight", side_effect=AssertionError("preflight")), \
             patch.object(live, "_grading_runtime", side_effect=AssertionError("grade preflight")):
            with self.assertRaises(live.AdaptiveCampaignRefusal):
                live.run_initial("a", "b", "c", "d", "e", "f", "fake-run")
            with self.assertRaises(live.AdaptiveCampaignRefusal):
                live.run_retry("a", "b", "c", "d", "e", "f", "g", "h")
            with self.assertRaisesRegex(live.AdaptiveCampaignRefusal, "digest required"):
                live.run_retry("a", "b", "c", "d", "e", "f", "g", "h", authorized=True)
            with self.assertRaises(live.AdaptiveCampaignRefusal):
                live.grade_round("a", 1, object(), "b", "c", "d")
        with patch.object(live.host, "load_evidence", side_effect=AssertionError("host preflight")), \
             redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                live.main(["--grade-round", "1"])

    def test_initial_ledger_before_fake_execution_and_resume(self):
        with ExitStack() as stack:
            self.fakes(stack)
            seen = []
            def execute(*args, **kwargs):
                seen.append(1)
                return self.execute(*args, **kwargs)
            first = self.initial(execute=execute)
            self.assertEqual(first["started_ledger_count"], 1)
            resumed = live.run_initial("a", "b", "c", "d", "e", "f", "fake-run",
                                       authorized=True, resume=True, execute_fn=execute)
            self.assertEqual((len(seen), resumed["codex_exec_processes_started_this_invocation"]), (1, 0))
            self.assertEqual(self.result()["profile"], "economy")

    def test_interruption_spends_ledger_and_never_reexecutes(self):
        with ExitStack() as stack:
            self.fakes(stack)
            with self.assertRaises(KeyboardInterrupt):
                self.initial(execute=lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
            self.assertEqual(live._started_count(self.artifacts), 1)
            summary = live.run_initial("a", "b", "c", "d", "e", "f", "fake-run",
                                       authorized=True, resume=True,
                                       execute_fn=lambda *a, **k: self.fail("reexecuted"))
            self.assertEqual(summary["started_without_result"], [live._job_id(*JOB)])

    def test_budget_and_unsafe_artifact_refusal(self):
        with ExitStack() as stack:
            self.fakes(stack)
            with patch.object(live, "_started_count", return_value=40):
                with self.assertRaisesRegex(live.AdaptiveCampaignRefusal, "budget"):
                    live._execute_attempt(
                        artifacts=self.artifacts, scenario=self.scenario,
                        repetition=0, seed=14, ordinal=1, decision=decision(),
                        campaign=self.campaign, runtime=object(), codex="/fake/codex",
                        execute_fn=lambda *a, **k: self.fail("executed"))
            link = self.root / "link"
            link.symlink_to(self.artifacts, target_is_directory=True)
            with self.assertRaisesRegex(live.AdaptiveCampaignRefusal, "symlink"):
                live._safe_path(link, directory=True)
            backing = self.root / "backing.json"
            backing.write_text("{}")
            hardlink = self.root / "hardlink.json"
            os.link(backing, hardlink)
            self.assertFalse(live._regular_file(hardlink))
            with self.assertRaises(live.AdaptiveCampaignRefusal):
                live._write_json(hardlink, {}, exclusive=False)

    def test_grade_round_interruption_and_authorization(self):
        with ExitStack() as stack:
            self.fakes(stack)
            with self.assertRaises(KeyboardInterrupt):
                self.initial(execute=lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
            bundle = self.root / "transfer"
            live.export_grading_bundle(self.artifacts, bundle)
            stack.enter_context(patch.object(live, "_grading_runtime", return_value=SimpleNamespace(
                inventory_reference=live.split.RUNTIME_INVENTORY_REFERENCE)))
            stack.enter_context(patch.object(live.adaptive, "profile_mapping_verified", return_value=True))
            stack.enter_context(patch.object(live.representative, "load", return_value=self.campaign))
            stack.enter_context(patch.object(live, "_grade_attempt", side_effect=AssertionError("grader run")))
            root = self.root / "grade-interrupted"
            summary = live.grade_round(bundle, 1, SimpleNamespace(
                reference=live.split.GRADING_HOST_RECEIPT), "/fake", "/fake", root,
                authorized=True)
            self.assertEqual(summary["graded_or_terminal_rows"], 1)
            self.assertEqual(live._load_grade_round(root, 1)[1][live._job_id(*JOB)]["failure_reason"],
                             "interrupted-no-result")

    def test_rejected_malformed_and_forged_grades(self):
        with ExitStack() as stack:
            self.fakes(stack)
            self.initial()
            result = self.result()
            started = live._load_started(self.attempt_dir(), *JOB, 1)
            valid = self.grade_row(result)
            live._match_grade(valid, started, result)
            for field, value in (("trace_sha256", "0" * 64),
                                 ("model_key", 30), ("agent_success", False)):
                forged = valid | {field: value}
                with self.subTest(field=field), self.assertRaises(live.AdaptiveCampaignRefusal):
                    live._match_grade(forged, started, result)
            root = self.grades(1, valid | {"scenario_id": "forged"})
            with self.assertRaisesRegex(live.AdaptiveCampaignRefusal, "identity"):
                live._load_grade_round(root, 1)
            row_path = root / f"{live._job_id(*JOB)}.json"
            row_path.unlink()
            row_path.symlink_to(self.root / "elsewhere")
            with self.assertRaises(live.AdaptiveCampaignRefusal):
                live._load_grade_round(root, 1)

            trusted = self.grades(2, self.grade_row(result, attempt=2, quality=False))
            digest = self.digest(trusted)
            row_file = trusted / f"{live._job_id(*JOB)}.json"
            row = json.loads(row_file.read_text())
            row["quality_pass"] = True
            row["failure_reason"] = None
            live._write_json(row_file, row, exclusive=False)
            manifest = json.loads((trusted / "summary.json").read_text())
            manifest["row_sha256"][row_file.name] = live._sha256(row_file)
            live._write_json(trusted / "summary.json", manifest, exclusive=False)
            with self.assertRaisesRegex(live.AdaptiveCampaignRefusal, "digest mismatch"):
                live._load_grade_round(trusted, 2, digest)

    def test_grading_bundle_contains_no_raw_logs_and_rejects_injection(self):
        with ExitStack() as stack:
            self.fakes(stack)
            stack.enter_context(patch.object(live.split, "validate_submission_envelope", return_value={}))
            self.initial()
            bundle = self.root / "transfer"
            exported = live.export_grading_bundle(self.artifacts, bundle)
            self.assertEqual(exported["completed_attempts"], 1)
            self.assertFalse(list(bundle.rglob("trace.jsonl")))
            self.assertFalse(list(bundle.rglob("stderr.txt")))
            self.assertEqual(live._validate_grading_bundle(bundle)["started_attempts"], 1)
            self.assertEqual(live._load_attempt_result(
                bundle / live._job_id(*JOB) / "attempt-1", *JOB, 1, transfer=True
            )["trace_sha256"], self.result()["trace_sha256"])
            (bundle / live._job_id(*JOB) / "attempt-1" / "stderr.txt").write_text("private")
            with self.assertRaises(live.AdaptiveCampaignRefusal):
                live._validate_grading_bundle(bundle)

    def test_completed_grade_round_uses_only_fake_grader(self):
        with ExitStack() as stack:
            self.fakes(stack)
            stack.enter_context(patch.object(live.split, "validate_submission_envelope", return_value={}))
            stack.enter_context(patch.object(live.split, "_materialize_envelope"))
            self.initial()
            bundle = self.root / "transfer"
            live.export_grading_bundle(self.artifacts, bundle)
            stack.enter_context(patch.object(live, "_grading_runtime", return_value=SimpleNamespace(
                inventory_reference=live.split.RUNTIME_INVENTORY_REFERENCE)))
            stack.enter_context(patch.object(live.adaptive, "profile_mapping_verified", return_value=True))
            stack.enter_context(patch.object(live.representative, "load", return_value=self.campaign))
            grader = stack.enter_context(patch.object(
                live.submission_grading, "grade_representative",
                return_value=SimpleNamespace(status="verified", quality_pass=True, reason=None)))
            root = self.root / "grades"
            live.grade_round(bundle, 1, SimpleNamespace(
                reference=live.split.GRADING_HOST_RECEIPT), "/fake", "/fake", root,
                authorized=True)
            grader.assert_called_once()
            self.assertTrue(live._load_grade_round(root, 1)[1][live._job_id(*JOB)]["quality_pass"])

    def test_retry_only_after_verified_failure_and_controller_escalation(self):
        with ExitStack() as stack:
            self.fakes(stack, adapter=lambda *a: decision("standard", 2) if len(a) == 3 else decision())
            stack.enter_context(patch.object(live.split, "validate_submission_envelope", return_value={}))
            stack.enter_context(patch.object(live.split, "_materialize_envelope"))
            self.initial()
            first = self.result()
            grades = self.grades(1, self.grade_row(first, quality=False))
            with patch.object(live.adaptive, "_adapter_output", return_value={
                **decision("economy", 2), "state": "completed", "model_key": None}):
                with self.assertRaisesRegex(live.AdaptiveCampaignRefusal, "authorize"):
                    live.run_retry("a", "b", "c", "d", "e", "f", "fake-run", grades,
                                   initial_grades_sha256=self.digest(grades),
                                   authorized=True, execute_fn=self.execute)
            with patch.object(live.adaptive, "_adapter_output", return_value=decision("economy", 2)):
                with self.assertRaisesRegex(live.AdaptiveCampaignRefusal, "did not escalate"):
                    live.run_retry("a", "b", "c", "d", "e", "f", "fake-run", grades,
                                   initial_grades_sha256=self.digest(grades),
                                   authorized=True, execute_fn=self.execute)
            def execute_retry(*args, **kwargs):
                self.assertTrue((self.attempt_dir(2) / "started.json").is_file())
                return self.execute(*args, **kwargs)
            summary = live.run_retry("a", "b", "c", "d", "e", "f", "fake-run", grades,
                                     initial_grades_sha256=self.digest(grades),
                                     authorized=True, execute_fn=execute_retry)
            self.assertEqual((summary["started_ledger_count"], self.result(2)["profile"]),
                             (2, "standard"))
            resumed = live.run_retry("a", "b", "c", "d", "e", "f", "fake-run", grades,
                                     initial_grades_sha256=self.digest(grades), authorized=True,
                                     execute_fn=lambda *a, **k: self.fail("retry reexecuted"))
            self.assertEqual(resumed["codex_exec_processes_started_this_invocation"], 0)

    def test_interrupted_retry_is_spent_and_final_failure(self):
        with ExitStack() as stack:
            self.fakes(stack, adapter=lambda *a: decision("standard", 2) if len(a) == 3 else decision())
            stack.enter_context(patch.object(live.split, "validate_submission_envelope", return_value={}))
            stack.enter_context(patch.object(live.split, "_materialize_envelope"))
            self.initial()
            first = self.grades(1, self.grade_row(self.result(), quality=False))
            with self.assertRaises(KeyboardInterrupt):
                live.run_retry("a", "b", "c", "d", "e", "f", "fake-run", first,
                               initial_grades_sha256=self.digest(first), authorized=True,
                               execute_fn=lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
            self.assertEqual(live._started_count(self.artifacts), 2)
            resumed = live.run_retry("a", "b", "c", "d", "e", "f", "fake-run", first,
                                     initial_grades_sha256=self.digest(first), authorized=True,
                                     execute_fn=lambda *a, **k: self.fail("retry reexecuted"))
            self.assertEqual(resumed["started_without_result"], [live._job_id(*JOB)])
            second = self.grades(2, self.grade_row(None, attempt=2))
            final = live.finalize(self.artifacts, first, second, self.root / "final",
                                  initial_grades_sha256=self.digest(first),
                                  retry_grades_sha256=self.digest(second))
            self.assertEqual((final["codex_exec_processes_started"], final["retry_count"],
                              final["started_without_result_count"], final["quality_passes"]),
                             (2, 1, 1, 0))
            self.assertIsNone(final["attempt_input_tokens_median"])

    def test_strong_high_ceiling_stays_failed_without_retry(self):
        with ExitStack() as stack:
            self.fakes(stack, adapter=lambda *a: decision("strong", 2) if len(a) == 3
                       else decision("strong"))
            self.initial()
            first = self.grades(1, self.grade_row(self.result(), quality=False))
            summary = live.run_retry("a", "b", "c", "d", "e", "f", "fake-run", first,
                                     initial_grades_sha256=self.digest(first),
                                     authorized=True,
                                     execute_fn=lambda *a, **k: self.fail("ceiling retry"))
            self.assertEqual(summary["strong_ceiling_no_escalation_no_retry"], 1)
            self.assertEqual(summary["started_ledger_count"], 1)
            second = self.grades(2)
            final = live.finalize(self.artifacts, first, second, self.root / "final",
                                  initial_grades_sha256=self.digest(first),
                                  retry_grades_sha256=self.digest(second))
            self.assertEqual((final["quality_passes"], final["retry_count"]), (0, 0))

    def test_pass_skips_retry_and_finalization_counts_unknowns(self):
        with ExitStack() as stack:
            self.fakes(stack, adapter=lambda *a: ({**decision(), "state": "completed",
                                                    "model_key": None} if len(a) == 3 else decision()))
            self.initial()
            first = self.result()
            grades = self.grades(1, self.grade_row(first))
            summary = live.run_retry("a", "b", "c", "d", "e", "f", "fake-run", grades,
                                     initial_grades_sha256=self.digest(grades), authorized=True,
                                     execute_fn=lambda *a, **k: self.fail("pass retried"))
            self.assertEqual(summary["initial_quality_pass_no_retry"], 1)
            second = self.grades(2)
            final = live.finalize(self.artifacts, grades, second, self.root / "final",
                                  initial_grades_sha256=self.digest(grades),
                                  retry_grades_sha256=self.digest(second))
            self.assertEqual((final["runs"], final["quality_passes"], final["codex_exec_processes_started"]),
                             (20, 1, 1))
            self.assertIsNone(final["winner"])
            self.assertIsNone(final["estimated_cost"])
            self.assertIsNone(final["savings_claim"])

    def test_interrupted_finalization_counts_spent_execution(self):
        with ExitStack() as stack:
            self.fakes(stack)
            with self.assertRaises(KeyboardInterrupt):
                self.initial(execute=lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
            first = self.grades(1, self.grade_row(None))
            live.run_retry("a", "b", "c", "d", "e", "f", "fake-run", first,
                           initial_grades_sha256=self.digest(first), authorized=True,
                           execute_fn=lambda *a, **k: self.fail("interrupted retry"))
            second = self.grades(2)
            final = live.finalize(self.artifacts, first, second, self.root / "final",
                                  initial_grades_sha256=self.digest(first),
                                  retry_grades_sha256=self.digest(second))
            self.assertEqual(final["codex_exec_processes_started"], 1)
            self.assertEqual(final["started_without_result_count"], 1)
            self.assertIsNone(final["attempt_input_tokens_median"])
            self.assertIsNone(final["total_lifecycle_latency_median_seconds"])


if __name__ == "__main__":
    unittest.main()
