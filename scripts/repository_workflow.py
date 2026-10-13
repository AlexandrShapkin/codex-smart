"""Explicit Git isolation and source receipts; diagnostics never fetch or write."""
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path

CANONICAL = "https://github.com/AlexandrShapkin/codex-smart.git"
ORIGINS = {CANONICAL, CANONICAL.removesuffix(".git"),
           "git@github.com:AlexandrShapkin/codex-smart.git"}
RECEIPT = ".codex-smart-source.json"


def safe_path(value, exists=True):
    path = Path(value)
    if (not path.is_absolute() or ".." in path.parts or ".git" in path.parts or path == Path("/")
            or any(p.is_symlink() for p in [path, *path.parents]) or path.resolve() != path
            or (exists and not path.exists())):
        raise ValueError("Unsafe, missing or symlinked path")
    return path


def full_sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("Expected a full lowercase source SHA")
    return value


def git(root, *args, binary=False):
    # No shell, hooks, fsmonitor, optional index refresh, or inherited Git redirection.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
         "-c", "core.untrackedCache=false", "-c", "core.logAllRefUpdates=false",
         "-C", str(root), *args], env=env, capture_output=True, check=False)
    if result.returncode:
        # Git errors/remote configuration can contain credential-bearing URLs.
        raise ValueError("Git operation refused or failed; inspect repository state")
    return result.stdout if binary else result.stdout.decode("utf-8").strip()


def repository(root):
    root = safe_path(root)
    if not root.is_dir() or Path(git(root, "rev-parse", "--show-toplevel")) != root:
        raise ValueError("Expected the exact repository worktree root")
    return root


def validate_origin(root):
    urls = git(root, "config", "--get-all", "remote.origin.url").splitlines()
    if len(urls) != 1 or urls[0] not in ORIGINS:
        raise ValueError("Unexpected or ambiguous origin; no remote operation performed")


def network_git(root, *args):
    # URL rewriting can turn even a literal GitHub URL into a remote helper/host.
    keys = git(root, "config", "--list", "--name-only").lower().splitlines()
    if any(key.startswith("url.") or key.startswith("http.") for key in keys):
        raise ValueError("Network URL/HTTP overrides require manual inspection")
    return git(root, "-c", "credential.helper=", "-c", "http.sslVerify=true",
               "-c", "protocol.allow=never", "-c", "protocol.https.allow=always", *args)


def worktrees(root):
    entries = []
    for block in git(root, "worktree", "list", "--porcelain", "-z", binary=True).split(b"\0\0"):
        if not block:
            continue
        item = {}
        for field in block.split(b"\0"):
            if field:
                key, _, value = field.decode("utf-8").partition(" ")
                item[key] = value
        entries.append(item)
    return entries


def changes(root):
    return git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all",
               binary=True).decode("utf-8").split("\0")[:-1]


def checkout_state(root):
    """One reusable read-only observation; callers establish repository/origin trust."""
    return {"branch": git(root, "branch", "--show-current"),
            "head": git(root, "rev-parse", "HEAD"), "changes": changes(root)}


def inspect(root):
    root = repository(root)
    validate_origin(root)
    state = checkout_state(root)
    head = state["head"]
    try:
        main = git(root, "rev-parse", "--verify", "refs/remotes/origin/main^{commit}")
        counts = [int(n) for n in git(root, "rev-list", "--left-right", "--count",
                                    f"{head}...{main}").split()]
    except ValueError:
        main, counts = None, None
    return {"repository": str(root), **state, "origin": CANONICAL, "cached_main": main,
            "local_only_main_only": counts,
            "worktrees": worktrees(root), "remote_freshness": "unknown (offline)"}


def remote_main(root):
    lines = network_git(root, "ls-remote", "--exit-code", CANONICAL, "refs/heads/main").splitlines()
    if len(lines) != 1 or lines[0].split()[1:] != ["refs/heads/main"]:
        raise ValueError("Ambiguous GitHub main")
    return full_sha(lines[0].split()[0])


