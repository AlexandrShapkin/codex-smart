import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import benchmark_host as host
import benchmark_representative as representative
import benchmark_representative_smoke as smoke


class RepresentativeSmokeTests(unittest.TestCase):
    def test_frozen_contract_is_one_execution_and_separate_from_campaign(self):
        contract = smoke.load()
        self.assertEqual(contract["scenario_id"], "python-billing")
        self.assertEqual(contract["variant"], "vanilla")
        self.assertEqual(contract["maximum_codex_executions"], 1)
        self.assertEqual(contract["retries"], 0)
        self.assertTrue(contract["budget"]["separate_from_primary_campaign"])
        self.assertFalse(contract["budget"]["counts_toward_40_primary_executions"])
        self.assertEqual(contract["authorization"]["flag"], "--authorize-smoke-execution")
        self.assertFalse(contract["authorization"]["authorization_overrides_security"])

    def test_offline_plan_never_enables_model_execution(self):
        plan = smoke.plan()
        self.assertEqual(plan["maximum_codex_executions"], 1)
        self.assertEqual(plan["model_calls"], 0)
        self.assertFalse(plan["model_execution_enabled"])
        self.assertTrue(plan["authorization_required"])
        self.assertFalse(plan["counts_toward_40_primary_executions"])

    def test_preflight_reuses_full_runner_and_requires_separate_smoke_authorization(self):
        qualification = object()
        expected = representative.PreflightRefusal(
            "explicit representative execution authorization required")
        with patch.object(representative, "real_run", side_effect=expected) as full, \
             patch.object(smoke.primitives, "artifact_directory",
                          side_effect=AssertionError("artifact")):
            with self.assertRaisesRegex(
                    smoke.SmokePreflightRefusal,
                    "explicit representative smoke execution authorization required"):
                smoke.real_smoke(
                    "/fake/codex", "smoke-test", qualification,
                    grading_runtime_root="/tmp/runtime",
                    grading_inventory_dir="/tmp/inventory",
                    authorized=False,
                )
        self.assertFalse(full.call_args.kwargs["authorized"])

    def test_failed_full_runner_gate_cannot_be_overridden_by_smoke_authorization(self):
        qualification = object()
        blocked = representative.PreflightRefusal(
            "production grading evidence is not verified")
        with patch.object(representative, "real_run", side_effect=blocked), \
             patch.object(smoke.primitives, "artifact_directory",
                          side_effect=AssertionError("artifact")), \
             patch.object(smoke.b, "execute", side_effect=AssertionError("model")):
            with self.assertRaisesRegex(
                    smoke.SmokePreflightRefusal,
                    "representative campaign preflight rejected"):
                smoke.real_smoke(
                    "/fake/codex", "smoke-test", qualification,
                    grading_runtime_root="/tmp/runtime",
                    grading_inventory_dir="/tmp/inventory",
                    authorized=True,
                )

    def test_authorized_path_runs_exactly_one_benchmark_job(self):
        qualification = type("Q", (), {
            "reference": "q" * 64,
            "evidence": type("E", (), {
                "components": (type("C", (), {
                    "component": "agent_execution_isolation",
                    "evidence_sha256": "a" * 64,
                })(),)
            })(),
        })()
        runtime = type("R", (), {"inventory_reference": "r" * 64})()
        contract = smoke.load()
        fake_record = {
            "schema_version": 1, "scenario_id": "python-billing", "variant": "vanilla",
            "repetition": 0, "order_seed": 14, "snapshot": "s", "references": {},
            "cold_warm": "unknown", "index_seconds": None, "bootstrap_seconds": None,
            "retry_count": 0, "initial_failure": None, "final_status": None,
            "quality_pass": True, "attempts": [{
                "terminal_status": "completed", "exit_status": 0, "errors": [],
                "quality_pass": True, "failure_reason": None, "duration": 1.0,
                "tokens": {"input": 1, "cached_input": 0, "output": 1,
                           "reasoning": 0, "fresh_input": None, "total": None},
                "observed_tool_calls": 0,
            }],
        }
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(smoke, "load", return_value=contract), \
             patch.object(smoke, "_prove_full_runner_preflight"), \
             patch.object(smoke.submission_grading, "prepare_runtime", return_value=runtime), \
             patch.object(representative, "_identity_preflight"), \
             patch.object(smoke.agent_isolation, "runtime_preflight"), \
             patch.object(smoke.readiness, "load_candidate_evidence",
                          return_value={"evidence_reference": contract["technical_readiness_reference"]}), \
             patch.object(smoke.primitives, "artifact_directory", return_value=Path(tmp)), \
             patch.object(smoke.submission_grading, "load_candidate_evidence",
                          return_value={"evidence_reference": contract["production_grading_reference"]}), \
             patch.object(smoke.b, "run", return_value=fake_record) as run, \
             patch.object(representative, "_normalized", return_value={"safe": True}):
            result = smoke.real_smoke(
                "/fake/codex", "one-smoke", qualification,
                grading_runtime_root="/tmp/runtime", grading_inventory_dir="/tmp/inventory",
                authorized=True,
            )
        self.assertEqual(run.call_count, 1)
        self.assertEqual(result["maximum_codex_executions"], 1)
        self.assertEqual(result["attempted_jobs"], 1)
        self.assertFalse(result["counts_toward_40_primary_executions"])

    def test_contract_tamper_fails_closed(self):
        changed = smoke.expected_contract()
        changed["maximum_codex_executions"] = 2
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "smoke.json"
            path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                smoke.load(path)

    def test_cli_real_without_smoke_authorization_refuses(self):
        expected = representative.PreflightRefusal(
            "explicit representative execution authorization required")
        with patch.object(smoke.host, "current_host", return_value=object()), \
             patch.object(representative, "real_run", side_effect=expected), \
             contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                smoke.main([
                    "--real",
                    "--codex", "/fake/codex",
                    "--grading-runtime-root", "/tmp/runtime",
                    "--grading-inventory-dir", "/tmp/inventory",
                ])


if __name__ == "__main__":
    unittest.main()
