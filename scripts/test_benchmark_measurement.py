import json
from pathlib import Path
import tempfile
import unittest

import benchmark_measurement as measurement


class RepresentativeMeasurementTests(unittest.TestCase):
    def test_candidate_is_frozen_but_not_yet_accepted(self):
        contract = measurement.load_contract()
        candidate = measurement.load_candidate()
        self.assertEqual(contract["planned_jobs"], 40)
        self.assertEqual(contract["completed_jobs"], 40)
        self.assertEqual(contract["retries"], 0)
        self.assertEqual(contract["accepted_evidence_sha256"], [])
        self.assertEqual(
            candidate["evidence_reference"],
            "ffd8fbbc66934478e4591d65811daecc7b8012083157c9fabc97f4647c9bc347",
        )
        self.assertFalse(measurement.measurement_verified())

    def test_strict_result_keeps_failures_in_denominator(self):
        result = measurement.load_candidate()["candidate"]
        self.assertEqual(result["strict"]["vanilla"]["runs"], 20)
        self.assertEqual(result["strict"]["vanilla"]["quality_passes"], 19)
        self.assertEqual(result["strict"]["vanilla"]["quality_pass_rate"], 0.95)
        self.assertEqual(result["strict"]["native"]["runs"], 20)
        self.assertEqual(result["strict"]["native"]["quality_passes"], 17)
        self.assertEqual(result["strict"]["native"]["quality_pass_rate"], 0.85)
        self.assertEqual(result["strict"]["vanilla"]["failures"], 1)
        self.assertEqual(result["strict"]["native"]["failures"], 3)

    def test_submission_quality_is_separate_from_operational_failures(self):
        result = measurement.load_candidate()["candidate"]["diagnostic"]
        self.assertEqual(result["exported_submissions"], 36)
        self.assertEqual(result["production_graded_submissions"], 36)
        self.assertEqual(result["production_quality_passes"], 36)
        self.assertEqual(result["production_quality_failures"], 0)
        self.assertEqual(len(result["provider_capacity_failures"]), 2)
        self.assertEqual(len(result["timeout_failures"]), 2)

    def test_paired_diagnostic_does_not_claim_general_savings(self):
        result = measurement.load_candidate()["candidate"]
        paired = result["diagnostic"]["paired_native_vs_vanilla"]
        self.assertEqual(
            result["diagnostic"]["successful_token_observed_matched_pairs"], 16)
        self.assertEqual(
            paired["observed_tool_calls_lower_bound"]["native_lower"], 12)
        self.assertEqual(
            paired["observed_tool_calls_lower_bound"]["native_higher"], 2)
        self.assertEqual(
            paired["observed_tool_calls_lower_bound"]["ties"], 2)
        self.assertAlmostEqual(
            paired["observed_tool_calls_lower_bound"]["median_percent_delta"],
            -19.444444,
        )
        self.assertAlmostEqual(
            paired["duration"]["median_percent_delta"], 3.712106)
        self.assertAlmostEqual(
            paired["input_tokens"]["median_percent_delta"], -1.316043)
        self.assertIsNone(result["interpretation"]["winner"])
        self.assertIsNone(result["interpretation"]["savings_claim"])

    def test_candidate_tamper_is_rejected(self):
        record = json.loads(measurement.CANDIDATE.read_text())
        record["candidate"]["strict"]["native"]["quality_passes"] = 18
        record["evidence_reference"] = measurement._hash_json(record["candidate"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.json"
            path.write_text(json.dumps(record))
            with self.assertRaises(measurement.MeasurementRefusal):
                measurement.load_candidate(path)


if __name__ == "__main__":
    unittest.main()
