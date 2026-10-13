"""Sandbox-side representative submission grader.

This file is mounted read-only by benchmark_isolation. Trusted fixtures/oracles are
loaded only from the immutable /trusted runtime. Submitted paths are copied through
descriptor-relative no-follow reads into private tmpfs before the trusted grader runs.
"""

import json
import os
import socket
from pathlib import Path, PurePosixPath
import stat
import sys

TRUSTED_REPO = Path("/trusted/repo")
WORKSPACE = Path("/work")
SANITIZED = Path("/tmp/submission")
MAX_SUBMISSION_FILE_BYTES = 8 * 1024 * 1024
MAX_SUBMISSION_BYTES = 32 * 1024 * 1024
VERDICT_SOCKET = "/verdict.sock"


class SubmissionRejected(ValueError):
    pass


def _safe_parts(name):
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise SubmissionRejected("unsafe-submission-path")
    return path.parts


def _read_regular(root_fd, name):
    """Read one relative regular file without following any submitted symlink."""
    parts = _safe_parts(name)
    current = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            next_fd = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=current,
            )
            os.close(current)
            current = next_fd
        try:
            fd = os.open(
                parts[-1],
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                dir_fd=current,
            )
        except FileNotFoundError:
            return None
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise SubmissionRejected("non-regular-submission-file")
            if info.st_nlink != 1:
                raise SubmissionRejected("linked-submission-file")
            if info.st_size > MAX_SUBMISSION_FILE_BYTES:
                raise SubmissionRejected("submission-file-too-large")
            data = bytearray()
            while True:
                chunk = os.read(fd, min(1024 * 1024, MAX_SUBMISSION_FILE_BYTES + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > MAX_SUBMISSION_FILE_BYTES:
                    raise SubmissionRejected("submission-file-too-large")
            try:
                return bytes(data).decode("utf-8")
            except UnicodeDecodeError:
                raise SubmissionRejected("non-utf8-submission-file") from None
        finally:
            os.close(fd)
    except OSError as error:
        raise SubmissionRejected("unsafe-submission-file") from error
    finally:
        os.close(current)


def _copy_expected(fixture):
    names = sorted(set(fixture["files"]) | set(fixture["reference"]))
    root_fd = os.open(WORKSPACE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    total = 0
    try:
        SANITIZED.mkdir(mode=0o700)
        for name in names:
            text = _read_regular(root_fd, name)
            if text is None:
                continue
            total += len(text.encode("utf-8"))
            if total > MAX_SUBMISSION_BYTES:
                raise SubmissionRejected("submission-too-large")
            dest = SANITIZED / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text)
            dest.chmod(0o600)
    finally:
        os.close(root_fd)


def _exploration_policy(fixture):
    """Exploration is read-only except for the single reviewed answer artifact."""
    allowed_files = set(fixture["files"]) | {"answer.json"}
    allowed_dirs = {""}
    for name in allowed_files:
        parts = PurePosixPath(name).parts
        for index in range(1, len(parts)):
            allowed_dirs.add(PurePosixPath(*parts[:index]).as_posix())

    seen = 0
    for root, dirs, files in os.walk(WORKSPACE, topdown=True, followlinks=False):
        relative_root = Path(root).relative_to(WORKSPACE)
        root_name = "" if relative_root == Path(".") else relative_root.as_posix()
        if root_name not in allowed_dirs:
            raise SubmissionRejected("exploration-extra-directory")
        for directory in list(dirs):
            path = Path(root) / directory
            if path.is_symlink():
                raise SubmissionRejected("exploration-symlink")
            relative = path.relative_to(WORKSPACE).as_posix()
            if relative not in allowed_dirs:
                raise SubmissionRejected("exploration-extra-directory")
        for filename in files:
            path = Path(root) / filename
            if path.is_symlink():
                raise SubmissionRejected("exploration-symlink")
            relative = path.relative_to(WORKSPACE).as_posix()
            if relative not in allowed_files:
                raise SubmissionRejected("exploration-extra-artifact")
            seen += 1
            if seen > len(allowed_files):
                raise SubmissionRejected("exploration-file-count")


def grade(scenario_id):
    sys.path.insert(0, str(TRUSTED_REPO / "scripts"))
    sys.path.insert(0, str(TRUSTED_REPO / "benchmarks"))

    import benchmark_coverage as coverage
    import representative_graders as graders

    coverage.load_campaign()
    scenario = next((row for row in coverage.load_manifest()["scenarios"] if row["id"] == scenario_id), None)
    if scenario is None:
        raise SubmissionRejected("unknown-scenario")
    fixture = coverage.fixture(scenario)

    if scenario_id == "explore-notification":
        _exploration_policy(fixture)
    _copy_expected(fixture)
    return bool(graders.check(scenario, fixture, SANITIZED))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        raise SystemExit(64)

    channel = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    channel.set_inheritable(False)
    try:
        channel.connect(VERDICT_SOCKET)
    except OSError:
        channel.close()
        raise SystemExit(65)

    try:
        try:
            quality = grade(argv[0])
            result = {"status": "verified", "quality_pass": quality}
        except SubmissionRejected as error:
            result = {"status": "verified", "quality_pass": False, "reason": str(error)}
        except Exception:
            result = {
                "status": "blocked",
                "quality_pass": False,
                "reason": "trusted-grader-failure",
            }
        data = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
        channel.sendall(data)
    finally:
        channel.close()


if __name__ == "__main__":
    main()
