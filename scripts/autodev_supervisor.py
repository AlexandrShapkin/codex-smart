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
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib

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
        if not isinstance(task, dict) or set(task) != {"id", "prompt", "paths"}:
            deny("invalid task fields")
        name, prompt, paths = task["id"], task["prompt"], task["paths"]
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
    return doc, hashlib.sha256(raw).hexdigest()


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
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
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
    if not isinstance(state, dict) or set(state) not in (
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


def apply_changes(repo, scratch, paths, copied):
    # Reject ALL out-of-scope edits in the sandbox, not just changes that
    # would otherwise be copied back to the operator's checkout.
    for candidate in scratch.rglob("*"):
        if candidate.is_symlink():
            deny("symlink introduced in temporary source")
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(scratch).as_posix()
        if relative not in copied:
            deny("unexpected new sandbox file")
        if relative not in paths and candidate.read_bytes() != (repo / relative).read_bytes():
            deny("source outside task scope was edited")
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
            target.write_bytes(after)
            changed.append(name)
    if not changed:
        deny("task made no permitted change")
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


def run_task(repo, directory, task, codex, seconds, rustfmt=None):
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
        env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "CODEX_HOME")
               if k in os.environ}
        with open(os.devnull, "wb") as sink:
            outcome = subprocess.run(
                [str(codex), "--ask-for-approval", "never", "exec",
                 "--sandbox", "workspace-write", "--skip-git-repo-check", prompt],
                cwd=scratch, env=env, stdin=subprocess.DEVNULL,
                stdout=sink, stderr=sink, timeout=seconds, check=False,
            )
        if outcome.returncode:
            deny("Codex exited unsuccessfully")
        validate_sources(scratch, task["paths"], rustfmt=rustfmt)
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


def publish(repo, directory, state, doc):
    if state["phase"] != "complete":
        deny("cannot publish incomplete or ambiguous run")
    head, branch = checkout(repo, doc)
    if head != state["head"] or state["index"] != len(doc["tasks"]):
        deny("head mismatch or unfinished tasks")
    state["phase"] = "publishing"
    save_state(directory, state)  # no retry after ambiguous remote side effect
    git(repo, "push", "--set-upstream", "origin", branch)
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


def execute(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "status", "run", "publish"))
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--codex", type=Path)
    parser.add_argument("--rustfmt", type=Path)
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
    if args.state_dir == args.repo or args.state_dir.is_relative_to(args.repo):
        deny("state must remain outside source worktree")
    with private_lock(args.state_dir):
        state = load_state(args.state_dir)
        if args.action == "status":
            print(json.dumps(state or {"phase": "not-started"}, sort_keys=True))
            return 0
        if not args.apply:
            deny("execution requires explicit --apply")
        if args.action == "publish":
            if state is None or state.get("manifest_sha256") != digest:
                deny("no matching completed manifest")
            publish(args.repo, args.state_dir, state, doc)
            return 0
        if not 30 <= args.stage_seconds <= 1200:
            deny("stage timeout outside approved range")
        if not 1 <= args.max_stages <= MAX_TASKS:
            deny("invalid invocation stage budget")
        if args.codex is None or not args.codex.is_absolute() or args.codex.is_symlink() or not args.codex.is_file():
            deny("absolute, installed Codex executable required")
        if not os.access(args.codex, os.X_OK):
            deny("Codex executable unavailable")
        head, branch = checkout(args.repo, doc)
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
            state["phase"] = "started"
            save_state(args.state_dir, state)  # before ANY model invocation
            changed = run_task(args.repo, args.state_dir, task, args.codex, args.stage_seconds,
                               rustfmt=args.rustfmt)
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
                publish(args.repo, args.state_dir, state, doc)
        else:
            if args.publish_draft:
                deny("cannot publish a partial stage batch")
            print("Paused at verified checkpoint; a later explicit run may resume",
                  flush=True)
        return 0


def main():
    try:
        sys.exit(execute())
    except (Refused, OSError, subprocess.TimeoutExpired, UnicodeError) as e:
        print(ERROR + ": " + (str(e) if isinstance(e, Refused) else type(e).__name__),
              file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