def fetch_main(root):
    network_git(root, "fetch", "--no-tags", "--no-recurse-submodules", CANONICAL,
                "refs/heads/main:refs/remotes/origin/main")


def new_destination(root, destination):
    path = safe_path(destination, exists=False)
    safe_path(path.parent)
    if not path.parent.is_dir() or path.exists():
        raise ValueError("Destination must be new with an existing parent")
    # Do not nest tasks/deployments in any registered checkout, even stale entries.
    for item in worktrees(root):
        tree = Path(item["worktree"])
        if path.is_relative_to(tree) or tree.is_relative_to(path):
            raise ValueError("Destination overlaps an existing worktree")
    return path


def start(root, branch, destination, expected):
    root = repository(root)
    validate_origin(root)
    expected = full_sha(expected)
    path = new_destination(root, destination)
    if not re.fullmatch(r"(?:feat|fix|docs|chore)/[a-z0-9][a-z0-9-]{0,79}", branch):
        raise ValueError("Use a new feat/fix/docs/chore task branch")
    refs = git(root, "for-each-ref", "--format=%(refname)", f"refs/heads/{branch}").splitlines()
    if refs:
        raise ValueError("Task branch already exists; inspect it instead of restarting")
    if remote_main(root) != expected:
        raise ValueError("GitHub main changed; inspect and select a new explicit SHA")
    fetch_main(root)
    if (git(root, "rev-parse", "refs/remotes/origin/main") != expected
            or remote_main(root) != expected):
        raise ValueError("GitHub main changed during fetch; no task worktree created")
    # Existing checkout can be dirty/diverged: none of its files/branch are changed.
    git(root, "worktree", "add", "-b", branch, str(path), expected)
    return inspect(path)


def verify(root, expected):
    root = repository(root)
    validate_origin(root)
    if git(root, "rev-parse", "HEAD") != full_sha(expected) or changes(root):
        raise ValueError("Source SHA mismatch or dirty checkout")
    return {"source_sha": expected, "clean": True, "remote_freshness": "unknown (offline)"}


def source_files(root, expected):
    root = repository(root)
    validate_origin(root)
    expected = full_sha(expected)
    if git(root, "rev-parse", "--verify", f"{expected}^{{commit}}") != expected:
        raise ValueError("Source is not the exact commit")
    git(root, "merge-base", "--is-ancestor", expected, "refs/remotes/origin/main")
    files = {}
    for entry in git(root, "ls-tree", "-rz", expected, binary=True).split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        name = name.decode("utf-8")
        parts = Path(name).parts
        if (mode not in {"100644", "100755"} or kind != "blob"
                or Path(name).is_absolute() or ".." in parts or ".git" in parts
                or RECEIPT in parts):
            raise ValueError("Unsafe source tree entry (including symlinks/submodules)")
        data = git(root, "cat-file", "blob", oid, binary=True)
        files[name] = (mode, data)
    if not files:
        raise ValueError("Empty source snapshot")
    return files


def receipt(expected, files):
    return {"schema": 1, "repository": CANONICAL, "source_sha": expected,
            "files": {name: {"sha256": hashlib.sha256(data).hexdigest(), "mode": mode}
                      for name, (mode, data) in sorted(files.items())}}


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def export(root, expected, destination):
    root = repository(root)
    path = new_destination(root, destination)
    files = source_files(root, expected)
    manifest = encode(receipt(expected, files))
    path.mkdir(mode=0o700)  # Exclusive; never overwrite even a partial prior export.
    path.chmod(0o700)
    directories = {parent for name in files for parent in Path(name).parents
                   if parent != Path(".")}
    for relative in sorted(directories, key=lambda p: (len(p.parts), str(p))):
        directory = path / relative
        directory.mkdir(mode=0o700)
        directory.chmod(0o700)
    for name, (mode, data) in files.items():
        target = path / name
        with target.open("xb") as stream:
            stream.write(data)
        target.chmod(0o755 if mode == "100755" else 0o644)
    # Completion receipt comes last. Interrupted directories are preserved/refused.
    with (path / RECEIPT).open("xb") as stream:
        stream.write(manifest)
    (path / RECEIPT).chmod(0o644)
    return {"snapshot": str(path), "source_sha": expected,
            "receipt_sha256": hashlib.sha256(manifest).hexdigest(), "files": len(files)}


