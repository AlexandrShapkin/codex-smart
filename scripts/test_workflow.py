"""Regression gates for isolated offline stage/document fixtures."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workflow import CONTEXT_BYTES, ROOT, Repository


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        docs = json.loads((ROOT / "docs/documents.json").read_text())
        stages = json.loads((ROOT / "docs/stages.json").read_text())
        for name in ["Cargo.toml", "docs/documents.json", "docs/stages.json",
                     "docs/issues/github-map.json", *[d["path"] for d in docs["documents"]]]:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, path)
        for stage in stages["stages"]:
            for name in stage["sources"]:
                path = self.root / name
                if path.exists():
                    continue
                if (ROOT / name).is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("isolated source placeholder\n")

    def edit(self, name, change):
        path = self.root / name
        data = json.loads(path.read_text())
        change(data)
        path.write_text(json.dumps(data))

    def snapshot(self):
        return {p.relative_to(self.root).as_posix():
                (p.read_bytes() if p.is_file() else None, p.stat().st_mtime_ns, p.stat().st_mode)
                for p in self.root.rglob("*")}

    def test_offline_deterministic_and_read_only(self):
        before = self.snapshot()
        with patch("socket.socket", side_effect=AssertionError("network")), \
                patch.object(subprocess, "run", side_effect=AssertionError("subprocess")):
            repo = Repository(self.root)
            repo.check()
            first = repo.context()
            self.assertEqual(first, repo.context())
            self.assertEqual(repo.views(), repo.views())
            self.assertLessEqual(len(first.encode()), CONTEXT_BYTES)
        self.assertEqual(before, self.snapshot())

    def test_unknown_stage_and_command_fields_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown stage"):
            Repository(self.root).context("bad; touch injected")
        self.edit("docs/stages.json", lambda d: d["stages"][0].update(command="arbitrary"))
        with self.assertRaisesRegex(ValueError, "Invalid stage"):
            Repository(self.root).validate()

    def test_dependency_cycle_and_unknown_issue_rejected(self):
        self.edit("docs/stages.json", lambda d: d["stages"][0].update(depends_on=["tools"]))
        with self.assertRaisesRegex(ValueError, "cycle"):
            Repository(self.root).validate()
        self.edit("docs/stages.json", lambda d: d["stages"][0].update(depends_on=[], issues=[999]))
        with self.assertRaisesRegex(ValueError, "GitHub mapping"):
            Repository(self.root).validate()

    def test_unowned_document_and_missing_contract_section(self):
        extra = self.root / "docs/unowned.md"
        extra.write_text("# Unowned\n")
        with self.assertRaisesRegex(ValueError, "inventory"):
            Repository(self.root).validate()
        extra.unlink()
        contract = self.root / "docs/stages/tools.md"
        contract.write_text(contract.read_text().replace("## Acceptance", "## Missing"))
        with self.assertRaisesRegex(ValueError, "sections"):
            Repository(self.root).validate()

    def test_broken_links_fragments_and_generated_drift(self):
        readme = self.root / "README.md"
        original = readme.read_text()
        for target in ["docs/nonexistent.md", "docs/workflow.md#nonexistent-fragment"]:
            readme.write_text(original + f"\n[broken]({target})\n")
            with self.assertRaises(ValueError):
                Repository(self.root).check()
        readme.write_text(original)
        (self.root / "ROADMAP.md").write_text("stale view\n")
        with self.assertRaisesRegex(ValueError, "drift"):
            Repository(self.root).check()

    def test_symlink_source_rejected(self):
        source = self.root / "crates/codex-smart-core/src/process.rs"
        source.unlink()
        source.symlink_to(self.root / "Cargo.toml")
        with self.assertRaisesRegex(ValueError, "symlinked"):
            Repository(self.root).validate()

    def test_unicode_context_is_bounded_with_explicit_followup(self):
        contract = self.root / "docs/stages/tools.md"
        contract.write_text(contract.read_text() + "\n" + "ж" * 10000)
        text = Repository(self.root).context("tools")
        self.assertLessEqual(len(text.encode()), CONTEXT_BYTES)
        self.assertIn("remaining evidence", text)
        self.assertIn("docs/stages/tools.md", text)


if __name__ == "__main__":
    unittest.main()
