import copy
import json
from pathlib import Path
import tempfile
import unittest

import benchmark_coverage as coverage
import benchmark_readiness_probe as readiness


class RepresentativeReadinessEvidenceTests(unittest.TestCase):
    def test_committed_candidate_is_valid_and_pinned_by_campaign(self):
        record = readiness.load_candidate_evidence()
        self.assertEqual(
            record["evidence_reference"],
            "1b5feee9b507f3bee97560a1a619a300e44a1e5372b10a832e23ce85b35fff2c",
        )
        self.assertEqual(record["model_calls"], 0)
        self.assertFalse(record["real_credentials_used"])
        candidate = record["candidate"]
        for key in (
            "codex_shell_environment_config_parse",
            "rust_compile_run",
            "go_compile_run",
            "python_run",
            "representative_campaign_ready",
        ):
            self.assertIs(candidate[key], True)
        self.assertFalse(candidate["plan_model_execution_enabled"])
        self.assertFalse(candidate["preauthorization_artifact_created"])
        self.assertEqual(candidate["preauthorization_model_calls"], 0)
        self.assertEqual(candidate["preauthorization_attempt_count"], 0)
        self.assertEqual(
            candidate["preauthorization_refusal"],
            "explicit representative execution authorization required",
        )
        campaign = coverage.load_campaign()
        self.assertEqual(
            campaign["runner_pins"]["readiness_candidate_evidence_sha256"],
            readiness.sha256(readiness.CANDIDATE_EVIDENCE),
        )
        self.assertEqual(
            campaign["runner_pins"]["readiness_probe_sha256"],
            readiness.sha256(Path(readiness.__file__)),
        )

    def test_candidate_tamper_fails_closed(self):
        record = json.loads(readiness.CANDIDATE_EVIDENCE.read_text())
        changed = copy.deepcopy(record)
        changed["candidate"]["preauthorization_model_calls"] = 1
        changed["evidence_reference"] = readiness.candidate_reference(changed["candidate"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.json"
            path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                readiness.load_candidate_evidence(path)

    def test_evidence_reference_tamper_fails_closed(self):
        record = json.loads(readiness.CANDIDATE_EVIDENCE.read_text())
        record["evidence_reference"] = "0" * 64
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.json"
            path.write_text(json.dumps(record))
            with self.assertRaises(ValueError):
                readiness.load_candidate_evidence(path)


if __name__ == "__main__":
    unittest.main()
