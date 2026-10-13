"""Production representative-submission grading candidate.

This module owns the only candidate path that may execute an untrusted representative
submission. Public representative grading remains fail-closed until a separately
reviewed production-grading evidence reference is admitted by the contract.

The accepted Ubuntu Bubblewrap backend is used only with its reviewed constrained
mount topology: trusted mounts first, exactly one writable untrusted bind at /work,
and no filesystem operation after that bind.
"""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

import benchmark_grading_backend as grading_backend
import benchmark_host as host

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "benchmarks/submission-grading-v1.json"
CANDIDATE_EVIDENCE = ROOT / "benchmarks/submission-grading-candidate-v1.json"
PROBE = Path(__file__).with_name("benchmark_submission_grading_probe.py")

RUNTIME_REPOSITORY_HEAD = "dc2befe8d143d670c7a0ac47c5c3141a964c0a7c"
RUNTIME_FILES_MANIFEST_SHA256 = "50c3b03c2bf1ae30ecb6d910c8e6d5b422d8bf839597f1de6dce55b355ab82df"
RUNTIME_SYMLINKS_MANIFEST_SHA256 = "e6831ba698554b772a1b7627833ad518cf43fe6eba451ddbdb02419d8fd1102d"
RUNTIME_DIRS_MANIFEST_SHA256 = "663c3335fe7586f5372615c65d71b88f098b5673990a65a6659809eaef83c78d"
RUNTIME_FILE_COUNT = 26885
RUNTIME_SYMLINK_COUNT = 495
RUNTIME_DIR_COUNT = 2469
QUALIFIED_HOST_RECEIPT = "d2af64ce237de72c9c0ee2659723e2d2858c9e19982cc85dd4420a6c6592d265"
GRADING_BACKEND_REFERENCE = "af25f5138a442a8ea1e52f09c81458a16f57e756f6502af8b49fc1be1b93dbec"

MEMORY_MAX = "3G"
MEMORY_SWAP_MAX = "0"
TASKS_MAX = 256
RUNTIME_MAX_SECONDS = 120

ENTRYPOINT_SOURCE = r'''import json
from pathlib import Path
import stat
import sys

sys.path.insert(0, "/runtime/grader/repo/scripts")
sys.path.insert(0, "/runtime/grader/repo/benchmarks")

import benchmark_coverage as coverage
import representative_graders as graders


def safe_relative(value):
    path = Path(value)
    return (not path.is_absolute() and ".." not in path.parts and "." not in path.parts
            and str(path) not in {"", "."})


def regular_tree(root):
    files = set()
    dirs = set()
    for item in root.rglob("*"):
        rel = item.relative_to(root).as_posix()
        mode = item.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ValueError("unsafe submission node")
        if stat.S_ISREG(mode) and item.stat().st_nlink != 1:
            raise ValueError("hardlinked submission file rejected")
        (dirs if stat.S_ISDIR(mode) else files).add(rel)
    return files, dirs


def enforce_policy(fixture, workspace, immutable, allowed):
    files, dirs = regular_tree(workspace)
    if not immutable:
        return
    expected = set(fixture["files"])
    allowed = set(allowed)
    if any(not safe_relative(name) for name in allowed):
        raise ValueError("unsafe answer artifact")
    expected_all = expected | allowed
    expected_dirs = {
        parent.as_posix()
        for name in expected_all
        for parent in Path(name).parents
        if parent != Path(".")
    }
    if files != expected_all or not dirs <= expected_dirs:
        raise ValueError("submission policy mismatch")
    for name, content in fixture["files"].items():
        path = workspace / name
        if not path.is_file() or path.read_text() != content:
            raise ValueError("immutable task file changed")


scenario_id = sys.argv[1]
immutable = sys.argv[2] == "1"
allowed = json.loads(sys.argv[3])
manifest = coverage.load_manifest()
scenario = next((row for row in manifest["scenarios"] if row["id"] == scenario_id), None)
if scenario is None:
    raise SystemExit(64)
fixture = coverage.fixture(scenario)
workspace = Path("/work")
try:
    enforce_policy(fixture, workspace, immutable, allowed)
    quality = bool(graders.check(scenario, fixture, workspace))
except (OSError, ValueError, TypeError):
    print(json.dumps({"schema_version": 1, "quality_pass": False, "policy_or_grader_refusal": True},
                     sort_keys=True))
    raise SystemExit(0)
print(json.dumps({"schema_version": 1, "quality_pass": quality,
                  "policy_or_grader_refusal": False}, sort_keys=True))
'''


