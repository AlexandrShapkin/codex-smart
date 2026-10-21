"""Run an explicitly trusted prepared doctor binary; never discover, build or install."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", default="")
    parser.add_argument("--sha256", default="")
    args = parser.parse_args(argv)
    if not Path(args.executable).is_absolute() or not re.fullmatch(r"[a-fA-F0-9]{64}", args.sha256):
        print("UNAVAILABLE: provide a trusted prepared absolute executable and its SHA-256; no build or download attempted", file=sys.stderr)
        return 2
    if sys.platform != "linux" or not Path("/proc/self/fd").is_dir():
        print("UNAVAILABLE: descriptor-pinned doctor launcher requires Linux /proc", file=sys.stderr)
        return 2
    descriptor = None
    try:
        descriptor = os.open(args.executable, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o022
                or not metadata.st_mode & 0o111
                or metadata.st_size > 128 * 1024 * 1024):
            raise ValueError("untrusted executable")
        with os.fdopen(os.dup(descriptor), "rb") as binary:
            digest = hashlib.file_digest(binary, "sha256").hexdigest()
        if digest != args.sha256.lower():
            raise ValueError("executable digest mismatch")
        os.lseek(descriptor, 0, os.SEEK_SET)
        # Execute the verified inode even if the pathname is replaced afterwards.
        return subprocess.run([f"/proc/self/fd/{descriptor}", "doctor"],
                              pass_fds=(descriptor,), check=False, timeout=30).returncode
    except (OSError, ValueError, subprocess.TimeoutExpired):
        print("UNAVAILABLE: trusted prepared doctor could not be verified or run; no build or download attempted", file=sys.stderr)
        return 2
    finally:
        if descriptor is not None:
            os.close(descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
