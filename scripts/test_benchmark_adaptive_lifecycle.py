import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import benchmark_adaptive_lifecycle as adaptive
import benchmark_adaptive_profile_smoke as profile_smoke


class AdaptiveLifecycleTests(unittest.TestCase):
    def test_contract_is_frozen_and_execution_stays_disabled(self):
        contract = adaptive.load_contract()
        self.assertEqual(contract["measurement_id"], "adaptive-lifecycle-v1")
        self.assertEqual(contract["adaptive_campaign"]["jobs"], 20)
        self.assertEqual(
            contract["adaptive_campaign"]["maximum_codex_executions"], 40
        )
        self.assertEqual(contract["adaptive_campaign"]["max_attempts_per_job"], 2)
        self.assertEqual(contract["adaptive_campaign"]["max_retries_per_job"], 1)
        self.assertEqual(
            contract["profile_smoke"]["maximum_codex_executions"], 3
        )
        self.assertEqual(contract["profile_smoke"]["accepted_evidence_sha256"], [])
        self.assertFalse(adaptive.profile_mapping_verified())
        execution = adaptive.load_profile_execution_candidate()
        self.assertEqual(
            execution["evidence_reference"],
            "908a97f105e1a29fbc5aafed15a3becbece6fa38311cde7d9f968b185f3814d0",
        )
        self.assertTrue(
            execution["candidate"]["all_profiles_execution_and_quality_verified"]
        )
        plan = adaptive.offline_plan()
        self.assertEqual(
            plan["profile_execution_evidence_reference"],
            "908a97f105e1a29fbc5aafed15a3becbece6fa38311cde7d9f968b185f3814d0",
        )
        self.assertFalse(plan["model_execution_enabled"])
        self.assertTrue(plan["profile_smoke_authorization_required"])
        self.assertTrue(plan["adaptive_campaign_authorization_required"])

    def test_profile_candidate_is_sanitized_and_unverified(self):
        record = adaptive.load_profile_candidate()
        candidate = record["candidate"]
        self.assertEqual(candidate["model_calls_during_probe"], 0)
        self.assertFalse(candidate["execution_verified"])
        self.assertEqual(
            set(candidate["profiles"]), {"economy", "standard", "strong"}
        )
        serialized = json.dumps(candidate)
        for forbidden in (
            "auth.json", "api_key", "/home/", "password", "credential_store"
        ):
            self.assertNotIn(forbidden, serialized.lower())

    def test_scenario_mapping_is_explicit_complete_and_ordered(self):
        manifest = json.loads(adaptive.REPRESENTATIVE_MANIFEST.read_text())
        expected = [row["id"] for row in manifest["scenarios"]]
        self.assertEqual(list(adaptive.SCENARIO_POLICY), expected)
        self.assertEqual(len(adaptive.SCENARIO_POLICY), 10)
        for policy in adaptive.SCENARIO_POLICY.values():
            self.assertEqual(
                set(policy), {"task", "archetype", "risk", "safety"}
            )

    def test_stub_adapter_output_is_strictly_validated(self):
        payload = {
            "schema_version": 1,
            "state": "ready",
            "profile": "economy",
            "reasoning": "medium",
            "model_key": 10,
            "attempts_started": 0,
            "retries_used": 0,
            "delegations_used": 0,
        }
        with tempfile.TemporaryDirectory() as tmp:
            adapter = Path(tmp) / "adapter"
            adapter.write_text(
                "#!/bin/sh\nprintf '%s\\n' '"
                + json.dumps(payload, separators=(",", ":"))
                + "'\n"
            )
            adapter.chmod(0o700)
            result = adaptive._adapter_output(
                adapter, adaptive.SCENARIO_POLICY["explore-notification"]
            )
            self.assertEqual(result, payload)

            payload["model_key"] = 30
            adapter.write_text(
                "#!/bin/sh\nprintf '%s\\n' '"
                + json.dumps(payload, separators=(",", ":"))
                + "'\n"
            )
            with self.assertRaisesRegex(
                adaptive.AdaptiveMeasurementRefusal, "profile mapping mismatch"
            ):
                adaptive._adapter_output(
                    adapter, adaptive.SCENARIO_POLICY["explore-notification"]
                )

    def test_adapter_symlink_and_unexpected_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.write_text("#!/bin/sh\necho '{}'\n")
            target.chmod(0o700)
            link = root / "link"
            link.symlink_to(target.name)
            with self.assertRaisesRegex(
                adaptive.AdaptiveMeasurementRefusal, "regular adaptive adapter"
            ):
                adaptive._adapter_output(
                    link, adaptive.SCENARIO_POLICY["explore-notification"]
                )

    def test_profile_candidate_tamper_is_rejected(self):
        record = json.loads(adaptive.PROFILE_CANDIDATE.read_text())
        record["candidate"]["profiles"]["economy"]["model"] = "unreviewed"
        record["evidence_reference"] = adaptive._json_hash(record["candidate"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.json"
            path.write_text(json.dumps(record))
            with self.assertRaises(adaptive.AdaptiveMeasurementRefusal):
                adaptive.load_profile_candidate(path)

    def test_profile_execution_evidence_tamper_is_rejected(self):
        record = json.loads(adaptive.PROFILE_EXECUTION_CANDIDATE.read_text())
        record["candidate"]["rows"][0]["quality_pass"] = False
        record["evidence_reference"] = adaptive._json_hash(record["candidate"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "execution.json"
            path.write_text(json.dumps(record))
            with self.assertRaises(adaptive.AdaptiveMeasurementRefusal):
                adaptive.load_profile_execution_candidate(path)

    def test_profile_smoke_plan_is_bounded_and_authorization_precedes_preflight(self):
        plan = profile_smoke.plan()
        self.assertEqual(plan["maximum_codex_executions"], 3)
        self.assertEqual(plan["retries"], 0)
        self.assertFalse(plan["model_execution_enabled"])
        with patch.object(
            profile_smoke.split, "agent_preflight",
            side_effect=AssertionError("preflight crossed"),
        ):
            with self.assertRaisesRegex(
                profile_smoke.ProfileSmokeRefusal,
                "explicit adaptive profile smoke execution authorization required",
            ):
                profile_smoke.run_agent(
                    "/fake/codex", "/fake/host", "/tmp/runtime", "/tmp/inventory",
                    "never-created", authorized=False,
                )

    def test_profile_smoke_command_override_changes_only_model_and_reasoning(self):
        argv = [
            "/codex", "exec", "--json", "--model", "gpt-6-sol",
            "-c", 'model_reasoning_effort="low"', "-",
        ]
        changed = profile_smoke._override_command(argv, "gpt-6-astra", "high")
        self.assertEqual(argv[4], "gpt-6-sol")
        self.assertEqual(changed[4], "gpt-6-astra")
        self.assertIn('model_reasoning_effort="high"', changed)
        self.assertEqual(changed[-1], "-")

    def test_contract_tamper_is_rejected(self):
        record = json.loads(adaptive.CONTRACT.read_text())
        record["adaptive_campaign"]["maximum_codex_executions"] = 41
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "contract.json"
            path.write_text(json.dumps(record))
            with self.assertRaises(adaptive.AdaptiveMeasurementRefusal):
                adaptive.load_contract(path)


if __name__ == "__main__":
    unittest.main()
