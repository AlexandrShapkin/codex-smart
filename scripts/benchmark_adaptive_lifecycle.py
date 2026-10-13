"""Prepared adaptive lifecycle measurement contract for issue #46.

The module is fail-closed. It validates a frozen scenario-policy mapping and delegates
all adaptive profile/reasoning transitions to the compiled Rust adapter built from
codex-smart-core. Live model execution remains disabled until the separately reviewed
profile-mapping smoke evidence is accepted and an explicit execution authorization is
provided.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "benchmarks/adaptive-lifecycle-v1.json"
PROFILE_CANDIDATE = ROOT / "benchmarks/adaptive-profile-candidate-v1.json"
PROFILE_EXECUTION_CANDIDATE = ROOT / "benchmarks/adaptive-profile-execution-candidate-v1.json"
REPRESENTATIVE_CAMPAIGN = ROOT / "benchmarks/representative-campaign-v1.json"
REPRESENTATIVE_MANIFEST = ROOT / "benchmarks/representative-manifest.json"
ADAPTER_SOURCE = (
    ROOT / "crates/codex-smart-core/examples/adaptive_benchmark_plan.rs"
)

BASELINE_EVIDENCE = (
    "ffd8fbbc66934478e4591d65811daecc7b8012083157c9fabc97f4647c9bc347"
)
SPLIT_HOST_REFERENCE = (
    "1a9e7a145e7271b872d2dfc54c92a6ac578cbd8859649f8c4c062a127f3aac43"
)
CAMPAIGN_SHA256 = (
    "902659ca56285a4731c3b0a6095f3c293c77246991e43bfecd8bb237f82e7efd"
)
MANIFEST_SHA256 = (
    "56ce0de31ac4b1c070b8e1e1911d7f396f754c3fefdf4bf675a4aa2b894ac486"
)

SCENARIO_POLICY = {
    "rust-ledger": {
        "task": "edit",
        "archetype": "focused-bug-fix",
        "risk": "medium",
        "safety": "none",
    },
    "rust-duration": {
        "task": "refactor",
        "archetype": "api-change",
        "risk": "medium",
        "safety": "none",
    },
    "go-pagination": {
        "task": "edit",
        "archetype": "api-change",
        "risk": "medium",
        "safety": "none",
    },
    "go-reservations": {
        "task": "refactor",
        "archetype": "refactor",
        "risk": "medium",
        "safety": "none",
    },
    "python-config-tests": {
        "task": "edit",
        "archetype": "failing-test-repair",
        "risk": "low",
        "safety": "none",
    },
    "python-billing": {
        "task": "edit",
        "archetype": "feature-implementation",
        "risk": "medium",
        "safety": "none",
    },
    "python-result-api": {
        "task": "refactor",
        "archetype": "api-change",
        "risk": "medium",
        "safety": "none",
    },
    "infra-service-policy": {
        "task": "edit",
        "archetype": "security-sensitive-change",
        "risk": "high",
        "safety": "security",
    },
    "repo-ci-gates": {
        "task": "edit",
        "archetype": "ci-config-repair",
        "risk": "high",
        "safety": "security",
    },
    "explore-notification": {
        "task": "inspect",
        "archetype": "inspection",
        "risk": "low",
        "safety": "none",
    },
}

PROFILE_MAP = {
    "10": {
        "profile": "economy",
        "model": "gpt-6-luna",
        "smoke_reasoning": "medium",
        "description": "fast-and-affordable-easier-tasks",
    },
    "20": {
        "profile": "standard",
        "model": "gpt-6-sol",
        "smoke_reasoning": "high",
        "description": "workhorse",
    },
    "30": {
        "profile": "strong",
        "model": "gpt-6-astra",
        "smoke_reasoning": "high",
        "description": "frontier-demanding-work",
    },
}

PROFILE_SMOKE = [
    {
        "profile": "economy",
        "model_key": 10,
        "scenario_id": "explore-notification",
        "reasoning": "medium",
    },
    {
        "profile": "standard",
        "model_key": 20,
        "scenario_id": "python-result-api",
        "reasoning": "high",
    },
    {
        "profile": "strong",
        "model_key": 30,
        "scenario_id": "infra-service-policy",
        "reasoning": "high",
    },
]


class AdaptiveMeasurementRefusal(ValueError):
    pass


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def expected_contract():
    return {
        "schema_version": 1,
        "measurement_id": "adaptive-lifecycle-v1",
        "status": "profile-mapping-verified-live-runner-required",
        "baseline": {
            "measurement_evidence_reference": BASELINE_EVIDENCE,
            "variant": "native",
            "comparison_policy": (
                "same representative scenarios/repetitions/seed; baseline remains strict "
                "and failed runs stay in denominators"
            ),
        },
        "representative_campaign_sha256": CAMPAIGN_SHA256,
        "representative_manifest_sha256": MANIFEST_SHA256,
        "split_host_topology_reference": SPLIT_HOST_REFERENCE,
        "scenario_policy": SCENARIO_POLICY,
        "profile_map": PROFILE_MAP,
        "profile_smoke": {
            "jobs": PROFILE_SMOKE,
            "maximum_codex_executions": 3,
            "retries": 0,
            "authorization_required": True,
            "accepted_evidence_sha256": ["908a97f105e1a29fbc5aafed15a3becbece6fa38311cde7d9f968b185f3814d0"],
        },
        "adaptive_campaign": {
            "repetitions": 2,
            "seed": 14,
            "jobs": 20,
            "max_attempts_per_job": 2,
            "max_retries_per_job": 1,
            "max_delegations_per_job": 0,
            "maximum_codex_executions": 40,
            "authorization_required": True,
            "profile_mapping_evidence_required": True,
        },
        "lifecycle_metrics": {
            "quality": True,
            "total_attempt_tokens": True,
            "estimated_cost": "unknown-until-reviewed-price-table",
            "total_lifecycle_latency": True,
            "escalation_count": True,
            "failed_cheap_attempt_count": True,
            "strong_model_avoided": True,
            "handoff_count": True,
            "handoff_overhead_seconds": True,
            "missing_counters_remain_unknown": True,
            "failed_attempts_remain_in_denominators": True,
        },
        "adapter": {
            "source": "codex-smart-core/adaptive+adaptive_routing",
            "source_sha256": _sha256(ADAPTER_SOURCE),
            "python_may_not_choose_profile_or_reasoning": True,
        },
        "interpretation_policy": {
            "quality_equivalence_required_before_savings_claim": True,
            "no_savings_claim_from_unverified_profile_mapping": True,
            "no_savings_claim_from_missing_cost_counter": True,
            "no_winner_claim_before_measurement_acceptance": True,
        },
    }


def load_contract(path=CONTRACT):
    actual = json.loads(Path(path).read_text())
    if json.dumps(actual, sort_keys=True) != json.dumps(expected_contract(), sort_keys=True):
        raise AdaptiveMeasurementRefusal("unreviewed adaptive lifecycle contract")
    if _sha256(REPRESENTATIVE_CAMPAIGN) != CAMPAIGN_SHA256:
        raise AdaptiveMeasurementRefusal("representative campaign identity mismatch")
    if _sha256(REPRESENTATIVE_MANIFEST) != MANIFEST_SHA256:
        raise AdaptiveMeasurementRefusal("representative manifest identity mismatch")
    manifest = json.loads(REPRESENTATIVE_MANIFEST.read_text())
    scenario_ids = [row["id"] for row in manifest["scenarios"]]
    if scenario_ids != list(SCENARIO_POLICY):
        raise AdaptiveMeasurementRefusal("adaptive scenario order mismatch")
    return actual


def expected_profile_candidate():
    return {
        "source": "local-codex-model-cache-sanitized",
        "codex_version": "0.162.1",
        "model_calls_during_probe": 0,
        "execution_verified": False,
        "profiles": {
            "economy": {
                "model_key": 10,
                "model": "gpt-6-luna",
                "advertised_medium_reasoning": True,
                "advertised_high_reasoning": True,
                "semantic_hint": "fast-and-affordable-easier-tasks",
            },
            "standard": {
                "model_key": 20,
                "model": "gpt-6-sol",
                "advertised_medium_reasoning": True,
                "advertised_high_reasoning": True,
                "semantic_hint": "workhorse",
            },
            "strong": {
                "model_key": 30,
                "model": "gpt-6-astra",
                "advertised_medium_reasoning": True,
                "advertised_high_reasoning": True,
                "semantic_hint": "frontier-demanding-work",
            },
        },
    }


def load_profile_candidate(path=PROFILE_CANDIDATE):
    record = json.loads(Path(path).read_text())
    if type(record) is not dict or set(record) != {
        "schema_version", "candidate", "evidence_reference"
    }:
        raise AdaptiveMeasurementRefusal("invalid adaptive profile candidate envelope")
    expected = expected_profile_candidate()
    if record["schema_version"] != 1 or record["candidate"] != expected:
        raise AdaptiveMeasurementRefusal("adaptive profile candidate mismatch")
    if record["evidence_reference"] != _json_hash(expected):
        raise AdaptiveMeasurementRefusal("adaptive profile evidence reference mismatch")
    return record


def expected_profile_execution_candidate():
    return {
        "repository_commit": "0c846addbb313524910ec9891482f0eddbfd2f3e",
        "measurement_id": "adaptive-lifecycle-v1",
        "profile_candidate_evidence_reference": (
            "baaab449793e0856b0d476732d6e1a547e6230bec0983c1d4f5b7452e210a0c1"
        ),
        "planned_jobs": 3,
        "codex_exec_processes_started": 3,
        "retries": 0,
        "all_profiles_execution_and_quality_verified": True,
        "private_agent_archive_sha256": (
            "a12cfedf7bea3f83c09c0f5b5547ee3f785bde5161d72fde5d4fb6d151d84ed8"
        ),
        "graded_summary_sha256": (
            "69366d056d86a59d80e1efa1b17c7cedd065c28b165628b2b90cd624eed62c3b"
        ),
        "rows": [
            {
                "profile": "economy",
                "model_key": 10,
                "model": "gpt-6-luna",
                "reasoning": "medium",
                "scenario_id": "explore-notification",
                "agent_success": True,
                "quality_pass": True,
                "failure_reason": None,
                "trace_sha256": (
                    "2ad97c991b132274eda6f874dd526f9e59207673468f5a56eb41cd3ae71d4eee"
                ),
                "submission_sha256": (
                    "f81d8d1b6fb6bdfa575d5b5141780170be0648bc40c0371b772d3995e98b4b65"
                ),
            },
            {
                "profile": "standard",
                "model_key": 20,
                "model": "gpt-6-sol",
                "reasoning": "high",
                "scenario_id": "python-result-api",
                "agent_success": True,
                "quality_pass": True,
                "failure_reason": None,
                "trace_sha256": (
                    "48f307bc5e994ad543c670a2da5955fad61ebb6fd59454cba3f35147367ccd7c"
                ),
                "submission_sha256": (
                    "cb018655c861d4786526ee9c18566a76adba439e648d1c9a4cf6a2339d8f2f94"
                ),
            },
            {
                "profile": "strong",
                "model_key": 30,
                "model": "gpt-6-astra",
                "reasoning": "high",
                "scenario_id": "infra-service-policy",
                "agent_success": True,
                "quality_pass": True,
                "failure_reason": None,
                "trace_sha256": (
                    "1ae826835960666fea33d0e282539e3d8df20fc4d94be42d2550d74cf99f9c79"
                ),
                "submission_sha256": (
                    "2aac769a897341b46416f537c17793e1ec6f6f2e565790c6c4aa3624e372107d"
                ),
            },
        ],
    }


def load_profile_execution_candidate(path=PROFILE_EXECUTION_CANDIDATE):
    record = json.loads(Path(path).read_text())
    if type(record) is not dict or set(record) != {
        "schema_version", "evidence_id", "candidate", "evidence_reference",
        "model_calls_during_analysis",
    }:
        raise AdaptiveMeasurementRefusal("invalid adaptive profile execution evidence")
    expected = expected_profile_execution_candidate()
    if (
        record["schema_version"] != 1
        or record["evidence_id"] != "adaptive-profile-smoke-v1-live"
        or record["candidate"] != expected
        or record["model_calls_during_analysis"] != 0
        or record["evidence_reference"] != _json_hash(expected)
    ):
        raise AdaptiveMeasurementRefusal("adaptive profile execution evidence mismatch")
    return record


def profile_mapping_verified():
    contract = load_contract()
    load_profile_candidate()
    execution = load_profile_execution_candidate()
    return (
        execution["candidate"]["all_profiles_execution_and_quality_verified"] is True
        and execution["evidence_reference"]
        in contract["profile_smoke"]["accepted_evidence_sha256"]
    )


def _adapter_output(adapter, policy, events=()):
    path = Path(adapter)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise AdaptiveMeasurementRefusal("explicit regular adaptive adapter required")
    event_arg = ",".join(events) if events else "none"
    command = [
        str(path),
        policy["task"],
        policy["archetype"],
        policy["risk"],
        policy["safety"],
        "2",
        "1",
        event_arg,
    ]
    observation = subprocess.run(
        command,
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
        check=False,
        env={
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "LANG": "C.UTF-8",
        },
    )
    if observation.returncode != 0:
        raise AdaptiveMeasurementRefusal("Rust adaptive adapter refused policy/history")
    try:
        result = json.loads(observation.stdout)
    except json.JSONDecodeError:
        raise AdaptiveMeasurementRefusal("invalid Rust adaptive adapter output") from None
    if type(result) is not dict or set(result) != {
        "schema_version", "state", "profile", "reasoning", "model_key",
        "attempts_started", "retries_used", "delegations_used",
    }:
        raise AdaptiveMeasurementRefusal("unexpected Rust adaptive adapter fields")
    if result["schema_version"] != 1:
        raise AdaptiveMeasurementRefusal("unsupported Rust adaptive adapter schema")
    if result["delegations_used"] != 0:
        raise AdaptiveMeasurementRefusal("measurement variant does not execute delegation")
    if result["model_key"] is not None:
        mapping = PROFILE_MAP.get(str(result["model_key"]))
        if mapping is None or mapping["profile"] != result["profile"]:
            raise AdaptiveMeasurementRefusal("Rust adapter profile mapping mismatch")
    return result


def offline_plan(adapter=None):
    contract = load_contract()
    candidate = load_profile_candidate()
    result = {
        "measurement_id": contract["measurement_id"],
        "status": contract["status"],
        "baseline_evidence_reference": BASELINE_EVIDENCE,
        "profile_candidate_evidence_reference": candidate["evidence_reference"],
        "profile_execution_evidence_reference": (
            load_profile_execution_candidate()["evidence_reference"]
        ),
        "profile_mapping_verified": profile_mapping_verified(),
        "profile_smoke_codex_executions": 3,
        "adaptive_jobs": 20,
        "maximum_adaptive_codex_executions": 40,
        "model_execution_enabled": False,
        "profile_smoke_authorization_required": True,
        "adaptive_campaign_authorization_required": True,
        "estimated_cost": None,
    }
    if adapter is not None:
        initial = {}
        for scenario_id, policy in SCENARIO_POLICY.items():
            initial[scenario_id] = _adapter_output(adapter, policy)
        result["initial_policy"] = initial
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter")
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--authorize-execution", action="store_true")
    args = parser.parse_args(argv)
    try:
        plan = offline_plan(args.adapter)
        if args.real:
            if not profile_mapping_verified():
                raise AdaptiveMeasurementRefusal(
                    "adaptive profile mapping execution evidence is not accepted"
                )
            if args.authorize_execution is not True:
                raise AdaptiveMeasurementRefusal(
                    "explicit adaptive lifecycle execution authorization required"
                )
            raise AdaptiveMeasurementRefusal(
                "adaptive live runner is not enabled by the prepared contract"
            )
        print(json.dumps(plan, indent=2, sort_keys=True))
    except (OSError, subprocess.TimeoutExpired, AdaptiveMeasurementRefusal) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
