"""Three-profile execution smoke for the adaptive lifecycle measurement contract.

Agent execution is allowed only with explicit profile-smoke authorization. Grading is
separate and uses the already accepted split-host production grader boundary.
"""

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import tempfile

import benchmark as b
import benchmark_adaptive_lifecycle as adaptive
import benchmark_campaign as primitives
import benchmark_coverage as coverage
import benchmark_host as host
import benchmark_isolation as isolation
import benchmark_representative as representative
import benchmark_split_host_campaign as split
import benchmark_submission_grading as submission_grading

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_ID = "adaptive-profile-smoke-v1"


class ProfileSmokeRefusal(ValueError):
    pass


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _job_id(job):
    value = f'{job["profile"]}-{job["scenario_id"]}-{job["reasoning"]}'
    if not re.fullmatch(r"[a-z0-9-]{1,128}", value):
        raise ProfileSmokeRefusal("unsafe adaptive profile smoke job identity")
    return value


def _profile_entry(job):
    entry = adaptive.PROFILE_MAP.get(str(job["model_key"]))
    if (
        entry is None
        or entry["profile"] != job["profile"]
        or entry["smoke_reasoning"] != job["reasoning"]
    ):
        raise ProfileSmokeRefusal("profile smoke mapping mismatch")
    return entry


def _override_command(argv, model, reasoning):
    result = list(argv)
    try:
        model_index = result.index("--model")
    except ValueError:
        raise ProfileSmokeRefusal("representative command missing model flag") from None
    if model_index + 1 >= len(result):
        raise ProfileSmokeRefusal("representative command model flag malformed")
    result[model_index + 1] = model
    found_reasoning = False
    for index in range(len(result) - 1):
        if (
            result[index] == "-c"
            and result[index + 1].startswith("model_reasoning_effort=")
        ):
            result[index + 1] = f'model_reasoning_effort="{reasoning}"'
            found_reasoning = True
            break
    if not found_reasoning:
        raise ProfileSmokeRefusal("representative command missing reasoning override")
    return result


def plan():
    contract = adaptive.load_contract()
    candidate = adaptive.load_profile_candidate()
    return {
        "schema_version": 1,
        "kind": "adaptive-profile-smoke-plan",
        "measurement_id": contract["measurement_id"],
        "jobs": contract["profile_smoke"]["jobs"],
        "maximum_codex_executions": 3,
        "retries": 0,
        "profile_candidate_evidence_reference": candidate["evidence_reference"],
        "model_execution_enabled": False,
        "authorization_required": True,
    }


