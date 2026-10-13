import json
import os
from pathlib import Path
import tempfile
import unittest

import benchmark_telemetry as telemetry


def record(*, scenario="s1", variant="vanilla", quality=True, failure=None,
           duration=1.5, input_tokens=10, tool_calls=2, cold_warm=None):
    value = {
        "schema_version": 1,
        "campaign_id": "campaign-v1",
        "scenario_id": scenario,
        "variant": variant,
        "repetition": 0,
        "seed": 14,
        "frozen_references": {
            "cold_warm": {"classification": "unknown"},
        },
        "host_qualification_reference": "host",
        "agent_execution_isolation_reference": "agent",
        "grading_isolation_reference": "grading",
        "production_grading_reference": "production",
        "grading_runtime_inventory_reference": "runtime",
        "terminal_status": "completed" if failure is None else "failed",
        "process_exit_status": 0 if failure is None else 1,
        "parser_valid": True,
        "parser_errors": [],
        "quality_pass": quality,
        "failure_reason": failure,
        "duration_seconds": duration,
        "observed_tokens": {
            "input": input_tokens,
            "cached_input": 4 if input_tokens is not None else None,
            "output": 2 if input_tokens is not None else None,
            "reasoning": 1 if input_tokens is not None else None,
            "fresh_input": None,
            "total": None,
        },
        "observed_tool_calls_lower_bound": tool_calls,
        "full_tool_calls": None,
        "retry_count": 0,
        "attempt_count": 1,
        "execution_kind": "test",
        "model_calls": None,
        "split_host_topology_reference": "split",
        "agent_trace_sha256": "0" * 64,
        "submission_sha256": "1" * 64 if quality else None,
    }
    if cold_warm is not None:
        value["cold_warm"] = cold_warm
    return value


