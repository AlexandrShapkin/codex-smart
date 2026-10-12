"""Reviewed grading-isolation backend contract and mount-topology guard.

The frozen Ubuntu backend is known to be affected by CVE-2026-87766 in general.
This module accepts only a narrower invocation shape where untrusted content is
mounted last and bubblewrap performs no later filesystem-destination operation.
"""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import subprocess
from typing import Literal

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "benchmarks/grading-isolation-backend-v1.json"
CANDIDATE_EVIDENCE = ROOT / "benchmarks/grading-isolation-backend-candidate-v1.json"
COMPONENT = "isolation_backend"


@dataclass(frozen=True)
class MountOp:
    option: str
    destination: str
    source: str | None = None
    trust: Literal["trusted", "untrusted"] = "trusted"
    size_bytes: int | None = None


def expected_contract():
    return {
        "schema_version": 1,
        "contract_id": "benchmark-grading-isolation-backend-v1",
        "backend_id": "ubuntu-bubblewrap-0.11.1-constrained-v1",
        "executable_path": "/usr/bin/bwrap",
        "version": "bubblewrap 0.11.1",
        "package_version": "0.11.1-1ubuntu0.3",
        "executable_sha256": "523da3e7399044be5163aee6f57a77a6bef7454376e28f0a0627920bae1b76b6",
        "apparmor_profile_path": "/etc/apparmor.d/bwrap-userns-restrict",
        "apparmor_profile_sha256": "d61facde27707b9c47ffe47921b7273e788784484cb5530eb819e6daac1f1990",
        "apparmor_restrict_unprivileged_userns": 1,
        "setuid_allowed": False,
        "known_upstream_issue": {
            "id": "CVE-2026-87766",
            "affected": True,
            "fixed_upstream_in": "0.12.0",
            "compensating_control": "untrusted-bind-last-no-followup-filesystem-ops",
            "untrusted_destination": "/work",
            "untrusted_root_bind_allowed": False,
            "filesystem_ops_after_untrusted_bind_allowed": False,
        },
        "required_evidence": [
            "exact-binary-sha256",
            "exact-package-version",
            "exact-apparmor-profile-sha256",
            "apparmor-userns-restriction-enabled",
            "non-setuid-backend",
            "unsafe-cve-control-escapes-synthetic-host-target",
            "constrained-cve-control-does-not-escape",
            "constrained-mount-plan-static-guard",
        ],
        "accepted_evidence_sha256": ["af25f5138a442a8ea1e52f09c81458a16f57e756f6502af8b49fc1be1b93dbec"],
        "authorization_overrides_security": False,
    }


def load_contract(path=CONTRACT):
    actual = json.loads(Path(path).read_text())
    if json.dumps(actual, sort_keys=True) != json.dumps(expected_contract(), sort_keys=True):
        raise ValueError("unreviewed grading backend contract")
    return actual