def run_agent(
    codex,
    code_mode_host,
    runtime_root,
    inventory_dir,
    run_id,
    *,
    authorized=False,
    execute_fn=b.execute,
):
    if authorized is not True:
        raise ProfileSmokeRefusal(
            "explicit adaptive profile smoke execution authorization required"
        )
    contract = adaptive.load_contract()
    adaptive.load_profile_candidate()
    if adaptive.profile_mapping_verified():
        raise ProfileSmokeRefusal("profile mapping is already accepted")
    try:
        campaign, runtime = split.agent_preflight(
            codex, code_mode_host, runtime_root, inventory_dir
        )
    except (ValueError, OSError) as error:
        raise ProfileSmokeRefusal("split-host agent preflight refused") from error

    artifacts = split._artifact_root(run_id, resume=False)
    jobs = contract["profile_smoke"]["jobs"]
    if len(jobs) != 3:
        raise ProfileSmokeRefusal("profile smoke job count mismatch")

    completed = []
    for ordinal, job in enumerate(jobs, start=1):
        entry = _profile_entry(job)
        scenario = next(
            row
            for row in coverage.load_manifest()["scenarios"]
            if row["id"] == job["scenario_id"]
        )
        scenario = scenario | {
            "allowed_variants": campaign["variants"],
            "quality_gates": ["independent-quality"],
        }
        job_id = _job_id(job)
        job_dir = artifacts / job_id
        job_dir.mkdir(mode=0o700)
        split._write_json_exclusive(
            job_dir / "started.json",
            {
                "schema_version": 1,
                "ordinal": ordinal,
                "job_id": job_id,
                "profile": job["profile"],
                "model_key": job["model_key"],
                "model": entry["model"],
                "reasoning": job["reasoning"],
                "scenario_id": job["scenario_id"],
                "started_at": datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
            },
        )

        with tempfile.TemporaryDirectory(
            prefix="adaptive-profile-smoke-", dir="/tmp"
        ) as tmp:
            workspace = Path(tmp)
            b.setup(scenario, workspace)
            base_argv = representative.command_plan(
                campaign,
                "native",
                str(codex),
                runtime=runtime,
                workspace=workspace,
            )
            argv = _override_command(base_argv, entry["model"], job["reasoning"])
            prompt = primitives.prompt(campaign, scenario, "native")
            started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            try:
                observation = execute_fn(
                    argv,
                    workspace,
                    prompt,
                    timeout=campaign["timeout_seconds"],
                )
            except OSError:
                observation = {
                    "stdout": "",
                    "stderr": "",
                    "exit_status": None,
                    "timeout": False,
                    "duration": 0.0,
                    "launch_failure": True,
                }

            parsed = b.parse_trace(observation["stdout"])
            failure = split._agent_reason(observation, parsed)
            envelope = None
            export_error = None
            if failure is None:
                try:
                    envelope = split.export_submission(scenario, workspace)
                except (OSError, ValueError) as error:
                    failure = "submission-export-refused"
                    export_error = type(error).__name__

            (job_dir / "trace.jsonl").write_text(observation["stdout"])
            (job_dir / "stderr.txt").write_text(observation["stderr"])
            if envelope is not None:
                split._write_json_exclusive(job_dir / "submission.json", envelope)
            result = {
                "schema_version": 1,
                "ordinal": ordinal,
                "job_id": job_id,
                "profile": job["profile"],
                "model_key": job["model_key"],
                "model": entry["model"],
                "reasoning": job["reasoning"],
                "scenario_id": job["scenario_id"],
                "execution_started_at": started_at,
                "duration_seconds": observation["duration"],
                "exit_status": observation["exit_status"],
                "timeout": observation["timeout"],
                "terminal_status": parsed["terminal_status"],
                "parser_errors": parsed["errors"],
                "tokens": parsed["tokens"],
                "observed_tool_calls": parsed["observed_tool_calls"],
                "failure_reason": failure,
                "submission_exported": envelope is not None,
                "export_error_class": export_error,
                "trace_sha256": _sha256(job_dir / "trace.jsonl"),
                "stderr_sha256": _sha256(job_dir / "stderr.txt"),
                "submission_sha256": (
                    _sha256(job_dir / "submission.json")
                    if envelope is not None
                    else None
                ),
            }
            split._write_json_exclusive(job_dir / "agent-result.json", result)
            completed.append(result)

    summary = {
        "schema_version": 1,
        "kind": "adaptive-profile-smoke-agent",
        "measurement_id": contract["measurement_id"],
        "planned_jobs": 3,
        "codex_exec_processes_started": 3,
        "retries": 0,
        "completed_results": len(completed),
        "submission_exports": sum(row["submission_exported"] for row in completed),
        "agent_successes": sum(row["failure_reason"] is None for row in completed),
        "profile_mapping_accepted": False,
    }
    split._write_json_exclusive(artifacts / "agent-summary.json", summary)
    return summary


def _grade_one(job, job_dir, qualification, runtime):
    result = json.loads((job_dir / "agent-result.json").read_text())
    expected = _profile_entry(job)
    if (
        result["profile"] != job["profile"]
        or result["model_key"] != job["model_key"]
        or result["model"] != expected["model"]
        or result["reasoning"] != job["reasoning"]
        or result["scenario_id"] != job["scenario_id"]
    ):
        raise ProfileSmokeRefusal("profile smoke agent identity mismatch")
    trace = job_dir / "trace.jsonl"
    stderr = job_dir / "stderr.txt"
    if (
        _sha256(trace) != result["trace_sha256"]
        or _sha256(stderr) != result["stderr_sha256"]
    ):
        raise ProfileSmokeRefusal("profile smoke raw artifact mismatch")
    parsed = b.parse_trace(trace.read_text())
    if (
        parsed["terminal_status"] != result["terminal_status"]
        or parsed["errors"] != result["parser_errors"]
        or parsed["tokens"] != result["tokens"]
        or parsed["observed_tool_calls"] != result["observed_tool_calls"]
    ):
        raise ProfileSmokeRefusal("profile smoke trace parse mismatch")

    if result["failure_reason"] is not None:
        return {
            "schema_version": 1,
            "profile": job["profile"],
            "model_key": job["model_key"],
            "model": expected["model"],
            "reasoning": job["reasoning"],
            "scenario_id": job["scenario_id"],
            "agent_success": False,
            "quality_pass": False,
            "failure_reason": result["failure_reason"],
            "trace_sha256": result["trace_sha256"],
            "submission_sha256": result["submission_sha256"],
        }

    submission = job_dir / "submission.json"
    if (
        not result["submission_exported"]
        or not submission.is_file()
        or _sha256(submission) != result["submission_sha256"]
    ):
        raise ProfileSmokeRefusal("profile smoke submission evidence mismatch")
    envelope = json.loads(submission.read_text())
    scenario = next(
        row
        for row in coverage.load_manifest()["scenarios"]
        if row["id"] == job["scenario_id"]
    )
    files = split.validate_submission_envelope(
        envelope, scenario, adaptive.CAMPAIGN_SHA256
    )
    with tempfile.TemporaryDirectory(
        prefix="adaptive-profile-grade-", dir="/tmp"
    ) as tmp:
        workspace = Path(tmp)
        split._materialize_envelope(files, workspace)
        policy = (
            isolation.SubmissionPolicy(True, ("answer.json",))
            if job["scenario_id"] == "explore-notification"
            else isolation.SubmissionPolicy()
        )
        grade = submission_grading.grade_representative(
            job["scenario_id"], workspace, qualification, runtime, policy
        )
    if grade.status != "verified" or type(grade.quality_pass) is not bool:
        raise ProfileSmokeRefusal("profile smoke production grading refused")
    return {
        "schema_version": 1,
        "profile": job["profile"],
        "model_key": job["model_key"],
        "model": expected["model"],
        "reasoning": job["reasoning"],
        "scenario_id": job["scenario_id"],
        "agent_success": True,
        "quality_pass": grade.quality_pass,
        "failure_reason": None if grade.quality_pass else "quality-failure",
        "trace_sha256": result["trace_sha256"],
        "submission_sha256": result["submission_sha256"],
    }


