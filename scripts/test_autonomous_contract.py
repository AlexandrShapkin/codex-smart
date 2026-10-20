"""Offline, negative-first tests for the metadata-only #165 contract."""

from pathlib import Path
import tempfile
import unittest

import autonomous_contract as contract

MAIN = "a" * 40
PROFILES = frozenset({"rust-format", "rust-clippy", "rust-tests", "rust-release", "python-tests"})


def source(*, kind="rust-workspace", profiles=None):
    if profiles is None:
        profiles = ["rust-format", "rust-tests"] if kind == "rust-workspace" else ["python-tests"]
    profile_toml = ", ".join(f'"{p}"' for p in profiles)
    return f'''schema_version = 1
project_id = "fixture"
project_type = "{kind}"
repository = "Owner/fixture"

[context]
entrypoint = "AGENTS.md"
architecture = "docs/architecture.md"
workflow = "docs/workflow.md"
current_plan = "ROADMAP.md"
security = "SECURITY.md"
task_source = "github-issues"

[verification]
profiles = [{profile_toml}]
ci_workflows = [".github/workflows/ci.yml"]
live_device_proof = "separate"

[execution]
enabled = false
max_stage_seconds = 1200
max_changed_files = 2
max_changed_lines = 180
checkpoint_mode = "external-private"
auto_merge = false
auto_deploy = false

[change_policy]
candidate_paths = ["crates/", "docs/"]
blocked_unattended_paths = ["deploy/", ".github/"]
'''.encode()


class PassiveContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "worktree"
        self.root.mkdir()
        for rel in ("AGENTS.md", "docs/architecture.md", "docs/workflow.md", "ROADMAP.md",
                    "SECURITY.md", ".github/workflows/ci.yml"):
            file = self.root / rel
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("fixture\n")
        self.kw = dict(root=self.root, expected_repository="Owner/fixture",
                       expected_project_id="fixture", accepted_main_sha=MAIN,
                       checkout_sha=MAIN, checkout_clean=True, trusted_profile_ids=PROFILES)

    def validate(self, data=None, **changed):
        return contract.validate_contract(source() if data is None else data,
                                          **(self.kw | changed))

    def denied(self, data=None, **changed):
        with self.assertRaises(contract.ContractRefused):
            self.validate(data, **changed)

    def replace(self, before, after, data=None):
        value = source() if data is None else data
        assert before.encode() in value
        return value.replace(before.encode(), after.encode())

    def test_valid_rust_and_python_are_inert_metadata(self):
        for kind in ("rust-workspace", "python-stdlib", "python-project"):
            doc = self.validate(source(kind=kind))
            self.assertIs(doc["execution"]["enabled"], False)
            self.assertIs(doc["execution"]["auto_merge"], False)

    def test_reject_unknown_version_and_unknown_fields(self):
        self.denied(self.replace("schema_version = 1", "schema_version = 2"))
        self.denied(self.replace("schema_version = 1", "schema_version = true"))
        self.denied(source() + b'command = "sh -c evil"\n')  # added in last table
        self.denied(self.replace('task_source = "github-issues"', 'task_source = "github-issues"\nexecute = "sh -c true"'))

    def test_reject_malformed_and_duplicate_toml(self):
        self.denied(b"\xff")
        self.denied(b"")
        self.denied(b"a" * (contract.MAX_BYTES + 1))
        self.denied(source() + b"\n[execution]\nenabled = false\n")

    def test_reject_unverified_identity_or_snapshots(self):
        self.denied(expected_repository="Different/repo")
        self.denied(expected_project_id="different")
        self.denied(accepted_main_sha="b" * 40)
        self.denied(checkout_sha="b" * 40)
        self.denied(checkout_sha="a" * 7)
        self.denied(checkout_clean=False)
        self.denied(checkout_clean=1)
        self.denied(accepted_main_sha="A" * 40)

    def test_reject_missing_or_untrusted_profiles(self):
        self.denied(self.replace('"rust-tests"', '"sh -c id"'))
        self.denied(self.replace('"rust-tests"', '"rust-unknown"'))
        self.denied(self.replace('"rust-tests"', '"rust-format"'))
        self.denied(trusted_profile_ids=frozenset({"rust-format"}))
        self.denied(self.replace('"rust-tests"', '"rust-clippy"'))
        self.denied(source(kind="python-project", profiles=["rust-tests"]))
        self.denied(source(kind="mixed", profiles=["rust-tests"]))
        self.validate(source(kind="mixed", profiles=["rust-tests", "python-tests"]))

    def test_reject_execution_and_weak_limits(self):
        for key in ("enabled", "auto_merge", "auto_deploy"):
            self.denied(self.replace(f"{key} = false", f"{key} = true"))
        self.denied(self.replace("max_changed_lines = 180", "max_changed_lines = 999999"))
        self.denied(self.replace("max_changed_files = 2", "max_changed_files = 0"))
        self.denied(self.replace("max_stage_seconds = 1200", "max_stage_seconds = true"))
        self.denied(self.replace('checkpoint_mode = "external-private"', 'checkpoint_mode = "git"'))

    def test_reject_paths_traversal_and_noncanonical(self):
        for bad in ("../secret", "/etc/passwd", "docs//architecture.md", "docs/./architecture.md",
                    "docs/../architecture.md", "docs\\architecture.md", ".git/config",
                    "https://example.org/file", "docs/%2e%2e/secret"):
            self.denied(self.replace('architecture = "docs/architecture.md"', f'architecture = "{bad}"'))
        self.denied(self.replace('candidate_paths = ["crates/", "docs/"]',
                                 'candidate_paths = ["docs", "docs/"]'))
        self.denied(self.replace('blocked_unattended_paths = ["deploy/", ".github/"]',
                                 'blocked_unattended_paths = ["docs/", ".github/"]'))

    def test_reject_symlinks_and_missing_context(self):
        target = self.root / "docs/architecture.md"
        target.unlink()
        target.symlink_to(self.root / "SECURITY.md")
        self.denied()
        target.unlink()
        self.denied()

    def test_reject_symlinked_policy_path(self):
        (self.root / "deploy").symlink_to(self.root / "docs", target_is_directory=True)
        self.denied()

    def test_reject_untrusted_ci_and_missing_workflow(self):
        self.denied(self.replace('.github/workflows/ci.yml', 'docs/workflow.md'))
        self.denied(self.replace('.github/workflows/ci.yml', '.github/workflows/missing.yml'))
        self.denied(self.replace('live_device_proof = "separate"', 'live_device_proof = "verified"'))

    def test_reject_unrecognized_queue_and_project_type(self):
        self.denied(self.replace('task_source = "github-issues"', 'task_source = "docs/roadmap.md"'))
        self.denied(self.replace('project_type = "rust-workspace"', 'project_type = "linux-host-admin"'))
        self.denied(self.replace('repository = "Owner/fixture"', 'repository = "Owner/../fixture"'))

    def test_reject_root_lexical_parent_component(self):
        # Path.is_absolute/is_dir accept this alias when the middle dir exists.
        detour = self.root.parent / "detour"
        detour.mkdir()
        alias = detour / ".." / "worktree"
        self.assertTrue(alias.is_absolute())
        self.assertTrue(alias.is_dir())
        self.assertIn("..", alias.parts)
        self.denied(root=alias)

    def test_reject_root_symlink(self):
        link = Path(self.temp.name) / "shortcut"
        link.symlink_to(self.root, target_is_directory=True)
        self.denied(root=link)


if __name__ == "__main__":
    unittest.main()
