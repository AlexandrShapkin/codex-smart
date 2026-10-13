"""Production representative-submission grading candidate.

The production path is deliberately separate from representative execution readiness:
candidate evidence can be generated and reviewed without enabling model execution.
Untrusted workspace bytes are mounted once, last, at /work. The sandbox-side trusted
controller copies only reviewed expected files through descriptor-relative no-follow
reads into private tmpfs before invoking the immutable grader.
"""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import struct
import subprocess
import tempfile
import time

import benchmark_grading_backend as grading_backend
import benchmark_host as host

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "benchmarks/submission-grading-v1.json"
CANDIDATE_EVIDENCE = ROOT / "benchmarks/submission-grading-candidate-v1.json"
PROBE = Path(__file__).with_name("benchmark_submission_grading_probe.py")
CONTROLLER = Path(__file__).with_name("benchmark_submission_grader.py")
SUPERVISOR = Path(__file__).with_name("benchmark_grading_supervisor.py")
BWRAP = Path("/usr/bin/bwrap")
SYSTEMD_RUN = Path("/usr/bin/systemd-run")
SYSTEMCTL = Path("/usr/bin/systemctl")

RUNTIME_REPOSITORY_HEAD = "dc2befe8d143d670c7a0ac47c5c3141a964c0a7c"
RUNTIME_FILES_MANIFEST_SHA256 = "50c3b03c2bf1ae30ecb6d910c8e6d5b422d8bf839597f1de6dce55b355ab82df"
RUNTIME_SYMLINKS_MANIFEST_SHA256 = "e6831ba698554b772a1b7627833ad518cf43fe6eba451ddbdb02419d8fd1102d"
RUNTIME_DIRS_MANIFEST_SHA256 = "663c3335fe7586f5372615c65d71b88f098b5673990a65a6659809eaef83c78d"
RUNTIME_FILE_COUNT = 26885
RUNTIME_SYMLINK_COUNT = 495
RUNTIME_DIR_COUNT = 2469
QUALIFIED_HOST_RECEIPT = "d2af64ce237de72c9c0ee2659723e2d2858c9e19982cc85dd4420a6c6592d265"
GRADING_BACKEND_REFERENCE = "af25f5138a442a8ea1e52f09c81458a16f57e756f6502af8b49fc1be1b93dbec"

CONTROLLER_SHA256 = "2d9212462ea84ca94491169d5b6d97649cd49a4e5494a17983c8ca62a3e8a652"
SUPERVISOR_SHA256 = "002224942d0f061718af15ac4dc562e9e1cd64931fe394b8c2ffd74bea8e57f8"

MEMORY_MAX = "3G"
MEMORY_SWAP_MAX = "0"
TASKS_MAX = 256
RUNTIME_MAX_SECONDS = 120


@dataclass(frozen=True)
class PreparedRuntime:
    root: Path
    inventory_reference: str
    root_identity: tuple[int, int]
    role_identities: tuple[tuple[str, int, int], ...]


@dataclass(frozen=True)
class CandidateGrade:
    status: str
    reason: str
    quality_pass: bool = False


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_rel(value):
    if type(value) is not str or not value or value.startswith("/"):
        return False
    path = Path(value)
    return ".." not in path.parts and "." not in path.parts


