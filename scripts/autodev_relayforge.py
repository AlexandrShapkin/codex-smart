#!/usr/bin/env python3
"""Read-only, fail-closed adapter for externally exported RelayForge job.chain receipts.

No MCP calls, credentials, Git mutations or privileged operations.
An imported JSON file is untrusted evidence, NOT authenticated device state.
"""
import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
import re
import sys

MAX_BUNDLE_BYTES = 512 * 1024
MAX_STEPS = 6
MAX_HANDOFF = 8192
MAX_LOG = 65536
JOB_ID = re.compile(r"relayforge-job-[0-9]{9,12}-[a-f0-9]{6}\Z")


class InvalidChain(ValueError):
    pass


def reject(message):
    raise InvalidChain(message)


def bounded_text(value, limit):
    if not isinstance(value, str):
        reject("non-text chain output")
    encoded = value.encode("utf-8")
    if len(encoded) > limit or "\x00" in value:
        reject("oversized or binary chain output")
    return encoded


def inspect_export(raw, expected_id=None):
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_BUNDLE_BYTES:
        reject("missing or oversized chain evidence")
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        reject("invalid chain evidence encoding")
    if not isinstance(value, dict) or set(value) != {"schema", "status", "outputs"}:
        reject("unsupported bundle schema")
    if type(value["schema"]) is not int or value["schema"] != 1:
        reject("unsupported bundle version")
    status, outputs = value["status"], value["outputs"]
    if not isinstance(status, dict) or not isinstance(outputs, list):
        reject("invalid chain sections")
    required = {"job_id", "chain", "steps", "completed_steps", "state", "exit_code"}
    if not required <= set(status) <= required | {"failure_kind"}:
        reject("invalid chain status fields")
    job_id = status["job_id"]
    if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id):
        reject("invalid chain ID")
    if expected_id is not None and job_id != expected_id:
        reject("chain ID mismatch")
    steps = status["steps"]
    if (status["chain"] is not True or type(steps) is not int
            or not 2 <= steps <= MAX_STEPS or len(outputs) != steps
            or type(status["completed_steps"]) is not int
            or status["completed_steps"] != steps
            or status["state"] != "finished"
            or type(status["exit_code"]) is not int
            or status["exit_code"] != 0
            or status.get("failure_kind") not in (None, "")):
        reject("unfinished or failed chain")
    for idx, output in enumerate(outputs, 1):
        if not isinstance(output, dict) or set(output) != {
            "job_id", "step", "steps", "result", "stdout", "stderr"
        }:
            reject("invalid per-stage fields")
        if output["job_id"] != job_id or type(output["step"]) is not int or output["step"] != idx:
            reject("stage ID mismatch")
        if type(output["steps"]) is not int or output["steps"] != steps:
            reject("stage count mismatch")
        receipt = output["result"]
        if not isinstance(receipt, dict) or set(receipt) != {
            "step", "exit_code", "stdout_truncated",
            "stderr_truncated", "handoff_accepted"
        }:
            reject("invalid stage receipt")
        if (type(receipt["step"]) is not int or receipt["step"] != idx
                or type(receipt["exit_code"]) is not int
                or receipt["exit_code"] != 0
                or receipt["stdout_truncated"] is not False
                or receipt["stderr_truncated"] is not False
                or receipt["handoff_accepted"] is not True):
            reject("failed or truncated stage")
        bounded_text(output["stdout"], MAX_HANDOFF if idx < steps else MAX_LOG)
        bounded_text(output["stderr"], MAX_LOG)
    return {
        "job_id": job_id,
        "steps": steps,
        "receipt_digest_sha256": hashlib.sha256(raw).hexdigest(),
        "trust": "unverified_external_export",
        "result": "reported_success",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--expected-job-id", required=True)
    args = parser.parse_args(argv)
    path = args.bundle
    if not path.is_absolute() or ".." in path.parts:
        reject("absolute private export path required")
    if any(part.is_symlink() for part in (path, *path.parents)):
        reject("symlinked export path denied")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        reject("private chain export unavailable")
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                or st.st_nlink != 1 or stat.S_IMODE(st.st_mode) != 0o600
                or st.st_size > MAX_BUNDLE_BYTES):
            reject("private export ownership or permissions denied")
        raw = os.read(fd, MAX_BUNDLE_BYTES + 1)
    finally:
        os.close(fd)
    report = inspect_export(raw, args.expected_job_id)
    # Never print raw stage logs, script source or potentially sensitive output.
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (InvalidChain, OSError):
        print("RelayForge chain evidence rejected (no execution)", file=sys.stderr)
        sys.exit(2)
