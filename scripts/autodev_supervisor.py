#!/usr/bin/env python3
"""Explicit, bounded, resumable-on-verified-checkpoints Codex development pilot.

The operator owns the checkout, manifest and local Codex authorization. This
does not install a daemon, timer, key or GitHub integration.
"""
import argparse
import ast
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import time

_spec = importlib.util.spec_from_file_location(
    "autodev_lifecycle", Path(__file__).resolve().with_name("autodev_lifecycle.py"))
lifecycle = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lifecycle)

MAX_TASKS = 5
MAX_FILES = 2
MAX_LINES = 180
MAX_TRACKED = 3000
MAX_SOURCE_BYTES = 30 * 1024 * 1024
MAX_SOURCE_FILE = 256 * 1024
ERROR = "autodev refused"


class Refused(Exception):
    pass


def deny(reason):
    raise Refused(reason)


def command(args, *, cwd, timeout=30, env=None, check=True):
    r = subprocess.run(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=timeout, check=False)
    if check and r.returncode:
        deny("local tool failed: " + Path(args[0]).name)
    return r


def git(repo, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    return command(["git", "-c", "core.hooksPath=/dev/null",
                    "-c", "core.fsmonitor=false", "-C", str(repo), *args],
                   cwd=repo, env=env)


def validate_path(raw):
    if not isinstance(raw, str) or len(raw) > 180 or not re.fullmatch(
        r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*(/[A-Za-z0-9_.-]+)?|[A-Za-z0-9_.-]+", raw
    ):
        deny("invalid source path")
    parts = PurePosixPath(raw).parts
    if any(x in (".", "..", ".git") or x.startswith(".") for x in parts):
        deny("hidden or escaping path denied")
    if not raw.endswith((".rs", ".py", ".md", ".toml")):
        deny("only tracked source files may be edited")
    return raw


def manifest(path):
    if not path.is_file() or path.stat().st_size > 16384 or path.is_symlink():
        deny("missing or oversized manifest")
    raw = path.read_bytes()
    try:
        doc = json.loads(raw)
    except (ValueError, UnicodeError):
        deny("invalid JSON manifest")
    if not isinstance(doc, dict) or set(doc) != {"schema", "expected_sha", "tasks", "repository"}:
        deny("invalid manifest fields")
    if doc["schema"] != 1 or not isinstance(doc["expected_sha"], str) or not re.fullmatch(
        r"[0-9a-f]{40}", doc["expected_sha"]
    ):
        deny("invalid manifest version or base SHA")
    if not isinstance(doc["repository"], str) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", doc["repository"]
    ):
        deny("invalid repository identity")
    tasks = doc["tasks"]
    if not isinstance(tasks, list) or not 3 <= len(tasks) <= MAX_TASKS:
        deny("exactly 3–5 small tasks required")
    names = set()
    for task in tasks:
        if not isinstance(task, dict) or not (
            {"id", "prompt", "paths"} <= set(task)
            <= {"id", "prompt", "paths", "recipe"}
        ):
            deny("invalid task fields")
        name, prompt, paths = task["id"], task["prompt"], task["paths"]
        recipe = task.get("recipe", "python-unittest")
        if recipe not in ("python-unittest", "rust-cargo-test"):
            deny("unsupported fixed project-test recipe")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", name):
            deny("invalid task identity")
        if name in names:
            deny("duplicate task")
        names.add(name)
        if not isinstance(prompt, str) or not 10 <= len(prompt) <= 1200 or "\x00" in prompt:
            deny("invalid bounded prompt")
        if not isinstance(paths, list) or not 1 <= len(paths) <= MAX_FILES:
            deny("invalid file scope")
        if len(paths) != len(set(map(str, paths))):
            deny("duplicate path")
        for path in paths:
            validate_path(path)
        if any(path.endswith(".rs") for path in paths) and recipe != "rust-cargo-test":
            deny("Rust edits require Rust workspace test recipe")
    return doc, hashlib.sha256(raw).hexdigest()


def overlaps(a, b):
    return a == b or a.is_relative_to(b) or b.is_relative_to(a)


def safe_directory(path, *, mode):
    if not path.is_absolute() or ".." in path.parts or path == Path("/"):
        deny("absolute private directory required")
    if not path.is_dir():
        deny("directory does not exist")
    for part in [path, *path.parents]:
        if part.is_symlink():
            deny("symlink ancestry denied")
    st = path.stat()
    if st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != mode:
        deny("unexpected directory ownership or permissions")
    return path


