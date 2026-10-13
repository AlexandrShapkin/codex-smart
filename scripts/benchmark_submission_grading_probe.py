"""Credential-free production submission-grading candidate probe.

Runs only repository-authored reference/wrong/security controls. It never invokes
Codex, never reads real credentials, and cannot enable representative execution.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

import benchmark as b
import benchmark_coverage as coverage
import benchmark_host as host
import benchmark_isolation as isolation
import benchmark_submission_grading as grading


def _sha256(path):
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return digest


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


def _policy(scenario):
    return (isolation.SubmissionPolicy(True, ("answer.json",))
            if scenario == "explore-notification" else isolation.SubmissionPolicy())


def _grade(scenario, workspace, qualification, runtime):
    return grading.grade_candidate_for_review(
        scenario, workspace, qualification, runtime, _policy(scenario))


def correctness_controls(qualification, runtime):
    rows = []
    for scenario in coverage.load_manifest()["scenarios"]:
        fixture = coverage.fixture(scenario)
        cases = [("reference", fixture["reference"])]
        cases.extend((f"wrong-{index+1}", fixture["reference"] | wrong)
                     for index, wrong in enumerate(fixture["wrong_controls"]))
        for kind, patch in cases:
            with tempfile.TemporaryDirectory(prefix="production-grade-control-") as tmp:
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
    rows = []

    def record(name, passed, **evidence):
        rows.append({"name": name, "passed": bool(passed), **evidence})

    billing = coverage.fixture(scenarios["python-billing"])

    with tempfile.TemporaryDirectory(prefix="prod-sec-symlink-") as tmp:
        workspace = Path(tmp) / "work"
        workspace.mkdir()
        b.materialize(billing["files"] | billing["reference"], workspace)
        external = Path(tmp) / "external"
        external.write_text("unchanged")
        (workspace / "escape-link").symlink_to(external)
        result = _grade("python-billing", workspace, qualification, runtime)
        record("symlink-rejected",
               result.status == "verified" and not result.quality_pass
               and external.read_text() == "unchanged",
               external_unchanged=external.read_text() == "unchanged")

    with tempfile.TemporaryDirectory(prefix="prod-sec-hardlink-") as tmp:
        root = Path(tmp)
        workspace = root / "work"
        workspace.mkdir()
        b.materialize(billing["files"] | billing["reference"], workspace)
        external = root / "external-hardlink-target"
        external.write_text("unchanged")
        os.link(external, workspace / "unexpected-hardlink")
        result = _grade("python-billing", workspace, qualification, runtime)
        record("hardlink-rejected",
               result.status == "verified" and not result.quality_pass
               and external.read_text() == "unchanged",
               external_unchanged=external.read_text() == "unchanged")

    with tempfile.TemporaryDirectory(prefix="prod-sec-fifo-") as tmp:
        workspace = Path(tmp)
        b.materialize(billing["files"] | billing["reference"], workspace)
        os.mkfifo(workspace / "unexpected-fifo")
        result = _grade("python-billing", workspace, qualification, runtime)
        record("special-node-rejected",
               result.status == "verified" and not result.quality_pass)

    exploration = coverage.fixture(scenarios["explore-notification"])
    with tempfile.TemporaryDirectory(prefix="prod-sec-explore-change-") as tmp:
        workspace = Path(tmp)
        b.materialize(exploration["files"] | exploration["reference"], workspace)
        name = next(iter(exploration["files"]))
        (workspace / name).write_text((workspace / name).read_text() + "\nchanged\n")
        result = _grade("explore-notification", workspace, qualification, runtime)
        record("exploration-task-immutability",
               result.status == "verified" and not result.quality_pass)

    with tempfile.TemporaryDirectory(prefix="prod-sec-explore-extra-") as tmp:
        workspace = Path(tmp)
        b.materialize(exploration["files"] | exploration["reference"], workspace)
        (workspace / "extra.txt").write_text("unexpected")
        result = _grade("explore-notification", workspace, qualification, runtime)
        record("exploration-extra-artifact-rejected",
               result.status == "verified" and not result.quality_pass)

    probe_source = r"""
