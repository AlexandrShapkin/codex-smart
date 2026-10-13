import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import benchmark as b
import benchmark_coverage as coverage
import benchmark_split_host_campaign as split


class SplitHostCampaignTests(unittest.TestCase):
    def test_contract_is_bounded_and_candidate_requires_separate_acceptance(self):
        contract = split.load_contract()
        candidate = split.load_candidate_evidence()
        self.assertEqual(contract["planned_primary_runs"], 40)
        self.assertEqual(contract["maximum_codex_exec_processes"], 40)
        self.assertEqual(contract["retries"], 0)
        self.assertTrue(contract["interruption_policy"]["started_ledger_written_before_codex"])
        self.assertTrue(contract["interruption_policy"]["started_without_result_never_retried"])
        self.assertEqual(contract["accepted_evidence_sha256"], [])
        self.assertEqual(
            candidate["evidence_reference"],
            "1a9e7a145e7271b872d2dfc54c92a6ac578cbd8859649f8c4c062a127f3aac43",
        )
        self.assertFalse(split.contract_verified())

    def test_offline_plan_never_enables_model_execution(self):
        plan = split.plan()
        self.assertEqual(plan["planned_primary_runs"], 40)
        self.assertEqual(plan["maximum_codex_exec_processes"], 40)
        self.assertEqual(plan["retries"], 0)
        self.assertFalse(plan["model_execution_enabled"])
        self.assertTrue(plan["authorization_required"])

    def test_authorization_refusal_precedes_preflight_and_artifacts(self):
        with patch.object(split, "agent_preflight",
                          side_effect=AssertionError("preflight crossed")):
            with self.assertRaisesRegex(
                    split.SplitHostRefusal,
                    "explicit split-host campaign execution authorization required"):
                split.run_agent_campaign(
                    "/fake/codex", "/fake/host", "/tmp/runtime", "/tmp/inventory",
                    "never-created", authorized=False)

    def test_expected_path_export_rejects_symlink_and_hardlink(self):
        scenario = next(
            row for row in coverage.load_manifest()["scenarios"]
            if row["id"] == "python-billing")
        fixture = coverage.fixture(scenario)
        for kind in ("symlink", "hardlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir="/tmp") as tmp:
                workspace = Path(tmp)
                b.materialize(fixture["files"] | fixture["reference"], workspace)
                target = workspace / "pricing.py"
                text = target.read_text()
                target.unlink()
                backing = workspace / "backing.py"
                backing.write_text(text)
                if kind == "symlink":
                    target.symlink_to("backing.py")
                else:
                    os.link(backing, target)
                with self.assertRaises(ValueError):
                    split.export_submission(scenario, workspace)

    def test_exploration_extra_artifact_is_rejected_before_export(self):
        scenario = next(
            row for row in coverage.load_manifest()["scenarios"]
            if row["id"] == "explore-notification")
        fixture = coverage.fixture(scenario)
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            workspace = Path(tmp)
            b.materialize(fixture["files"] | fixture["reference"], workspace)
            (workspace / "extra.txt").write_text("unexpected")
            with self.assertRaisesRegex(
                    split.SplitHostRefusal, "exploration export policy rejected"):
                split.export_submission(scenario, workspace)

    def test_envelope_rejects_unexpected_and_unsafe_paths(self):
        scenario = next(
            row for row in coverage.load_manifest()["scenarios"]
            if row["id"] == "python-billing")
        base = {
            "schema_version": 1,
            "campaign_sha256": split.load_contract()["campaign_sha256"],
            "scenario_id": scenario["id"],
            "files": {"pricing.py": "pass\n"},
        }
        self.assertEqual(
            split.validate_submission_envelope(
                base, scenario, split.load_contract()["campaign_sha256"]),
            {"pricing.py": "pass\n"})
        for name in ("unexpected.py", "../escape", "/absolute"):
            changed = json.loads(json.dumps(base))
            changed["files"] = {name: "x"}
            with self.subTest(name=name), self.assertRaises(split.SplitHostRefusal):
                split.validate_submission_envelope(
                    changed, scenario, split.load_contract()["campaign_sha256"])

    def test_resume_never_reexecutes_started_job(self):
        campaign = coverage.load_campaign()
        runtime = object()
        jobs = [
            ("python-billing", "vanilla", 0, 14),
            ("python-billing", "native", 0, 14),
        ]
        trace = json.dumps({
            "type": "turn.completed",
            "usage": {"input_tokens": 1, "cached_input_tokens": 0,
                      "output_tokens": 1, "reasoning_tokens": 0},
        }) + "\n"
        calls = []

        def execute(argv, workspace, prompt="", timeout=0):
            calls.append((tuple(argv), str(workspace), prompt, timeout))
            return {
                "stdout": trace,
                "stderr": "",
                "exit_status": 0,
                "timeout": False,
                "duration": 0.01,
            }

        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            target = Path(tmp) / "run"
            target.mkdir()
            first = target / split._safe_job_id(*jobs[0])
            first.mkdir()
            (first / "started.json").write_text("{}\n")
            with patch.object(split, "agent_preflight",
                              return_value=(campaign, runtime)), \
                 patch.object(split, "_artifact_root", return_value=target), \
                 patch.object(split.representative, "jobs", return_value=jobs), \
                 patch.object(split.representative, "command_plan",
                              return_value=["/fake/codex"]), \
                 patch.object(split, "contract_verified", return_value=True):
                summary = split.run_agent_campaign(
                    "/fake/codex", "/fake/host", "/tmp/runtime", "/tmp/inventory",
                    "resume-run", authorized=True, resume=True, execute_fn=execute)
            self.assertEqual(len(calls), 1)
            self.assertEqual(summary["codex_exec_processes_started_this_invocation"], 1)
            self.assertEqual(summary["started_ledger_count"], 2)
            self.assertEqual(
                summary["started_without_result"],
                [split._safe_job_id(*jobs[0])],
            )
            self.assertTrue(
                (target / split._safe_job_id(*jobs[1]) / "agent-result.json").is_file())

    def test_candidate_tamper_is_rejected(self):
        record = split.load_candidate_evidence()
        record = json.loads(json.dumps(record))
        record["candidate"]["max_codex_exec_processes"] = 41
        record["evidence_reference"] = split.evidence_reference(record["candidate"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.json"
            path.write_text(json.dumps(record))
            with self.assertRaises(split.SplitHostRefusal):
                split.load_candidate_evidence(path)


if __name__ == "__main__":
    unittest.main()
