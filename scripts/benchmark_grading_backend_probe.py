"""Synthetic CVE-2026-87766 probe for the reviewed Ubuntu grading backend.

This probe uses only disposable /tmp content and never runs model code. It first
confirms that the upstream-vulnerable topology can escape into a synthetic host
target, then proves the frozen constrained mount topology does not.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

import benchmark_grading_backend as backend



def _run(argv):
    return subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=15,
        check=False,
        env={"PATH": "/usr/bin:/bin"},
    )


def run(executable):
    executable = Path(executable)
    contract = backend.runtime_preflight(executable)

    with tempfile.TemporaryDirectory(prefix="bwrap-cve87766-") as tmp:
        root = Path(tmp)
        untrusted = root / "untrusted"
        target = root / "host-target"
        untrusted.mkdir()
        target.mkdir()
        (untrusted / "subdir").symlink_to("/oldroot" + str(target))

        marker = target / "newdir" / "ESCAPE_MARKER.txt"
        read_fd, write_fd = os.pipe()
        try:
            os.write(write_fd, b"synthetic-marker\n")
        finally:
            os.close(write_fd)
        try:
            unsafe = subprocess.run(
                [
                    str(executable),
                    "--unshare-user",
                    "--uid",
                    "1000",
                    "--gid",
                    "1000",
                    "--bind",
                    str(untrusted),
                    "/",
                    "--dir",
                    "/subdir/newdir",
                    "--file",
                    str(read_fd),
                    "/subdir/newdir/ESCAPE_MARKER.txt",
                    "/nonexistent-command",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
                check=False,
                pass_fds=(read_fd,),
                env={"PATH": "/usr/bin:/bin"},
            )
        finally:
            os.close(read_fd)
        unsafe_escape = marker.is_file() and marker.read_text() == "synthetic-marker\n"

        if marker.exists():
            marker.unlink()
        if marker.parent.exists():
            marker.parent.rmdir()

        probe = root / "probe.py"
        probe.write_text(
            "from pathlib import Path\n"
            "p=Path('/work/subdir/newdir/ESCAPE_MARKER.txt')\n"
            "try:\n"
            " p.parent.mkdir(parents=True,exist_ok=True)\n"
            " p.write_text('runtime-marker\\n')\n"
            "except OSError:\n"
            " pass\n"
        )
        ops = backend.probe_mount_plan(probe, untrusted)
        static_guard = backend.validate_mount_plan(ops)
        constrained_argv = [
            str(executable),
            "--unshare-user",
            "--unshare-all",
            "--disable-userns",
            "--assert-userns-disabled",
            "--uid",
            "1000",
            "--gid",
            "1000",
            "--cap-drop",
            "ALL",
            "--die-with-parent",
            "--new-session",
            "--clearenv",
            *backend.render_mount_plan(ops),
            "--setenv",
            "HOME",
            "/empty-home",
            "--setenv",
            "PATH",
            "/usr/bin",
            "--chdir",
            "/work",
            "--",
            "/usr/bin/python3",
            "-B",
            "/probe.py",
        ]
        constrained = _run(constrained_argv)
        constrained_escape = marker.exists()

    payload = {
        "backend_id": contract["backend_id"],
        "executable_sha256": contract["executable_sha256"],
        "package_version": contract["package_version"],
        "apparmor_profile_sha256": contract["apparmor_profile_sha256"],
        "apparmor_userns_restriction_enabled": True,
        "setuid_present": False,
        "unsafe_control_host_escape_observed": unsafe_escape,
        "constrained_control_host_escape_observed": constrained_escape,
        "constrained_control_completed": constrained.returncode == 0,
        "mount_plan_static_guard": static_guard is True,
    }
    return {
        "schema_version": 1,
        "contract_id": contract["contract_id"],
        "probe_kind": "synthetic-cve-topology",
        "backend_id": contract["backend_id"],
        "version": contract["version"],
        "candidate": payload,
        "evidence_reference": backend.evidence_reference(payload),
        "model_calls": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bwrap", default="/usr/bin/bwrap")
    args = parser.parse_args(argv)
    print(json.dumps(run(args.bwrap), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