def grade_agent_artifacts(
    agent_artifacts,
    qualification,
    runtime_root,
    inventory_dir,
    output_dir,
):
    adaptive.load_contract()
    adaptive.load_profile_candidate()
    if (
        type(qualification) is not host.QualifiedHostContract
        or qualification.status != "verified"
        or qualification.reference != split.GRADING_HOST_RECEIPT
    ):
        raise ProfileSmokeRefusal("accepted grading host receipt required")
    if not submission_grading.contract_verified(qualification):
        raise ProfileSmokeRefusal("accepted production grading evidence required")
    runtime = submission_grading.prepare_runtime(
        runtime_root, inventory_dir, qualification
    )
    if runtime.inventory_reference != split.RUNTIME_INVENTORY_REFERENCE:
        raise ProfileSmokeRefusal("grading runtime inventory mismatch")

    source = Path(agent_artifacts)
    target = Path(output_dir)
    if (
        not source.is_absolute()
        or source.is_symlink()
        or not source.is_dir()
        or not target.is_absolute()
        or target.exists()
        or target.is_symlink()
    ):
        raise ProfileSmokeRefusal("unsafe profile smoke grading path")
    target.mkdir(mode=0o700)

    rows = []
    for job in adaptive.PROFILE_SMOKE:
        row = _grade_one(job, source / _job_id(job), qualification, runtime)
        split._write_json_exclusive(
            target / f'{job["profile"]}.json', row
        )
        rows.append(row)

    all_pass = (
        len(rows) == 3
        and all(row["agent_success"] and row["quality_pass"] for row in rows)
    )
    summary = {
        "schema_version": 1,
        "kind": "adaptive-profile-smoke-graded",
        "measurement_id": adaptive.load_contract()["measurement_id"],
        "planned_jobs": 3,
        "graded_jobs": 3,
        "all_profiles_execution_and_quality_verified": all_pass,
        "rows": rows,
        "profile_mapping_accepted": False,
    }
    split._write_json_exclusive(target / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", action="store_true")
    parser.add_argument("--grade", action="store_true")
    parser.add_argument("--authorize-profile-smoke", action="store_true")
    parser.add_argument("--codex")
    parser.add_argument("--code-mode-host")
    parser.add_argument("--runtime-root")
    parser.add_argument("--inventory-dir")
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--agent-artifacts")
    parser.add_argument("--qualification-evidence")
    parser.add_argument("--output-dir")
    args = parser.parse_args(argv)
    if args.agent and args.grade:
        parser.error("--agent and --grade are mutually exclusive")
    try:
        if args.agent:
            result = run_agent(
                args.codex,
                args.code_mode_host,
                args.runtime_root,
                args.inventory_dir,
                args.run_id,
                authorized=args.authorize_profile_smoke,
            )
        elif args.grade:
            qualification = host.load_evidence(args.qualification_evidence)
            result = grade_agent_artifacts(
                args.agent_artifacts,
                qualification,
                args.runtime_root,
                args.inventory_dir,
                args.output_dir,
            )
        else:
            result = plan()
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