import json, os, pathlib, socket
from validation import percentage
obs = {"synthetic_secret": os.environ.get("BENCHMARK_SYNTHETIC_SECRET"),
       "home_exists": pathlib.Path("/home").exists()}
try:
    pathlib.Path("/tmp/codex-smart-production-sentinel").write_text("changed")
    obs["private_tmp_write"] = True
except OSError:
    obs["private_tmp_write"] = False
try:
    pathlib.Path("/home/production-grading-escape").write_text("changed")
    obs["home_write_error"] = None
except OSError as e:
    obs["home_write_error"] = e.errno
for line in pathlib.Path("/proc/self/status").read_text().splitlines():
    if line.startswith("CapEff:"):
        obs["cap_eff"] = line.split()[1]
s = socket.socket()
s.settimeout(0.3)
obs["external_tcp_rc"] = s.connect_ex(("192.0.2.1", 9))
s.close()
pathlib.Path("/work/security-observation.json").write_text(json.dumps(obs, sort_keys=True))
def discounted(cents, percent):
    return cents * (100 - percentage(percent)) // 100
"""
    host_sentinel = Path("/tmp/codex-smart-production-sentinel")
    host_sentinel.write_text("unchanged")
    try:
        with tempfile.TemporaryDirectory(prefix="prod-sec-observe-") as tmp:
            workspace = Path(tmp)
            patch = dict(billing["reference"])
            patch["pricing.py"] = probe_source
            b.materialize(billing["files"] | patch, workspace)
            previous = os.environ.get("BENCHMARK_SYNTHETIC_SECRET")
            os.environ["BENCHMARK_SYNTHETIC_SECRET"] = "synthetic-parent-only"
            try:
                result = _grade("python-billing", workspace, qualification, runtime)
            finally:
                if previous is None:
                    os.environ.pop("BENCHMARK_SYNTHETIC_SECRET", None)
                else:
                    os.environ["BENCHMARK_SYNTHETIC_SECRET"] = previous
            observation = json.loads((workspace / "security-observation.json").read_text())
            normalized = {
                "synthetic_secret_absent": observation["synthetic_secret"] is None,
                "home_absent": observation["home_exists"] is False,
                "home_write_blocked": observation["home_write_error"] is not None,
                "capabilities_zero": observation["cap_eff"] == "0000000000000000",
                "external_tcp_blocked": observation["external_tcp_rc"] != 0,
                "host_tmp_unchanged": host_sentinel.read_text() == "unchanged",
                "private_tmp_available": observation["private_tmp_write"] is True,
            }
            record("host-env-network-capability-isolation",
                   result.status == "verified" and result.quality_pass
                   and all(normalized.values()), **normalized)
    finally:
        host_sentinel.unlink(missing_ok=True)

    descendant_source = r"""
import os, pathlib, time
from validation import percentage
if os.fork() == 0:
    try:
        os.setsid()
    except OSError:
        pass
    fd = os.open("/dev/null", os.O_RDWR)
    for target in (0, 1, 2):
        os.dup2(fd, target)
    if fd > 2:
        os.close(fd)
    time.sleep(3)
    pathlib.Path("/work/descendant-survived").write_text("survived")
    os._exit(0)
def discounted(cents, percent):
    return cents * (100 - percentage(percent)) // 100
"""
    with tempfile.TemporaryDirectory(prefix="prod-sec-descendant-") as tmp:
        workspace = Path(tmp)
        patch = dict(billing["reference"])
        patch["pricing.py"] = descendant_source
        b.materialize(billing["files"] | patch, workspace)
        result = _grade("python-billing", workspace, qualification, runtime)
        time.sleep(4)
        survived = (workspace / "descendant-survived").exists()
        record("descendant-cleanup",
               result.status == "verified" and result.quality_pass and not survived,
               survived=survived)

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
        "entrypoint_sha256": hashlib.sha256(grading.ENTRYPOINT_SOURCE.encode()).hexdigest(),
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