def expected_contract():
    return {
        "schema_version": 1,
        "contract_id": "benchmark-production-submission-grading-v1",
        "qualified_host_receipt": QUALIFIED_HOST_RECEIPT,
        "grading_backend_reference": GRADING_BACKEND_REFERENCE,
        "runtime_repository_head": RUNTIME_REPOSITORY_HEAD,
        "runtime_inventory": {
            "files_manifest_sha256": RUNTIME_FILES_MANIFEST_SHA256,
            "symlinks_manifest_sha256": RUNTIME_SYMLINKS_MANIFEST_SHA256,
            "dirs_manifest_sha256": RUNTIME_DIRS_MANIFEST_SHA256,
            "regular_file_count": RUNTIME_FILE_COUNT,
            "symlink_count": RUNTIME_SYMLINK_COUNT,
            "directory_count": RUNTIME_DIR_COUNT,
        },
        "trusted_controller_sha256": CONTROLLER_SHA256,
        "grading_supervisor_sha256": SUPERVISOR_SHA256,
        "resource_limits": {
            "memory_max": MEMORY_MAX,
            "memory_swap_max": MEMORY_SWAP_MAX,
            "tasks_max": TASKS_MAX,
            "runtime_max_seconds": RUNTIME_MAX_SECONDS,
            "kill_mode": "control-group",
        },
        "mount_policy": {
            "untrusted_destination": "/work",
            "untrusted_bind_count": 1,
            "untrusted_bind_last": True,
            "host_usr_mounted": False,
            "runtime_read_only": True,
            "trusted_controller_read_only": True,
            "verdict_channel": "private-unix-socket",
            "clear_environment": True,
            "network_namespace": True,
            "cap_drop_all": True,
        },
        "submission_copy_policy": {
            "descriptor_relative": True,
            "no_follow": True,
            "hardlinks_rejected": True,
            "special_nodes_rejected": True,
            "private_tmpfs_copy": True,
            "max_file_bytes": 8388608,
            "max_total_bytes": 33554432,
        },
        "required_evidence": [
            "runtime-full-inventory-rehash",
            "all-reference-controls-pass",
            "all-wrong-controls-rejected",
            "expected-file-symlink-rejected",
            "expected-file-hardlink-rejected",
            "expected-file-special-node-rejected",
            "exploration-immutability-and-extra-artifact-rejected",
            "trusted-runtime-read-only",
            "host-filesystem-write-blocked",
            "credential-and-environment-isolation",
            "network-isolation",
            "zero-effective-capabilities",
            "detached-descendant-cleanup",
            "forged-verdict-rejected",
            "resource-limit-launch-shape",
        ],
        "accepted_evidence_sha256": [],
        "authorization_overrides_security": False,
    }


def _review_contract_bytes():
    """Exact pre-acceptance contract bytes used by candidate qualification evidence."""
    return (json.dumps(expected_contract(), indent=2, sort_keys=True) + "\n").encode()


def load_contract(path=CONTRACT):
    actual = json.loads(Path(path).read_text())
    accepted = actual.get("accepted_evidence_sha256")
    if (type(accepted) is not list or len(accepted) > 1
            or any(type(value) is not str or not re.fullmatch("[0-9a-f]{64}", value)
                   for value in accepted)):
        raise ValueError("invalid production grading acceptance list")
    reviewed_shape = dict(actual)
    reviewed_shape["accepted_evidence_sha256"] = []
    if json.dumps(reviewed_shape, sort_keys=True) != json.dumps(expected_contract(), sort_keys=True):
        raise ValueError("unreviewed production grading contract")
    return actual


def _parse_file_manifest(path):
    rows = Path(path).read_text().splitlines()
    if not rows or rows[0] != "sha256\tsize\tmode\tpath":
        raise ValueError("runtime file manifest schema")
    result = {}
    for row in rows[1:]:
        digest, size, mode, rel = row.split("\t", 3)
        if (not re.fullmatch("[0-9a-f]{64}", digest) or not size.isdigit()
                or not re.fullmatch(r"0o[0-7]{3,4}", mode) or not _safe_rel(rel)
                or rel in result):
            raise ValueError("runtime file manifest row")
        result[rel] = (digest, int(size), int(mode, 8))
    return result


def _parse_symlink_manifest(path):
    rows = Path(path).read_text().splitlines()
    if not rows or rows[0] != "mode\tpath\ttarget":
        raise ValueError("runtime symlink manifest schema")
    result = {}
    for row in rows[1:]:
        mode, rel, target = row.split("\t", 2)
        if (not re.fullmatch(r"0o[0-7]{3,4}", mode) or not _safe_rel(rel)
                or not target or rel in result):
            raise ValueError("runtime symlink manifest row")
        result[rel] = (int(mode, 8), target)
    return result


