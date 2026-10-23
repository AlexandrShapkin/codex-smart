"""Two-round split-host adaptive lifecycle campaign runner.

Initial agent attempts run on the accepted agent boundary. Trusted production grading
runs separately. Only independently failed jobs may receive one Rust-controller-authorized
retry. The absolute frozen ceiling is 20 jobs / 40 Codex exec processes.
"""

import argparse
import datetime
import json
import math
from pathlib import Path
import re
import tempfile
import time

import benchmark as b
import benchmark_adaptive_lifecycle as adaptive
import benchmark_adaptive_profile_smoke as profile_smoke
import benchmark_adaptive_trusted_handoff as trusted_handoff
import benchmark_campaign as primitives
import benchmark_coverage as coverage
import benchmark_host as host
import benchmark_isolation as isolation
import benchmark_representative as representative
import benchmark_runner as runner
import benchmark_split_host_campaign as split
import benchmark_submission_grading as submission_grading

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUN_ID = "adaptive-lifecycle-live-v1"
BASELINE_NATIVE_QUALITY_PASSES = 17
BASELINE_NATIVE_RUNS = 20


class AdaptiveCampaignRefusal(ValueError):
    pass


def _sha256(path):
    return runner.sha256(path)


def _artifact_refusal(message):
    return AdaptiveCampaignRefusal(message.replace("artifact", "adaptive artifact"))


def _safe_path(path, *, directory=False):
    return runner.safe_path(path, directory=directory, refusal=_artifact_refusal)


def _regular_file(path):
    return runner.regular_file(path, refusal=_artifact_refusal)


def jobs():
    campaign = representative.load()
    native = [
        (scenario_id, repetition, seed)
        for scenario_id, variant, repetition, seed in representative.jobs(campaign)
        if variant == "native"
    ]
    contract = adaptive.load_contract()["adaptive_campaign"]
    if (
        len(native) != contract["jobs"]
        or contract["repetitions"] != 2
        or contract["seed"] != 14
    ):
        raise AdaptiveCampaignRefusal("adaptive job matrix mismatch")
    return native


def _job_id(scenario_id, repetition, seed):
    value = f"{scenario_id}-adaptive-{repetition}-{seed}"
    if not re.fullmatch(r"[a-z0-9-]{1,128}", value):
        raise AdaptiveCampaignRefusal("unsafe adaptive job identifier")
    return value


def _scenario(scenario_id, campaign):
    scenario = next(
        row for row in coverage.load_manifest()["scenarios"]
        if row["id"] == scenario_id
    )
    return scenario | {
        "allowed_variants": campaign["variants"],
        "quality_gates": ["independent-quality"],
    }


def _profile_target(decision):
    if decision["state"] != "ready":
        raise AdaptiveCampaignRefusal("Rust adaptive controller is not execution ready")
    model_key = decision["model_key"]
    entry = adaptive.PROFILE_MAP.get(str(model_key))
    if (
        entry is None
        or entry["profile"] != decision["profile"]
        or type(model_key) is not int
        or decision["reasoning"] not in {"medium", "high"}
    ):
        raise AdaptiveCampaignRefusal("Rust adaptive profile resolution mismatch")
    return entry["model"], decision["reasoning"]


def _escalated(previous, current):
    order = {"medium": 1, "high": 2}
    _profile_target(current | {"state": "ready"})
    return (
        current["model_key"] >= previous["model_key"]
        and order[current["reasoning"]] >= order[previous["reasoning"]]
        and (current["model_key"] > previous["model_key"]
             or order[current["reasoning"]] > order[previous["reasoning"]])
    )


def agent_preflight(codex, code_mode_host, runtime_root, inventory_dir,
                    adapter, adapter_sha256):
    if not adaptive.profile_mapping_verified():
        raise AdaptiveCampaignRefusal("adaptive profile mapping evidence is not accepted")
    campaign, runtime = runner.agent_preflight(
        codex, code_mode_host, runtime_root, inventory_dir, refusal=AdaptiveCampaignRefusal
    )

    adapter = Path(adapter)
    if (
        not adapter.is_absolute()
        or adapter.is_symlink()
        or not adapter.is_file()
        or not re.fullmatch(r"[0-9a-f]{64}", adapter_sha256 or "")
        or _sha256(adapter) != adapter_sha256
    ):
        raise AdaptiveCampaignRefusal("adaptive adapter identity mismatch")

    for policy in adaptive.SCENARIO_POLICY.values():
        decision = adaptive._adapter_output(adapter, policy)
        _profile_target(decision)
        if (
            decision["attempts_started"] != 0
            or decision["retries_used"] != 0
            or decision["delegations_used"] != 0
        ):
            raise AdaptiveCampaignRefusal("unexpected initial adaptive controller state")
    return campaign, runtime, adapter


def _artifact_root(run_id, resume, *, destination=None):
    if destination is not None:
        path = _safe_path(destination)
        if (".." in path.parts or path.is_relative_to(ROOT)
                or not path.parent.is_dir()):
            raise AdaptiveCampaignRefusal("external adaptive artifact destination required")
        if resume:
            return _safe_path(path, directory=True)
        path.mkdir(mode=0o700)  # Exclusive; never adopt an existing campaign directory.
        return path
    try:
        return _safe_path(split._artifact_root(run_id, resume), directory=True)
    except split.SplitHostRefusal as error:
        raise AdaptiveCampaignRefusal(str(error)) from error


def _write_json(path, value, *, exclusive=True):
    path = _safe_path(path)
    if exclusive:
        split._write_json_exclusive(path, value)
        path.chmod(0o600)
        if path.name == "started.json":
            runner.sync_ledger(path)
    else:
        if path.exists() and not _regular_file(path):
            raise AdaptiveCampaignRefusal("unsafe adaptive summary artifact")
        with path.open("w") as stream:
            stream.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
        path.chmod(0o600)


def _write_text_exclusive(path, value):
    path = _safe_path(path)
    with path.open("x") as stream:
        stream.write(value)
    path.chmod(0o600)


def _attempt_dir(job_dir, ordinal):
    return job_dir / f"attempt-{ordinal}"


def _started_count(artifacts):
    root = _safe_path(artifacts, directory=True)
    count = 0
    known = {_job_id(*job) for job in jobs()}
    for child in root.iterdir():
        if child.name not in known and child.name not in {
            "initial-agent-summary.json", "retry-agent-summary.json"
        }:
            raise AdaptiveCampaignRefusal("unexpected adaptive artifact entry")
    for scenario_id, repetition, seed in jobs():
        job_dir = root / _job_id(scenario_id, repetition, seed)
        if job_dir.exists() or job_dir.is_symlink():
            _safe_path(job_dir, directory=True)
            if any(child.name not in {"attempt-1", "attempt-2"} for child in job_dir.iterdir()):
                raise AdaptiveCampaignRefusal("unexpected adaptive job artifact entry")
            if ((job_dir / "attempt-2").exists() or (job_dir / "attempt-2").is_symlink()) and not (
                (job_dir / "attempt-1").exists() or (job_dir / "attempt-1").is_symlink()
            ):
                raise AdaptiveCampaignRefusal("adaptive retry without initial ledger")
        for ordinal in (1, 2):
            attempt_dir = _attempt_dir(job_dir, ordinal)
            if attempt_dir.exists() or attempt_dir.is_symlink():
                _load_started(attempt_dir, scenario_id, repetition, seed, ordinal)
                count += 1
    return count


