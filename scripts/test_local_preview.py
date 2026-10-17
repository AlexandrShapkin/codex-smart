"""Offline artifact lifecycle negative controls; never execute an installed artifact."""
import hashlib
import io
import platform
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest


@unittest.skipUnless(platform.system() == "Linux" and platform.machine() == "x86_64", "Linux x86_64 helper")
class LocalPreviewTests(unittest.TestCase):
    def test_install_collision_checksum_and_owned_removal(self):
        script = Path(__file__).with_name("local_preview.py")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            archive = root / "preview.tar.gz"
            payload = b"fake executable, never executed"
            with tarfile.open(archive, "w:gz") as output:
                info = tarfile.TarInfo("codex-smart")
                info.size = len(payload)
                output.addfile(info, io.BytesIO(payload))
                manifest = b"version=0.1.0-preview\ncommit=" + b"0" * 40 + b"\n"
                details = tarfile.TarInfo("build-info.txt")
                details.size = len(manifest)
                output.addfile(details, io.BytesIO(manifest))
            checksum = archive.with_suffix(".gz.sha256")
            checksum.write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "  preview.tar.gz\n")
            destination = root / "bin"
            destination.mkdir()

            def run(action):
                return subprocess.run([sys.executable, str(script), action, str(archive), str(destination)], capture_output=True).returncode

            self.assertEqual(run("install"), 0)
            self.assertEqual((destination / "codex-smart").read_bytes(), payload)
            self.assertNotEqual(run("install"), 0)
            (destination / "codex-smart").write_bytes(b"other installation")
            self.assertNotEqual(run("remove"), 0)
            (destination / "codex-smart").write_bytes(payload)
            checksum.write_text("wrong")
            self.assertNotEqual(run("remove"), 0)
            checksum.write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + "  preview.tar.gz\n")
            self.assertEqual(run("remove"), 0)
            (destination / "codex-smart").symlink_to(root / "missing")
            self.assertNotEqual(run("install"), 0)
            self.assertNotEqual(run("remove"), 0)