class BenchmarkTelemetryTests(unittest.TestCase):
    def make_dir(self, values):
        tmp = tempfile.TemporaryDirectory(dir="/tmp")
        root = Path(tmp.name)
        for index, value in enumerate(values):
            (root / f"record-{index}.json").write_text(json.dumps(value))
        return tmp, root

    def test_default_aggregate_is_privacy_bounded_and_no_breakdown(self):
        tmp, root = self.make_dir([
            record(variant="vanilla"),
            record(variant="native", duration=2.5, input_tokens=20, tool_calls=1),
        ])
        self.addCleanup(tmp.cleanup)
        report = telemetry.aggregate_directory(root)
        self.assertEqual(report["record_count"], 2)
        self.assertNotIn("scenarios", report)
        self.assertEqual(set(report["variants"]), {"native", "vanilla"})
        self.assertEqual(report["overall"]["quality_passes"], 2)
        self.assertEqual(report["overall"]["tokens"]["input"]["sum"], 30)
        self.assertEqual(report["overall"]["observed_tool_calls_lower_bound"]["sum"], 3)
        self.assertEqual(report["overall"]["cold_warm"], {
            "cold": 0, "warm": 0, "unknown": 2})
        self.assertEqual(report["privacy"], {
            "input_contract": "normalized-records-only",
            "raw_trace_ingested": False,
            "prompt_ingested": False,
            "source_ingested": False,
            "stderr_ingested": False,
            "credential_data_ingested": False,
            "network_export": False,
            "scenario_breakdown_included": False,
        })
        serialized = json.dumps(report)
        for forbidden in ("prompt", "stderr", "credential", "/tmp/"):
            if forbidden == "prompt":
                self.assertIn('"prompt_ingested": false', serialized)
            elif forbidden == "stderr":
                self.assertIn('"stderr_ingested": false', serialized)
            elif forbidden == "credential":
                self.assertIn('"credential_data_ingested": false', serialized)
            else:
                self.assertNotIn(forbidden, serialized)

    def test_scenario_breakdown_requires_explicit_opt_in(self):
        tmp, root = self.make_dir([
            record(scenario="a"),
            record(scenario="b", variant="native"),
        ])
        self.addCleanup(tmp.cleanup)
        default = telemetry.aggregate_directory(root)
        detailed = telemetry.aggregate_directory(root, include_scenario_breakdown=True)
        self.assertNotIn("scenarios", default)
        self.assertEqual(set(detailed["scenarios"]), {"a", "b"})
        self.assertTrue(detailed["privacy"]["scenario_breakdown_included"])

    def test_missing_counters_remain_unknown_not_zero(self):
        tmp, root = self.make_dir([
            record(input_tokens=None, tool_calls=None, quality=False, failure="timeout"),
        ])
        self.addCleanup(tmp.cleanup)
        report = telemetry.aggregate_directory(root)
        for key in ("input", "fresh_input", "total"):
            metric = report["overall"]["tokens"][key]
            self.assertEqual(metric, {
                "samples": 0, "sum": None, "median": None, "range": None})
        self.assertEqual(report["overall"]["full_tool_calls"], {
            "samples": 0, "sum": None, "median": None, "range": None})
        self.assertEqual(report["overall"]["model_calls"], {
            "samples": 0, "sum": None, "median": None, "range": None})
        self.assertEqual(report["overall"]["setup_seconds"], {
            "samples": 0, "sum": None, "median": None, "range": None})

    def test_explicit_overhead_and_cold_warm_are_aggregated_when_present(self):
        value = record(cold_warm="cold")
        value["setup_seconds"] = 0.4
        value["index_seconds"] = 1.2
        value["bootstrap_seconds"] = 0.8
        tmp, root = self.make_dir([value])
        self.addCleanup(tmp.cleanup)
        report = telemetry.aggregate_directory(root)
        self.assertEqual(report["overall"]["cold_warm"]["cold"], 1)
        self.assertEqual(report["overall"]["setup_seconds"]["sum"], 0.4)
        self.assertEqual(report["overall"]["index_seconds"]["sum"], 1.2)
        self.assertEqual(report["overall"]["bootstrap_seconds"]["sum"], 0.8)

    def test_unexpected_raw_like_field_is_rejected_without_reflection(self):
        value = record()
        value["prompt"] = "SECRET_MARKER"
        tmp, root = self.make_dir([value])
        self.addCleanup(tmp.cleanup)
        with self.assertRaisesRegex(
                telemetry.TelemetryRefusal,
                "^normalized record field contract rejected$") as error:
            telemetry.aggregate_directory(root)
        self.assertNotIn("SECRET_MARKER", str(error.exception))

    def test_unknown_failure_string_is_bucketed_without_reflection(self):
        value = record(quality=False, failure="PRIVATE_ERROR_TEXT")
        tmp, root = self.make_dir([value])
        self.addCleanup(tmp.cleanup)
        report = telemetry.aggregate_directory(root)
        self.assertEqual(report["overall"]["failure_counts"]["other"], 1)
        self.assertNotIn("PRIVATE_ERROR_TEXT", json.dumps(report))

    def test_symlink_record_is_rejected(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            target = root / "target"
            target.write_text(json.dumps(record()))
            (root / "record.json").symlink_to(target.name)
            with self.assertRaisesRegex(
                    telemetry.TelemetryRefusal, "symlink normalized record rejected"):
                telemetry.aggregate_directory(root)

    def test_private_output_is_exclusive_and_mode_0600(self):
        tmp, root = self.make_dir([record()])
        self.addCleanup(tmp.cleanup)
        report = telemetry.aggregate_directory(root)
        output = root / "telemetry-output"
        telemetry._write_private(output, report)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        with self.assertRaisesRegex(
                telemetry.TelemetryRefusal, "telemetry output already exists"):
            telemetry._write_private(output, report)

    def test_checked_in_representative_snapshot_is_safe_and_complete(self):
        path = Path(__file__).resolve().parent.parent / "benchmarks/representative-telemetry-v1.json"
        report = json.loads(path.read_text())
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["telemetry_kind"], "benchmark-aggregate-v1")
        self.assertEqual(report["record_count"], 40)
        self.assertEqual(report["overall"]["quality_passes"], 36)
        self.assertEqual(report["overall"]["quality_failures"], 4)
        self.assertEqual(report["overall"]["tokens"]["input"]["samples"], 36)
        self.assertEqual(report["overall"]["fresh_input"] if "fresh_input" in report["overall"] else None, None)
        self.assertEqual(report["overall"]["tokens"]["fresh_input"]["samples"], 0)
        self.assertEqual(report["overall"]["full_tool_calls"]["samples"], 0)
        self.assertEqual(report["overall"]["model_calls"]["samples"], 0)
        self.assertEqual(report["overall"]["cold_warm"]["unknown"], 40)
        self.assertFalse(report["privacy"]["scenario_breakdown_included"])
        self.assertNotIn("scenarios", report)
        self.assertEqual(
            telemetry.hashlib.sha256(path.read_bytes()).hexdigest(),
            "359b01bcabd104a5b02289be9d9fdb599d0831acbbdf676514acc9fd7a2686a7",
        )

    def test_schema_top_level_matches_emitted_contract(self):
        schema_path = Path(__file__).resolve().parent.parent / "benchmarks/schema/telemetry.schema.json"
        schema = json.loads(schema_path.read_text())
        tmp, root = self.make_dir([record()])
        self.addCleanup(tmp.cleanup)
        report = telemetry.aggregate_directory(root)
        self.assertEqual(set(schema["required"]), set(report))
        self.assertFalse(schema["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