def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def runtime_preflight(executable=Path('/usr/bin/bwrap')):
    contract = load_contract()
    executable = Path(executable)
    if executable != Path(contract['executable_path']) or not executable.is_file():
        raise ValueError('exact grading backend path required')
    if executable.stat().st_mode & (stat.S_ISUID | stat.S_ISGID):
        raise ValueError('privileged grading backend rejected')
    if _sha256(executable) != contract['executable_sha256']:
        raise ValueError('grading backend executable mismatch')
    try:
        version = subprocess.run(
            [str(executable), '--version'], env={'PATH': '/usr/bin:/bin'},
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5, check=False)
        package = subprocess.run(
            ['/usr/bin/dpkg-query', '-W', '-f=' + '$' + '{Version}', 'bubblewrap'],
            env={'PATH': '/usr/bin:/bin'}, stdin=subprocess.DEVNULL, capture_output=True,
            text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('grading backend identity unavailable') from None
    if version.returncode != 0 or version.stdout.strip() != contract['version']:
        raise ValueError('grading backend version mismatch')
    if package.returncode != 0 or package.stdout.strip() != contract['package_version']:
        raise ValueError('grading backend package mismatch')
    profile = Path(contract['apparmor_profile_path'])
    if not profile.is_file() or _sha256(profile) != contract['apparmor_profile_sha256']:
        raise ValueError('grading backend AppArmor profile mismatch')
    sysctl = Path('/proc/sys/kernel/apparmor_restrict_unprivileged_userns')
    try:
        value = sysctl.read_text().strip()
    except OSError:
        raise ValueError('AppArmor userns restriction unavailable') from None
    if value != str(contract['apparmor_restrict_unprivileged_userns']):
        raise ValueError('AppArmor userns restriction mismatch')
    return contract

def _absolute_destination(value):
    if type(value) is not str or not value.startswith("/"):
        return False
    path = PurePosixPath(value)
    return ".." not in path.parts and "." not in path.parts


def validate_mount_plan(ops):
    """Reject any CVE-2026-87766-reachable mount topology.

    Untrusted content must be exactly one bind at /work, cannot become the root,
    and must be the final filesystem operation. All destination paths are fixed
    absolute normalized paths.
    """
    contract = load_contract()
    if type(ops) not in (tuple, list) or not ops:
        raise ValueError("empty grading mount plan")
    if any(type(op) is not MountOp for op in ops):
        raise ValueError("untyped grading mount operation")

    untrusted = [index for index, op in enumerate(ops) if op.trust == "untrusted"]
    if untrusted != [len(ops) - 1]:
        raise ValueError("untrusted bind must be the final filesystem operation")

    for index, op in enumerate(ops):
        if op.option not in {"--bind", "--ro-bind", "--symlink", "--proc", "--dev", "--tmpfs", "--dir"}:
            raise ValueError("unreviewed grading mount operation")
        if not _absolute_destination(op.destination):
            raise ValueError("unsafe grading mount destination")
        if op.option in {"--bind", "--ro-bind", "--symlink"} and (
            type(op.source) is not str or not op.source
        ):
            raise ValueError("grading mount source required")
        if op.size_bytes is not None and (
            op.option != "--tmpfs" or type(op.size_bytes) is not int or op.size_bytes <= 0
        ):
            raise ValueError("invalid grading tmpfs size")
        if op.trust == "untrusted":
            if op.option != "--bind":
                raise ValueError("untrusted source must use writable bind")
            if op.destination != contract["known_upstream_issue"]["untrusted_destination"]:
                raise ValueError("untrusted destination drift")
            if op.destination == "/":
                raise ValueError("untrusted root bind forbidden")
        elif op.trust != "trusted":
            raise ValueError("unknown mount trust class")
        if index > untrusted[0]:
            raise ValueError("filesystem operation after untrusted bind")

    return True


def probe_mount_plan(probe_source, workspace):
    ops = (
        MountOp("--ro-bind", "/usr", "/usr"),
        MountOp("--symlink", "/lib", "usr/lib"),
        MountOp("--symlink", "/lib64", "usr/lib64"),
        MountOp("--proc", "/proc"),
        MountOp("--dev", "/dev"),
        MountOp("--tmpfs", "/tmp", size_bytes=16777216),
        MountOp("--dir", "/empty-home"),
        MountOp("--ro-bind", "/probe.py", str(probe_source)),
        MountOp("--bind", "/work", str(workspace), "untrusted"),
    )
    validate_mount_plan(ops)
    return ops


def render_mount_plan(ops):
    validate_mount_plan(ops)
    argv = []
    for op in ops:
        if op.option in {"--bind", "--ro-bind", "--symlink"}:
            argv.extend([op.option, op.source, op.destination])
        else:
            if op.option == "--tmpfs" and op.size_bytes is not None:
                argv.extend(["--size", str(op.size_bytes)])
            argv.extend([op.option, op.destination])
    return argv


def evidence_reference(payload):
    allowed = {
        "backend_id",
        "executable_sha256",
        "package_version",
        "apparmor_profile_sha256",
        "apparmor_userns_restriction_enabled",
        "setuid_present",
        "unsafe_control_host_escape_observed",
        "constrained_control_host_escape_observed",
        "constrained_control_completed",
        "mount_plan_static_guard",
    }
    if type(payload) is not dict or set(payload) != allowed:
        raise ValueError("invalid grading backend evidence")
    contract = load_contract()
    if (
        payload["backend_id"] != contract["backend_id"]
        or payload["executable_sha256"] != contract["executable_sha256"]
        or payload["package_version"] != contract["package_version"]
        or payload["apparmor_profile_sha256"] != contract["apparmor_profile_sha256"]
    ):
        raise ValueError("grading backend evidence identity mismatch")
    for key in (
        "apparmor_userns_restriction_enabled",
        "setuid_present",
        "unsafe_control_host_escape_observed",
        "constrained_control_host_escape_observed",
        "constrained_control_completed",
        "mount_plan_static_guard",
    ):
        if type(payload[key]) is not bool:
            raise ValueError("grading backend evidence must use typed booleans")
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(normalized).hexdigest()


def load_candidate_evidence(path=CANDIDATE_EVIDENCE):
    record = json.loads(Path(path).read_text())
    required = {
        "schema_version",
        "contract_id",
        "probe_kind",
        "backend_id",
        "version",
        "candidate",
        "evidence_reference",
        "model_calls",
    }
    if type(record) is not dict or set(record) != required:
        raise ValueError("invalid grading backend candidate evidence")
    contract = load_contract()
    if (
        record["schema_version"] != 1
        or record["contract_id"] != contract["contract_id"]
        or record["probe_kind"] != "synthetic-cve-topology"
        or record["backend_id"] != contract["backend_id"]
        or record["version"] != contract["version"]
        or record["model_calls"] != 0
    ):
        raise ValueError("grading backend candidate identity mismatch")
    candidate = record["candidate"]
    if evidence_reference(candidate) != record["evidence_reference"]:
        raise ValueError("grading backend evidence reference mismatch")
    required_values = {
        "apparmor_userns_restriction_enabled": True,
        "setuid_present": False,
        "unsafe_control_host_escape_observed": True,
        "constrained_control_host_escape_observed": False,
        "constrained_control_completed": True,
        "mount_plan_static_guard": True,
    }
    if any(candidate[key] is not value for key, value in required_values.items()):
        raise ValueError("grading backend candidate failed required security evidence")
    return record


def representative_contract_verified(qualification):
    import benchmark_host as host

    contract = load_contract()
    candidate = load_candidate_evidence()
    if type(qualification) is not host.QualifiedHostContract or qualification.status != "verified":
        return False
    component = next(
        (row for row in qualification.evidence.components if row.component == COMPONENT),
        None,
    )
    return (
        component is not None
        and component.state == "verified"
        and component.evidence_sha256 == candidate["evidence_reference"]
        and component.evidence_sha256 in contract["accepted_evidence_sha256"]
    )
