"""Passive Autonomous Development Contract v1 metadata validator (#165).

Not an executor, authorization mechanism, source attestor or security sandbox.
Evidence and trusted profile IDs MUST come from an independently trusted caller;
this module neither obtains nor proves them. No shell, subprocess, network, or writes.
"""

from __future__ import annotations

from pathlib import Path
import re
import stat
import tomllib

MAX_BYTES = 16_384
SHA = re.compile(r"[0-9a-f]{40}\Z")
IDENTIFIER = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,38}[A-Za-z0-9])?/[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,98}[A-Za-z0-9])?\Z")
PROFILE = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
TYPES = {"rust-workspace", "python-stdlib", "python-project", "mixed"}
KEYS = {
    "top": {"schema_version", "project_id", "project_type", "repository", "context", "verification", "execution", "change_policy"},
    "context": {"entrypoint", "architecture", "workflow", "current_plan", "security", "task_source"},
    "verification": {"profiles", "ci_workflows", "live_device_proof"},
    "execution": {"enabled", "max_stage_seconds", "max_changed_files", "max_changed_lines", "checkpoint_mode", "auto_merge", "auto_deploy"},
    "change_policy": {"candidate_paths", "blocked_unattended_paths"},
}


class ContractRefused(ValueError):
    """Metadata cannot be accepted; never treat this as a runnable contract."""


def refuse(message: str) -> None:
    raise ContractRefused(message)


def exact_keys(value: object, required: set[str], label: str) -> dict:
    if type(value) is not dict or set(value) != required:
        refuse(f"{label}: missing or unknown fields")
    return value


def text(value: object, label: str, max_length: int = 160) -> str:
    if type(value) is not str or not value or len(value) > max_length or any(ord(c) < 32 or ord(c) == 127 for c in value):
        refuse(f"{label}: invalid text")
    return value


def positive_int(value: object, label: str, minimum: int, maximum: int) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        refuse(f"{label}: outside bounded integer range")


def string_array(value: object, label: str, maximum: int = 16) -> list[str]:
    if type(value) is not list or not 1 <= len(value) <= maximum:
        refuse(f"{label}: invalid nonempty array")
    values = [text(item, label) for item in value]
    if len(values) != len(set(values)):
        refuse(f"{label}: duplicate entries")
    return values


def relative_path(value: object, *, directory: bool = False) -> str:
    raw = text(value, "path", 200)
    name = raw[:-1] if directory and raw.endswith("/") else raw
    segments = name.split("/")
    if (not name or name.startswith("/") or "\\" in name or ":" in name or
            any(s in ("", ".", "..", ".git") for s in segments) or
            any(not re.fullmatch(r"[A-Za-z0-9_.-]+", s) for s in segments)):
        refuse("unsafe, noncanonical or traversal path")
    return name


def no_symlink_ancestry(path: Path) -> None:
    # lstat each present component, including dangling symlinks. Missing final
    # segments are permitted only for informational change-policy paths.
    for component in reversed((path, *path.parents)):
        try:
            mode = component.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            refuse("symlink in path ancestry")


def checked_file(root: Path, raw: object) -> str:
    name = relative_path(raw)
    target = root / name
    no_symlink_ancestry(target)
    try:
        metadata = target.lstat()
    except FileNotFoundError:
        refuse("required tracked-file pointer missing")
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        refuse("context/workflow target must be a regular single-link file")
    return name


