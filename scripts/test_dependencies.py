"""Exercise provenance rejection in isolated repositories without Cargo/network."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CHECK = Path(__file__).with_name("check_dependencies.py").resolve()


class DependencyTests(unittest.TestCase):
    def check(self, spec):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "crates/core").mkdir(parents=True)
            (root / "crates/core/Cargo.toml").write_text(
                '[dependencies]\ntoml_edit = ' + spec + '\n'
            )
            (root / "Cargo.lock").write_text('package = []\n')
            return subprocess.run(
                [sys.executable, str(CHECK)], cwd=root, capture_output=True
            ).returncode

    def test_reviewed_pin(self):
        self.assertEqual(self.check(
            '{version="=0.25.15", default-features=false, features=["parse","display"]}'
        ), 0)

    def test_source_and_feature_overrides_fail(self):
        base = 'version="=0.25.15", default-features=false, features=["parse","display"]'
        for extra in ['path="../../unreviewed"', 'git="https://example.invalid"',
                      'package="different-crate"', 'optional=true']:
            with self.subTest(extra=extra):
                self.assertNotEqual(self.check('{' + base + ', ' + extra + '}'), 0)
        self.assertNotEqual(self.check('{version="=0.25.15", features=["parse","display"]}'), 0)


if __name__ == "__main__":
    unittest.main()