def checkout(repo, doc):
    if not repo.is_absolute() or not repo.is_dir() or repo.is_symlink():
        deny("absolute checkout required")
    for part in [repo, *repo.parents]:
        if part.is_symlink():
            deny("symlink in checkout ancestry")
    # The source branch must be a separate Git worktree, never a renamed
    # primary checkout that might hold unrelated operator state.
    if not (repo / ".git").is_file() or (repo / ".git").is_symlink():
        deny("dedicated linked git worktree required")
    top = git(repo, "rev-parse", "--show-toplevel").stdout.decode().strip()
    branch = git(repo, "symbolic-ref", "--short", "HEAD").stdout.decode().strip()
    head = git(repo, "rev-parse", "HEAD").stdout.decode().strip()
    if top != str(repo) or not re.fullmatch(r"autodev/[a-z0-9][a-z0-9-]{0,55}", branch):
        deny("dedicated autodev branch and worktree required")
    origin = git(repo, "remote", "get-url", "origin").stdout.decode().strip()
    owner_repo = doc["repository"]
    urls = {
        "https://github.com/" + owner_repo,
        "https://github.com/" + owner_repo + ".git",
        "git@github.com:" + owner_repo + ".git",
    }
    if origin not in urls:
        deny("origin does not match manifest repository")
    if git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout:
        deny("checkout must be clean")
    return head, branch