def snapshot_directory(path):
    mode = path.stat().st_mode
    if not stat.S_ISDIR(mode) or mode & 0o022:
        raise ValueError("Unsafe snapshot directory permissions")


def verify_snapshot(snapshot, expected, trusted_receipt):
    path = safe_path(snapshot)
    snapshot_directory(path)
    expected = full_sha(expected)
    if not re.fullmatch(r"[0-9a-f]{64}", trusted_receipt):
        raise ValueError("Expected independently recorded receipt SHA-256")
    manifest_path = safe_path(path / RECEIPT)
    if (not path.is_dir() or not manifest_path.is_file() or manifest_path.stat().st_nlink != 1
            or stat.S_IMODE(manifest_path.stat().st_mode) != 0o644
            or manifest_path.stat().st_size > 4 * 1024 * 1024):
        raise ValueError("Invalid snapshot receipt")
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != trusted_receipt:
        raise ValueError("Receipt integrity mismatch")
    manifest = json.loads(raw)
    if (set(manifest) != {"schema", "repository", "source_sha", "files"}
            or manifest["schema"] != 1 or manifest["repository"] != CANONICAL
            or manifest["source_sha"] != expected or not manifest["files"]
            or not isinstance(manifest["files"], dict)):
        raise ValueError("Snapshot source identity mismatch")
    wanted_dirs = set()
    for name, record in manifest["files"].items():
        relative = Path(name)
        if (relative.is_absolute() or ".." in relative.parts or ".git" in relative.parts
                or RECEIPT in relative.parts or relative.as_posix() != name
                or set(record) != {"sha256", "mode"} or record["mode"] not in {"100644", "100755"}):
            raise ValueError("Unsafe snapshot entry")
        for parent in relative.parents:
            if parent != Path("."):
                snapshot_directory(safe_path(path / parent))
        target = safe_path(path / relative)
        mode = target.stat().st_mode
        if (not stat.S_ISREG(mode) or target.stat().st_nlink != 1
                or hashlib.sha256(target.read_bytes()).hexdigest() != record["sha256"]
                or stat.S_IMODE(mode) != (0o755 if record["mode"] == "100755" else 0o644)):
            raise ValueError("Snapshot file integrity/mode mismatch")
        wanted_dirs.update(p.as_posix() for p in relative.parents if p != Path("."))
    actual_files, actual_dirs = set(), set()
    for current, directories, filenames in os.walk(path, followlinks=False):
        for name in directories + filenames:
            entry = safe_path(Path(current) / name)
            relative = entry.relative_to(path).as_posix()
            if entry.is_dir():
                snapshot_directory(entry)
                actual_dirs.add(relative)
            else:
                actual_files.add(relative)
    if (actual_files != {*manifest["files"], RECEIPT} or actual_dirs != wanted_dirs):
        raise ValueError("Snapshot inventory drift; preserve and investigate")
    return {"source_sha": expected, "receipt_sha256": trusted_receipt,
            "files": len(manifest["files"]), "integrity": "verified"}


def run(action, args):
    if action == "repo-inspect":
        return inspect(args.root)
    if action == "task-start":
        return start(args.root, args.branch, args.destination, args.expected_sha)
    if action == "source-verify":
        return verify(args.root, args.expected_sha)
    if action == "snapshot-export":
        return export(args.root, args.expected_sha, args.destination)
    return verify_snapshot(args.snapshot, args.expected_sha, args.receipt_sha256)
