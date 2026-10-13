"""One-execution representative live smoke.

This is a separately budgeted end-to-end smoke and is never part of the 40 primary
representative executions. The offline path performs no model work. The real path
first proves that the frozen 40-run entry reaches only its explicit authorization
gate, then requires a separate explicit smoke authorization before one Codex exec.
"""

import argparse
import hashlib
import json
from pathlib import Path

import benchmark as b
import benchmark_agent_isolation as agent_isolation
import benchmark_campaign as primitives
import benchmark_coverage as coverage
import benchmark_host as host
import benchmark_isolation as isolation
import benchmark_readiness_probe as readiness
import benchmark_representative as representative
import benchmark_submission_grading as submission_grading

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "benchmarks/representative-smoke-v1.json"
SCENARIO_ID = "python-billing"
VARIANT = "vanilla"
REPETITION = 0
SEED = 14
MAX_CODEX_EXECUTIONS = 1


class SmokePreflightRefusal(ValueError):
    model_calls = 0
    attempt_count = 0

    def as_record(self):
        return {
            "smoke_id": "representative-live-smoke-v1",
            "status": "preflight-refused",
            "failure_reason": str(self),
            "attempt_count": 0,
            "model_calls": 0,
        }


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_contract():
    campaign = representative.load()
    manifest = coverage.load_manifest()
    scenario = next(row for row in manifest["scenarios"] if row["id"] == SCENARIO_ID)
    readiness_evidence = readiness.load_candidate_evidence()
    production = submission_grading.load_candidate_evidence()
    return {
        "schema_version": 1,
        "smoke_id": "representative-live-smoke-v1",
        "status": "ready-authorization-required",
        "campaign_id": campaign["campaign_id"],
        "campaign_sha256": sha256(representative.CONFIG),
        "technical_readiness_reference": readiness_evidence["evidence_reference"],
        "qualified_host_receipt": submission_grading.QUALIFIED_HOST_RECEIPT,
        "agent_execution_isolation_reference": agent_isolation.load_candidate_evidence()["evidence_reference"],
        "grading_backend_reference": submission_grading.GRADING_BACKEND_REFERENCE,
        "production_grading_reference": production["evidence_reference"],
        "scenario_id": SCENARIO_ID,
        "scenario_snapshot": scenario["snapshot"],
        "variant": VARIANT,
        "repetition": REPETITION,
        "seed": SEED,
        "retries": 0,
        "timeout_seconds": campaign["timeout_seconds"],
        "maximum_codex_executions": MAX_CODEX_EXECUTIONS,
        "settings": {
            "model": campaign["settings"]["model"],
            "reasoning_effort": campaign["settings"]["reasoning_effort"],
            "codex_executable_sha256": campaign["codex"]["executable_sha256"],
            "codex_version": campaign["codex"]["version"],
        },
        "budget": {
            "separate_from_primary_campaign": True,
            "counts_toward_40_primary_executions": False,
            "maximum_codex_exec_processes": 1,
            "internal_model_request_count": "unsupported",
            "retries": 0,
        },
        "authorization": {
            "required": True,
            "flag": "--authorize-smoke-execution",
            "authorization_overrides_security": False,
        },
    }


def load(path=CONFIG):
    actual = json.loads(Path(path).read_text())
    if json.dumps(actual, sort_keys=True) != json.dumps(expected_contract(), sort_keys=True):
        raise ValueError("unreviewed representative smoke contract")
    return actual


def plan(path=CONFIG):
    contract = load(path)
    return {
        "smoke_id": contract["smoke_id"],
        "scenario_id": contract["scenario_id"],
        "variant": contract["variant"],
        "maximum_codex_executions": contract["maximum_codex_executions"],
        "counts_toward_40_primary_executions": False,
        "model_calls": 0,
        "model_execution_enabled": False,
        "authorization_required": True,
    }


def _qualification(path):
    return host.load_evidence(path) if path else host.current_host()


def _prove_full_runner_preflight(executable, qualification, runtime_root, inventory_dir):
    probe_run_id = "representative-smoke-preauthorization"
    try:
        representative.real_run(
            executable,
            probe_run_id,
            qualification,
            grading_runtime_root=runtime_root,
            grading_inventory_dir=inventory_dir,
            authorized=False,
        )
    except representative.PreflightRefusal as error:
        if (str(error) != "explicit representative execution authorization required"
                or error.model_calls != 0 or error.attempt_count != 0):
            raise SmokePreflightRefusal("representative campaign preflight rejected") from None
    else:
        raise SmokePreflightRefusal("representative campaign authorization gate missing")