@contextlib.contextmanager
def private_lock(directory):
    safe_directory(directory, mode=0o700)
    fd = os.open(directory / "supervisor.lock",
                 os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        st = os.fstat(fd)
        if st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1:
            deny("unsafe lock inode")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            deny("another supervisor owns this state")
        yield
    finally:
        os.close(fd)


def load_state(directory):
    path = directory / "state.json"
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError:
        deny("unsafe state receipt")
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1
                or st.st_size > 8192 or st.st_uid != os.geteuid()
                or stat.S_IMODE(st.st_mode) != 0o600):
            deny("unsafe state receipt")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            raw = handle.read(8193)
        if len(raw) > 8192:
            deny("oversized state receipt")
    finally:
        os.close(fd)
    try:
        state = json.loads(raw)
    except (ValueError, UnicodeError):
        deny("corrupt state")
    if not isinstance(state, dict):
        deny("unknown receipt schema")
    if "lifecycle" in state:
        try:
            lifecycle.validate(state["lifecycle"])
        except lifecycle.LifecycleRefused:
            deny("corrupt lifecycle receipt")
    if set(state) - {"lifecycle"} not in (
        {"schema", "manifest_sha256", "phase", "head", "branch", "index", "commits"},
        {"schema", "manifest_sha256", "phase", "head", "branch", "index", "commits", "draft_pr_created"},
    ) or state.get("schema") != 1:
        deny("unknown receipt schema")
    index = state.get("index")
    commits = state.get("commits")
    if (type(index) is not int or not 0 <= index <= MAX_TASKS
            or not isinstance(commits, list) or len(commits) != index
            or state.get("phase") not in {"ready", "started", "complete", "publishing", "published"}
            or not isinstance(state.get("head"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", state["head"])):
        deny("corrupt state receipt")
    for entry in commits:
        if (not isinstance(entry, dict) or set(entry) != {"task_id", "sha"}
                or not isinstance(entry["sha"], str)
                or not re.fullmatch(r"[0-9a-f]{40}", entry["sha"])):
            deny("corrupt checkpoint")
    return state


def save_state(directory, state):
    data = (json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(data) > 8192:
        deny("state budget exceeded")
    with tempfile.NamedTemporaryFile(mode="wb", prefix=".state-", dir=directory,
                                     delete=False) as tmp:
        name = tmp.name
        os.fchmod(tmp.fileno(), 0o600)
        try:
            tmp.write(data)
            tmp.flush()
            os.fsync(tmp.fileno())
        finally:
            pass
    os.replace(name, directory / "state.json")
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def preflight_scopes(repo, doc, rustfmt):
    """Reject unusable task paths before committing a model attempt."""
    tracked = {os.fsdecode(p) for p in
               git(repo, "ls-files", "-z").stdout.split(b"\0") if p}
    for task in doc["tasks"]:
        for name in task["paths"]:
            path = repo / name
            if (name not in tracked or not path.is_file()
                    or path.is_symlink() or path.stat().st_size > MAX_SOURCE_FILE):
                deny("task path missing, unsafe or oversized")
            if any(parent.is_symlink() for parent in path.parents if parent != repo):
                deny("task path has symlink ancestor")
            if name.endswith(".rs") and (
                rustfmt is None or not rustfmt.is_absolute()
                or rustfmt.is_symlink() or not rustfmt.is_file()
                or not os.access(rustfmt, os.X_OK)
            ):
                deny("Rust task requires explicit --rustfmt before model launch")


def source_copy(repo, temp):
    items = git(repo, "ls-files", "-z").stdout.split(b"\0")
    entries = [os.fsdecode(s) for s in items if s]
    if len(entries) > MAX_TRACKED:
        deny("source inventory exceeds budget")
    total = 0
    copied = set()
    for raw in entries:
        if raw.startswith(".git") or raw.startswith(".codex"):
            continue
        source = repo / raw
        if not source.is_file() or source.is_symlink():
            continue
        if any(p.is_symlink() for p in source.parents if p != repo):
            deny("tracked symlink ancestry")
        size = source.stat().st_size
        if size > MAX_SOURCE_FILE:
            continue
        total += size
        if total > MAX_SOURCE_BYTES:
            deny("source copy exceeds budget")
        dest = temp / raw
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        copied.add(raw)
    return copied


def validate_sources(scratch, paths, rustfmt=None):
    """Never execute model-authored Python or shell; parse source only.

    Rust requires an explicit operator-provided formatting tool path. This
    is a structural gate, NOT evidence that the code passes project tests.
    """
    for name in paths:
        source = scratch / name
        if not source.is_file() or source.is_symlink():
            deny("validation source unavailable")
        data = source.read_bytes()
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError:
            deny("non-UTF8 candidate")
        if "\x00" in content:
            deny("NUL in candidate")
        if name.endswith(".py"):
            try:
                ast.parse(content, filename=name)
            except (SyntaxError, ValueError):
                deny("Python source syntax invalid")
        elif name.endswith(".toml"):
            try:
                tomllib.loads(content)
            except tomllib.TOMLDecodeError:
                deny("TOML source syntax invalid")
        elif name.endswith(".rs"):
            if (rustfmt is None or not rustfmt.is_absolute()
                    or rustfmt.is_symlink() or not rustfmt.is_file()
                    or not os.access(rustfmt, os.X_OK)):
                deny("Rust edits require explicit --rustfmt tool")
            result = command([str(rustfmt), "--check", "--edition", "2024",
                              "--config", "skip_children=true", name],
                             cwd=scratch, timeout=25, check=False,
                             env={"PATH": "/usr/bin:/bin", "HOME": str(scratch)})
            if result.returncode:
                deny("Rust source formatting invalid")
        elif name.endswith(".md"):
            if not content.strip():
                deny("empty Markdown candidate")
        else:
            deny("no bounded syntax verification for source extension")


def scoped_candidates(repo, scratch, paths, copied):
    """Read-only safety check BEFORE running any project test code."""

    # Reject ALL out-of-scope edits in the sandbox, not just changes that
    # would otherwise be copied back to the operator's checkout.
    seen = set()
    for candidate in scratch.rglob("*"):
        if candidate.is_symlink():
            deny("symlink introduced in temporary source")
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            deny("nonregular file introduced in temporary source")
        relative = candidate.relative_to(scratch).as_posix()
        seen.add(relative)
        if relative not in copied:
            deny("unexpected new sandbox file")
        if relative not in paths and candidate.read_bytes() != (repo / relative).read_bytes():
            deny("source outside task scope was edited")
    if seen != copied:
        deny("source deleted from validation snapshot")
    changed = []
    for name in paths:
        source, target = scratch / name, repo / name
        if not target.is_file() or target.is_symlink() or not source.is_file() or source.is_symlink():
            deny("allowlisted source not regular")
        if any(parent.is_symlink() for parent in source.parents if parent != scratch):
            deny("symlink ancestry in candidate")
        if name not in copied:
            deny("allowlisted source not regular")
        if source.stat().st_size > MAX_SOURCE_FILE:
            deny("candidate file too large")
        before, after = target.read_bytes(), source.read_bytes()
        if after != before:
            after.decode("utf-8")
            changed.append(name)
    if not changed:
        deny("task made no permitted change")
    return changed


def apply_changes(repo, scratch, paths, copied):
    changed = scoped_candidates(repo, scratch, paths, copied)
    for name in changed:
        (repo / name).write_bytes((scratch / name).read_bytes())
    status = git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
    rows = status.split(b"\0")
    if rows[-1] != b"":
        deny("invalid git status")
    for row in rows[:-1]:
        if len(row) < 4 or row[:3] != b" M " or os.fsdecode(row[3:]) not in changed:
            deny("changed files escaped the task allowlist")
    lines = 0
    for row in git(repo, "diff", "--numstat", "--", *changed).stdout.decode().splitlines():
        parts = row.split("\t")
        if len(parts) != 3 or not parts[0].isdigit() or not parts[1].isdigit():
            deny("binary diff denied")
        lines += int(parts[0]) + int(parts[1])
    if not 1 <= lines <= MAX_LINES or git(repo, "diff", "--check").stdout:
        deny("patch budget or whitespace check failed")
    return changed


def pinned_executable(path, expected_sha):
    if (not isinstance(expected_sha, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha)
            or not path.is_absolute() or path.is_symlink()
            or not path.is_file() or not os.access(path, os.X_OK)):
        deny("absolute executable and SHA256 pin required")
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_size > 100 * 1024 * 1024:
        deny("unsafe Codex executable")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha:
        deny("Codex binary SHA256 changed")
    return path


def bounded_codex(argv, *, cwd, env, seconds, cancelled=None):
    """Retire the private process group on success, timeout or interruption."""
    if cancelled is not None:
        cancelled()
    with open(os.devnull, "wb") as sink:
        child = subprocess.Popen(
            argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
            stdout=sink, stderr=sink, start_new_session=True,
        )
        try:
            deadline = time.monotonic() + seconds
            while True:
                if cancelled is not None:
                    cancelled()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(argv, seconds)
                try:
                    child.communicate(timeout=min(remaining, 0.2))
                    break
                except subprocess.TimeoutExpired:
                    continue
        except BaseException:
            # Kill the entire private session, not just the launcher PID.
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            # A descendant may survive SIGTERM even after the main CLI exits.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait(timeout=2)
            raise
        # A successful launcher can leave descendants mutating the snapshot.
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return child.returncode


def project_test_gate(scratch, bwrap, expected_sha, *, timeout, recipe="python-unittest",
                      cancelled=None):
    """Run ONE fixed project-test recipe inside a networkless OS sandbox.

    Project test code is untrusted: never execute it directly on the host.
    The validation copy is mounted read-only. No user HOME, secrets, network,
    SSH, Git metadata, host services or mutable host worktree are mounted.
    """
    if not 15 <= timeout <= 240:
        deny("validation timeout outside bounded range")
    pinned_executable(bwrap, expected_sha)
    if recipe == "python-unittest":
        if not (scratch / "scripts").is_dir():
            deny("Python project test directory unavailable")
        inside_command = [
            "/usr/bin/python3", "-I", "-B", "-m", "unittest",
            "discover", "-s", "scripts", "-p", "test_*.py",
        ]
    elif recipe == "rust-cargo-test":
        # Only system-installed Cargo and offline, self-contained/vendor-based
        # workspaces are supported. No $HOME/rustup, user registries or tokens.
        if not (scratch / "Cargo.toml").is_file():
            deny("Rust workspace manifest unavailable")
        if not Path("/usr/bin/cargo").is_file():
            deny("system Cargo unavailable")
        if not Path("/usr/bin/rustc").is_file() or not Path("/usr/bin/gcc").is_file():
            deny("system Rust compiler or GCC linker unavailable")
        inside_command = [
            "/usr/bin/cargo", "test", "--locked", "--offline", "--workspace",
        ]
    else:
        deny("unrecognized validation recipe")
    # Limit the filesystem view to the system Python runtime and this source
    # snapshot. Do not accidentally ro-bind /, /home, /etc or /var.
    args = [str(bwrap), "--die-with-parent", "--unshare-all", "--new-session",
            "--ro-bind", "/usr", "/usr"]
    for system in ("/bin", "/lib", "/lib64"):
        if Path(system).exists():
            if Path(system).is_symlink():
                args += ["--symlink", os.readlink(system), system]
            else:
                args += ["--ro-bind", system, system]
    args += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
             "--ro-bind", str(scratch), "/workspace",
             "--chdir", "/workspace", "--setenv", "HOME", "/tmp",
             "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
             "--setenv", "PATH", "/usr/bin:/bin",
             "--setenv", "CARGO_HOME", "/tmp/cargo",
             "--setenv", "CARGO_TARGET_DIR", "/tmp/target",
             "--setenv", "CARGO_NET_OFFLINE", "true",
             "--setenv", "RUSTFLAGS", "-C linker=/usr/bin/gcc",
             "--", *inside_command]
    try:
        status = bounded_codex(
            args, cwd=scratch,
            env={"PATH": "/usr/bin:/bin", "HOME": "/tmp", "LANG": "C.UTF-8"},
            seconds=timeout, cancelled=cancelled,
        )
    except subprocess.TimeoutExpired:
        deny("isolated project tests exceeded time budget")
    if status != 0:
        deny("isolated project tests did not pass")
    # The OS sandbox normally keeps snapshot read-only. This repeat check
    # below prevents a broken/mock sandbox from silently altering sources.


def run_task(repo, directory, task, codex, seconds, rustfmt=None, codex_sha=None,
             codex_home=None, test_bwrap=None, test_bwrap_sha=None,
             test_seconds=120, cancelled=None):
    with tempfile.TemporaryDirectory(prefix="source-", dir=directory) as base:
        scratch = Path(base)
        copied = source_copy(repo, scratch)
        prompt = (
            "Codex Smart controlled source-only pilot. Work ONLY in: "
            + ", ".join(task["paths"])
            + ". No commits, git, network, deployment, SSH, credentials, "
            "services, config mutation or unrequested files. Keep the "
            "edit small and testable. Task: " + task["prompt"]
        )
        # Do not forward GitHub tokens or unrelated secrets to the model.
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
               "HOME": str(scratch), "LANG": "C.UTF-8"}
        if codex_home is not None:
            env["CODEX_HOME"] = str(codex_home)
        pinned_executable(codex, codex_sha)
        code = bounded_codex(
            [str(codex), "--ask-for-approval", "never", "exec",
             "--sandbox", "workspace-write", "--skip-git-repo-check", prompt],
            cwd=scratch, env=env, seconds=seconds, cancelled=cancelled,
        )
        if code:
            deny("Codex exited unsuccessfully")
        scoped_candidates(repo, scratch, task["paths"], copied)
        validate_sources(scratch, task["paths"], rustfmt=rustfmt)
        project_test_gate(scratch, test_bwrap, test_bwrap_sha,
                          timeout=test_seconds, recipe=task.get("recipe", "python-unittest"),
                          cancelled=cancelled)
        if cancelled is not None:
            cancelled()
        # Model code and all project checks finished before ANY worktree write.
        return apply_changes(repo, scratch, task["paths"], copied)


def commit_stage(repo, task, files):
    git(repo, "add", "--", *files)
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_AUTHOR_NAME="codex-smart-autodev",
               GIT_COMMITTER_NAME="codex-smart-autodev",
               GIT_AUTHOR_EMAIL="codex-smart-autodev@users.noreply.github.com",
               GIT_COMMITTER_EMAIL="codex-smart-autodev@users.noreply.github.com")
    command(["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), "commit",
             "-m", "test: autodev stage " + task["id"]], cwd=repo, env=env)
    return git(repo, "rev-parse", "HEAD").stdout.decode().strip()


def publish(repo, directory, state, doc, *, cancelled=None):
    if state["phase"] != "complete":
        deny("cannot publish incomplete or ambiguous run")
    head, branch = checkout(repo, doc)
    if head != state["head"] or state["index"] != len(doc["tasks"]):
        deny("head mismatch or unfinished tasks")
    if cancelled is not None:
        cancelled()
    state["phase"] = "publishing"
    save_state(directory, state)  # no retry after ambiguous remote side effect
    if cancelled is not None:
        cancelled()
    git(repo, "push", "--set-upstream", "origin", branch)
    if cancelled is not None:
        cancelled()
    result = command(
        ["gh", "pr", "create", "--draft", "--base", "main", "--head", branch,
         "--title", "test: bounded autonomous development pilot",
         "--body", "3–5 bounded stages generated by a locally opted-in "
         "Codex Smart pilot. Human review and independent exact-SHA CI "
         "required. No automatic merge or deployment."],
        cwd=repo, timeout=90,
    )
    url = result.stdout.decode("utf-8", "replace").strip()
    # Avoid retaining free-form remote output in the receipt.
    state["phase"] = "published"
    state["draft_pr_created"] = url.startswith("https://github.com/")
    save_state(directory, state)
    print("Draft PR created" if state["draft_pr_created"] else "Publish result unverified")


def cancellation(directory, digest, *, request=False):
    """Cancellation can interrupt a lock-owning worker without taking its lock."""
    safe_directory(directory, mode=0o700)
    path = directory / "cancel"
    if request:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            cancellation(directory, digest)
        else:
            try:
                os.write(fd, digest.encode("ascii"))
                os.fsync(fd)
            finally:
                os.close(fd)
            parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_nlink != 1
                or stat.S_IMODE(st.st_mode) != 0o600 or os.read(fd, 65) != digest.encode("ascii")):
            deny("unsafe or foreign cancellation marker")
    finally:
        os.close(fd)
    deny("run cancelled; a new run requires a new private state directory")


