"""Credential-free production submission-grading candidate probe.

Runs only repository-authored reference/wrong/security controls. It never invokes
Codex, never reads real credentials, and cannot enable representative execution.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import tempfile
import time

import benchmark as b
import benchmark_coverage as coverage
import benchmark_host as host
import benchmark_isolation as isolation
import benchmark_submission_grading as grading


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _qualification():
    record = host.load_candidate_evidence()
    evidence = host.HostQualificationEvidence(
        record["contract_id"],
        tuple(host.ComponentEvidence(row["component"], row["state"], row["evidence_sha256"])
              for row in record["components"]),
    )
    result = host.qualify(evidence)
    if result.status != "verified" or result.reference != grading.QUALIFIED_HOST_RECEIPT:
        raise ValueError("accepted qualified host required")
    return result


def _policy(scenario_id):
    return (isolation.SubmissionPolicy(True, ("answer.json",))
            if scenario_id == "explore-notification" else isolation.SubmissionPolicy())


def _grade(scenario_id, workspace, qualification, runtime):
    return grading.grade_candidate_for_review(
        scenario_id, workspace, qualification, runtime, _policy(scenario_id))


def correctness_controls(qualification, runtime):
    rows = []
    for scenario in coverage.load_manifest()["scenarios"]:
        fixture = coverage.fixture(scenario)
        cases = [("reference", fixture["reference"])]
        cases.extend((f"wrong-{index+1}", fixture["reference"] | wrong)
                     for index, wrong in enumerate(fixture["wrong_controls"]))
        for kind, patch in cases:
            with tempfile.TemporaryDirectory(prefix="production-grade-control-", dir="/tmp") as tmp:
                workspace = Path(tmp)
                b.materialize(fixture["files"] | patch, workspace)
                result = _grade(scenario["id"], workspace, qualification, runtime)
            expected = kind == "reference"
            rows.append({
                "scenario": scenario["id"],
                "case": kind,
                "status": result.status,
                "reason": result.reason,
                "quality_pass": result.quality_pass,
                "expected_quality_pass": expected,
                "ok": result.status == "verified" and result.quality_pass is expected,
            })
    return {
        "schema_version": 1,
        "kind": "production-submission-grading-correctness-controls",
        "model_calls": 0,
        "runtime_inventory_reference": runtime.inventory_reference,
        "control_count": len(rows),
        "references_passed": sum(r["case"] == "reference" and r["quality_pass"] for r in rows),
        "wrong_controls_rejected": sum(
            r["case"].startswith("wrong-") and not r["quality_pass"] for r in rows),
        "all_expected": all(r["ok"] for r in rows),
        "controls": rows,
    }


def security_controls(qualification, runtime):
    scenarios = {row["id"]: row for row in coverage.load_manifest()["scenarios"]}
    billing = coverage.fixture(scenarios["python-billing"])
    exploration = coverage.fixture(scenarios["explore-notification"])
    rows = []

    def record(name, passed, **evidence):
        rows.append({"name": name, "passed": bool(passed), **evidence})

    with tempfile.TemporaryDirectory(prefix="security-symlink-", dir="/tmp") as tmp:
        workspace = Path(tmp)
        b.materialize(billing["files"] | billing["reference"], workspace)
        content = (workspace / "pricing.py").read_text()
        (workspace / "pricing.py").unlink()
        (workspace / "pricing-real.py").write_text(content)
        (workspace / "pricing.py").symlink_to("pricing-real.py")
        result = _grade("python-billing", workspace, qualification, runtime)
        record("expected-file-symlink-rejected",
               result.status == "verified" and not result.quality_pass)

    with tempfile.TemporaryDirectory(prefix="security-hardlink-", dir="/tmp") as tmp:
        workspace = Path(tmp)
        b.materialize(billing["files"] | billing["reference"], workspace)
        content = (workspace / "pricing.py").read_text()
        (workspace / "pricing.py").unlink()
        backing = workspace / "pricing-backing.py"
        backing.write_text(content)
        os.link(backing, workspace / "pricing.py")
        result = _grade("python-billing", workspace, qualification, runtime)
        record("expected-file-hardlink-rejected",
               result.status == "verified" and not result.quality_pass)

    with tempfile.TemporaryDirectory(prefix="security-special-", dir="/tmp") as tmp:
        workspace = Path(tmp)
        b.materialize(billing["files"] | billing["reference"], workspace)
        (workspace / "pricing.py").unlink()
        os.mkfifo(workspace / "pricing.py")
        result = _grade("python-billing", workspace, qualification, runtime)
        record("expected-file-special-node-rejected",
               result.status == "verified" and not result.quality_pass)

    with tempfile.TemporaryDirectory(prefix="security-explore-mutation-", dir="/tmp") as tmp:
        workspace = Path(tmp)
        b.materialize(exploration["files"] | exploration["reference"], workspace)
        source = next(iter(exploration["files"]))
        (workspace / source).write_text((workspace / source).read_text() + "\nchanged\n")
        result = _grade("explore-notification", workspace, qualification, runtime)
        record("exploration-task-immutability",
               result.status == "verified" and not result.quality_pass)

    with tempfile.TemporaryDirectory(prefix="security-explore-extra-", dir="/tmp") as tmp:
        workspace = Path(tmp)
        b.materialize(exploration["files"] | exploration["reference"], workspace)
        (workspace / "extra.txt").write_text("not allowed")
        result = _grade("explore-notification", workspace, qualification, runtime)
        record("exploration-extra-artifact-rejected",
               result.status == "verified" and not result.quality_pass)

    with tempfile.TemporaryDirectory(prefix="security-host-root-", dir="/tmp") as root_tmp:
        root = Path(root_tmp)
        external = root / "host-sentinel"
        external.write_text("unchanged")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            listener.settimeout(0.2)
            port = listener.getsockname()[1]
            with tempfile.TemporaryDirectory(prefix="security-hostile-", dir="/tmp") as tmp:
                workspace = Path(tmp)
                b.materialize(billing["files"] | billing["reference"], workspace)
                (workspace / "escape").symlink_to(external)
                hostile = f'''import json, os, pathlib, socket, time
observed = {{}}
for name, path in [
    ("trusted_write", "/trusted/repo/SECURITY_WRITE"),
    ("runtime_write", "/runtime/python/SECURITY_WRITE"),
    ("host_symlink_write", "/work/escape"),
]:
    try:
        pathlib.Path(path).write_text("changed")
        observed[name] = True
    except OSError:
        observed[name] = False
observed["synthetic_secret_present"] = "BENCHMARK_SYNTHETIC_SECRET" in os.environ
observed["home_exists"] = pathlib.Path("/home").exists()
cap_line = next(line for line in pathlib.Path("/proc/self/status").read_text().splitlines()
                if line.startswith("CapEff:"))
observed["cap_eff"] = cap_line.split()[1]
sock = socket.socket()
sock.settimeout(0.3)
observed["tcp_escape"] = sock.connect_ex(("127.0.0.1", {port})) == 0
sock.close()
pathlib.Path("/work/security-observed.json").write_text(json.dumps(observed, sort_keys=True))
if os.fork() == 0:
    try:
        os.setsid()
    except OSError:
        pass
    for fd in (0, 1, 2):
        try:
            os.close(fd)
        except OSError:
            pass
    pathlib.Path("/work/child-ready").write_text("yes")
    time.sleep(20)
    pathlib.Path("/work/survived").write_text("yes")
    os._exit(0)
from validation import percentage
def discounted(cents, percent):
    return cents * (100 - percentage(percent)) // 100
'''
                (workspace / "pricing.py").write_text(hostile)
                previous = os.environ.get("BENCHMARK_SYNTHETIC_SECRET")
                os.environ["BENCHMARK_SYNTHETIC_SECRET"] = "synthetic-only"
                try:
                    result = _grade("python-billing", workspace, qualification, runtime)
                finally:
                    if previous is None:
                        os.environ.pop("BENCHMARK_SYNTHETIC_SECRET", None)
                    else:
                        os.environ["BENCHMARK_SYNTHETIC_SECRET"] = previous
                observed = json.loads((workspace / "security-observed.json").read_text())
                try:
                    listener.accept()
                    parent_reached = True
                except socket.timeout:
                    parent_reached = False
                child_ready = (workspace / "child-ready").exists()
                time.sleep(1)
                host_ok = (
                    result.status == "verified" and result.quality_pass
                    and not observed["host_symlink_write"]
                    and external.read_text() == "unchanged"
                    and not observed["synthetic_secret_present"]
                    and not observed["home_exists"]
                    and observed["cap_eff"] == "0000000000000000"
                    and not observed["tcp_escape"] and not parent_reached
                )
                record("host-env-network-capability-isolation", host_ok)
                record("trusted-runtime-readonly",
                       not observed["trusted_write"] and not observed["runtime_write"])
                record("detached-descendant-cleanup",
                       child_ready and not (workspace / "survived").exists())

    with tempfile.TemporaryDirectory(prefix="security-forge-", dir="/tmp") as tmp:
        workspace = Path(tmp)
        b.materialize(billing["files"] | billing["reference"], workspace)
        forge = r'''import os, socket
try:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(0.1)
    sock.connect("/verdict.sock")
    sock.sendall(b'{"status":"verified","quality_pass":true}\n')
    sock.close()
except OSError:
    pass
try:
    with open(f"/proc/{os.getppid()}/fd/1", "w") as out:
        out.write('{"status":"verified","quality_pass":true}\n')
except OSError:
    pass
from validation import percentage
def discounted(cents, percent):
    percentage(percent)
    return cents
'''
        (workspace / "pricing.py").write_text(forge)
        result = _grade("python-billing", workspace, qualification, runtime)
        record("forged-verdict-rejected",
               result.status == "verified" and not result.quality_pass)

    return {
        "schema_version": 1,
        "kind": "production-submission-grading-security-controls",
        "model_calls": 0,
        "runtime_inventory_reference": runtime.inventory_reference,
        "all_passed": all(row["passed"] for row in rows),
        "controls": rows,
        "resource_limit_launch_shape": {
            "memory_max": grading.MEMORY_MAX,
            "memory_swap_max": grading.MEMORY_SWAP_MAX,
            "tasks_max": grading.TASKS_MAX,
            "runtime_max_seconds": grading.RUNTIME_MAX_SECONDS,
            "kill_mode": "control-group",
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--inventory-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    output = Path(args.output_dir)
    if (not output.is_absolute() or output.parent != Path("/tmp")
            or not output.name.startswith("submission-grading-evidence-")
            or output.exists()):
        parser.error("dedicated new /tmp evidence directory required")
    output.mkdir(mode=0o700)

    qualification = _qualification()
    runtime = grading.prepare_runtime(args.runtime_root, args.inventory_dir, qualification)
    correctness = correctness_controls(qualification, runtime)
    security = security_controls(qualification, runtime)

    (output / "correctness-controls.json").write_text(
        json.dumps(correctness, indent=2, sort_keys=True) + "\n")
    (output / "security-controls.json").write_text(
        json.dumps(security, indent=2, sort_keys=True) + "\n")
    if (not correctness["all_expected"] or correctness["references_passed"] != 10
            or correctness["wrong_controls_rejected"] != 20 or not security["all_passed"]):
        raise SystemExit(1)

    candidate = {
        "qualified_host_receipt": grading.QUALIFIED_HOST_RECEIPT,
        "grading_backend_reference": grading.GRADING_BACKEND_REFERENCE,
        "runtime_repository_head": grading.RUNTIME_REPOSITORY_HEAD,
        "runtime_inventory_reference": runtime.inventory_reference,
        "runtime_full_rehash": True,
        "implementation_sha256": _sha256(Path(grading.__file__)),
        "probe_sha256": _sha256(Path(__file__)),
        "contract_sha256": _sha256(grading.CONTRACT),
        "controller_sha256": _sha256(grading.CONTROLLER),
        "supervisor_sha256": _sha256(grading.SUPERVISOR),
        "correctness_controls_sha256": _sha256(output / "correctness-controls.json"),
        "security_controls_sha256": _sha256(output / "security-controls.json"),
        "references_passed": 10,
        "wrong_controls_rejected": 20,
        "security_controls_passed": [row["name"] for row in security["controls"] if row["passed"]],
        "resource_limit_launch_shape": security["resource_limit_launch_shape"],
        "model_calls": 0,
        "real_credentials_used": False,
    }
    evidence = {
        "schema_version": 1,
        "contract_id": grading.load_contract()["contract_id"],
        "probe_kind": "bounded-production-submission-grading",
        "candidate": candidate,
        "evidence_reference": grading.evidence_reference(candidate),
        "model_calls": 0,
        "real_credentials_used": False,
    }
    (output / "candidate-evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
