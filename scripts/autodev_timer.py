#!/usr/bin/env python3
"""One-time, local-consent-gated systemd schedule for bounded autodev stages.

This module NEVER writes systemd units, enables a timer, or requests Codex
credentials. Render is read-only. Run requires a 0600 local consent file.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

import autodev_supervisor as supervisor

CONFIG_KEYS = {
    "schema", "manifest", "repo", "state_dir", "codex", "codex_sha256",
    "test_bwrap", "test_bwrap_sha256", "codex_home", "consent_file",
    "start_utc", "interval_minutes", "stage_seconds", "test_seconds",
    "runner",
}
VALID_PATH = re.compile(r"/[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)*\Z")
CONSENT = b"ALLOW_CODEX_SMART_AUTODEV\n"


def safe_absolute(raw):
    if (not isinstance(raw, str) or not VALID_PATH.fullmatch(raw)
            or "." in Path(raw).parts or ".." in Path(raw).parts):
        supervisor.deny("absolute, escape-free service path required")
    return Path(raw)


def private_bytes(path, *, limit=8192):
    if not path.is_absolute() or ".." in path.parts:
        supervisor.deny("private absolute path required")
    if any(p.is_symlink() for p in (path, *path.parents)):
        supervisor.deny("private path symlink denied")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError:
        supervisor.deny("private file unavailable")
    try:
        st = os.fstat(fd)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
                or st.st_nlink != 1 or stat.S_IMODE(st.st_mode) != 0o600
                or not 1 <= st.st_size <= limit):
            supervisor.deny("private file ownership or permission denied")
        raw = os.read(fd, limit + 1)
    finally:
        os.close(fd)
    if not 1 <= len(raw) <= limit:
        supervisor.deny("private file budget exceeded")
    return raw


def read_configuration(path):
    doc = json.loads(private_bytes(path))
    if not isinstance(doc, dict) or set(doc) != CONFIG_KEYS or doc["schema"] != 1:
        supervisor.deny("unsupported one-night schedule contract")
    paths = {}
    for key in (
        "manifest", "repo", "state_dir", "codex", "test_bwrap",
        "codex_home", "consent_file",
    ):
        paths[key] = safe_absolute(doc[key])
    if len({str(p) for p in paths.values()}) != len(paths):
        supervisor.deny("schedule paths must be distinct")
    if supervisor.overlaps(paths["state_dir"], paths["repo"]) or supervisor.overlaps(
        paths["codex_home"], paths["state_dir"]
    ) or supervisor.overlaps(paths["codex_home"], paths["repo"]):
        supervisor.deny("overlapping state, source or Codex profile")
    for name in ("codex_sha256", "test_bwrap_sha256"):
        if not isinstance(doc[name], str) or not re.fullmatch(r"[0-9a-f]{64}", doc[name]):
            supervisor.deny("invalid executable pin")
    for name, low, high in (
        ("interval_minutes", 60, 120),
        ("stage_seconds", 30, 1200),
        ("test_seconds", 15, 240),
    ):
        if type(doc[name]) is not int or not low <= doc[name] <= high:
            supervisor.deny("invalid stage or schedule time budget")
    if (not isinstance(doc["start_utc"], str)
            or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", doc["start_utc"])):
        supervisor.deny("fixed UTC start required")
    try:
        start = datetime.strptime(doc["start_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        supervisor.deny("invalid UTC calendar value")
    manifest, manifest_hash = supervisor.manifest(paths["manifest"])
    return doc, paths, start, manifest, manifest_hash


def slots(start, count, interval_minutes):
    return [start + timedelta(minutes=index * interval_minutes) for index in range(count)]


def slot_at(schedule, now):
    """Only the exact upcoming stage's 15-minute interval can execute."""
    for index, start in enumerate(schedule):
        if start <= now < start + timedelta(minutes=15):
            return index
    return None


def render(config_path, doc, paths, schedule):
    # Owner manually stores these rendered units and enables the timer.
    # Paths are restricted ASCII without spaces, newlines, % or shell syntax.
    runner = safe_absolute(doc["runner"])
    args = [
        "/usr/bin/python3", "-I", str(runner), "run",
        "--config", str(config_path),
    ]
    service = "\n".join([
        "[Unit]",
        "Description=Codex Smart one-night bounded local stage",
        "[Service]",
        "Type=oneshot",
        "UMask=0077",
        "NoNewPrivileges=true",
        "PrivateTmp=true",
        "ProtectSystem=full",
        "KillMode=control-group",
        "Restart=no",
        "TimeoutStartSec=1500",
        "ExecStart=" + " ".join(args),
        "",
    ])
    timer = "\n".join([
        "[Unit]",
        "Description=Codex Smart fixed one-night stage schedule",
        "[Timer]",
        *["OnCalendar=" + t.strftime("%Y-%m-%d %H:%M:%S UTC") for t in schedule],
        "AccuracySec=1min",
        "Persistent=false",
        "RandomizedDelaySec=0",
        "Unit=codex-smart-autodev.service",
        "[Install]",
        "WantedBy=timers.target",
        "",
    ])
    return {"service": service, "timer": timer, "activated": False}


def execute(argv=None, *, now=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("render", "run"))
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args(argv)
    doc, paths, start, manifest, _ = read_configuration(args.config)
    schedule = slots(start, len(manifest["tasks"]), doc["interval_minutes"])
    if args.action == "render":
        print(json.dumps(render(args.config, doc, paths, schedule), sort_keys=True))
        return 0
    # Nothing in render nor the GitHub PR creates the local consent marker.
    if private_bytes(paths["consent_file"], limit=128) != CONSENT:
        supervisor.deny("local one-night consent absent or invalid")
    supervisor.safe_directory(paths["state_dir"], mode=0o700)
    supervisor.safe_directory(paths["codex_home"], mode=0o700)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        supervisor.deny("timezone-aware time required")
    current = current.astimezone(timezone.utc)
    index = slot_at(schedule, current)
    if index is None:
        supervisor.deny("outside explicitly scheduled night")
    state = supervisor.load_state(paths["state_dir"])
    if state is not None:
        if state.get("phase") in ("complete", "published"):
            return 0
        if state.get("phase") != "ready":
            supervisor.deny("ambiguous stage requires operator reconciliation")
        if state.get("index") != index:
            supervisor.deny("missed or duplicated stage, no catch-up")
    elif index != 0:
        supervisor.deny("cannot begin scheduled work after missing first stage")
    command = [
        "run", "--apply", "--max-stages", "1",
        "--manifest", str(paths["manifest"]),
        "--repo", str(paths["repo"]),
        "--state-dir", str(paths["state_dir"]),
        "--codex", str(paths["codex"]),
        "--codex-sha256", doc["codex_sha256"],
        "--codex-home", str(paths["codex_home"]),
        "--test-bwrap", str(paths["test_bwrap"]),
        "--test-bwrap-sha256", doc["test_bwrap_sha256"],
        "--stage-seconds", str(doc["stage_seconds"]),
        "--test-seconds", str(doc["test_seconds"]),
    ]
    return supervisor.execute(command)


def main():
    try:
        sys.exit(execute())
    except (supervisor.Refused, OSError, ValueError) as error:
        print("Autodev schedule refused: " + type(error).__name__, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
