"""Frozen split-host representative campaign transport and execution boundary.

Agent execution occurs on the agent host. Trusted grading occurs later on the accepted
grading host. The module never transports credentials and never accepts agent-produced
test verdicts as quality evidence.
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile

import benchmark as b
import benchmark_agent_isolation as agent_isolation
import benchmark_coverage as coverage
import benchmark_isolation as isolation
import benchmark_host as host
import benchmark_representative as representative
import benchmark_submission_grading as submission_grading
import benchmark_submission_grader as submission_grader

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "benchmarks/representative-split-host-v1.json"
CANDIDATE_EVIDENCE = ROOT / "benchmarks/representative-split-host-candidate-v1.json"
CAMPAIGN = coverage.CAMPAIGN

CODE_MODE_HOST_SHA256 = "a11665cbc33423c909d2df47f414b8a7eccb62234c50829fc310d879904f1c69"
AGENT_ISOLATION_REFERENCE = "ae2840a92172e46eedf574885bf2d68a31043f5d0ad9a586fc8a9921aea848cb"
GRADING_HOST_RECEIPT = "d2af64ce237de72c9c0ee2659723e2d2858c9e19982cc85dd4420a6c6592d265"
PRODUCTION_GRADING_REFERENCE = "199ec7721ec56c57f1e09f19267e8888cc3f1ee31a8ccf754a4b0af0742bf602"
RUNTIME_INVENTORY_REFERENCE = "d8abc626e72bc7ef483ac408c085b638c807712a47f12342b31583ed4f108208"
V4_TRACE_SHA256 = "e6b60c8d0ad162e0b9e4c9d298b595cdd81a1f8e2815e5d498766a26fc9e7824"
V4_AGENT_RESULT_SHA256 = "8b429bc0400285557edd0ef7bb78ae1aa92acf197cbe210b6c4257c7709a8056"
V4_SUBMISSION_SHA256 = "0d8eb699a27655c58a2e9ebba2d8694db8aa3399b5d5040511c17e02dde9f653"
V4_GRADE_SHA256 = "e8396065024b98e3b697abaf6bb054c8f0bb14490066e78529b8c7020faf00fa"
V4_SUMMARY_SHA256 = "5889da2814fed708242d5a4db95970bf531b0d49a3453657084d5aae3d59e080"


class SplitHostRefusal(ValueError):
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
    campaign = representative.load()
    return {
        "schema_version": 1,
        "contract_id": "benchmark-representative-split-host-v1",
        "campaign_id": campaign["campaign_id"],
        "campaign_sha256": _sha256(CAMPAIGN),
        "planned_primary_runs": 40,
        "maximum_codex_exec_processes": 40,
        "retries": 0,
        "agent_role": {
            "codex_executable_sha256": campaign["codex"]["executable_sha256"],
            "code_mode_host_sha256": CODE_MODE_HOST_SHA256,
            "agent_execution_isolation_reference": AGENT_ISOLATION_REFERENCE,
            "runtime_inventory_reference": RUNTIME_INVENTORY_REFERENCE,
            "workspace_sandbox": "codex-workspace-write-reviewed",
            "credentials_transport": "forbidden",
        },
        "grading_role": {
            "qualified_host_receipt": GRADING_HOST_RECEIPT,
            "production_grading_reference": PRODUCTION_GRADING_REFERENCE,
            "runtime_inventory_reference": RUNTIME_INVENTORY_REFERENCE,
            "grader_location": "separate-accepted-grading-host",
        },
        "transport": {
            "schema_version": 1,
            "format": "bounded-json-utf8-expected-paths-only",
            "descriptor_relative": True,
            "no_follow": True,
            "hardlinks_rejected": True,
            "special_nodes_rejected": True,
            "max_file_bytes": submission_grader.MAX_SUBMISSION_FILE_BYTES,
            "max_total_bytes": submission_grader.MAX_SUBMISSION_BYTES,
            "exploration_extra_artifacts_rejected_before_export": True,
            "ssh_or_equivalent_authenticated_transport_required": True,
        },
        "interruption_policy": {
            "started_ledger_written_before_codex": True,
            "started_without_result_never_retried": True,
            "completed_jobs_never_reexecuted": True,
            "resume_may_only_launch_never_started_jobs": True,
        },
        "authorization": {
            "required": True,
            "flag": "--authorize-execution",
            "authorization_overrides_security": False,
        },
        "live_topology_evidence": {
            "scenario_id": "python-billing",
            "variant": "vanilla",
            "quality_pass": True,
            "trace_sha256": V4_TRACE_SHA256,
            "agent_result_sha256": V4_AGENT_RESULT_SHA256,
            "submission_sha256": V4_SUBMISSION_SHA256,
            "production_grade_sha256": V4_GRADE_SHA256,
            "summary_sha256": V4_SUMMARY_SHA256,
        },
        "accepted_evidence_sha256": [],
    }


def load_contract(path=CONTRACT):
    actual = json.loads(Path(path).read_text())
    if json.dumps(actual, sort_keys=True) != json.dumps(expected_contract(), sort_keys=True):
        raise SplitHostRefusal("unreviewed split-host campaign contract")
    return actual


def evidence_reference(candidate):
    if type(candidate) is not dict:
        raise SplitHostRefusal("invalid split-host evidence")
    return _json_hash(candidate)


def load_candidate_evidence(path=CANDIDATE_EVIDENCE):
    record = json.loads(Path(path).read_text())
    required = {
        "schema_version", "contract_id", "probe_kind", "candidate",
        "evidence_reference", "model_calls_during_probe",
    }
    if type(record) is not dict or set(record) != required:
        raise SplitHostRefusal("invalid split-host candidate evidence")
    contract = load_contract()
    if (record["schema_version"] != 1
            or record["contract_id"] != contract["contract_id"]
            or record["probe_kind"] != "reviewed-live-smoke-plus-offline-boundary"
            or record["model_calls_during_probe"] != 0):
        raise SplitHostRefusal("split-host candidate identity mismatch")
    candidate = record["candidate"]
    expected_keys = {
        "campaign_sha256", "agent_execution_isolation_reference",
        "grading_host_receipt", "production_grading_reference",
        "runtime_inventory_reference", "live_smoke_quality_pass",
        "live_smoke_trace_sha256", "live_smoke_agent_result_sha256",
        "live_smoke_submission_sha256", "live_smoke_grade_sha256",
        "live_smoke_summary_sha256", "reference_transport_quality_pass",
        "wrong_transport_quality_pass", "max_codex_exec_processes",
        "retries", "started_ledger_before_codex", "no_retry_after_started",
    }
    if type(candidate) is not dict or set(candidate) != expected_keys:
        raise SplitHostRefusal("invalid split-host candidate payload")
    expected = {
        "campaign_sha256": contract["campaign_sha256"],
        "agent_execution_isolation_reference": AGENT_ISOLATION_REFERENCE,
        "grading_host_receipt": GRADING_HOST_RECEIPT,
        "production_grading_reference": PRODUCTION_GRADING_REFERENCE,
        "runtime_inventory_reference": RUNTIME_INVENTORY_REFERENCE,
        "live_smoke_quality_pass": True,
        "live_smoke_trace_sha256": V4_TRACE_SHA256,
        "live_smoke_agent_result_sha256": V4_AGENT_RESULT_SHA256,
        "live_smoke_submission_sha256": V4_SUBMISSION_SHA256,
        "live_smoke_grade_sha256": V4_GRADE_SHA256,
        "live_smoke_summary_sha256": V4_SUMMARY_SHA256,
        "reference_transport_quality_pass": True,
        "wrong_transport_quality_pass": False,
        "max_codex_exec_processes": 40,
        "retries": 0,
        "started_ledger_before_codex": True,
        "no_retry_after_started": True,
    }
    if candidate != expected or evidence_reference(candidate) != record["evidence_reference"]:
        raise SplitHostRefusal("split-host candidate evidence mismatch")
    return record


def contract_verified():
    try:
        contract = load_contract()
        candidate = load_candidate_evidence()
    except (OSError, ValueError):
        return False
    return candidate["evidence_reference"] in contract["accepted_evidence_sha256"]


def _runtime_reference():
    expected = submission_grading.expected_contract()["runtime_inventory"]
    return hashlib.sha256(json.dumps({
        "files": expected["files_manifest_sha256"],
        "symlinks": expected["symlinks_manifest_sha256"],
        "dirs": expected["dirs_manifest_sha256"],
        "head": submission_grading.RUNTIME_REPOSITORY_HEAD,
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_agent_runtime(runtime_root, inventory_dir):
    """Full topology/byte/mode verification without claiming grading-host qualification."""
    root = Path(runtime_root)
    inventory = Path(inventory_dir)
    if (not root.is_absolute() or root.parent != Path("/tmp")
            or root.is_symlink() or not root.is_dir()
            or not root.name.startswith("benchmark-runtime-")):
        raise SplitHostRefusal("unreviewed agent runtime root")
    roles = ("python", "rust", "go", "libraries", "linker", "grader")
    if {entry.name for entry in root.iterdir()} != set(roles):
        raise SplitHostRefusal("agent runtime role set mismatch")

    manifest_paths = {
        "files": inventory / "runtime-files.tsv",
        "symlinks": inventory / "runtime-symlinks.tsv",
        "dirs": inventory / "runtime-dirs.tsv",
    }
    expected = submission_grading.expected_contract()["runtime_inventory"]
    if (_sha256(manifest_paths["files"]) != expected["files_manifest_sha256"]
            or _sha256(manifest_paths["symlinks"]) != expected["symlinks_manifest_sha256"]
            or _sha256(manifest_paths["dirs"]) != expected["dirs_manifest_sha256"]):
        raise SplitHostRefusal("agent runtime manifest mismatch")
    files = submission_grading._parse_file_manifest(manifest_paths["files"])
    links = submission_grading._parse_symlink_manifest(manifest_paths["symlinks"])
    dirs = submission_grading._parse_dir_manifest(manifest_paths["dirs"])
    if (len(files) != expected["regular_file_count"]
            or len(links) != expected["symlink_count"]
            or len(dirs) != expected["directory_count"]):
        raise SplitHostRefusal("agent runtime count mismatch")

    seen_files, seen_links, seen_dirs = set(), set(), set()
    for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        if current_path != root:
            if current_path.is_symlink():
                raise SplitHostRefusal("agent runtime walk followed symlink")
            seen_dirs.add(current_path.relative_to(root).as_posix())
        for name in list(dirnames):
            path = current_path / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                seen_links.add(rel)
                dirnames.remove(name)
        for name in filenames:
            path = current_path / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                seen_links.add(rel)
            elif path.is_file():
                seen_files.add(rel)
            else:
                raise SplitHostRefusal("agent runtime special node")
    if seen_files != set(files) or seen_links != set(links) or seen_dirs != set(dirs):
        raise SplitHostRefusal("agent runtime topology mismatch")

    for rel, (digest, size, mode) in files.items():
        path = root / rel
        info = path.stat()
        if (info.st_size != size or stat.S_IMODE(info.st_mode) != mode
                or _sha256(path) != digest):
            raise SplitHostRefusal("agent runtime file mismatch")
    for rel, (mode, target) in links.items():
        path = root / rel
        if stat.S_IMODE(path.lstat().st_mode) != mode or os.readlink(path) != target:
            raise SplitHostRefusal("agent runtime symlink mismatch")
    for rel, mode in dirs.items():
        if stat.S_IMODE((root / rel).stat().st_mode) != mode:
            raise SplitHostRefusal("agent runtime directory mismatch")

    head = root / "grader/repository-head.txt"
    if not head.is_file() or head.read_text().strip() != submission_grading.RUNTIME_REPOSITORY_HEAD:
        raise SplitHostRefusal("agent runtime repository identity mismatch")
    reference = _runtime_reference()
    if reference != RUNTIME_INVENTORY_REFERENCE:
        raise SplitHostRefusal("agent runtime reference mismatch")
    info = root.stat()
    role_ids = tuple(
        (role, (root / role).stat().st_dev, (root / role).stat().st_ino)
        for role in roles
    )
    return submission_grading.PreparedRuntime(
        root.resolve(), reference, (info.st_dev, info.st_ino), role_ids)


def _accepted_agent_isolation():
    contract = agent_isolation.load_contract()
    candidate = agent_isolation.load_candidate_evidence()
    return (
        candidate["evidence_reference"] == AGENT_ISOLATION_REFERENCE
        and AGENT_ISOLATION_REFERENCE in contract["accepted_evidence_sha256"]
    )


def agent_preflight(codex, code_mode_host, runtime_root, inventory_dir):
    if not contract_verified():
        raise SplitHostRefusal("split-host evidence is not accepted")
    campaign = representative.load()
    if campaign["readiness"]["representative_campaign_ready"] is not True:
        raise SplitHostRefusal("representative campaign is not ready")
    codex = Path(codex)
    code_mode_host = Path(code_mode_host)
    if (not codex.is_absolute() or not codex.is_file()
            or _sha256(codex) != campaign["codex"]["executable_sha256"]):
        raise SplitHostRefusal("Codex identity mismatch")
    if (not code_mode_host.is_absolute() or code_mode_host.is_symlink()
            or not code_mode_host.is_file()
            or code_mode_host.parent != codex.parent
            or code_mode_host.name != "codex-code-mode-host"
            or _sha256(code_mode_host) != CODE_MODE_HOST_SHA256):
        raise SplitHostRefusal("code-mode host identity mismatch")
    if not _accepted_agent_isolation():
        raise SplitHostRefusal("agent execution isolation evidence is not accepted")
    agent_isolation.runtime_preflight()
    runtime = verify_agent_runtime(runtime_root, inventory_dir)
    representative._identity_preflight(campaign, str(codex), runtime)
    return campaign, runtime


def _exploration_tree_allowed(fixture, workspace):
    allowed_files = set(fixture["files"]) | {"answer.json"}
    allowed_dirs = {""}
    for name in allowed_files:
        parts = PurePosixPath(name).parts
        for index in range(1, len(parts)):
            allowed_dirs.add(PurePosixPath(*parts[:index]).as_posix())
    seen = 0
    for root, dirs, files in os.walk(workspace, topdown=True, followlinks=False):
        relative_root = Path(root).relative_to(workspace)
        root_name = "" if relative_root == Path(".") else relative_root.as_posix()
        if root_name not in allowed_dirs:
            return False
        for directory in list(dirs):
            path = Path(root) / directory
            relative = path.relative_to(workspace).as_posix()
            if path.is_symlink() or relative not in allowed_dirs:
                return False
        for filename in files:
            path = Path(root) / filename
            relative = path.relative_to(workspace).as_posix()
            if path.is_symlink() or relative not in allowed_files:
                return False
            seen += 1
            if seen > len(allowed_files):
                return False
    return True


def export_submission(scenario, workspace):
    fixture = coverage.fixture(scenario)
    workspace = Path(workspace)
    if scenario["id"] == "explore-notification" and not _exploration_tree_allowed(
            fixture, workspace):
        raise SplitHostRefusal("exploration export policy rejected")
    names = sorted(set(fixture["files"]) | set(fixture["reference"]))
    root_fd = os.open(
        workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    files = {}
    total = 0
    try:
        for name in names:
            text = submission_grading._read_regular(root_fd, name)                 if hasattr(submission_grading, "_read_regular") else None
            if text is None:
                # The no-follow reader lives in the trusted grader module, not this module.
                from benchmark_submission_grader import _read_regular
                text = _read_regular(root_fd, name)
            if text is None:
                continue
            total += len(text.encode("utf-8"))
            if total > submission_grader.MAX_SUBMISSION_BYTES:
                raise SplitHostRefusal("submission export too large")
            files[name] = text
    finally:
        os.close(root_fd)
    return {
        "schema_version": 1,
        "campaign_sha256": _sha256(CAMPAIGN),
        "scenario_id": scenario["id"],
        "files": files,
    }


def _safe_job_id(scenario_id, variant, repetition, seed):
    value = f"{scenario_id}-{variant}-{repetition}-{seed}"
    if not re.fullmatch(r"[a-z0-9-]{1,128}", value):
        raise SplitHostRefusal("unsafe job identifier")
    return value


def _agent_reason(observation, parsed):
    if observation.get("launch_failure"):
        return "launch-failure"
    if observation["timeout"]:
        return "timeout"
    if not parsed["errors"] and parsed["terminal_status"] == "failed":
        return "agent-failure"
    if observation["exit_status"]:
        return "process-failure"
    if parsed["errors"]:
        return "trace-invalid"
    return None


def _artifact_root(run_id, resume):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", run_id):
        raise SplitHostRefusal("invalid split-host run identifier")
    root = b.ROOT / ".artifacts"
    if root.is_symlink():
        raise SplitHostRefusal("symlink artifact root rejected")
    root.mkdir(mode=0o700, exist_ok=True)
    root.chmod(0o700)
    target = root / run_id
    if resume:
        if target.is_symlink() or not target.is_dir():
            raise SplitHostRefusal("resume target missing or unsafe")
    else:
        if target.exists() or target.is_symlink():
            raise SplitHostRefusal("existing split-host run evidence")
        target.mkdir(mode=0o700)
    return target


def _write_json_exclusive(path, value):
    with Path(path).open("x") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True) + "\n")


def run_agent_campaign(codex, code_mode_host, runtime_root, inventory_dir, run_id, *,
                       authorized=False, resume=False, execute_fn=b.execute):
    if authorized is not True:
        raise SplitHostRefusal("explicit split-host campaign execution authorization required")
    campaign, runtime = agent_preflight(
        codex, code_mode_host, runtime_root, inventory_dir)
    contract = load_contract()
    artifacts = _artifact_root(run_id, resume)
    refs = representative.references(campaign, CAMPAIGN)
    launched = 0
    completed = 0
    unresolved = []

    for scenario_id, variant, repetition, seed in representative.jobs(campaign):
        scenario = next(
            row for row in coverage.load_manifest()["scenarios"]
            if row["id"] == scenario_id)
        scenario = scenario | {
            "allowed_variants": campaign["variants"],
            "quality_gates": ["independent-quality"],
        }
        job_id = _safe_job_id(scenario_id, variant, repetition, seed)
        job_dir = artifacts / job_id
        if job_dir.exists():
            if not resume or job_dir.is_symlink() or not (job_dir / "started.json").is_file():
                raise SplitHostRefusal("existing or invalid job evidence")
            if (job_dir / "agent-result.json").is_file():
                completed += 1
            else:
                unresolved.append(job_id)
            continue

        with tempfile.TemporaryDirectory(prefix="split-host-agent-", dir="/tmp") as tmp:
            workspace = Path(tmp)
            b.setup(scenario, workspace)
            argv = representative.command_plan(
                campaign, variant, str(codex), runtime=runtime, workspace=workspace)
            prompt = __import__("benchmark_campaign").prompt(campaign, scenario, variant)

            # Everything above is deterministic/model-free. From this point onward the
            # execution may start, so persist the no-retry ledger first.
            job_dir.mkdir(mode=0o700)
            started = {
                "schema_version": 1,
                "job_id": job_id,
                "scenario_id": scenario_id,
                "variant": variant,
                "repetition": repetition,
                "seed": seed,
                "campaign_sha256": contract["campaign_sha256"],
                "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            _write_json_exclusive(job_dir / "started.json", started)
            launched += 1
            execution_start = datetime.datetime.now(datetime.timezone.utc).isoformat()
            try:
                observation = execute_fn(
                    argv, workspace, prompt, timeout=campaign["timeout_seconds"])
            except OSError:
                observation = {
                    "stdout": "", "stderr": "", "exit_status": None,
                    "timeout": False, "duration": 0.0, "launch_failure": True,
                }
            parsed = b.parse_trace(observation["stdout"])
            reason = _agent_reason(observation, parsed)
            submission_exported = False
            export_error = None
            envelope = None
            if reason is None:
                try:
                    envelope = export_submission(scenario, workspace)
                    submission_exported = True
                except (OSError, ValueError) as error:
                    reason = "submission-export-refused"
                    export_error = type(error).__name__

            (job_dir / "trace.jsonl").write_text(observation["stdout"])
            (job_dir / "stderr.txt").write_text(observation["stderr"])
            if envelope is not None:
                _write_json_exclusive(job_dir / "submission.json", envelope)
            result = {
                "schema_version": 1,
                "job_id": job_id,
                "scenario_id": scenario_id,
                "variant": variant,
                "repetition": repetition,
                "seed": seed,
                "campaign_sha256": contract["campaign_sha256"],
                "execution_started_at": execution_start,
                "duration_seconds": observation["duration"],
                "exit_status": observation["exit_status"],
                "timeout": observation["timeout"],
                "terminal_status": parsed["terminal_status"],
                "parser_errors": parsed["errors"],
                "tokens": parsed["tokens"],
                "observed_tool_calls": parsed["observed_tool_calls"],
                "failure_reason": reason,
                "submission_exported": submission_exported,
                "export_error_class": export_error,
                "trace_sha256": _sha256(job_dir / "trace.jsonl"),
                "stderr_sha256": _sha256(job_dir / "stderr.txt"),
                "submission_sha256": (
                    _sha256(job_dir / "submission.json") if submission_exported else None),
            }
            _write_json_exclusive(job_dir / "agent-result.json", result)
            completed += 1

    started_count = sum(
        1 for path in artifacts.iterdir()
        if path.is_dir() and (path / "started.json").is_file())
    if started_count > contract["maximum_codex_exec_processes"]:
        raise SplitHostRefusal("Codex execution ledger exceeds frozen budget")
    summary = {
        "schema_version": 1,
        "kind": "split-host-agent-campaign",
        "campaign_id": campaign["campaign_id"],
        "campaign_sha256": contract["campaign_sha256"],
        "planned_jobs": 40,
        "maximum_codex_exec_processes": 40,
        "codex_exec_processes_started_this_invocation": launched,
        "started_ledger_count": started_count,
        "completed_agent_results": completed,
        "started_without_result": sorted(unresolved),
        "model_request_count": None,
        "quality_not_evaluated_on_agent_host": True,
        "frozen_references": refs,
    }
    summary_path = artifacts / "agent-summary.json"
    if summary_path.exists():
        summary_path.unlink()
    _write_json_exclusive(summary_path, summary)
    return summary


def _safe_rel_name(name):
    if type(name) is not str:
        return False
    path = PurePosixPath(name)
    return (not path.is_absolute() and bool(path.parts)
            and all(part not in {"", ".", ".."} for part in path.parts))


def validate_submission_envelope(envelope, scenario, campaign_sha256):
    if type(envelope) is not dict or set(envelope) != {
            "schema_version", "campaign_sha256", "scenario_id", "files"}:
        raise SplitHostRefusal("invalid submission envelope")
    if (envelope["schema_version"] != 1
            or envelope["campaign_sha256"] != campaign_sha256
            or envelope["scenario_id"] != scenario["id"]
            or type(envelope["files"]) is not dict):
        raise SplitHostRefusal("submission envelope identity mismatch")
    fixture = coverage.fixture(scenario)
    expected_names = set(fixture["files"]) | set(fixture["reference"])
    if not set(envelope["files"]) <= expected_names:
        raise SplitHostRefusal("unexpected submitted path")
    total = 0
    for name, text in envelope["files"].items():
        if not _safe_rel_name(name) or type(text) is not str:
            raise SplitHostRefusal("unsafe submitted value")
        encoded = text.encode("utf-8")
        if len(encoded) > submission_grader.MAX_SUBMISSION_FILE_BYTES:
            raise SplitHostRefusal("submitted file too large")
        total += len(encoded)
    if total > submission_grader.MAX_SUBMISSION_BYTES:
        raise SplitHostRefusal("submitted payload too large")
    return envelope["files"]


def _materialize_envelope(files, workspace):
    for name, text in files.items():
        destination = workspace / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text)
        destination.chmod(0o600)


def _record_from_agent(agent, quality, failure_reason, refs):
    attempt = {
        "start": agent["execution_started_at"],
        "end": agent["execution_started_at"],
        "duration": agent["duration_seconds"],
        "exit_status": agent["exit_status"],
        "quality_gates": {"independent-quality": quality},
        "quality_pass": quality,
        "failure_reason": failure_reason,
        "setup_seconds": None,
        "terminal_status": agent["terminal_status"],
        "tokens": agent["tokens"],
        "observed_tool_calls": agent["observed_tool_calls"],
        "tool_calls": None,
        "errors": agent["parser_errors"],
    }
    return {
        "schema_version": 1,
        "scenario_id": agent["scenario_id"],
        "variant": agent["variant"],
        "repetition": agent["repetition"],
        "order_seed": agent["seed"],
        "snapshot": next(
            s["snapshot"] for s in coverage.load_manifest()["scenarios"]
            if s["id"] == agent["scenario_id"]),
        "references": refs,
        "cold_warm": "unknown",
        "index_seconds": None,
        "bootstrap_seconds": None,
        "retry_count": 0,
        "attempts": [attempt],
        "initial_failure": failure_reason,
        "final_status": failure_reason,
        "quality_pass": quality,
    }


def grade_exported_campaign(agent_artifacts, qualification, runtime_root, inventory_dir,
                            output_dir):
    if not contract_verified():
        raise SplitHostRefusal("split-host evidence is not accepted")
    contract = load_contract()
    campaign = representative.load()
    if (type(qualification) is not host.QualifiedHostContract
            or qualification.status != "verified"
            or qualification.reference != GRADING_HOST_RECEIPT):
        raise SplitHostRefusal("accepted grading host receipt required")
    if not submission_grading.contract_verified(qualification):
        raise SplitHostRefusal("accepted production grading evidence required")
    runtime = submission_grading.prepare_runtime(
        runtime_root, inventory_dir, qualification)
    if runtime.inventory_reference != RUNTIME_INVENTORY_REFERENCE:
        raise SplitHostRefusal("grading runtime inventory mismatch")

    source = Path(agent_artifacts)
    output = Path(output_dir)
    if (not source.is_absolute() or source.is_symlink() or not source.is_dir()
            or not output.is_absolute() or output.exists() or output.is_symlink()):
        raise SplitHostRefusal("unsafe split-host grading paths")
    output.mkdir(mode=0o700)

    refs = representative.references(campaign, CAMPAIGN)
    agent_reference = AGENT_ISOLATION_REFERENCE
    expected_jobs = representative.jobs(campaign)
    records = []
    normalized = []
    incomplete = []

    for scenario_id, variant, repetition, seed in expected_jobs:
        job_id = _safe_job_id(scenario_id, variant, repetition, seed)
        job_dir = source / job_id
        result_path = job_dir / "agent-result.json"
        if not result_path.is_file():
            incomplete.append(job_id)
            continue
        agent = json.loads(result_path.read_text())
        required_agent = {
            "schema_version", "job_id", "scenario_id", "variant", "repetition",
            "seed", "campaign_sha256", "execution_started_at", "duration_seconds",
            "exit_status", "timeout", "terminal_status", "parser_errors", "tokens",
            "observed_tool_calls", "failure_reason", "submission_exported",
            "export_error_class", "trace_sha256", "stderr_sha256", "submission_sha256",
        }
        if (type(agent) is not dict or set(agent) != required_agent
                or agent["schema_version"] != 1
                or agent["job_id"] != job_id
                or agent["scenario_id"] != scenario_id
                or agent["variant"] != variant
                or agent["repetition"] != repetition
                or agent["seed"] != seed
                or agent["campaign_sha256"] != contract["campaign_sha256"]):
            raise SplitHostRefusal("agent result identity mismatch")
        trace = job_dir / "trace.jsonl"
        stderr = job_dir / "stderr.txt"
        if (_sha256(trace) != agent["trace_sha256"]
                or _sha256(stderr) != agent["stderr_sha256"]):
            raise SplitHostRefusal("agent raw artifact mismatch")
        parsed = b.parse_trace(trace.read_text())
        if (parsed["terminal_status"] != agent["terminal_status"]
                or parsed["errors"] != agent["parser_errors"]
                or parsed["tokens"] != agent["tokens"]
                or parsed["observed_tool_calls"] != agent["observed_tool_calls"]):
            raise SplitHostRefusal("agent trace parse mismatch")

        failure = agent["failure_reason"]
        quality = False
        grade_record = None
        scenario = next(
            row for row in coverage.load_manifest()["scenarios"]
            if row["id"] == scenario_id)
        if failure is None:
            submission = job_dir / "submission.json"
            if (not agent["submission_exported"] or not submission.is_file()
                    or _sha256(submission) != agent["submission_sha256"]):
                failure = "submission-evidence-missing"
            else:
                envelope = json.loads(submission.read_text())
                files = validate_submission_envelope(
                    envelope, scenario, contract["campaign_sha256"])
                with tempfile.TemporaryDirectory(
                        prefix="split-host-grade-", dir="/tmp") as tmp:
                    workspace = Path(tmp)
                    _materialize_envelope(files, workspace)
                    policy = (isolation.SubmissionPolicy(True, ("answer.json",))
                              if scenario_id == "explore-notification"
                              else isolation.SubmissionPolicy())
                    result = submission_grading.grade_representative(
                        scenario_id, workspace, qualification, runtime, policy)
                if result.status != "verified" or type(result.quality_pass) is not bool:
                    failure = "grading-refusal"
                else:
                    quality = result.quality_pass
                    if not quality:
                        failure = "quality-failure"
                    grade_record = {
                        "schema_version": 1,
                        "job_id": job_id,
                        "status": result.status,
                        "reason": result.reason,
                        "quality_pass": result.quality_pass,
                        "submission_sha256": agent["submission_sha256"],
                    }
        record = _record_from_agent(agent, quality, failure, refs)
        safe = representative._normalized(
            campaign, record, refs, qualification.reference, agent_reference,
            campaign["runner_pins"]["isolation_sha256"],
            PRODUCTION_GRADING_REFERENCE, runtime.inventory_reference,
            "real-representative-split-host")
        safe["split_host_topology_reference"] = load_candidate_evidence()["evidence_reference"]
        safe["agent_trace_sha256"] = agent["trace_sha256"]
        safe["submission_sha256"] = agent["submission_sha256"]
        _write_json_exclusive(output / f"{job_id}.json", safe)
        if grade_record is not None:
            _write_json_exclusive(output / f"{job_id}.grade.json", grade_record)
        records.append(record)
        normalized.append(safe)

    if incomplete:
        summary = {
            "schema_version": 1,
            "kind": "split-host-graded-campaign",
            "campaign_id": campaign["campaign_id"],
            "campaign_sha256": contract["campaign_sha256"],
            "planned_jobs": 40,
            "graded_or_terminal_jobs": len(records),
            "incomplete_jobs": sorted(incomplete),
            "complete": False,
        }
    else:
        summary = {
            "schema_version": 1,
            "kind": "split-host-graded-campaign",
            "campaign_id": campaign["campaign_id"],
            "campaign_sha256": contract["campaign_sha256"],
            "planned_jobs": 40,
            "graded_or_terminal_jobs": len(records),
            "incomplete_jobs": [],
            "complete": True,
            "summary": b.aggregate(records),
        }
    _write_json_exclusive(output / "summary.json", summary)
    return summary


def plan():
    contract = load_contract()
    return {
        "contract_id": contract["contract_id"],
        "campaign_id": contract["campaign_id"],
        "planned_primary_runs": 40,
        "maximum_codex_exec_processes": 40,
        "retries": 0,
        "split_host_contract_verified": contract_verified(),
        "model_execution_enabled": False,
        "authorization_required": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", action="store_true")
    parser.add_argument("--grade", action="store_true")
    parser.add_argument("--authorize-execution", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--codex")
    parser.add_argument("--code-mode-host")
    parser.add_argument("--runtime-root")
    parser.add_argument("--inventory-dir")
    parser.add_argument("--run-id", default="representative-split-host-v1")
    parser.add_argument("--agent-artifacts")
    parser.add_argument("--qualification-evidence")
    parser.add_argument("--output-dir")
    args = parser.parse_args(argv)
    if args.agent and args.grade:
        parser.error("--agent and --grade are mutually exclusive")
    try:
        if args.agent:
            result = run_agent_campaign(
                args.codex, args.code_mode_host, args.runtime_root,
                args.inventory_dir, args.run_id,
                authorized=args.authorize_execution, resume=args.resume)
        elif args.grade:
            qualification = host.load_evidence(args.qualification_evidence)
            result = grade_exported_campaign(
                args.agent_artifacts, qualification, args.runtime_root,
                args.inventory_dir, args.output_dir)
        else:
            result = plan()
    except SplitHostRefusal as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
