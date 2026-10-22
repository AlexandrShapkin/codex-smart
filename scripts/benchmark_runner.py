"""Benchmark-only mechanisms; no campaign policy, identity, budget or retry authority.

Extracted from the Adaptive runner. Callers retain provenance/schema checks and
supply their own refusal type. This module defines no static campaign and never
labels a result as Adaptive. Host qualification remains in the existing split-host
preflight; SSH authentication remains in the reviewed trusted-handoff module.
"""

import hashlib
import os
from pathlib import Path
import shlex
import stat
import statistics
import subprocess

import benchmark as b
import benchmark_split_host_campaign as split


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_path(path, *, directory=False, refusal):
    try:
        path = Path(path)
    except (TypeError, ValueError):
        raise refusal("invalid artifact path") from None
    if not path.is_absolute() or any(part.is_symlink() for part in (path, *path.parents)):
        raise refusal("symlink or relative artifact path")
    if directory and not path.is_dir():
        raise refusal("missing artifact directory")
    return path


def regular_file(path, *, refusal):
    path = safe_path(path, refusal=refusal)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISREG(info.st_mode) and info.st_nlink == 1


def attempt_identity_matches(record, expected):
    """Bind a schema-checked ledger/result to the caller's campaign identity.

    The caller checks the exact field set and chooses the measurement/job IDs.
    Integer identity fields deliberately reject bool, as the Adaptive reader did.
    """
    return (all(type(record[key]) is int for key in (
                "schema_version", "repetition", "seed", "attempt"))
            and all(record[key] == value for key, value in expected.items()))


def sync_ledger(path):
    """Persist a written attempt marker and its directory before execution."""
    with path.open("rb") as stream:
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def agent_preflight(codex, code_mode_host, runtime_root, inventory_dir, *, refusal):
    try:
        return split.agent_preflight(codex, code_mode_host, runtime_root, inventory_dir)
    except (OSError, ValueError) as error:
        raise refusal("split-host agent preflight refused") from error


def observe_attempt(argv, workspace, prompt, timeout, execute_fn, scenario):
    try:
        observation = execute_fn(
            argv, workspace, prompt, timeout=timeout
        )
    except OSError:
        observation = {
            "stdout": "",
            "stderr": "",
            "exit_status": None,
            "timeout": False,
            "duration": 0.0,
            "launch_failure": True,
        }
    parsed = b.parse_trace(observation["stdout"])
    failure = split._agent_reason(observation, parsed)
    envelope = None
    export_error = None
    if failure is None:
        try:
            envelope = split.export_submission(scenario, workspace)
        except (OSError, ValueError) as error:
            failure = "submission-export-refused"
            export_error = type(error).__name__

    return observation, parsed, failure, envelope, export_error


def match_grade(grade, started, result, *, refusal):
    if grade is None:
        raise refusal("missing grade")
    if any(grade[key] != started[key] for key in (
        "job_id", "scenario_id", "repetition", "seed", "attempt"
    )):
        raise refusal("grade/started identity mismatch")
    if result is None:
        if (grade["failure_reason"] != "interrupted-no-result"
                or grade["quality_pass"] or grade["agent_success"]
                or any(grade[key] is not None for key in (
                    "profile", "reasoning", "model_key", "model",
                    "trace_sha256", "submission_sha256"
                ))):
            raise refusal("interrupted grade mismatch")
    elif (any(grade[key] != result[key] for key in (
            "profile", "reasoning", "model_key", "model", "trace_sha256",
            "submission_sha256"))
            or grade["agent_success"] != (result["failure_reason"] is None)
            or (result["failure_reason"] is not None and (
                grade["failure_reason"] != result["failure_reason"]
                or grade["quality_pass"]))
            or (result["failure_reason"] is None and not grade["quality_pass"]
                and grade["failure_reason"] != "quality-failure")):
        raise refusal("grade/agent evidence mismatch")


def sum_observed_tokens(results, key):
    values = [result["tokens"].get(key) if result is not None else None for result in results]
    if not values or any(value is None for value in values):
        return None
    return sum(values)


def median(values):
    return statistics.median(values) if values and all(
        value is not None for value in values
    ) else None


def pinned_request(handoff, bootstrap, body, timeout, decode, *, refusal):
    """One authenticated request, with no retry or model replay on failure.

    The caller validates the operation/payload and constructs a source-verifying
    bootstrap before reaching this boundary. Host pin lookup is never bypassed.
    """
    options = handoff.pinned_srv0_options()
    command = shlex.join(["/usr/bin/python3", "-I", "-B", "-c", bootstrap])
    try:
        result = subprocess.run([handoff.SSH, *options, "-T", handoff.TRUSTED_ALIAS, command],
                                input=body, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise refusal("pinned transport interrupted/unavailable; inspect and resume") from error
    if result.returncode:
        raise refusal("pinned host operation refused; no model replay")
    reply = decode(result.stdout)
    if not isinstance(reply, dict):
        raise refusal("malformed pinned host response")
    return reply