def _load_started(attempt_dir, scenario_id, repetition, seed, ordinal):
    attempt_dir = _safe_path(attempt_dir, directory=True)
    if any(child.name not in {
        "started.json", "trace.jsonl", "stderr.txt", "submission.json",
        "agent-result.json", "trace-summary.json",
    } for child in attempt_dir.iterdir()):
        raise AdaptiveCampaignRefusal("unexpected adaptive attempt artifact entry")
    path = attempt_dir / "started.json"
    if not _regular_file(path):
        raise AdaptiveCampaignRefusal("missing or unsafe adaptive started ledger")
    started = json.loads(path.read_text())
    required = {
        "schema_version", "measurement_id", "job_id", "scenario_id", "repetition",
        "seed", "attempt", "profile", "reasoning", "model_key", "model",
        "controller_attempts_started_before", "controller_retries_used_before",
        "adapter_state", "started_at",
    }
    if (type(started) is not dict or set(started) != required
            or not runner.attempt_identity_matches(started, {
                "schema_version": 1,
                "measurement_id": adaptive.load_contract()["measurement_id"],
                "job_id": _job_id(scenario_id, repetition, seed),
                "scenario_id": scenario_id, "repetition": repetition,
                "seed": seed, "attempt": ordinal,
            })
            or started["adapter_state"] != "ready"
            or started["controller_attempts_started_before"] != ordinal - 1
            or started["controller_retries_used_before"] != ordinal - 1
            or type(started["started_at"]) is not str
            or not re.fullmatch(r"[0-9T:+.Z-]{20,40}", started["started_at"])):
        raise AdaptiveCampaignRefusal("adaptive started ledger identity mismatch")
    _profile_target(started | {"state": started["adapter_state"]})
    if started["model"] != adaptive.PROFILE_MAP[str(started["model_key"])]["model"]:
        raise AdaptiveCampaignRefusal("adaptive started ledger model mismatch")
    return started


