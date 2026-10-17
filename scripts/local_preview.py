#!/usr/bin/env python3
"""Explicit local Linux x86_64 artifact lifecycle; no network or publication."""
import hashlib
import io
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("Linux x86_64 required")
    if len(sys.argv) not in (3, 4):
        raise ValueError("build NEW_DIRECTORY | install ARCHIVE BIN_DIRECTORY | remove ARCHIVE BIN_DIRECTORY")
    action = sys.argv[1]
    artifact = Path(sys.argv[2]).absolute()
    if action == "build" and len(sys.argv) == 3:
        artifact.mkdir(mode=0o700)  # Existing output is never replaced.
        root = Path(__file__).resolve().parent.parent
        subprocess.run(
            ["cargo", "build", "--release", "--locked", "--offline",
             "--target-dir", str(root / "target"),
             "--target", "x86_64-unknown-linux-gnu", "-p", "codex-smart-cli",
             "--bin", "codex-smart"],
            cwd=root, check=True,
        )
        source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit):
            raise ValueError("unverified source commit")
        if subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=root).strip():
            raise ValueError("build from a clean, committed source tree only")
        data = (root / "target/x86_64-unknown-linux-gnu/release/codex-smart").read_bytes()
        build_info = f"version=0.1.0-preview\ncommit={source_commit}\n".encode("ascii")
        archive = artifact / "codex-smart-0.1.0-preview-linux-x86_64.tar.gz"
        with tarfile.open(archive, "w:gz") as output:
            info = tarfile.TarInfo("codex-smart")
            info.size, info.mode = len(data), 0o755
            output.addfile(info, io.BytesIO(data))
            manifest = tarfile.TarInfo("build-info.txt")
            manifest.size, manifest.mode = len(build_info), 0o644
            output.addfile(manifest, io.BytesIO(build_info))
        archive.with_suffix(archive.suffix + ".sha256").write_text(
            digest(archive.read_bytes()) + "  " + archive.name + "\n"
        )
        print(archive)
        return
    if action not in ("install", "remove") or len(sys.argv) != 4:
        raise ValueError("invalid action/arguments")
    raw = artifact.read_bytes()
    expected = artifact.with_suffix(artifact.suffix + ".sha256").read_text()
    if expected != digest(raw) + "  " + artifact.name + "\n":
        raise ValueError("archive checksum mismatch")
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        members = archive.getmembers()
        if len(members) != 2 or {item.name for item in members} != {"codex-smart", "build-info.txt"}:
            raise ValueError("invalid archive members")
        entries = {item.name: item for item in members}
        binary, manifest = entries["codex-smart"], entries["build-info.txt"]
        if not binary.isfile() or not 0 < binary.size <= 100_000_000 or not manifest.isfile() or not 0 < manifest.size <= 200:
            raise ValueError("invalid archive types or bounds")
        lines = archive.extractfile(manifest).read().decode("ascii").splitlines()
        if len(lines) != 2 or lines[0] != "version=0.1.0-preview" or not lines[1].startswith("commit=") or len(lines[1]) != 47 or any(c not in "0123456789abcdef" for c in lines[1][7:]):
            raise ValueError("invalid source commit manifest")
        data = archive.extractfile(binary).read()
    directory = Path(sys.argv[3])
    if not directory.is_absolute() or directory.resolve() != directory:
        raise ValueError("existing absolute bin directory without symlinks required")
    if not directory.is_dir():
        raise ValueError("create the explicit bin directory first")
    target = directory / "codex-smart"
    if action == "install":
        # Exclusive creation refuses existing files and symlinks, including dangling links.
        with target.open("xb") as output:
            output.write(data)
            output.flush()
            os.fchmod(output.fileno(), 0o755)
    else:
        if target.is_symlink() or not target.is_file() or target.read_bytes() != data:
            raise ValueError("installed binary differs; refusing removal")
        target.unlink()
    print(action + " completed; PATH/config/auth unchanged")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, tarfile.TarError, subprocess.CalledProcessError):
        sys.exit("Local preview operation failed; inspect paths, checksum and prerequisites")