def validate_contract(
    data: bytes, *, root: Path, expected_repository: str,
    expected_project_id: str, accepted_main_sha: str, checkout_sha: str,
    checkout_clean: bool, trusted_profile_ids: frozenset[str],
) -> dict:
    """Validate inert metadata under caller-supplied, independently verified facts.

    Returns parsed data, NOT authority or proof of runtime readiness. The caller
    must establish the actual Git remote/main, clean source/worktree, provenance
    and trusted profile mapping; input flags and strings are NOT attestations.
    """
    if type(data) is not bytes or not 0 < len(data) <= MAX_BYTES:
        refuse("missing or oversized TOML")
    if (not isinstance(root, Path) or not root.is_absolute() or
            ".." in root.parts or not root.is_dir()):
        refuse("canonical absolute project root required")
    no_symlink_ancestry(root)
    if (type(expected_repository) is not str or not REPOSITORY.fullmatch(expected_repository)
            or type(expected_project_id) is not str or not IDENTIFIER.fullmatch(expected_project_id)):
        refuse("invalid externally supplied identity")
    if (type(accepted_main_sha) is not str or not SHA.fullmatch(accepted_main_sha)
            or type(checkout_sha) is not str or not SHA.fullmatch(checkout_sha)
            or checkout_sha != accepted_main_sha or checkout_clean is not True):
        refuse("unverified, dirty or conflicting source snapshot")
    if type(trusted_profile_ids) is not frozenset or any(
        type(profile) is not str or not PROFILE.fullmatch(profile)
        for profile in trusted_profile_ids
    ):
        refuse("invalid independently trusted profile registry")
    try:
        doc = tomllib.loads(data.decode("utf-8"))
    except (UnicodeError, tomllib.TOMLDecodeError):
        refuse("invalid TOML")
    exact_keys(doc, KEYS["top"], "contract")
    if type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
        refuse("unsupported schema major version")
    if text(doc["project_id"], "project_id", 64) != expected_project_id:
        refuse("project identity mismatch")
    if text(doc["repository"], "repository") != expected_repository:
        refuse("repository origin mismatch")
    if not REPOSITORY.fullmatch(doc["repository"]):
        refuse("noncanonical repository identity")
    if type(doc["project_type"]) is not str or doc["project_type"] not in TYPES:
        refuse("unsupported project type")

    ctx = exact_keys(doc["context"], KEYS["context"], "context")
    if ctx["task_source"] != "github-issues":
        refuse("github issues must remain the live queue")
    ctx_files = [checked_file(root, ctx[key]) for key in
                 ("entrypoint", "architecture", "workflow", "current_plan", "security")]
    if len(set(ctx_files)) != len(ctx_files):
        refuse("ambiguous context paths")

    verify = exact_keys(doc["verification"], KEYS["verification"], "verification")
    profiles = string_array(verify["profiles"], "profiles")
    if any(not PROFILE.fullmatch(p) or p not in trusted_profile_ids for p in profiles):
        refuse("unknown verification profile; never execute a manifest value")
    if doc["project_type"] == "rust-workspace" and not {"rust-tests", "rust-ci"}.intersection(profiles):
        refuse("Rust contract lacks a trusted Rust test profile")
    if doc["project_type"] in ("python-stdlib", "python-project") and not {"python-tests", "python-unittest"}.intersection(profiles):
        refuse("Python contract lacks a trusted Python test profile")
    if doc["project_type"] == "mixed" and not (
        {"rust-tests", "rust-ci"}.intersection(profiles) and
        {"python-tests", "python-unittest"}.intersection(profiles)
    ):
        refuse("mixed project needs both native test profiles")
    ci_files = [checked_file(root, p) for p in string_array(verify["ci_workflows"], "ci_workflows")]
    if any(not p.startswith(".github/workflows/") or not p.endswith((".yml", ".yaml")) for p in ci_files):
        refuse("CI workflow must reference a tracked workflow YAML")
    if verify["live_device_proof"] not in ("separate", "not-applicable"):
        refuse("invalid live-device evidence declaration")

    execution = exact_keys(doc["execution"], KEYS["execution"], "execution")
    if any(execution[key] is not False for key in ("enabled", "auto_merge", "auto_deploy")):
        refuse("v1 metadata must remain disabled; no merge or deploy")
    positive_int(execution["max_stage_seconds"], "max_stage_seconds", 1, 3600)
    positive_int(execution["max_changed_files"], "max_changed_files", 1, 5)
    positive_int(execution["max_changed_lines"], "max_changed_lines", 1, 400)
    if execution["checkpoint_mode"] != "external-private":
        refuse("checkpoint must remain external and private")

    change = exact_keys(doc["change_policy"], KEYS["change_policy"], "change_policy")
    candidate = [relative_path(p, directory=True) for p in
                 string_array(change["candidate_paths"], "candidate_paths")]
    blocked = [relative_path(p, directory=True) for p in
               string_array(change["blocked_unattended_paths"], "blocked_unattended_paths")]
    if len(set(candidate)) != len(candidate) or len(set(blocked)) != len(blocked):
        refuse("duplicate normalized policy paths")
    for name in candidate + blocked:
        no_symlink_ancestry(root / name)
    for c in candidate:
        for b in blocked:
            if c == b or c.startswith(b + "/") or b.startswith(c + "/"):
                refuse("overlapping candidate and blocked path scopes")
    return doc