def _parse_dir_manifest(path):
    rows = Path(path).read_text().splitlines()
    if not rows or rows[0] != "mode\tpath":
        raise ValueError("runtime directory manifest schema")
    result = {}
    for row in rows[1:]:
        mode, rel = row.split("\t", 1)
        if (not re.fullmatch(r"0o[0-7]{3,4}", mode) or not _safe_rel(rel) or rel in result):
            raise ValueError("runtime directory manifest row")
        result[rel] = int(mode, 8)
    return result


def prepare_runtime(runtime_root, inventory_dir, qualification):
    contract = load_contract()
    if (type(qualification) is not host.QualifiedHostContract
            or qualification.status != "verified"
            or qualification.reference != contract["qualified_host_receipt"]
            or not grading_backend.representative_contract_verified(qualification)):
        raise ValueError("qualified host/backend required")
    grading_backend.runtime_preflight(BWRAP)

    root = Path(runtime_root)
    inventory = Path(inventory_dir)
    if (not root.is_absolute() or root.parent != Path("/tmp")
            or root.is_symlink() or not root.is_dir()
            or not root.name.startswith("benchmark-runtime-")):
        raise ValueError("unreviewed runtime staging root")

    roles = ("python", "rust", "go", "libraries", "linker", "grader")
    if {entry.name for entry in root.iterdir()} != set(roles):
        raise ValueError("runtime role set mismatch")
    role_identities = []
    for role in roles:
        source = root / role
        if source.is_symlink() or not source.is_dir() or source.resolve() != source.absolute():
            raise ValueError("runtime role rejected")
        info = source.stat()
        role_identities.append((role, info.st_dev, info.st_ino))

    manifest_paths = {
        "files": inventory / "runtime-files.tsv",
        "symlinks": inventory / "runtime-symlinks.tsv",
        "dirs": inventory / "runtime-dirs.tsv",
    }
    expected = contract["runtime_inventory"]
    if (_sha256(manifest_paths["files"]) != expected["files_manifest_sha256"]
            or _sha256(manifest_paths["symlinks"]) != expected["symlinks_manifest_sha256"]
            or _sha256(manifest_paths["dirs"]) != expected["dirs_manifest_sha256"]):
        raise ValueError("runtime inventory manifest mismatch")

    files = _parse_file_manifest(manifest_paths["files"])
    links = _parse_symlink_manifest(manifest_paths["symlinks"])
    dirs = _parse_dir_manifest(manifest_paths["dirs"])
    if (len(files) != expected["regular_file_count"]
            or len(links) != expected["symlink_count"]
            or len(dirs) != expected["directory_count"]):
        raise ValueError("runtime inventory count mismatch")

    seen_files, seen_links, seen_dirs = set(), set(), set()
    for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        if current_path != root:
            rel = current_path.relative_to(root).as_posix()
            if current_path.is_symlink():
                raise ValueError("runtime walk followed symlink")
            seen_dirs.add(rel)
        for name in list(dirnames):
            p = current_path / name
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                seen_links.add(rel)
                dirnames.remove(name)
        for name in filenames:
            p = current_path / name
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                seen_links.add(rel)
            elif p.is_file():
                seen_files.add(rel)
            else:
                raise ValueError("runtime special node rejected")
    if seen_files != set(files) or seen_links != set(links) or seen_dirs != set(dirs):
        raise ValueError("runtime inventory topology mismatch")

    for rel, (digest, size, mode) in files.items():
        p = root / rel
        info = p.stat()
        if info.st_size != size or stat.S_IMODE(info.st_mode) != mode or _sha256(p) != digest:
            raise ValueError("runtime file mismatch")
    for rel, (mode, target) in links.items():
        p = root / rel
        if stat.S_IMODE(p.lstat().st_mode) != mode or os.readlink(p) != target:
            raise ValueError("runtime symlink mismatch")
    for rel, mode in dirs.items():
        p = root / rel
        if stat.S_IMODE(p.stat().st_mode) != mode:
            raise ValueError("runtime directory mismatch")

    head = root / "grader/repository-head.txt"
    if not head.is_file() or head.read_text().strip() != contract["runtime_repository_head"]:
        raise ValueError("runtime grader repository identity mismatch")
    if _sha256(CONTROLLER) != contract["trusted_controller_sha256"]:
        raise ValueError("trusted controller identity mismatch")
    if _sha256(SUPERVISOR) != contract["grading_supervisor_sha256"]:
        raise ValueError("grading supervisor identity mismatch")

    reference = hashlib.sha256(json.dumps({
        "files": expected["files_manifest_sha256"],
        "symlinks": expected["symlinks_manifest_sha256"],
        "dirs": expected["dirs_manifest_sha256"],
        "head": contract["runtime_repository_head"],
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    root_info = root.stat()
    return PreparedRuntime(
        root.resolve(),
        reference,
        (root_info.st_dev, root_info.st_ino),
        tuple(role_identities),
    )


def _runtime_identity_matches(runtime):
    try:
        info = runtime.root.stat()
        if runtime.root.is_symlink() or (info.st_dev, info.st_ino) != runtime.root_identity:
            return False
        for role, device, inode in runtime.role_identities:
            path = runtime.root / role
            current = path.stat()
            if path.is_symlink() or (current.st_dev, current.st_ino) != (device, inode):
                return False
    except OSError:
        return False
    return True


def _policy_values(policy):
    immutable = getattr(policy, "task_files_immutable", None)
    allowed = getattr(policy, "allowed_answer_artifacts", None)
    if type(immutable) is not bool or type(allowed) is not tuple:
        raise ValueError("invalid submission policy")
    if any(type(name) is not str or not _safe_rel(name) for name in allowed):
        raise ValueError("invalid answer artifact")
    return immutable, allowed


def _user_manager_env():
    runtime = Path("/run/user") / str(os.getuid())
    return {
        "PATH": "/usr/bin:/bin",
        "XDG_RUNTIME_DIR": str(runtime),
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(runtime / "bus"),
    }


def _unit_state(unit):
    try:
        result = subprocess.run(
            [str(SYSTEMCTL), "--user", "show", unit, "--property=ActiveState", "--value"],
            env=_user_manager_env(), stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=3, check=False, close_fds=True)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _unit_control_group(unit):
    try:
        result = subprocess.run(
            [str(SYSTEMCTL), "--user", "show", unit, "--property=ControlGroup", "--value"],
            env=_user_manager_env(), stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=3, check=False, close_fds=True)
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip() if result.returncode == 0 else ""
    if not value.startswith("/") or ".." in Path(value).parts:
        return None
    return value


def _cgroup_empty(control_group):
    if control_group is None:
        return None
    path = Path("/sys/fs/cgroup") / control_group.lstrip("/")
    try:
        return not (path / "cgroup.procs").read_text().strip()
    except FileNotFoundError:
        return True
    except OSError:
        return None


def _stop_unit(unit, control_group=None):
    if control_group is None:
        control_group = _unit_control_group(unit)
    state = _unit_state(unit)
    if state not in {None, "inactive", "failed"}:
        try:
            result = subprocess.run(
                [str(SYSTEMCTL), "--user", "stop", unit],
                env=_user_manager_env(), stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=8, check=False, close_fds=True)
        except (OSError, subprocess.TimeoutExpired):
            return False
        if result.returncode != 0 and _unit_state(unit) not in {None, "inactive", "failed"}:
            return False
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        empty = _cgroup_empty(control_group)
        state = _unit_state(unit)
        if empty is True and state in {None, "inactive", "failed"}:
            return True
        if control_group is None and state in {None, "inactive", "failed"}:
            return True
        time.sleep(0.05)
    return False


def _execute_isolated_grade(scenario, workspace, runtime):
    unit = f"codex-smart-grade-{os.getpid()}-{secrets.token_hex(6)}.service"
    with tempfile.TemporaryDirectory(prefix="codex-smart-grade-channel-", dir="/tmp") as tmp:
        socket_path = Path(tmp) / "verdict.sock"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(socket_path))
            os.chmod(socket_path, 0o600)
            listener.listen(1)
            listener.settimeout(0.1)

            mounts = grading_backend.production_mount_plan(
                runtime.root, CONTROLLER, socket_path, workspace)
            sandbox = [
                str(BWRAP), "--unshare-user", "--unshare-all", "--disable-userns",
                "--assert-userns-disabled", "--uid", str(os.getuid()), "--gid", str(os.getgid()),
                "--cap-drop", "ALL", "--die-with-parent", "--new-session", "--clearenv",
                *grading_backend.render_mount_plan(mounts),
                "--setenv", "HOME", "/empty-home",
                "--setenv", "CODEX_HOME", "/empty-home",
                "--setenv", "PATH",
                "/trusted/bin:/runtime/linker/bin:/runtime/rust/bin:/runtime/go/bin:/runtime/python/bin",
                "--setenv", "RUSTUP_TOOLCHAIN", "1.98.0",
                "--setenv", "LANG", "C",
                "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
                "--chdir", "/work",
                "--", "/runtime/python/bin/python3.14", "-B", "/controller.py", scenario,
            ]
            command = [
                str(SYSTEMD_RUN), "--user", "--unit=" + unit, "--collect", "--quiet",
                f"--property=MemoryMax={MEMORY_MAX}",
                f"--property=MemorySwapMax={MEMORY_SWAP_MAX}",
                f"--property=TasksMax={TASKS_MAX}",
                f"--property=RuntimeMaxSec={RUNTIME_MAX_SECONDS}s",
                "--property=KillMode=control-group",
                "--", "/usr/bin/python3", "-B", str(SUPERVISOR), "--", *sandbox,
            ]
            try:
                launched = subprocess.run(
                    command, env=_user_manager_env(), stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=8, check=False, close_fds=True)
            except (OSError, subprocess.TimeoutExpired):
                _stop_unit(unit)
                return CandidateGrade("blocked", "grading-launch-failed")
            if launched.returncode != 0:
                _stop_unit(unit)
                return CandidateGrade("blocked", "grading-launch-failed")
            control_group = _unit_control_group(unit)

            connection = None
            deadline = time.monotonic() + 8
            try:
                while time.monotonic() < deadline:
                    try:
                        connection, _ = listener.accept()
                        break
                    except socket.timeout:
                        if _unit_state(unit) in {None, "failed", "inactive"}:
                            break
                if connection is None:
                    _stop_unit(unit, control_group)
                    return CandidateGrade("blocked", "grading-service-failed")

                with connection:
                    credentials = connection.getsockopt(
                        socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
                    _pid, uid, _gid = struct.unpack("3i", credentials)
                    if uid != os.getuid():
                        _stop_unit(unit, control_group)
                        return CandidateGrade("blocked", "grading-channel-peer-rejected")
                    verdict_deadline = time.monotonic() + RUNTIME_MAX_SECONDS + 5
                    connection.settimeout(0.2)
                    data = bytearray()
                    while time.monotonic() < verdict_deadline:
                        try:
                            chunk = connection.recv(4097 - len(data))
                        except socket.timeout:
                            if _unit_state(unit) in {None, "failed", "inactive"}:
                                break
                            continue
                        if not chunk:
                            break
                        data.extend(chunk)
                        if len(data) > 4096 or b"\n" in data:
                            break
                    raw = bytes(data)
            except KeyboardInterrupt:
                _stop_unit(unit, control_group)
                raise
            except OSError:
                _stop_unit(unit, control_group)
                return CandidateGrade("blocked", "grading-channel-failed")

        if not _stop_unit(unit, control_group):
            return CandidateGrade("blocked", "grading-cleanup-failed")
        if not raw or b"\n" not in raw:
            return CandidateGrade("blocked", "grading-service-failed")
        if len(raw) > 4096:
            return CandidateGrade("blocked", "grading-result-invalid")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return CandidateGrade("blocked", "grading-result-invalid")
        lines = [line for line in text.splitlines() if line.strip()]
        if len(lines) != 1:
            return CandidateGrade("blocked", "grading-result-invalid")
        try:
            payload = json.loads(lines[0])
        except (json.JSONDecodeError, TypeError):
            return CandidateGrade("blocked", "grading-result-invalid")
        required = {"status", "quality_pass"}
        if type(payload) is not dict or set(payload) not in (required, required | {"reason"}):
            return CandidateGrade("blocked", "grading-result-invalid")
        if payload.get("status") == "blocked":
            return CandidateGrade("blocked", "trusted-grader-failure")
        if payload.get("status") != "verified" or type(payload.get("quality_pass")) is not bool:
            return CandidateGrade("blocked", "grading-result-invalid")
        reason = payload.get("reason", "isolated-grading-complete")
        return CandidateGrade("verified", reason, payload["quality_pass"])


def _run_candidate(scenario, workspace, runtime, policy):
    contract = load_contract()
    if type(runtime) is not PreparedRuntime:
        return CandidateGrade("blocked", "grading-runtime-not-prepared")
    if not _runtime_identity_matches(runtime):
        return CandidateGrade("blocked", "grading-runtime-identity-drift")
    workspace = Path(workspace)
    if not workspace.is_absolute() or workspace.is_symlink() or not workspace.is_dir():
        return CandidateGrade("blocked", "submission-workspace-rejected")
    if type(scenario) is not str or not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", scenario):
        return CandidateGrade("blocked", "scenario-rejected")
    try:
        immutable, allowed = _policy_values(policy)
    except ValueError:
        return CandidateGrade("blocked", "submission-policy-mismatch")
    expected = (True, ("answer.json",)) if scenario == "explore-notification" else (False, ())
    if (immutable, allowed) != expected:
        return CandidateGrade("blocked", "submission-policy-mismatch")
    try:
        grading_backend.runtime_preflight(BWRAP)
        if _sha256(CONTROLLER) != contract["trusted_controller_sha256"]:
            raise ValueError
        if _sha256(SUPERVISOR) != contract["grading_supervisor_sha256"]:
            raise ValueError
    except (OSError, ValueError):
        return CandidateGrade("blocked", "grading-runtime-identity-drift")
    bus = Path("/run/user") / str(os.getuid()) / "bus"
    if not bus.exists():
        return CandidateGrade("unavailable", "user-systemd-manager-unavailable")
    try:
        return _execute_isolated_grade(scenario, workspace, runtime)
    except ValueError:
        return CandidateGrade("blocked", "grading-mount-plan-rejected")


def evidence_reference(payload):
    if type(payload) is not dict:
        raise ValueError("invalid production grading evidence")
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(normalized).hexdigest()


def load_candidate_evidence(path=CANDIDATE_EVIDENCE):
    record = json.loads(Path(path).read_text())
    if (type(record) is not dict or set(record) != {
            "schema_version", "contract_id", "probe_kind", "candidate",
            "evidence_reference", "model_calls", "real_credentials_used"}):
        raise ValueError("invalid production grading candidate evidence")
    contract = load_contract()
    if (record["schema_version"] != 1
            or record["contract_id"] != contract["contract_id"]
            or record["probe_kind"] != "bounded-production-submission-grading"
            or record["model_calls"] != 0
            or record["real_credentials_used"] is not False):
        raise ValueError("production grading candidate identity mismatch")
    candidate = record["candidate"]
    required = {
        "qualified_host_receipt", "grading_backend_reference", "runtime_repository_head",
        "runtime_inventory_reference", "runtime_full_rehash", "implementation_sha256",
        "probe_sha256", "contract_sha256", "controller_sha256", "supervisor_sha256",
        "correctness_controls_sha256", "security_controls_sha256",
        "references_passed", "wrong_controls_rejected", "security_controls_passed",
        "resource_limit_launch_shape", "model_calls", "real_credentials_used",
    }
    if type(candidate) is not dict or set(candidate) != required:
        raise ValueError("invalid production grading candidate payload")
    expected_runtime_reference = hashlib.sha256(json.dumps({
        "files": contract["runtime_inventory"]["files_manifest_sha256"],
        "symlinks": contract["runtime_inventory"]["symlinks_manifest_sha256"],
        "dirs": contract["runtime_inventory"]["dirs_manifest_sha256"],
        "head": contract["runtime_repository_head"],
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    expected_security = [
        "expected-file-symlink-rejected",
        "expected-file-hardlink-rejected",
        "expected-file-special-node-rejected",
        "exploration-task-immutability",
        "exploration-extra-artifact-rejected",
        "host-env-network-capability-isolation",
        "trusted-runtime-readonly",
        "detached-descendant-cleanup",
        "forged-verdict-rejected",
    ]
    if (candidate["qualified_host_receipt"] != contract["qualified_host_receipt"]
            or candidate["grading_backend_reference"] != contract["grading_backend_reference"]
            or candidate["runtime_repository_head"] != contract["runtime_repository_head"]
            or candidate["runtime_inventory_reference"] != expected_runtime_reference
            or candidate["runtime_full_rehash"] is not True
            or candidate["implementation_sha256"] != _sha256(Path(__file__))
            or candidate["probe_sha256"] != _sha256(PROBE)
            or candidate["contract_sha256"] != hashlib.sha256(_review_contract_bytes()).hexdigest()
            or candidate["controller_sha256"] != contract["trusted_controller_sha256"]
            or candidate["supervisor_sha256"] != contract["grading_supervisor_sha256"]
            or candidate["references_passed"] != 10
            or candidate["wrong_controls_rejected"] != 20
            or candidate["security_controls_passed"] != expected_security
            or candidate["resource_limit_launch_shape"] != {
                "memory_max": MEMORY_MAX, "memory_swap_max": MEMORY_SWAP_MAX,
                "tasks_max": TASKS_MAX, "runtime_max_seconds": RUNTIME_MAX_SECONDS,
                "kill_mode": "control-group"}
            or candidate["model_calls"] != 0
            or candidate["real_credentials_used"] is not False):
        raise ValueError("production grading candidate failed required evidence")
    for key in ("implementation_sha256", "probe_sha256", "contract_sha256",
                "controller_sha256", "supervisor_sha256",
                "correctness_controls_sha256", "security_controls_sha256",
                "runtime_inventory_reference"):
        if type(candidate[key]) is not str or not re.fullmatch("[0-9a-f]{64}", candidate[key]):
            raise ValueError("invalid production grading evidence digest")
    if evidence_reference(candidate) != record["evidence_reference"]:
        raise ValueError("production grading evidence reference mismatch")
    return record


def contract_verified(qualification):
    contract = load_contract()
    if (type(qualification) is not host.QualifiedHostContract
            or qualification.status != "verified"
            or qualification.reference != contract["qualified_host_receipt"]
            or not grading_backend.representative_contract_verified(qualification)):
        return False
    try:
        candidate = load_candidate_evidence()
    except (OSError, ValueError):
        return False
    return candidate["evidence_reference"] in contract["accepted_evidence_sha256"]


def grade_candidate_for_review(scenario, workspace, qualification, runtime, policy):
    if (type(qualification) is not host.QualifiedHostContract
            or qualification.status != "verified"
            or not grading_backend.representative_contract_verified(qualification)):
        return CandidateGrade("blocked", "qualified-host-not-verified")
    return _run_candidate(scenario, workspace, runtime, policy)


def grade_representative(scenario, workspace, qualification, runtime, policy):
    if not contract_verified(qualification):
        return CandidateGrade("blocked", "production-grading-evidence-not-accepted")
    return _run_candidate(scenario, workspace, runtime, policy)
