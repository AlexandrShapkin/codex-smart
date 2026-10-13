"""Credential-free representative technical-readiness probe.

This probe can verify every pre-authorization gate but never passes execution
authorization to the representative runner. It uses only repository-authored
toolchain smoke programs and reports no private credential values.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import benchmark_agent_isolation as agent_isolation
import benchmark_host as host
import benchmark_grading_backend as grading_backend
import benchmark_coverage as coverage
import benchmark_representative as runner
import benchmark_submission_grading as submission_grading


ROOT = Path(__file__).resolve().parent.parent
CANDIDATE_EVIDENCE = ROOT / "benchmarks/representative-readiness-candidate-v1.json"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_checked(argv, *, cwd, env=None, expected_stdout=None, timeout=30):
    result = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        close_fds=True,
    )
    if result.returncode != 0:
        raise ValueError("readiness smoke command failed")
    if expected_stdout is not None and result.stdout.strip() != expected_stdout:
        raise ValueError("readiness smoke output mismatch")
    return result


def smoke_staged_environment(campaign, runtime, codex):
    with tempfile.TemporaryDirectory(prefix="representative-readiness-", dir="/tmp") as tmp:
        workspace = Path(tmp)
        child_env = runner._staged_environment(campaign, runtime, workspace)
        env = dict(child_env)
        home = workspace / ".home"
        home.mkdir()
        env["HOME"] = str(home)
        env["LANG"] = "C"

        argv = runner.command_plan(
            campaign, "vanilla", codex, runtime=runtime, workspace=workspace)
        setting = next(
            value for value in argv if value.startswith("shell_environment_policy.set="))
        help_argv = [codex, "exec", "-c", setting, "--help"]
        run_checked(help_argv, cwd=workspace, timeout=10)

        rust = workspace / "rust"
        (rust / "src").mkdir(parents=True)
        (rust / "Cargo.toml").write_text(
            '[package]\nname="runtime_smoke"\nversion="0.1.0"\nedition="2024"\n')
        (rust / "src/main.rs").write_text('fn main(){println!("rust-ok");}\n')
        run_checked(
            ["cargo", "run", "--quiet", "--offline"],
            cwd=rust, env=env, expected_stdout="rust-ok", timeout=30)

        go = workspace / "go"
        go.mkdir()
        (go / "go.mod").write_text("module runtime-smoke\ngo 1.27\n")
        (go / "main.go").write_text(
            'package main\nimport "fmt"\nfunc main(){fmt.Println("go-ok")}\n')
        run_checked(["go", "run", "main.go"], cwd=go, env=env,
                    expected_stdout="go-ok", timeout=30)

        python = workspace / "python"
        python.mkdir()
        (python / "main.py").write_text('print("python-ok")\n')
        run_checked(["python3", "main.py"], cwd=python, env=env,
                    expected_stdout="python-ok", timeout=10)

    return {
        "codex_shell_environment_config_parse": True,
        "rust_compile_run": True,
        "go_compile_run": True,
        "python_run": True,
    }


def candidate_reference(candidate):
    return hashlib.sha256(
        json.dumps(candidate, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_candidate_evidence(path=CANDIDATE_EVIDENCE):
    record = json.loads(Path(path).read_text())
    if (type(record) is not dict or set(record) != {
            "schema_version", "contract_id", "probe_kind", "candidate",
            "evidence_reference", "model_calls", "real_credentials_used"}):
        raise ValueError("invalid representative readiness evidence")
    if (record["schema_version"] != 1
            or record["contract_id"] != "benchmark-representative-readiness-v1"
            or record["probe_kind"] != "credential-free-preauthorization-readiness"
            or record["model_calls"] != 0
            or record["real_credentials_used"] is not False):
        raise ValueError("representative readiness evidence identity mismatch")
    candidate = record["candidate"]
    required = {
        "qualification_reference", "agent_execution_isolation_reference",
        "grading_backend_reference", "production_grading_reference",
        "qualified_runtime_inventory_component_reference",
        "prepared_runtime_inventory_reference", "codex_executable_sha256",
        "codex_version", "toolchain_versions", "runner_sha256", "probe_sha256",
        "representative_campaign_ready", "plan_model_execution_enabled",
        "preauthorization_refusal", "preauthorization_model_calls",
        "preauthorization_attempt_count", "preauthorization_artifact_created",
        "real_credentials_used", "codex_shell_environment_config_parse",
        "rust_compile_run", "go_compile_run", "python_run",
    }
    if type(candidate) is not dict or set(candidate) != required:
        raise ValueError("invalid representative readiness candidate")
    host_contract = host.load_contract()
    host_candidate = host.load_candidate_evidence()
    agent_candidate = agent_isolation.load_candidate_evidence()
    backend_candidate = grading_backend.load_candidate_evidence()
    production_candidate = submission_grading.load_candidate_evidence()
    runtime_component = next(
        row for row in host_candidate["components"] if row["component"] == "runtime_inventory")
    expected_tools = {
        name: spec["version"] for name, spec in coverage.REPRESENTATIVE_TOOLCHAINS.items()}
    required_values = {
        "qualification_reference": host_candidate["receipt_reference"],
        "agent_execution_isolation_reference": agent_candidate["evidence_reference"],
        "grading_backend_reference": backend_candidate["evidence_reference"],
        "production_grading_reference": production_candidate["evidence_reference"],
        "qualified_runtime_inventory_component_reference": runtime_component["evidence_sha256"],
        "prepared_runtime_inventory_reference": production_candidate["candidate"]["runtime_inventory_reference"],
        "codex_executable_sha256": agent_isolation.load_contract()["codex_executable_sha256"],
        "codex_version": "0.162.1",
        "toolchain_versions": expected_tools,
        "runner_sha256": sha256(Path(runner.__file__)),
        "probe_sha256": sha256(Path(__file__)),
        "representative_campaign_ready": True,
        "plan_model_execution_enabled": False,
        "preauthorization_refusal": "explicit representative execution authorization required",
        "preauthorization_model_calls": 0,
        "preauthorization_attempt_count": 0,
        "preauthorization_artifact_created": False,
        "real_credentials_used": False,
        "codex_shell_environment_config_parse": True,
        "rust_compile_run": True,
        "go_compile_run": True,
        "python_run": True,
    }
    if candidate != required_values:
        raise ValueError("representative readiness candidate values mismatch")
    if candidate["qualification_reference"] not in host_contract["accepted_qualification_receipts"]:
        raise ValueError("representative readiness host receipt not accepted")
    if candidate["agent_execution_isolation_reference"] not in agent_isolation.load_contract()["accepted_evidence_sha256"]:
        raise ValueError("representative readiness agent evidence not accepted")
    if candidate["grading_backend_reference"] not in grading_backend.load_contract()["accepted_evidence_sha256"]:
        raise ValueError("representative readiness backend evidence not accepted")
    if candidate["production_grading_reference"] not in submission_grading.load_contract()["accepted_evidence_sha256"]:
        raise ValueError("representative readiness production grading evidence not accepted")
    if candidate_reference(candidate) != record["evidence_reference"]:
        raise ValueError("representative readiness evidence reference mismatch")
    return record


def probe(codex, runtime_root, inventory_dir, qualification_path):
    qualification = host.load_evidence(qualification_path)
    campaign = runner.load()
    if qualification.status != "verified":
        raise ValueError("reviewed qualification required")
    if not submission_grading.contract_verified(qualification):
        raise ValueError("accepted production grading evidence required")

    runtime = submission_grading.prepare_runtime(
        runtime_root, inventory_dir, qualification)
    runner._identity_preflight(campaign, codex, runtime)
    agent_isolation.runtime_preflight()

    smokes = smoke_staged_environment(campaign, runtime, codex)
    run_id = "readiness-preflight-noauth"
    artifact = ROOT / ".artifacts" / run_id
    if artifact.exists() or artifact.is_symlink():
        raise ValueError("readiness preflight artifact already exists")

    try:
        runner.real_run(
            codex,
            run_id,
            qualification,
            grading_runtime_root=runtime_root,
            grading_inventory_dir=inventory_dir,
            authorized=False,
        )
    except runner.PreflightRefusal as error:
        if (str(error) != "explicit representative execution authorization required"
                or error.model_calls != 0 or error.attempt_count != 0):
            raise ValueError("unexpected representative pre-authorization result") from None
    else:
        raise ValueError("representative runner unexpectedly crossed authorization gate")

    if artifact.exists() or artifact.is_symlink():
        raise ValueError("pre-authorization run created artifact evidence")

    agent_reference = next(
        row.evidence_sha256 for row in qualification.evidence.components
        if row.component == agent_isolation.COMPONENT)
    inventory_component = next(
        row.evidence_sha256 for row in qualification.evidence.components
        if row.component == "runtime_inventory")
    grading_candidate = submission_grading.load_candidate_evidence()

    candidate = {
        "qualification_reference": qualification.reference,
        "agent_execution_isolation_reference": agent_reference,
        "grading_backend_reference": submission_grading.GRADING_BACKEND_REFERENCE,
        "production_grading_reference": grading_candidate["evidence_reference"],
        "qualified_runtime_inventory_component_reference": inventory_component,
        "prepared_runtime_inventory_reference": runtime.inventory_reference,
        "codex_executable_sha256": sha256(codex),
        "codex_version": campaign["codex"]["version"],
        "toolchain_versions": {
            name: spec["version"] for name, spec in campaign["toolchains"].items()
        },
        "runner_sha256": sha256(Path(runner.__file__)),
        "probe_sha256": sha256(Path(__file__)),
        "representative_campaign_ready": campaign["readiness"]["representative_campaign_ready"],
        "plan_model_execution_enabled": False,
        "preauthorization_refusal": "explicit representative execution authorization required",
        "preauthorization_model_calls": 0,
        "preauthorization_attempt_count": 0,
        "preauthorization_artifact_created": False,
        "real_credentials_used": False,
        **smokes,
    }
    return {
        "schema_version": 1,
        "contract_id": "benchmark-representative-readiness-v1",
        "probe_kind": "credential-free-preauthorization-readiness",
        "candidate": candidate,
        "evidence_reference": candidate_reference(candidate),
        "model_calls": 0,
        "real_credentials_used": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--inventory-dir", required=True)
    parser.add_argument(
        "--qualification-evidence",
        default=str(ROOT / "benchmarks/qualified-host-receipt-v1.json"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    output = Path(args.output)
    if (not output.is_absolute() or output.parent != Path("/tmp")
            or not output.name.startswith("representative-readiness-evidence-")
            or output.exists()):
        parser.error("new /tmp representative-readiness-evidence-* output required")
    result = probe(
        args.codex, args.runtime_root, args.inventory_dir, args.qualification_evidence)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
