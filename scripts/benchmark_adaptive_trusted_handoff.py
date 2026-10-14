"""Authenticate adaptive grading receipts from the pinned srv0 SSH host.

This is a control-plane-only read. No model execution and no remote mutation.
The returned hash is trustworthy only when the SSH server key is pinned here,
not merely when the bytes of a locally supplied SHA-256 string look correct.
"""

import os
from pathlib import Path
import re
import shlex
import stat
import subprocess

TRUSTED_ALIAS = "srv0"
TRUSTED_ED25519_SHA256 = "SHA256:ANyuKBwjgCuRri4MuJaHJLRBQnqMlDtzKivQKzkExvo"
SSH = "/usr/bin/ssh"
SSH_KEYGEN = "/usr/bin/ssh-keygen"
REMOTE_SUMMARY = re.compile(r"/tmp/[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*/summary\.json\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class GradingHandoffRefusal(ValueError):
    pass


def _result(argv, run, *, timeout=15):
    try:
        reply = run(argv, check=False, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GradingHandoffRefusal("trusted grading SSH command unavailable") from error
    if reply.returncode != 0:
        raise GradingHandoffRefusal("trusted grading SSH command rejected")
    return reply.stdout


def _ssh_options(known_hosts):
    return [
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=yes",
        "-o", "HostKeyAlgorithms=ssh-ed25519",
        "-o", "UpdateHostKeys=no",
        "-o", "VerifyHostKeyDNS=no",
        "-o", "ClearAllForwardings=yes",
        "-o", "ForwardAgent=no",
        "-o", "ForwardX11=no",
        "-o", "ConnectTimeout=10",
        "-o", "GlobalKnownHostsFile=/dev/null",
        "-o", f"UserKnownHostsFile={known_hosts}",
    ]


def pinned_srv0_options(*, run=subprocess.run):
    """Resolve the existing alias and verify its reviewed identity; no config writes."""
    known_hosts = Path.home() / ".ssh/known_hosts"
    try:
        metadata = known_hosts.lstat()
    except OSError as error:
        raise GradingHandoffRefusal("trusted SSH known_hosts missing") from error
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_mode & 0o022
    ):
        raise GradingHandoffRefusal("unsafe SSH known_hosts ownership or mode")

    options = _ssh_options(str(known_hosts))
    config = _result([SSH, *options, "-G", TRUSTED_ALIAS], run)
    values = {}
    for line in config.splitlines():
        key, _, value = line.partition(" ")
        if key in {"hostname", "port"}:
            if key in values:
                raise GradingHandoffRefusal("ambiguous SSH configuration")
            values[key] = value.strip()
    hostname = values.get("hostname")
    port = values.get("port")
    if not hostname or not port or not port.isdecimal() or not 0 < int(port) < 65536:
        raise GradingHandoffRefusal("unresolved trusted grader SSH host")
    if not re.fullmatch(r"[a-zA-Z0-9.:-]+", hostname):
        raise GradingHandoffRefusal("unsafe trusted grader SSH hostname")
    lookup = hostname if int(port) == 22 else f"[{hostname}]:{port}"
    host_keys = _result([SSH_KEYGEN, "-F", lookup, "-l", "-f", str(known_hosts)], run)
    fingerprints = [
        line.split()[-1] for line in host_keys.splitlines()
        if "ED25519" in line and "SHA256:" in line
    ]
    if TRUSTED_ED25519_SHA256 not in fingerprints or len(set(fingerprints)) != 1:
        raise GradingHandoffRefusal("trusted grader ED25519 host key pin mismatch")
    return [*options, "-o", f"HostKeyAlias={lookup}"]


def pinned_srv0_summary_sha256(remote_summary, *, run=subprocess.run):
    """Read a fresh remote digest; caller strings cannot replace host authentication."""
    if (
        type(remote_summary) is not str
        or len(remote_summary) > 256
        or not REMOTE_SUMMARY.fullmatch(remote_summary)
        or any(part in (".", "..") for part in remote_summary.split("/"))
    ):
        raise GradingHandoffRefusal("unsafe remote adaptive grading summary path")
    options = pinned_srv0_options(run=run)

    quoted = shlex.quote(remote_summary)
    remote_command = (
        f"set -eu; test -f {quoted}; test ! -L {quoted}; "
        f'test "$(/usr/bin/realpath -e -- {quoted})" = {quoted}; '
        f"/usr/bin/sha256sum -- {quoted} | /usr/bin/cut -d ' ' -f1"
    )
    digest = _result([
        SSH, *options, "-T",
        TRUSTED_ALIAS, remote_command,
    ], run).strip()
    if not DIGEST.fullmatch(digest):
        raise GradingHandoffRefusal("invalid trusted grader summary digest")
    return digest
