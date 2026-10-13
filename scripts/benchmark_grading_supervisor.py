"""Trusted host-side supervisor for one isolated grading service."""

import subprocess
import sys


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2 or argv[0] != "--":
        return 64
    command = argv[1:]
    try:
        child = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return child.wait()
    except OSError:
        return 65


if __name__ == "__main__":
    raise SystemExit(main())