def execution_preflight(args):
    if not 30 <= args.stage_seconds <= 1200:
        deny("stage timeout outside approved range")
    if not 1 <= args.max_stages <= MAX_TASKS:
        deny("invalid invocation stage budget")
    if args.codex is None:
        deny("Codex executable required")
    pinned_executable(args.codex, args.codex_sha256)
    if args.test_bwrap is None:
        deny("offline project validation requires pinned bubblewrap")
    pinned_executable(args.test_bwrap, args.test_bwrap_sha256)
    if not 15 <= args.test_seconds <= 240:
        deny("project test timeout outside approved range")
    if args.codex_home is not None:
        safe_directory(args.codex_home, mode=0o700)
        if overlaps(args.codex_home, args.repo) or overlaps(
            args.codex_home, args.state_dir
        ):
            deny("dedicated Codex profile cannot overlap source or receipts")


def revise_findings(args, doc, state, expected, findings, host, cancelled):
    execution_preflight(args)
    head, branch = checkout(args.repo, doc)
    if head != expected or branch != state["branch"]:
        deny("revision checkout mismatch")
    paths = {f["path"] for f in findings}
    tasks = [t for t in doc["tasks"] if paths <= set(t["paths"])]
    if not tasks:
        deny("findings exceed one original bounded task")
    prompt = "Address independent review findings: " + " ".join(f["instruction"] for f in findings)
    if len(prompt) > 1200:
        deny("finding instructions exceed task budget")
    task = dict(tasks[0], prompt=prompt)
    changed = run_task(args.repo, args.state_dir, task, args.codex, args.stage_seconds,
                       rustfmt=args.rustfmt, codex_sha=args.codex_sha256,
                       codex_home=args.codex_home, test_bwrap=args.test_bwrap,
                       test_bwrap_sha=args.test_bwrap_sha256, test_seconds=args.test_seconds,
                       cancelled=cancelled)
    cancelled()
    head = commit_stage(args.repo, task, changed)
    cancelled()
    host.publish_revision(head)  # uncertain push stays revising; never replay
    return head