@dataclass(frozen=True)
class PreparedRuntime:
    root: Path
    inventory_reference: str


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
            "clear_environment": True,
            "network_namespace": True,
            "cap_drop_all": True,
        },
        "entrypoint_sha256": hashlib.sha256(ENTRYPOINT_SOURCE.encode()).hexdigest(),
        "required_evidence": [
            "runtime-full-inventory-rehash",
            "all-reference-controls-pass",
            "all-wrong-controls-rejected",
            "symlink-and-special-node-rejected",
            "hardlink-rejected",
            "host-filesystem-write-blocked",
            "credential-and-environment-isolation",
            "network-isolation",
            "descendant-cleanup",
            "resource-limit-launch-shape",
        ],
        "accepted_evidence_sha256": [],
        "authorization_overrides_security": False,
    }


def load_contract(path=CONTRACT):
    actual = json.loads(Path(path).read_text())
    if json.dumps(actual, sort_keys=True) != json.dumps(expected_contract(), sort_keys=True):
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

    root = Path(runtime_root)
    inventory = Path(inventory_dir)
    if (not root.is_absolute() or root.is_symlink() or not root.is_dir()
            or not root.name.startswith("benchmark-runtime-")):
        raise ValueError("unreviewed runtime staging root")
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
        st = p.stat()
        if st.st_size != size or stat.S_IMODE(st.st_mode) != mode or _sha256(p) != digest:
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
    if (not head.is_file() or head.read_text().strip() != contract["runtime_repository_head"]):
        raise ValueError("runtime grader repository identity mismatch")

    reference = hashlib.sha256(json.dumps({
        "files": expected["files_manifest_sha256"],
        "symlinks": expected["symlinks_manifest_sha256"],
        "dirs": expected["dirs_manifest_sha256"],
        "head": contract["runtime_repository_head"],
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return PreparedRuntime(root.resolve(), reference)


def _mount_plan(runtime, workspace, entrypoint):
    root = runtime.root
    ops = (
        grading_backend.MountOp("--ro-bind", "/runtime", str(root)),
        grading_backend.MountOp("--dir", "/lib"),
        grading_backend.MountOp("--ro-bind", "/lib/x86_64-linux-gnu",
                                str(root / "libraries/x86_64-linux-gnu")),
        grading_backend.MountOp("--dir", "/usr"),
        grading_backend.MountOp("--dir", "/usr/lib"),
        grading_backend.MountOp("--ro-bind", "/usr/lib/x86_64-linux-gnu",
                                str(root / "libraries/x86_64-linux-gnu")),
        grading_backend.MountOp("--dir", "/lib64"),
        grading_backend.MountOp("--ro-bind", "/lib64/ld-linux-x86-64.so.2",
                                str(root / "libraries/lib64/ld-linux-x86-64.so.2")),
        grading_backend.MountOp("--proc", "/proc"),
        grading_backend.MountOp("--dev", "/dev"),
        grading_backend.MountOp("--tmpfs", "/tmp", size_bytes=2147483648),
        grading_backend.MountOp("--dir", "/empty-home"),
        grading_backend.MountOp("--ro-bind", "/grader-entry.py", str(entrypoint)),
        grading_backend.MountOp("--bind", "/work", str(workspace), "untrusted"),
    )
    grading_backend.validate_mount_plan(ops)
    return ops


def _policy_values(policy):
    immutable = getattr(policy, "task_files_immutable", None)
    allowed = getattr(policy, "allowed_answer_artifacts", None)
    if type(immutable) is not bool or type(allowed) is not tuple:
        raise ValueError("invalid submission policy")
    if any(type(name) is not str or not _safe_rel(name) for name in allowed):
        raise ValueError("invalid answer artifact")
    return immutable, allowed


def _run_candidate(scenario, workspace, runtime, policy):
    load_contract()
    if type(runtime) is not PreparedRuntime:
        return CandidateGrade("blocked", "grading-runtime-not-prepared")
    workspace = Path(workspace)
    if (not workspace.is_absolute() or workspace.is_symlink() or not workspace.is_dir()):
        return CandidateGrade("blocked", "submission-workspace-rejected")
    if type(scenario) is not str or not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", scenario):
        return CandidateGrade("blocked", "scenario-rejected")
    try:
        immutable, allowed = _policy_values(policy)
    except ValueError:
        return CandidateGrade("blocked", "submission-policy-mismatch")
    try:
        grading_backend.runtime_preflight()
    except (OSError, ValueError):
        return CandidateGrade("blocked", "grading-backend-runtime-rejected")

    runtime_dir = Path("/run/user") / str(os.getuid())
    bus = runtime_dir / "bus"
    if not bus.exists():
        return CandidateGrade("unavailable", "user-systemd-manager-unavailable")

    with tempfile.TemporaryDirectory(prefix="submission-grader-") as tmp:
        entrypoint = Path(tmp) / "grader-entry.py"
        entrypoint.write_text(ENTRYPOINT_SOURCE)
        entrypoint.chmod(0o444)
        mounts = _mount_plan(runtime, workspace, entrypoint)
        bwrap = [
            "/usr/bin/bwrap",
            "--unshare-user", "--unshare-all", "--disable-userns", "--assert-userns-disabled",
            "--uid", str(os.getuid()), "--gid", str(os.getgid()),
            "--cap-drop", "ALL", "--die-with-parent", "--new-session", "--clearenv",
            *grading_backend.render_mount_plan(mounts),
            "--setenv", "HOME", "/empty-home",
            "--setenv", "CODEX_HOME", "/empty-home",
            "--setenv", "PATH",
            "/runtime/grader/bin:/runtime/linker/bin:/runtime/rust/bin:/runtime/go/bin:/runtime/python/bin",
            "--setenv", "COMPILER_PATH",
            "/runtime/linker/libexec/gcc/x86_64-linux-gnu/15:/runtime/linker/lib/gcc/x86_64-linux-gnu/15:/runtime/linker/bin",
            "--setenv", "LIBRARY_PATH",
            "/runtime/linker/lib/gcc/x86_64-linux-gnu/15:/lib/x86_64-linux-gnu:/usr/lib/x86_64-linux-gnu",
            "--setenv", "RUSTUP_TOOLCHAIN", "1.98.0",
            "--setenv", "LANG", "C",
            "--chdir", "/work",
            "--", "/runtime/python/bin/python3.14", "-B", "/grader-entry.py",
            scenario, "1" if immutable else "0", json.dumps(list(allowed), separators=(",", ":")),
        ]
        command = [
            "/usr/bin/systemd-run", "--user", "--wait", "--collect", "--pipe", "--quiet",
            "-p", f"MemoryMax={MEMORY_MAX}",
            "-p", f"MemorySwapMax={MEMORY_SWAP_MAX}",
            "-p", f"TasksMax={TASKS_MAX}",
            "-p", f"RuntimeMaxSec={RUNTIME_MAX_SECONDS}s",
            "-p", "KillMode=control-group",
            *bwrap,
        ]
        env = {
            "PATH": "/usr/bin",
            "XDG_RUNTIME_DIR": str(runtime_dir),
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(bus),
        }
        try:
            result = subprocess.run(command, env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=RUNTIME_MAX_SECONDS + 15,
                                    close_fds=True)
        except (OSError, subprocess.TimeoutExpired):
            return CandidateGrade("blocked", "grading-sandbox-launch-failed")
    if result.returncode != 0 or len(result.stdout) > 4096 or len(result.stderr) > 16384:
        return CandidateGrade("blocked", "grading-sandbox-failed")
    try:
        record = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return CandidateGrade("blocked", "grading-result-rejected")
    if (type(record) is not dict
            or set(record) != {"schema_version", "quality_pass", "policy_or_grader_refusal"}
            or record["schema_version"] != 1
            or type(record["quality_pass"]) is not bool
            or type(record["policy_or_grader_refusal"]) is not bool):
        return CandidateGrade("blocked", "grading-result-rejected")
    if record["policy_or_grader_refusal"]:
        return CandidateGrade("verified", "isolated-grader-refused-submission", False)
    return CandidateGrade("verified", "isolated-grader-completed", record["quality_pass"])


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
        "probe_sha256", "contract_sha256", "entrypoint_sha256",
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
        "symlink-rejected",
        "hardlink-rejected",
        "special-node-rejected",
        "exploration-task-immutability",
        "exploration-extra-artifact-rejected",
        "host-env-network-capability-isolation",
        "descendant-cleanup",
    ]
    if (candidate["qualified_host_receipt"] != contract["qualified_host_receipt"]
            or candidate["grading_backend_reference"] != contract["grading_backend_reference"]
            or candidate["runtime_repository_head"] != contract["runtime_repository_head"]
            or candidate["runtime_inventory_reference"] != expected_runtime_reference
            or candidate["runtime_full_rehash"] is not True
            or candidate["implementation_sha256"] != _sha256(Path(__file__))
            or candidate["probe_sha256"] != _sha256(PROBE)
            or candidate["contract_sha256"] != _sha256(CONTRACT)
            or candidate["entrypoint_sha256"] != contract["entrypoint_sha256"]
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
                "entrypoint_sha256", "correctness_controls_sha256",
                "security_controls_sha256", "runtime_inventory_reference"):
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