def real_smoke(executable, run_id, qualification, *, grading_runtime_root=None,
               grading_inventory_dir=None, authorized=False, path=CONFIG):
    try:
        contract = load(path)
    except (OSError, ValueError):
        raise SmokePreflightRefusal("frozen representative smoke contract rejected") from None

    _prove_full_runner_preflight(
        executable, qualification, grading_runtime_root, grading_inventory_dir)

    if authorized is not True:
        raise SmokePreflightRefusal("explicit representative smoke execution authorization required")

    try:
        runtime = submission_grading.prepare_runtime(
            grading_runtime_root, grading_inventory_dir, qualification)
        campaign = representative.load()
        representative._identity_preflight(campaign, executable, runtime)
        agent_isolation.runtime_preflight()
    except (OSError, TypeError, ValueError):
        raise SmokePreflightRefusal("smoke runtime or identity rejected") from None

    if (contract["technical_readiness_reference"]
            != readiness.load_candidate_evidence()["evidence_reference"]):
        raise SmokePreflightRefusal("technical readiness evidence changed")

    try:
        artifacts = primitives.artifact_directory(run_id)
    except (OSError, ValueError):
        raise SmokePreflightRefusal("private smoke artifact target rejected") from None

    scenario = next(
        row for row in coverage.load_manifest()["scenarios"]
        if row["id"] == contract["scenario_id"])
    scenario = scenario | {
        "allowed_variants": campaign["variants"],
        "quality_gates": ["independent-quality"],
    }

    def codex_runner(row, variant, workspace):
        return b.execute(
            representative.command_plan(
                campaign, variant, executable, runtime=runtime, workspace=workspace),
            workspace,
            primitives.prompt(campaign, row, variant),
            timeout=contract["timeout_seconds"],
        )

    grading_failure = False

    def isolated_grade(row, workspace):
        nonlocal grading_failure
        try:
            return representative._grade_submission(row, workspace, qualification, runtime)
        except (OSError, ValueError):
            grading_failure = True
            return False

    refs = representative.references(campaign, representative.CONFIG)
    record = b.run(
        scenario,
        contract["variant"],
        contract["seed"],
        contract["repetition"],
        codex_runner,
        retries=0,
        cold="unknown",
        references=refs,
        artifacts=artifacts,
        grader=isolated_grade,
    )
    if grading_failure:
        record["attempts"][0]["failure_reason"] = "grading-refusal"
        record["final_status"] = "grading-refusal"

    agent_reference = next(
        row.evidence_sha256 for row in qualification.evidence.components
        if row.component == agent_isolation.COMPONENT)
    normalized = representative._normalized(
        campaign,
        record,
        refs,
        qualification.reference,
        agent_reference,
        campaign["runner_pins"]["isolation_sha256"],
        submission_grading.load_candidate_evidence()["evidence_reference"],
        runtime.inventory_reference,
        "real-representative-smoke",
    )
    target = artifacts / "smoke-result.json"
    with target.open("x") as output:
        output.write(json.dumps(normalized, indent=2) + "\n")

    return {
        "smoke_id": contract["smoke_id"],
        "maximum_codex_executions": 1,
        "attempted_jobs": 1,
        "model_calls": None,
        "counts_toward_40_primary_executions": False,
        "record": normalized,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--authorize-smoke-execution", action="store_true")
    parser.add_argument("--codex")
    parser.add_argument("--run-id", default="representative-live-smoke-v1")
    parser.add_argument("--qualification-evidence")
    parser.add_argument("--grading-runtime-root")
    parser.add_argument("--grading-inventory-dir")
    args = parser.parse_args(argv)
    try:
        if args.real:
            result = real_smoke(
                args.codex,
                args.run_id,
                _qualification(args.qualification_evidence),
                grading_runtime_root=args.grading_runtime_root,
                grading_inventory_dir=args.grading_inventory_dir,
                authorized=args.authorize_smoke_execution,
            )
        else:
            result = plan()
    except SmokePreflightRefusal as error:
        print(json.dumps(error.as_record()))
        parser.error(str(error))
    except (OSError, ValueError):
        parser.error("representative smoke contract or qualification rejected")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