def execute(argv=None, *, host=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "status", "run", "publish", "cancel",
                                                  "review", "retry", "reconcile", "integrate", "verify"))
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--codex", type=Path)
    parser.add_argument("--codex-sha256")
    parser.add_argument("--codex-home", type=Path)
    parser.add_argument("--rustfmt", type=Path)
    parser.add_argument("--test-bwrap", type=Path)
    parser.add_argument("--test-bwrap-sha256")
    parser.add_argument("--test-seconds", type=int, default=120)
    parser.add_argument("--stage-seconds", type=int, default=900)
    parser.add_argument("--max-stages", type=int, default=5)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--publish-draft", action="store_true")
    args = parser.parse_args(argv)
    doc, digest = manifest(args.manifest)
    if args.action == "plan":
        print(json.dumps({"tasks": [t["id"] for t in doc["tasks"]],
                          "expected_sha": doc["expected_sha"],
                          "repository": doc["repository"], "executes": False}))
        return 0
    if args.state_dir is None or not args.state_dir.is_absolute():
        deny("explicit private state directory required")
    if overlaps(args.state_dir, args.repo):
        deny("state must remain disjoint from source worktree")
    if args.action == "cancel":
        if not args.apply:
            deny("cancellation requires explicit --apply")
        try:
            cancellation(args.state_dir, digest, request=True)
        except Refused as error:
            if str(error).startswith("run cancelled;"):
                print("Cancellation recorded")
                return 0
            raise
    cancelled = lambda: cancellation(args.state_dir, digest)
    with private_lock(args.state_dir):
        state = load_state(args.state_dir)
        if args.action == "status":
            report = dict(state or {"phase": "not-started"})
            try:
                cancelled()
            except Refused as error:
                if not str(error).startswith("run cancelled;"):
                    raise
                report["cancellation_requested"] = True
            print(json.dumps(report, sort_keys=True))
            return 0
        if not args.apply:
            deny("execution requires explicit --apply")
        if args.action not in {"reconcile", "verify"}:
            cancelled()
        if args.action in {"review", "retry", "reconcile", "integrate", "verify"}:
            if host is None:
                deny("independently authorized lifecycle host unavailable; no runtime adapter enrolled")
            if state is None or state.get("manifest_sha256") != digest:
                deny("no matching published run")
            if host.repository != doc["repository"]:
                deny("lifecycle host repository mismatch")
            controller = lifecycle.Lifecycle(
                state, lambda value: save_state(args.state_dir, value), host,
                revise=lambda head, findings: revise_findings(
                    args, doc, state, head, findings, host, cancelled),
                cancelled=cancelled)
            if "lifecycle" not in state:
                controller.attach()
            if args.action == "review":
                controller.review({p for t in doc["tasks"] for p in t["paths"]})
            elif args.action == "retry":
                controller.retry()
            else:
                getattr(controller, args.action)()
            return 0
        if args.action == "publish":
            if state is None or state.get("manifest_sha256") != digest:
                deny("no matching completed manifest")
            publish(args.repo, args.state_dir, state, doc, cancelled=cancelled)
            return 0
        execution_preflight(args)
        head, branch = checkout(args.repo, doc)
        preflight_scopes(args.repo, doc, args.rustfmt)
        if state is None:
            if head != doc["expected_sha"]:
                deny("initial SHA mismatch")
            state = {"schema": 1, "manifest_sha256": digest, "phase": "ready",
                     "head": head, "branch": branch, "index": 0, "commits": []}
            save_state(args.state_dir, state)
        if state.get("manifest_sha256") != digest or state.get("branch") != branch:
            deny("manifest or branch changed")
        if state.get("phase") != "ready" or head != state.get("head"):
            deny("ambiguous attempt or checkout mismatch: manual review required")
        remaining = len(doc["tasks"]) - state["index"]
        if remaining <= 0:
            deny("all stages already complete or receipt inconsistent")
        last_stage = state["index"] + min(remaining, args.max_stages)
        for index in range(state["index"], last_stage):
            task = doc["tasks"][index]
            cancelled()
            state["phase"] = "started"
            save_state(args.state_dir, state)  # before ANY model invocation
            changed = run_task(args.repo, args.state_dir, task, args.codex, args.stage_seconds,
                               rustfmt=args.rustfmt, codex_sha=args.codex_sha256,
                               codex_home=args.codex_home,
                               test_bwrap=args.test_bwrap,
                               test_bwrap_sha=args.test_bwrap_sha256,
                               test_seconds=args.test_seconds, cancelled=cancelled)
            cancelled()
            new_head = commit_stage(args.repo, task, changed)
            state["commits"].append({"task_id": task["id"], "sha": new_head})
            state["head"] = new_head
            state["index"] = index + 1
            state["phase"] = "ready"
            save_state(args.state_dir, state)
            print("Committed syntax-checked stage " + str(index + 1), flush=True)
        if state["index"] == len(doc["tasks"]):
            state["phase"] = "complete"
            save_state(args.state_dir, state)
            if args.publish_draft:
                publish(args.repo, args.state_dir, state, doc, cancelled=cancelled)
        else:
            if args.publish_draft:
                deny("cannot publish a partial stage batch")
            print("Paused at verified checkpoint; a later explicit run may resume",
                  flush=True)
        return 0


def main():
    try:
        sys.exit(execute())
    except (Refused, lifecycle.LifecycleRefused, OSError, subprocess.TimeoutExpired, UnicodeError) as e:
        print(ERROR + ": " + (str(e) if isinstance(e, Refused) else type(e).__name__),
              file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
