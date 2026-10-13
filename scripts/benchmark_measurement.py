"""Frozen representative measured-baseline evidence.

This module validates only sanitized, normalized measurement evidence. Raw traces,
stderr, prompts, source and credentials remain off-repository.
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "benchmarks/representative-measurement-v1.json"
CANDIDATE = ROOT / "benchmarks/representative-measurement-candidate-v1.json"

CAMPAIGN_SHA256 = "902659ca56285a4731c3b0a6095f3c293c77246991e43bfecd8bb237f82e7efd"
CAMPAIGN_REPOSITORY_COMMIT = "08d255788562b03d0682ca92ee6141f26c5a1618"
SPLIT_HOST_REFERENCE = "1a9e7a145e7271b872d2dfc54c92a6ac578cbd8859649f8c4c062a127f3aac43"
GRADED_SUMMARY_SHA256 = "731507580e252f49efcdb8e93dede5e5c0dd4be3ec30e55865f68660192cd542"
PRIVATE_AGENT_ARCHIVE_SHA256 = "3636514e3f5dbc1e300938bfed23a058d3fbd824ddd0fb51306615543bbc9dcd"
PRIVATE_EVIDENCE_MANIFEST_SHA256 = "391bb8f0ecc5a8d792478580d596efecd05598e311894075f24aa4b9055b1a43"


class MeasurementRefusal(ValueError):
    pass


def _hash_json(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def expected_contract():
    return {
        "schema_version": 1,
        "measurement_id": "representative-development-measurement-v1",
        "campaign_id": "representative-development-v1",
        "campaign_sha256": CAMPAIGN_SHA256,
        "campaign_repository_commit": CAMPAIGN_REPOSITORY_COMMIT,
        "split_host_topology_reference": SPLIT_HOST_REFERENCE,
        "planned_jobs": 40,
        "completed_jobs": 40,
        "retries": 0,
        "variants": ["vanilla", "native"],
        "repetitions_per_variant": 20,
        "raw_evidence_policy": "private-off-repository",
        "normalized_evidence": {
            "graded_summary_sha256": GRADED_SUMMARY_SHA256,
            "private_agent_archive_sha256": PRIVATE_AGENT_ARCHIVE_SHA256,
            "private_evidence_manifest_sha256": PRIVATE_EVIDENCE_MANIFEST_SHA256,
        },
        "interpretation_policy": {
            "strict_failures_remain_in_denominator": True,
            "provider_capacity_is_not_relabelled_as_quality_pass": True,
            "diagnostic_submission_quality_reported_separately": True,
            "paired_cost_analysis_requires_both_variants_quality_pass_and_observed_counter": True,
            "no_winner_claim_from_this_sample": True,
        },
        "accepted_evidence_sha256": ["ffd8fbbc66934478e4591d65811daecc7b8012083157c9fabc97f4647c9bc347"],
    }


def load_contract(path=CONTRACT):
    actual = json.loads(Path(path).read_text())
    if json.dumps(actual, sort_keys=True) != json.dumps(expected_contract(), sort_keys=True):
        raise MeasurementRefusal("unreviewed representative measurement contract")
    return actual


def expected_candidate():
    return {
        "campaign_sha256": CAMPAIGN_SHA256,
        "completed_jobs": 40,
        "strict": {
            "vanilla": {
                "runs": 20,
                "quality_passes": 19,
                "quality_pass_rate": 0.95,
                "failures": 1,
                "failure_rate": 0.05,
                "timeout_failures": 1,
                "agent_failures": 0,
                "cost_samples": 16,
                "duration_median_seconds": 60.132829870501155,
                "input_tokens_median": 129602.0,
                "cached_input_tokens_median": 111104.0,
                "output_tokens_median": 1755.5,
                "reasoning_tokens_median": 137.5,
            },
            "native": {
                "runs": 20,
                "quality_passes": 17,
                "quality_pass_rate": 0.85,
                "failures": 3,
                "failure_rate": 0.15,
                "timeout_failures": 1,
                "agent_failures": 2,
                "cost_samples": 16,
                "duration_median_seconds": 61.52577563600062,
                "input_tokens_median": 130725.0,
                "cached_input_tokens_median": 121216.0,
                "output_tokens_median": 1668.5,
                "reasoning_tokens_median": 123.5,
            },
        },
        "diagnostic": {
            "exported_submissions": 36,
            "production_graded_submissions": 36,
            "production_quality_passes": 36,
            "production_quality_failures": 0,
            "provider_capacity_failures": [
                "infra-service-policy-native-0-14",
                "infra-service-policy-native-1-14",
            ],
            "timeout_failures": [
                "explore-notification-native-1-14",
                "python-config-tests-vanilla-0-14",
            ],
            "successful_token_observed_matched_pairs": 16,
            "paired_native_vs_vanilla": {
                "duration": {
                    "median_percent_delta": 3.712106,
                    "mean_percent_delta": 0.804644,
                    "native_lower": 8,
                    "native_higher": 8,
                    "ties": 0,
                },
                "input_tokens": {
                    "median_percent_delta": -1.316043,
                    "mean_percent_delta": 0.429739,
                    "native_lower": 9,
                    "native_higher": 7,
                    "ties": 0,
                },
                "cached_input_tokens": {
                    "median_percent_delta": 4.288858,
                    "mean_percent_delta": 7.186859,
                    "native_lower": 5,
                    "native_higher": 11,
                    "ties": 0,
                },
                "output_tokens": {
                    "median_percent_delta": -0.641315,
                    "mean_percent_delta": 3.055669,
                    "native_lower": 8,
                    "native_higher": 8,
                    "ties": 0,
                },
                "reasoning_tokens": {
                    "median_percent_delta": 11.859838,
                    "mean_percent_delta": 27.828131,
                    "native_lower": 7,
                    "native_higher": 9,
                    "ties": 0,
                },
                "observed_tool_calls_lower_bound": {
                    "median_percent_delta": -19.444444,
                    "mean_percent_delta": -14.077089,
                    "native_lower": 12,
                    "native_higher": 2,
                    "ties": 2,
                },
            },
        },
        "scenario_quality_passes": {
            "explore-notification": {"vanilla": 2, "native": 1},
            "go-pagination": {"vanilla": 2, "native": 2},
            "go-reservations": {"vanilla": 2, "native": 2},
            "infra-service-policy": {"vanilla": 2, "native": 0},
            "python-billing": {"vanilla": 2, "native": 2},
            "python-config-tests": {"vanilla": 1, "native": 2},
            "python-result-api": {"vanilla": 2, "native": 2},
            "repo-ci-gates": {"vanilla": 2, "native": 2},
            "rust-duration": {"vanilla": 2, "native": 2},
            "rust-ledger": {"vanilla": 2, "native": 2},
        },
        "interpretation": {
            "strict_headline": "vanilla 95% quality pass; native 85% quality pass",
            "submission_quality": "all 36 exported submissions passed independent production grading",
            "failure_diagnosis": "native strict deficit includes two provider-capacity failures; each variant also had one timeout",
            "cost_diagnosis": "matched successful pairs show no latency or input-token win; native shows a descriptive reduction in observed tool-call lower bound",
            "winner": None,
            "savings_claim": None,
        },
    }


def load_candidate(path=CANDIDATE):
    record = json.loads(Path(path).read_text())
    if type(record) is not dict or set(record) != {
            "schema_version", "measurement_id", "candidate",
            "evidence_reference", "model_calls_during_analysis"}:
        raise MeasurementRefusal("invalid measurement candidate envelope")
    contract = load_contract()
    if (record["schema_version"] != 1
            or record["measurement_id"] != contract["measurement_id"]
            or record["model_calls_during_analysis"] != 0):
        raise MeasurementRefusal("measurement candidate identity mismatch")
    expected = expected_candidate()
    if record["candidate"] != expected:
        raise MeasurementRefusal("measurement candidate payload mismatch")
    if record["evidence_reference"] != _hash_json(expected):
        raise MeasurementRefusal("measurement candidate evidence reference mismatch")
    return record


def measurement_verified():
    try:
        contract = load_contract()
        candidate = load_candidate()
    except (OSError, ValueError):
        return False
    return candidate["evidence_reference"] in contract["accepted_evidence_sha256"]


def report():
    candidate = load_candidate()["candidate"]
    return {
        "measurement_id": load_contract()["measurement_id"],
        "completed_jobs": candidate["completed_jobs"],
        "strict": candidate["strict"],
        "diagnostic": candidate["diagnostic"],
        "interpretation": candidate["interpretation"],
        "measurement_verified": measurement_verified(),
    }


if __name__ == "__main__":
    print(json.dumps(report(), indent=2, sort_keys=True))
