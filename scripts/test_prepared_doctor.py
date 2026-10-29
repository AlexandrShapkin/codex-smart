import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("prepared_doctor.py")
JUSTFILE = SCRIPT.parent.parent / "justfile"


class PreparedDoctorTests(unittest.TestCase):
    def test_doctor_never_builds_fixture_or_creates_target(self):
        self.assertIsNotNone(shutil.which("just"), "just is a required developer tool")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "src").mkdir()
            (root / "scripts").mkdir()
            shutil.copyfile(SCRIPT, root / "scripts/prepared_doctor.py")
            (root / "Cargo.toml").write_text('[package]\nname="codex-smart-cli"\nversion="0.0.0"\nedition="2021"\n[[bin]]\nname="codex-smart"\npath="src/main.rs"\n')
            (root / "src/main.rs").write_text('fn main() {}')
            (root / "build.rs").write_text('fn main() { std::fs::write("build-script-ran", b"unexpected").unwrap(); }')
            # A valid lockfile lets the old --locked cargo recipe actually build.
            (root / "Cargo.lock").write_text('version = 4\n[[package]]\nname = "codex-smart-cli"\nversion = "0.0.0"\n')
            recipe = JUSTFILE.read_text().split("# Canonical nonmutating local CLI doctor", 1)[1]
            (root / "justfile").write_text("# Canonical nonmutating local CLI doctor" + recipe)
            for arguments in [[], [str(root / "missing"), "0" * 64]]:
                result = subprocess.run(["just", "--justfile", str(root / "justfile"), "doctor", *arguments],
                                        cwd=root, capture_output=True, text=True, timeout=30)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("UNAVAILABLE", result.stderr)
                self.assertFalse((root / "build-script-ran").exists())
                self.assertFalse((root / "target").exists())

    @unittest.skipUnless(sys.platform == "linux", "Linux descriptor launcher")
    def test_explicit_prepared_executable_and_digest(self):
        executable = Path("/usr/bin/true")
        self.assertTrue(executable.is_file())
        digest = hashlib.sha256(executable.read_bytes()).hexdigest()
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--executable", str(executable), "--sha256", digest],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        denied = subprocess.run([sys.executable, "-B", str(SCRIPT), "--executable", str(executable), "--sha256", "0" * 64],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(denied.returncode, 2)
        self.assertIn("UNAVAILABLE", denied.stderr)

    def test_path_discovery_and_symlink_are_not_execution_authority(self):
        with tempfile.TemporaryDirectory() as raw:
            alias = Path(raw) / "alias"
            alias.symlink_to("/usr/bin/true")
            digest = hashlib.sha256(Path("/usr/bin/true").read_bytes()).hexdigest()
            for executable in ["true", str(alias)]:
                result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--executable", executable, "--sha256", digest],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