def _execute_attempt(
    *,
    artifacts,
    scenario,
    repetition,
    seed,
    ordinal,
    decision,
    campaign,
    runtime,
    codex,
    prior_submission=None,
    execute_fn=b.execute,
):
    job_id = _job_id(scenario["id"], repetition, seed)
    job_dir = artifacts / job_id
    attempt_dir = _attempt_dir(job_dir, ordinal)
    if ordinal not in (1, 2) or (ordinal == 2 and not _regular_file(job_dir / "attempt-1" / "started.json")):
        raise AdaptiveCampaignRefusal("adaptive attempt order or budget mismatch")
    if job_dir.exists() or job_dir.is_symlink():
        _safe_path(job_dir, directory=True)
    if attempt_dir.exists() or attempt_dir.is_symlink():
        raise AdaptiveCampaignRefusal("existing adaptive attempt evidence")
    if _started_count(artifacts) >= adaptive.load_contract()["adaptive_campaign"]["maximum_codex_executions"]:
        raise AdaptiveCampaignRefusal("adaptive Codex execution ledger exceeds budget")

    with tempfile.TemporaryDirectory(prefix="adaptive-agent-", dir="/tmp") as tmp:
        workspace = Path(tmp)
        b.setup(scenario, workspace)
        if prior_submission is not None:
            if not _regular_file(prior_submission):
                raise AdaptiveCampaignRefusal("unsafe prior adaptive submission")
            envelope = json.loads(Path(prior_submission).read_text())
            files = split.validate_submission_envelope(
                envelope, scenario, adaptive.CAMPAIGN_SHA256
            )
            split._materialize_envelope(files, workspace)

        model, reasoning = _profile_target(decision)
        argv = representative.command_plan(
            campaign, "native", str(codex), runtime=runtime, workspace=workspace
        )
        argv = profile_smoke._override_command(argv, model, reasoning)
        prompt = primitives.prompt(campaign, scenario, "native")

        job_dir.mkdir(mode=0o700, exist_ok=True)
        attempt_dir.mkdir(mode=0o700)
        started = {
            "schema_version": 1,
            "measurement_id": adaptive.load_contract()["measurement_id"],
            "job_id": job_id,
            "scenario_id": scenario["id"],
            "repetition": repetition,
            "seed": seed,
            "attempt": ordinal,
            "profile": decision["profile"],
            "reasoning": reasoning,
            "model_key": decision["model_key"],
            "model": model,
            "controller_attempts_started_before": decision["attempts_started"],
            "controller_retries_used_before": decision["retries_used"],
            "adapter_state": decision["state"],
            "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        _write_json(attempt_dir / "started.json", started)

        if _started_count(artifacts) > adaptive.load_contract()[
            "adaptive_campaign"
        ]["maximum_codex_executions"]:
            raise AdaptiveCampaignRefusal("adaptive Codex execution ledger exceeds budget")

        execution_started_at = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        observation, parsed, failure, envelope, export_error = runner.observe_attempt(
            argv, workspace, prompt, campaign["timeout_seconds"], execute_fn, scenario
        )

        _write_text_exclusive(attempt_dir / "trace.jsonl", observation["stdout"])
        _write_text_exclusive(attempt_dir / "stderr.txt", observation["stderr"])
        if envelope is not None:
            _write_json(attempt_dir / "submission.json", envelope)

        result = {
            "schema_version": 1,
            "measurement_id": adaptive.load_contract()["measurement_id"],
            "job_id": job_id,
            "scenario_id": scenario["id"],
            "repetition": repetition,
            "seed": seed,
            "attempt": ordinal,
            "profile": decision["profile"],
            "reasoning": reasoning,
            "model_key": decision["model_key"],
            "model": model,
            "execution_started_at": execution_started_at,
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
            "trace_sha256": _sha256(attempt_dir / "trace.jsonl"),
            "stderr_sha256": _sha256(attempt_dir / "stderr.txt"),
            "submission_sha256": (
                _sha256(attempt_dir / "submission.json")
                if envelope is not None else None
            ),
        }
        _write_json(attempt_dir / "agent-result.json", result)
        return result


def run_initial(
    codex,
    code_mode_host,
    runtime_root,
    inventory_dir,
    adapter,
    adapter_sha256,
    run_id,
    *,
    authorized=False,
    resume=False,
    execute_fn=b.execute,
    agent_artifacts=None,
    planned_decisions=None,
):
    if authorized is not True:
        raise AdaptiveCampaignRefusal(
            "explicit adaptive lifecycle execution authorization required"
        )
    if planned_decisions is not None and (
        type(planned_decisions) is not dict
        or set(planned_decisions) != {_job_id(*job) for job in jobs()}
    ):
        raise AdaptiveCampaignRefusal("complete reviewed decision matrix required")
    campaign, runtime, adapter = agent_preflight(
        codex, code_mode_host, runtime_root, inventory_dir, adapter, adapter_sha256
    )
    artifacts = _artifact_root(run_id, resume, destination=agent_artifacts)
    _started_count(artifacts)
    launched = 0
    completed = 0
    unresolved = []

    for scenario_id, repetition, seed in jobs():
        job_id = _job_id(scenario_id, repetition, seed)
        job_dir = artifacts / job_id
        attempt_dir = _attempt_dir(job_dir, 1)
        if attempt_dir.exists() or attempt_dir.is_symlink():
            if (
                not resume
            ):
                raise AdaptiveCampaignRefusal("existing or invalid initial attempt")
            started = _load_started(attempt_dir, scenario_id, repetition, seed, 1)
            if planned_decisions is not None and any(
                started[key] != planned_decisions[job_id][key]
                for key in ("profile", "reasoning", "model_key")
            ):
                raise AdaptiveCampaignRefusal("started ledger differs from reviewed plan")
            if _load_attempt_result(attempt_dir, scenario_id, repetition, seed, 1) is not None:
                completed += 1
            else:
                unresolved.append(job_id)
            continue

        scenario = _scenario(scenario_id, campaign)
        decision = adaptive._adapter_output(
            adapter, adaptive.SCENARIO_POLICY[scenario_id]
        )
        if planned_decisions is not None and decision != planned_decisions.get(job_id):
            raise AdaptiveCampaignRefusal("controller decision differs from reviewed plan before launch")
        _execute_attempt(
            artifacts=artifacts,
            scenario=scenario,
            repetition=repetition,
            seed=seed,
            ordinal=1,
            decision=decision,
            campaign=campaign,
            runtime=runtime,
            codex=codex,
            execute_fn=execute_fn,
        )
        launched += 1
        completed += 1

    summary = {
        "schema_version": 1,
        "kind": "adaptive-lifecycle-initial-agent",
        "measurement_id": adaptive.load_contract()["measurement_id"],
        "planned_jobs": 20,
        "maximum_codex_executions": 40,
        "codex_exec_processes_started_this_invocation": launched,
        "started_ledger_count": _started_count(artifacts),
        "completed_initial_results": completed,
        "started_without_result": sorted(unresolved),
        "profile_mapping_evidence_reference": adaptive.load_profile_execution_candidate()[
            "evidence_reference"
        ],
        "adapter_sha256": adapter_sha256,
        "model_request_count": None,
    }
    _write_json(artifacts / "initial-agent-summary.json", summary, exclusive=False)
    return summary


def _load_attempt_result(attempt_dir, scenario_id, repetition, seed, ordinal, *, transfer=False):
    attempt_dir = Path(attempt_dir)
    started = _load_started(attempt_dir, scenario_id, repetition, seed, ordinal)
    result_path = attempt_dir / "agent-result.json"
    if not result_path.exists() and not result_path.is_symlink():
        return None
    if not _regular_file(result_path):
        raise AdaptiveCampaignRefusal("unsafe adaptive result path")
    result = json.loads(result_path.read_text())
    required = {
        "schema_version", "measurement_id", "job_id", "scenario_id", "repetition",
        "seed", "attempt", "profile", "reasoning", "model_key", "model",
        "execution_started_at", "duration_seconds", "exit_status", "timeout",
        "terminal_status", "parser_errors", "tokens", "observed_tool_calls",
        "failure_reason", "submission_exported", "export_error_class",
        "trace_sha256", "stderr_sha256", "submission_sha256",
    }
    if (
        type(result) is not dict
        or set(result) != required
        or not runner.attempt_identity_matches(result, {
            "schema_version": 1,
            "measurement_id": adaptive.load_contract()["measurement_id"],
            "job_id": _job_id(scenario_id, repetition, seed),
            "scenario_id": scenario_id, "repetition": repetition,
            "seed": seed, "attempt": ordinal,
        })
        or any(result[key] != started[key] for key in (
            "profile", "reasoning", "model_key", "model"
        ))
        or type(result["duration_seconds"]) not in (int, float)
        or not math.isfinite(result["duration_seconds"])
        or result["duration_seconds"] < 0
        or type(result["execution_started_at"]) is not str
        or not re.fullmatch(r"[0-9T:+.Z-]{20,40}", result["execution_started_at"])
        or (result["exit_status"] is not None and type(result["exit_status"]) is not int)
        or type(result["timeout"]) is not bool
        or type(result["submission_exported"]) is not bool
        or (result["export_error_class"] is not None and (
            type(result["export_error_class"]) is not str
            or not re.fullmatch(r"[A-Za-z]{1,80}", result["export_error_class"])))
        or not all(type(result[name]) is str and re.fullmatch(r"[0-9a-f]{64}", result[name])
                   for name in ("trace_sha256", "stderr_sha256"))
    ):
        raise AdaptiveCampaignRefusal("adaptive attempt identity mismatch")
    if transfer:
        if any((attempt_dir / name).exists() or (attempt_dir / name).is_symlink()
               for name in ("trace.jsonl", "stderr.txt")):
            raise AdaptiveCampaignRefusal("raw agent logs in grading transfer")
        safe_trace = attempt_dir / "trace-summary.json"
        if not _regular_file(safe_trace):
            raise AdaptiveCampaignRefusal("missing sanitized trace summary")
        parsed = json.loads(safe_trace.read_text())
        if type(parsed) is not dict or set(parsed) != {
            "terminal_status", "errors", "tokens", "observed_tool_calls",
            "trace_sha256",
        } or parsed["trace_sha256"] != result["trace_sha256"]:
            raise AdaptiveCampaignRefusal("sanitized trace summary mismatch")
    else:
        trace = attempt_dir / "trace.jsonl"
        stderr = attempt_dir / "stderr.txt"
        if (
            not _regular_file(trace)
            or not _regular_file(stderr)
            or _sha256(trace) != result["trace_sha256"]
            or _sha256(stderr) != result["stderr_sha256"]
        ):
            raise AdaptiveCampaignRefusal("adaptive raw attempt artifact mismatch")
        parsed = b.parse_trace(trace.read_text())
    if (
        parsed["terminal_status"] != result["terminal_status"]
        or parsed["errors"] != result["parser_errors"]
        or parsed["tokens"] != result["tokens"]
        or parsed["observed_tool_calls"] != result["observed_tool_calls"]
    ):
        raise AdaptiveCampaignRefusal("adaptive trace parse mismatch")
    expected_failure = split._agent_reason({
        "timeout": result["timeout"], "exit_status": result["exit_status"],
        "launch_failure": result["failure_reason"] == "launch-failure",
    }, parsed)
    if (result["failure_reason"] not in (expected_failure, "submission-export-refused")
            or (result["failure_reason"] == "submission-export-refused"
                and expected_failure is not None)
            or (result["submission_exported"] and result["failure_reason"] is not None)):
        raise AdaptiveCampaignRefusal("adaptive failure evidence mismatch")
    if result["submission_exported"]:
        submission = attempt_dir / "submission.json"
        if (
            not _regular_file(submission)
            or _sha256(submission) != result["submission_sha256"]
        ):
            raise AdaptiveCampaignRefusal("adaptive submission evidence mismatch")
    elif result["submission_sha256"] is not None or (attempt_dir / "submission.json").exists():
        raise AdaptiveCampaignRefusal("unexpected adaptive submission hash")
    return result


def export_grading_bundle(agent_artifacts, output_dir):
    """Copy only checked, bounded grading inputs; raw logs remain on the agent host."""
    source = _safe_path(agent_artifacts, directory=True)
    target = Path(output_dir)
    if not target.is_absolute() or target.exists() or target.is_symlink():
        raise AdaptiveCampaignRefusal("unsafe adaptive grading bundle output")
    _safe_path(target)
    _started_count(source)
    target.mkdir(mode=0o700)
    copied = 0
    for scenario_id, repetition, seed in jobs():
        job_id = _job_id(scenario_id, repetition, seed)
        for ordinal in (1, 2):
            attempt_dir = _attempt_dir(source / job_id, ordinal)
            if not attempt_dir.exists() and not attempt_dir.is_symlink():
                continue
            started = _load_started(attempt_dir, scenario_id, repetition, seed, ordinal)
            result = _load_attempt_result(attempt_dir, scenario_id, repetition, seed, ordinal)
            destination = _attempt_dir(target / job_id, ordinal)
            destination.mkdir(mode=0o700, parents=True)
            _write_json(destination / "started.json", started)
            if result is None:
                continue
            _write_json(destination / "agent-result.json", result)
            _write_json(destination / "trace-summary.json", {
                "terminal_status": result["terminal_status"],
                "errors": result["parser_errors"],
                "tokens": result["tokens"],
                "observed_tool_calls": result["observed_tool_calls"],
                "trace_sha256": result["trace_sha256"],
            })
            if result["submission_exported"]:
                scenario = _scenario(scenario_id, representative.load())
                envelope = json.loads((attempt_dir / "submission.json").read_text())
                split.validate_submission_envelope(
                    envelope, scenario, adaptive.CAMPAIGN_SHA256
                )
                _write_json(destination / "submission.json", envelope)
            copied += 1
    _write_json(target / "grading-bundle.json", {
        "schema_version": 1,
        "measurement_id": adaptive.load_contract()["measurement_id"],
        "started_attempts": _started_count(source),
        "completed_attempts": copied,
        "raw_logs_included": False,
    })
    return {"started_attempts": _started_count(source), "completed_attempts": copied,
            "raw_logs_included": False}


def _validate_grading_bundle(source):
    source = _safe_path(source, directory=True)
    marker = source / "grading-bundle.json"
    if not _regular_file(marker):
        raise AdaptiveCampaignRefusal("sanitized grading bundle required")
    record = json.loads(marker.read_text())
    if (type(record) is not dict or set(record) != {
            "schema_version", "measurement_id", "started_attempts",
            "completed_attempts", "raw_logs_included"
        } or type(record["schema_version"]) is not int or record["schema_version"] != 1
            or record["measurement_id"] != adaptive.load_contract()["measurement_id"]
            or record["raw_logs_included"] is not False
            or type(record["started_attempts"]) is not int
            or type(record["completed_attempts"]) is not int):
        raise AdaptiveCampaignRefusal("invalid sanitized grading bundle")
    known = {_job_id(*job) for job in jobs()}
    started_count = completed_count = 0
    for job_dir in source.iterdir():
        if job_dir == marker:
            continue
        if job_dir.name not in known:
            raise AdaptiveCampaignRefusal("unexpected grading bundle entry")
        _safe_path(job_dir, directory=True)
        if (job_dir / "attempt-2").exists() and not (job_dir / "attempt-1").exists():
            raise AdaptiveCampaignRefusal("grading retry without initial ledger")
        for attempt_dir in job_dir.iterdir():
            if attempt_dir.name not in ("attempt-1", "attempt-2"):
                raise AdaptiveCampaignRefusal("unexpected grading attempt entry")
            _safe_path(attempt_dir, directory=True)
            if any(file.name not in {
                    "started.json", "agent-result.json", "trace-summary.json",
                    "submission.json"
                } or file.is_symlink() or not file.is_file()
                   for file in attempt_dir.iterdir()):
                raise AdaptiveCampaignRefusal("unsafe grading bundle file")
            started_count += 1
            completed_count += int((attempt_dir / "agent-result.json").is_file())
    if (started_count != record["started_attempts"]
            or completed_count != record["completed_attempts"]
            or started_count > 40):
        raise AdaptiveCampaignRefusal("grading bundle count mismatch")
    return record


def _grading_runtime(qualification, runtime_root, inventory_dir):
    if (
        type(qualification) is not host.QualifiedHostContract
        or qualification.status != "verified"
        or qualification.reference != split.GRADING_HOST_RECEIPT
    ):
        raise AdaptiveCampaignRefusal("accepted grading host receipt required")
    if not submission_grading.contract_verified(qualification):
        raise AdaptiveCampaignRefusal("accepted production grading evidence required")
    runtime = submission_grading.prepare_runtime(
        runtime_root, inventory_dir, qualification
    )
    if runtime.inventory_reference != split.RUNTIME_INVENTORY_REFERENCE:
        raise AdaptiveCampaignRefusal("grading runtime inventory mismatch")
    return runtime


def _grade_attempt(result, attempt_dir, scenario, qualification, runtime):
    started = time.monotonic()
    quality = False
    reason = result["failure_reason"]
    grader_reason = None
    if reason is None:
        submission = Path(attempt_dir) / "submission.json"
        envelope = json.loads(submission.read_text())
        files = split.validate_submission_envelope(
            envelope, scenario, adaptive.CAMPAIGN_SHA256
        )
        with tempfile.TemporaryDirectory(
            prefix="adaptive-grade-", dir="/tmp"
        ) as tmp:
            workspace = Path(tmp)
            split._materialize_envelope(files, workspace)
            policy = (
                isolation.SubmissionPolicy(True, ("answer.json",))
                if scenario["id"] == "explore-notification"
                else isolation.SubmissionPolicy()
            )
            grade = submission_grading.grade_representative(
                scenario["id"], workspace, qualification, runtime, policy
            )
        if grade.status != "verified" or type(grade.quality_pass) is not bool:
            raise AdaptiveCampaignRefusal("adaptive production grading refused")
        quality = grade.quality_pass
        grader_reason = grade.reason
        if not quality:
            reason = "quality-failure"

    return {
        "schema_version": 1,
        "measurement_id": adaptive.load_contract()["measurement_id"],
        "job_id": result["job_id"],
        "scenario_id": result["scenario_id"],
        "repetition": result["repetition"],
        "seed": result["seed"],
        "attempt": result["attempt"],
        "profile": result["profile"],
        "reasoning": result["reasoning"],
        "model_key": result["model_key"],
        "model": result["model"],
        "agent_success": result["failure_reason"] is None,
        "quality_pass": quality,
        "failure_reason": reason,
        "grader_reason": grader_reason,
        "grading_seconds": time.monotonic() - started,
        "trace_sha256": result["trace_sha256"],
        "submission_sha256": result["submission_sha256"],
        "host_qualification_reference": qualification.reference,
        "production_grading_reference": split.PRODUCTION_GRADING_REFERENCE,
        "runtime_inventory_reference": runtime.inventory_reference,
    }


def grade_round(
    agent_artifacts,
    attempt,
    qualification,
    runtime_root,
    inventory_dir,
    output_dir,
    *,
    authorized=False,
    resume=False,
):
    if authorized is not True:
        raise AdaptiveCampaignRefusal(
            "explicit adaptive lifecycle grading authorization required"
        )
    if attempt not in (1, 2):
        raise AdaptiveCampaignRefusal("unsupported adaptive grading round")
    source = _safe_path(agent_artifacts, directory=True)
    _validate_grading_bundle(source)
    target = Path(output_dir)
    if not target.is_absolute() or (target.exists() and not resume) or target.is_symlink():
        raise AdaptiveCampaignRefusal("unsafe adaptive grading paths")
    _safe_path(target)
    adaptive.load_contract()
    if not adaptive.profile_mapping_verified():
        raise AdaptiveCampaignRefusal("adaptive profile mapping evidence is not accepted")
    runtime = _grading_runtime(qualification, runtime_root, inventory_dir)
    if target.exists():
        _safe_path(target, directory=True)
    else:
        target.mkdir(mode=0o700)

    allowed = {"summary.json", *(_job_id(*job) + ".json" for job in jobs())}
    if any(entry.name not in allowed or not _regular_file(entry) for entry in target.iterdir()):
        raise AdaptiveCampaignRefusal("unexpected partial grading output")
    if any(not (source / entry.stem / f"attempt-{attempt}").is_dir()
           for entry in target.iterdir() if entry.name != "summary.json"):
        raise AdaptiveCampaignRefusal("partial grading row without started input")

    campaign = representative.load()
    rows = []
    hashes = {}
    missing = []
    for scenario_id, repetition, seed in jobs():
        job_id = _job_id(scenario_id, repetition, seed)
        attempt_dir = _attempt_dir(source / job_id, attempt)
        if not attempt_dir.exists() and not attempt_dir.is_symlink():
            if attempt == 1:
                missing.append(job_id)
            continue
        _load_started(attempt_dir, scenario_id, repetition, seed, attempt)
        result = _load_attempt_result(
            attempt_dir, scenario_id, repetition, seed, attempt, transfer=True
        )
        path = target / f"{job_id}.json"
        if path.exists():
            row = _load_grade_row(target, path.name, _sha256(path), attempt)
            _match_grade(row, _load_started(attempt_dir, scenario_id, repetition, seed, attempt), result)
        elif result is None:
            row = {
                "schema_version": 1,
                "measurement_id": adaptive.load_contract()["measurement_id"],
                "job_id": job_id,
                "scenario_id": scenario_id,
                "repetition": repetition,
                "seed": seed,
                "attempt": attempt,
                "profile": None,
                "reasoning": None,
                "model_key": None,
                "model": None,
                "agent_success": False,
                "quality_pass": False,
                "failure_reason": "interrupted-no-result",
                "grader_reason": None,
                "grading_seconds": 0.0,
                "trace_sha256": None,
                "submission_sha256": None,
                "host_qualification_reference": qualification.reference,
                "production_grading_reference": split.PRODUCTION_GRADING_REFERENCE,
                "runtime_inventory_reference": runtime.inventory_reference,
            }
        else:
            scenario = _scenario(scenario_id, campaign)
            row = _grade_attempt(
                result, attempt_dir, scenario, qualification, runtime
            )
        if not path.exists():
            _write_json(path, row)
        hashes[path.name] = _sha256(path)
        rows.append(row)

    summary = {
        "schema_version": 1,
        "kind": "adaptive-lifecycle-grade-round",
        "measurement_id": adaptive.load_contract()["measurement_id"],
        "attempt": attempt,
        "graded_or_terminal_rows": len(rows),
        "missing_jobs": sorted(missing),
        "row_sha256": hashes,
        "host_qualification_reference": qualification.reference,
        "production_grading_reference": split.PRODUCTION_GRADING_REFERENCE,
        "runtime_inventory_reference": runtime.inventory_reference,
    }
    if (target / "summary.json").exists():
        actual, _ = _load_grade_round(target, attempt)
        if actual != summary:
            raise AdaptiveCampaignRefusal("existing grading summary mismatch")
    else:
        _write_json(target / "summary.json", summary)
    return summary | {"summary_sha256": _sha256(target / "summary.json")}


def _load_grade_row(root, name, digest, attempt):
    if (type(name) is not str or not re.fullmatch(r"[a-z0-9-]+\.json", name)
            or name == "summary.json" or type(digest) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        raise AdaptiveCampaignRefusal("unsafe adaptive grade filename")
    file = root / name
    if not _regular_file(file) or _sha256(file) != digest:
        raise AdaptiveCampaignRefusal("adaptive grade row hash mismatch")
    row = json.loads(file.read_text())
    required_row = {
        "schema_version", "measurement_id", "job_id", "scenario_id",
        "repetition", "seed", "attempt", "profile", "reasoning",
        "model_key", "model", "agent_success", "quality_pass",
        "failure_reason", "grader_reason", "grading_seconds",
        "trace_sha256", "submission_sha256", "host_qualification_reference",
        "production_grading_reference", "runtime_inventory_reference",
    }
    job = next((job for job in jobs() if _job_id(*job) + ".json" == name), None)
    if (type(row) is not dict or set(row) != required_row or job is None
            or type(row["schema_version"]) is not int or row["schema_version"] != 1
            or row["measurement_id"] != adaptive.load_contract()["measurement_id"]
            or row["job_id"] != _job_id(*job)
            or row["scenario_id"] != job[0]
            or type(row["repetition"]) is not int or row["repetition"] != job[1]
            or type(row["seed"]) is not int or row["seed"] != job[2]
            or type(row["attempt"]) is not int or row["attempt"] != attempt
            or type(row["agent_success"]) is not bool
            or type(row["quality_pass"]) is not bool
            or (row["quality_pass"] and (not row["agent_success"] or row["failure_reason"] is not None))
            or (not row["quality_pass"] and not isinstance(row["failure_reason"], str))
            or (row["failure_reason"] is not None and row["failure_reason"] not in {
                "quality-failure", "interrupted-no-result", "timeout", "launch-failure",
                "agent-failure", "process-failure", "trace-invalid",
                "submission-export-refused",
            })
            or (row["grader_reason"] is not None and (
                type(row["grader_reason"]) is not str
                or len(row["grader_reason"]) > 256))
            or type(row["grading_seconds"]) not in (int, float)
            or not math.isfinite(row["grading_seconds"]) or row["grading_seconds"] < 0
            or row["host_qualification_reference"] != split.GRADING_HOST_RECEIPT
            or row["production_grading_reference"] != split.PRODUCTION_GRADING_REFERENCE
            or row["runtime_inventory_reference"] != split.RUNTIME_INVENTORY_REFERENCE):
        raise AdaptiveCampaignRefusal("adaptive grade row identity mismatch")
    return row


def _load_grade_round(path, attempt, expected_sha256=None):
    root = _safe_path(path, directory=True)
    summary_path = root / "summary.json"
    if not _regular_file(summary_path):
        raise AdaptiveCampaignRefusal("invalid adaptive grade round")
    if expected_sha256 is not None and (
        type(expected_sha256) is not str
        or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
        or _sha256(summary_path) != expected_sha256
    ):
        raise AdaptiveCampaignRefusal("trusted adaptive grade summary digest mismatch")
    summary = json.loads(summary_path.read_text())
    required = {
        "schema_version", "kind", "measurement_id", "attempt",
        "graded_or_terminal_rows", "missing_jobs", "row_sha256",
        "host_qualification_reference", "production_grading_reference",
        "runtime_inventory_reference",
    }
    if (
        type(summary) is not dict
        or set(summary) != required
        or type(summary["schema_version"]) is not int or summary["schema_version"] != 1
        or summary["kind"] != "adaptive-lifecycle-grade-round"
        or summary["measurement_id"] != adaptive.load_contract()["measurement_id"]
        or type(summary["attempt"]) is not int or summary["attempt"] != attempt
        or summary["host_qualification_reference"] != split.GRADING_HOST_RECEIPT
        or summary["production_grading_reference"] != split.PRODUCTION_GRADING_REFERENCE
        or summary["runtime_inventory_reference"] != split.RUNTIME_INVENTORY_REFERENCE
        or type(summary["row_sha256"]) is not dict
        or type(summary["missing_jobs"]) is not list
        or type(summary["graded_or_terminal_rows"]) is not int
        or len(summary["row_sha256"]) > 20
    ):
        raise AdaptiveCampaignRefusal("adaptive grade round identity mismatch")
    expected = {_job_id(*job) for job in jobs()}
    if (not all(type(job_id) is str for job_id in summary["missing_jobs"])
            or not set(summary["missing_jobs"]) <= expected
            or len(summary["missing_jobs"]) != len(set(summary["missing_jobs"]))
            or (attempt == 2 and summary["missing_jobs"])):
        raise AdaptiveCampaignRefusal("adaptive grade round missing-job mismatch")
    if {entry.name for entry in root.iterdir()} != {"summary.json", *summary["row_sha256"]}:
        raise AdaptiveCampaignRefusal("unexpected adaptive grade artifact")
    rows = {}
    for name, digest in summary["row_sha256"].items():
        row = _load_grade_row(root, name, digest, attempt)
        rows[row["job_id"]] = row
    if (len(rows) != summary["graded_or_terminal_rows"]
            or set(rows) != {name[:-5] for name in summary["row_sha256"]}
            or (attempt == 1 and set(rows) | set(summary["missing_jobs"]) != expected)):
        raise AdaptiveCampaignRefusal("adaptive grade row count mismatch")
    return summary, rows


def _match_grade(grade, started, result):
    def refusal(message):
        if message == "missing grade":
            return AdaptiveCampaignRefusal("missing adaptive grade")
        return AdaptiveCampaignRefusal("adaptive " + message)
    return runner.match_grade(grade, started, result, refusal=refusal)


def _event_from_initial(result, grade):
    if result is None:
        return None
    if result["failure_reason"] == "submission-export-refused":
        return None
    if result["failure_reason"] == "timeout":
        return "timeout"
    if result["failure_reason"] is not None:
        return "runtime-failure"
    return "quality-pass" if grade["quality_pass"] else "quality-failure"


def run_retry(
    codex,
    code_mode_host,
    runtime_root,
    inventory_dir,
    adapter,
    adapter_sha256,
    run_id,
    initial_grades,
    *,
    initial_grades_sha256=None,
    authorized=False,
    execute_fn=b.execute,
    agent_artifacts=None,
):
    if authorized is not True:
        raise AdaptiveCampaignRefusal(
            "explicit adaptive lifecycle execution authorization required"
        )
    if not isinstance(initial_grades_sha256, str):
        raise AdaptiveCampaignRefusal("trusted initial grade summary digest required")
    campaign, runtime, adapter = agent_preflight(
        codex, code_mode_host, runtime_root, inventory_dir, adapter, adapter_sha256
    )
    artifacts = _artifact_root(run_id, resume=True, destination=agent_artifacts)
    _started_count(artifacts)
    summary, grades = _load_grade_round(initial_grades, 1, initial_grades_sha256)
    if summary["missing_jobs"]:
        raise AdaptiveCampaignRefusal("initial grading is incomplete")

    launched = 0
    completed = 0
    unresolved = []
    skipped_pass = 0
    skipped_unsafe = 0
    skipped_no_escalation = 0
    for scenario_id, repetition, seed in jobs():
        job_id = _job_id(scenario_id, repetition, seed)
        job_dir = artifacts / job_id
        initial_dir = _attempt_dir(job_dir, 1)
        started = _load_started(initial_dir, scenario_id, repetition, seed, 1)
        initial = _load_attempt_result(
            initial_dir, scenario_id, repetition, seed, 1
        )
        grade = grades.get(job_id)
        _match_grade(grade, started, initial)
        event = _event_from_initial(initial, grade)
        if event is None:
            if _attempt_dir(job_dir, 2).exists():
                raise AdaptiveCampaignRefusal("retry exists without valid controller event")
            skipped_unsafe += 1
            continue
        decision = adaptive._adapter_output(
            adapter, adaptive.SCENARIO_POLICY[scenario_id], (event,)
        )
        if event == "quality-pass":
            if decision["state"] != "completed" or decision["model_key"] is not None:
                raise AdaptiveCampaignRefusal("Rust controller did not complete passed job")
            if _attempt_dir(job_dir, 2).exists():
                raise AdaptiveCampaignRefusal("retry exists after quality pass")
            skipped_pass += 1
            continue
        if (decision["state"] != "ready" or decision["attempts_started"] != 1
                or decision["retries_used"] != 1 or decision["delegations_used"] != 0):
            raise AdaptiveCampaignRefusal("Rust controller did not authorize bounded retry")
        if not _escalated(started, decision):
            if (started["model_key"] != 30 or started["reasoning"] != "high"
                    or decision["model_key"] != 30 or decision["reasoning"] != "high"):
                raise AdaptiveCampaignRefusal("Rust controller retry did not escalate")
            if _attempt_dir(job_dir, 2).exists() or _attempt_dir(job_dir, 2).is_symlink():
                raise AdaptiveCampaignRefusal("retry exists without profile escalation")
            skipped_no_escalation += 1
            continue

        retry_dir = _attempt_dir(job_dir, 2)
        if retry_dir.exists() or retry_dir.is_symlink():
            retry_started = _load_started(retry_dir, scenario_id, repetition, seed, 2)
            if any(retry_started[key] != decision[key] for key in (
                "profile", "reasoning", "model_key"
            )):
                raise AdaptiveCampaignRefusal("retry ledger/controller mismatch")
            if _load_attempt_result(retry_dir, scenario_id, repetition, seed, 2) is not None:
                completed += 1
            else:
                unresolved.append(job_id)
            continue

        scenario = _scenario(scenario_id, campaign)
        prior = (
            initial_dir / "submission.json"
            if initial is not None and initial["submission_exported"] else None
        )
        _execute_attempt(
            artifacts=artifacts,
            scenario=scenario,
            repetition=repetition,
            seed=seed,
            ordinal=2,
            decision=decision,
            campaign=campaign,
            runtime=runtime,
            codex=codex,
            prior_submission=prior,
            execute_fn=execute_fn,
        )
        launched += 1
        completed += 1

    started_count = _started_count(artifacts)
    if started_count > 40:
        raise AdaptiveCampaignRefusal("adaptive Codex execution ledger exceeds budget")
    result = {
        "schema_version": 1,
        "kind": "adaptive-lifecycle-retry-agent",
        "measurement_id": adaptive.load_contract()["measurement_id"],
        "maximum_codex_executions": 40,
        "codex_exec_processes_started_this_invocation": launched,
        "started_ledger_count": started_count,
        "completed_retry_results": completed,
        "started_without_result": sorted(unresolved),
        "initial_quality_pass_no_retry": skipped_pass,
        "unsafe_or_unresolved_no_retry": skipped_unsafe,
        "strong_ceiling_no_escalation_no_retry": skipped_no_escalation,
        "adapter_sha256": adapter_sha256,
        "model_request_count": None,
    }
    _write_json(artifacts / "retry-agent-summary.json", result, exclusive=False)
    return result


def _sum_observed_tokens(results, key):
    return runner.sum_observed_tokens(results, key)


def _median(values):
    return runner.median(values)


def finalize(agent_artifacts, initial_grades, retry_grades, output_dir, *,
             initial_grades_sha256=None, retry_grades_sha256=None, resume=False):
    if not isinstance(initial_grades_sha256, str) or not isinstance(retry_grades_sha256, str):
        raise AdaptiveCampaignRefusal("trusted adaptive grade summary digests required")
    source = _safe_path(agent_artifacts, directory=True)
    target = Path(output_dir)
    if not target.is_absolute() or (target.exists() and not resume) or target.is_symlink():
        raise AdaptiveCampaignRefusal("unsafe adaptive finalize paths")
    _safe_path(target)
    retry_summary_path = source / "retry-agent-summary.json"
    if not _regular_file(retry_summary_path):
        raise AdaptiveCampaignRefusal("retry decision round has not completed")
    retry_summary = json.loads(retry_summary_path.read_text())
    if (type(retry_summary) is not dict
            or retry_summary.get("kind") != "adaptive-lifecycle-retry-agent"
            or retry_summary.get("measurement_id") != adaptive.load_contract()["measurement_id"]
            or type(retry_summary.get("started_ledger_count")) is not int
            or retry_summary["started_ledger_count"] != _started_count(source)):
        raise AdaptiveCampaignRefusal("retry decision round evidence mismatch")
    initial_summary, first_grades = _load_grade_round(
        initial_grades, 1, initial_grades_sha256
    )
    if initial_summary["missing_jobs"]:
        raise AdaptiveCampaignRefusal("initial adaptive grading incomplete")
    _, second_grades = _load_grade_round(retry_grades, 2, retry_grades_sha256)
    _started_count(source)

    rows = []
    quality_passes = 0
    retries = 0
    strong_avoided = 0
    failed_cheap = 0
    total_executions = 0
    interrupted_attempts = 0
    for scenario_id, repetition, seed in jobs():
        job_id = _job_id(scenario_id, repetition, seed)
        first_dir = _attempt_dir(source / job_id, 1)
        first_started = _load_started(first_dir, scenario_id, repetition, seed, 1)
        first = _load_attempt_result(first_dir, scenario_id, repetition, seed, 1)
        first_grade = first_grades.get(job_id)
        _match_grade(first_grade, first_started, first)
        attempts = [(first_started, first)]
        final_grade = first_grade
        second_dir = _attempt_dir(source / job_id, 2)
        if second_dir.exists() or second_dir.is_symlink():
            if first is None or first_grade["quality_pass"] or first["failure_reason"] == "submission-export-refused":
                raise AdaptiveCampaignRefusal("retry lacks eligible initial outcome")
            second_started = _load_started(second_dir, scenario_id, repetition, seed, 2)
            if not _escalated(first_started, second_started):
                raise AdaptiveCampaignRefusal("adaptive retry did not escalate")
            second = _load_attempt_result(second_dir, scenario_id, repetition, seed, 2)
            final_grade = second_grades.get(job_id)
            _match_grade(final_grade, second_started, second)
            attempts.append((second_started, second))
        elif job_id in second_grades:
            raise AdaptiveCampaignRefusal("grade exists without retry attempt")

        final_quality = final_grade["quality_pass"] is True
        quality_passes += int(final_quality)
        retries += max(0, len(attempts) - 1)
        total_executions += len(attempts)
        interrupted_attempts += sum(result is None for _, result in attempts)
        used_profiles = [started["profile"] for started, _ in attempts]
        strong_avoided += int(bool(attempts) and "strong" not in used_profiles)
        failed_cheap += int(
            bool(attempts)
            and not first_grade["quality_pass"]
            and first_started["profile"] in {"economy", "standard"}
        )

        token_sums = {
            key: _sum_observed_tokens([result for _, result in attempts], key)
            for key in (
                "input", "cached_input", "output", "reasoning",
                "fresh_input", "total",
            )
        }
        lifecycle_seconds = (
            sum(result["duration_seconds"] for _, result in attempts)
            + first_grade["grading_seconds"]
            + (final_grade["grading_seconds"] if len(attempts) == 2 else 0)
            if all(result is not None for _, result in attempts) else None
        )

        row = {
            "schema_version": 1,
            "kind": "adaptive-lifecycle-job",
            "measurement_id": adaptive.load_contract()["measurement_id"],
            "scenario_id": scenario_id,
            "repetition": repetition,
            "seed": seed,
            "quality_pass": final_quality,
            "attempt_count": len(attempts),
            "retry_count": max(0, len(attempts) - 1),
            "escalation_count": max(0, len(attempts) - 1),
            "failed_cheap_attempt_count": int(
                bool(attempts)
                and not first_grade["quality_pass"]
                and first_started["profile"] in {"economy", "standard"}
            ),
            "strong_model_avoided": bool(attempts) and "strong" not in used_profiles,
            "handoff_count": 0,
            "handoff_overhead_seconds": 0.0,
            "total_lifecycle_latency_seconds": lifecycle_seconds,
            "total_attempt_tokens": token_sums,
            "estimated_cost": None,
            "attempts": [
                {
                    "attempt": started["attempt"],
                    "profile": started["profile"],
                    "reasoning": started["reasoning"],
                    "model_key": started["model_key"],
                    "model": started["model"],
                    "duration_seconds": result["duration_seconds"] if result else None,
                    "tokens": result["tokens"] if result else None,
                    "observed_tool_calls": result["observed_tool_calls"] if result else None,
                    "failure_reason": result["failure_reason"] if result else "interrupted-no-result",
                    "trace_sha256": result["trace_sha256"] if result else None,
                    "submission_sha256": result["submission_sha256"] if result else None,
                }
                for started, result in attempts
            ],
            "final_failure_reason": (
                None if final_quality else final_grade["failure_reason"]
            ),
            "profile_mapping_evidence_reference":
                adaptive.load_profile_execution_candidate()["evidence_reference"],
            "baseline_evidence_reference": adaptive.BASELINE_EVIDENCE,
            "split_host_topology_reference": adaptive.SPLIT_HOST_REFERENCE,
        }
        rows.append(row)

    if total_executions > 40 or total_executions != _started_count(source):
        raise AdaptiveCampaignRefusal("adaptive final execution count exceeds budget")
    if target.exists():
        _safe_path(target, directory=True)
        allowed = {"summary.json", *(_job_id(*job) + ".json" for job in jobs())}
        if any(entry.name not in allowed or not _regular_file(entry) for entry in target.iterdir()):
            raise AdaptiveCampaignRefusal("unexpected partial finalization output")
    else:
        target.mkdir(mode=0o700)
    for row in rows:
        path = target / f"{_job_id(row['scenario_id'], row['repetition'], row['seed'])}.json"
        if path.exists():
            if json.dumps(json.loads(path.read_text()), sort_keys=True) != json.dumps(row, sort_keys=True):
                raise AdaptiveCampaignRefusal("existing finalization row mismatch")
        else:
            _write_json(path, row)
    summary = {
        "schema_version": 1,
        "kind": "adaptive-lifecycle-measurement",
        "measurement_id": adaptive.load_contract()["measurement_id"],
        "runs": 20,
        "quality_passes": quality_passes,
        "quality_pass_rate": quality_passes / 20,
        "baseline_native_quality_passes": BASELINE_NATIVE_QUALITY_PASSES,
        "baseline_native_runs": BASELINE_NATIVE_RUNS,
        "strict_quality_not_below_native_baseline": (
            quality_passes >= BASELINE_NATIVE_QUALITY_PASSES
        ),
        "codex_exec_processes_started": total_executions,
        "started_without_result_count": interrupted_attempts,
        "retry_count": retries,
        "retry_rate": retries / 20,
        "escalation_count": retries,
        "failed_cheap_attempt_count": failed_cheap,
        "strong_model_avoided_jobs": strong_avoided,
        "handoff_count": 0,
        "handoff_overhead_seconds": 0.0,
        "lifecycle_latency_unknown_jobs": sum(
            row["total_lifecycle_latency_seconds"] is None for row in rows
        ),
        "total_lifecycle_latency_median_seconds": _median(
            [row["total_lifecycle_latency_seconds"] for row in rows]
        ),
        "attempt_input_tokens_unknown_jobs": sum(
            row["total_attempt_tokens"]["input"] is None for row in rows
        ),
        "attempt_input_tokens_median": _median(
            [row["total_attempt_tokens"]["input"] for row in rows]
        ),
        "attempt_output_tokens_unknown_jobs": sum(
            row["total_attempt_tokens"]["output"] is None for row in rows
        ),
        "attempt_output_tokens_median": _median(
            [row["total_attempt_tokens"]["output"] for row in rows]
        ),
        "attempt_reasoning_tokens_unknown_jobs": sum(
            row["total_attempt_tokens"]["reasoning"] is None for row in rows
        ),
        "attempt_reasoning_tokens_median": _median(
            [row["total_attempt_tokens"]["reasoning"] for row in rows]
        ),
        "attempt_total_tokens_unknown_jobs": sum(
            row["total_attempt_tokens"]["total"] is None for row in rows
        ),
        "attempt_total_tokens_median": _median(
            [row["total_attempt_tokens"]["total"] for row in rows]
        ),
        "estimated_cost": None,
        "savings_claim": None,
        "winner": None,
        "profile_mapping_evidence_reference":
            adaptive.load_profile_execution_candidate()["evidence_reference"],
        "baseline_evidence_reference": adaptive.BASELINE_EVIDENCE,
        "split_host_topology_reference": adaptive.SPLIT_HOST_REFERENCE,
    }
    if (target / "summary.json").exists():
        if json.dumps(json.loads((target / "summary.json").read_text()), sort_keys=True) != json.dumps(summary, sort_keys=True):
            raise AdaptiveCampaignRefusal("existing finalization summary mismatch")
    else:
        _write_json(target / "summary.json", summary)
    return summary


def plan():
    contract = adaptive.load_contract()
    return {
        "schema_version": 1,
        "kind": "adaptive-lifecycle-live-plan",
        "measurement_id": contract["measurement_id"],
        "profile_mapping_verified": adaptive.profile_mapping_verified(),
        "jobs": len(jobs()),
        "max_attempts_per_job": contract["adaptive_campaign"]["max_attempts_per_job"],
        "max_retries_per_job": contract["adaptive_campaign"]["max_retries_per_job"],
        "maximum_codex_executions": contract["adaptive_campaign"][
            "maximum_codex_executions"
        ],
        "two_round_split_host_grading": True,
        "sanitized_grading_bundle_required": True,
        "trusted_grade_summary_digest_required": True,
        "model_execution_enabled": False,
        "authorization_required": True,
    }


def _trusted_grade_digest(remote_summary, local_grade_dir, supplied_digest=None):
    """Cross-check local transfer against srv0 over pinned ED25519 SSH.

    A caller-supplied digest is never sufficient to establish grade origin.
    """
    if not remote_summary or not local_grade_dir:
        raise AdaptiveCampaignRefusal("authenticated srv0 grading handoff required")
    authoritative = trusted_handoff.pinned_srv0_summary_sha256(remote_summary)
    if supplied_digest is not None and supplied_digest != authoritative:
        raise AdaptiveCampaignRefusal("supplied digest differs from trusted srv0 receipt")
    summary_path = _safe_path(Path(local_grade_dir) / "summary.json")
    if not _regular_file(summary_path) or _sha256(summary_path) != authoritative:
        raise AdaptiveCampaignRefusal("local grade summary differs from trusted srv0 receipt")
    return authoritative


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--initial-agent", action="store_true")
    mode.add_argument("--retry-agent", action="store_true")
    mode.add_argument("--grade-round", type=int, choices=(1, 2))
    mode.add_argument("--export-grading-bundle", action="store_true")
    mode.add_argument("--finalize", action="store_true")
    parser.add_argument("--authorize-execution", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--codex")
    parser.add_argument("--code-mode-host")
    parser.add_argument("--runtime-root")
    parser.add_argument("--inventory-dir")
    parser.add_argument("--adapter")
    parser.add_argument("--adapter-sha256")
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--agent-artifacts")
    parser.add_argument("--initial-grades")
    parser.add_argument("--initial-grades-sha256")
    parser.add_argument("--trusted-initial-remote-summary")
    parser.add_argument("--trusted-retry-remote-summary")
    parser.add_argument("--retry-grades")
    parser.add_argument("--retry-grades-sha256")
    parser.add_argument("--qualification-evidence")
    parser.add_argument("--output-dir")
    args = parser.parse_args(argv)

    try:
        if args.initial_agent:
            result = run_initial(
                args.codex, args.code_mode_host, args.runtime_root,
                args.inventory_dir, args.adapter, args.adapter_sha256,
                args.run_id, authorized=args.authorize_execution,
                resume=args.resume,
            )
        elif args.retry_agent:
            if not args.authorize_execution:
                raise AdaptiveCampaignRefusal(
                    "explicit adaptive lifecycle execution authorization required"
                )
            trusted_initial_sha256 = _trusted_grade_digest(
                args.trusted_initial_remote_summary, args.initial_grades,
                args.initial_grades_sha256,
            )
            result = run_retry(
                args.codex, args.code_mode_host, args.runtime_root,
                args.inventory_dir, args.adapter, args.adapter_sha256,
                args.run_id, args.initial_grades,
                initial_grades_sha256=trusted_initial_sha256,
                authorized=True,
            )
        elif args.grade_round:
            if not args.authorize_execution:
                raise AdaptiveCampaignRefusal(
                    "explicit adaptive lifecycle grading authorization required"
                )
            qualification = host.load_evidence(args.qualification_evidence)
            result = grade_round(
                args.agent_artifacts, args.grade_round, qualification,
                args.runtime_root, args.inventory_dir, args.output_dir,
                authorized=args.authorize_execution,
                resume=args.resume,
            )
        elif args.export_grading_bundle:
            result = export_grading_bundle(args.agent_artifacts, args.output_dir)
        elif args.finalize:
            trusted_initial_sha256 = _trusted_grade_digest(
                args.trusted_initial_remote_summary, args.initial_grades,
                args.initial_grades_sha256,
            )
            trusted_retry_sha256 = _trusted_grade_digest(
                args.trusted_retry_remote_summary, args.retry_grades,
                args.retry_grades_sha256,
            )
            result = finalize(
                args.agent_artifacts, args.initial_grades,
                args.retry_grades, args.output_dir,
                initial_grades_sha256=trusted_initial_sha256,
                retry_grades_sha256=trusted_retry_sha256,
                resume=args.resume,
            )
        else:
            result = plan()
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
