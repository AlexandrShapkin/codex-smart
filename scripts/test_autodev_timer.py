"""Deterministic, source-only tests of the one-night systemd renderer."""
import hashlib
import importlib.util
import io
import json
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name("autodev_timer.py")
spec = importlib.util.spec_from_file_location("autodev_timer", SCRIPT)
timer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timer)


class NightScheduleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="night-plan-")
        self.addCleanup(self.temp.cleanup)
        home = Path(self.temp.name)
        self.base = home
        self.repo = home / "dedicated-repo"
        self.repo.mkdir()
        self.state = home / "receipts"
        self.state.mkdir(mode=0o700)
        self.codex_home = home / "profile"
        self.codex_home.mkdir(mode=0o700)
        self.manifest = home / "manifest.json"
        self.manifest.write_text(json.dumps({
            "schema": 1, "expected_sha": "a" * 40,
            "repository": "AlexandrShapkin/sandbox",
            "tasks": [
                {"id": f"stage-{n}", "prompt": f"Add test stage {n}",
                 "paths": ["small.py"]}
                for n in range(3)
            ],
        }))
        self.manifest.chmod(0o600)
        self.grant = home / "allow-once"
        self.grant.write_bytes(timer.CONSENT)
        self.grant.chmod(0o600)
        self.config = home / "configuration.json"
        self.start = datetime(2026, 10, 21, 0, 15, tzinfo=timezone.utc)
        self.doc = {
            "schema": 1,
            "manifest": str(self.manifest),
            "repo": str(self.repo),
            "state_dir": str(self.state),
            "codex": "/usr/bin/codex",
            "codex_sha256": "b" * 64,
            "test_bwrap": "/usr/bin/bwrap",
            "test_bwrap_sha256": "c" * 64,
            "codex_home": str(self.codex_home),
            "consent_file": str(self.grant),
            "runner": str(SCRIPT),
            "start_utc": "2026-10-21T00:15:00Z",
            "interval_minutes": 60,
            "stage_seconds": 900,
            "test_seconds": 120,
        }
        self.write_config()

    def write_config(self):
        self.config.write_text(json.dumps(self.doc))
        self.config.chmod(0o600)

    def call(self, action, *, now=None):
        return timer.execute([action, "--config", str(self.config)], now=now)

    def test_render_is_inert_exactly_three_utc_occurrences(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(self.call("render"), 0)
        units = json.loads(output.getvalue())
        self.assertEqual(units["activated"], False)
        self.assertEqual(units["timer"].count("OnCalendar="), 3)
        self.assertIn("OnCalendar=2026-10-21 00:15:00 UTC", units["timer"])
        self.assertIn("OnCalendar=2026-10-21 02:15:00 UTC", units["timer"])
        self.assertIn("Persistent=false", units["timer"])
        self.assertIn("NoNewPrivileges=true", units["service"])
        self.assertIn("autodev_timer.py run --config", units["service"])
        self.assertNotIn("--publish-draft", units["service"])
        self.assertFalse((self.state / "state.json").exists())

    def test_first_slot_runs_one_stage_without_auto_publish(self):
        with mock.patch.object(timer.supervisor, "execute", return_value=0) as run:
            self.assertEqual(self.call("run", now=self.start + timedelta(minutes=1)), 0)
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[0], "run")
        self.assertEqual(cmd[cmd.index("--max-stages") + 1], "1")
        self.assertIn("--apply", cmd)
        self.assertNotIn("--publish-draft", cmd)

    def test_missing_or_readable_grant_never_executes(self):
        self.grant.unlink()
        with mock.patch.object(timer.supervisor, "execute") as worker:
            with self.assertRaises(timer.supervisor.Refused):
                self.call("run", now=self.start)
            worker.assert_not_called()
        self.grant.write_bytes(timer.CONSENT)
        self.grant.chmod(0o644)
        with self.assertRaises(timer.supervisor.Refused):
            self.call("run", now=self.start)

    def test_missed_first_stage_blocks_later_invocation(self):
        with mock.patch.object(timer.supervisor, "execute") as worker:
            with self.assertRaises(timer.supervisor.Refused):
                self.call("run", now=self.start + timedelta(minutes=61))
            worker.assert_not_called()

    def test_started_receipt_is_not_retried(self):
        _, _, _, doc, sha = timer.read_configuration(self.config)
        timer.supervisor.save_state(self.state, {
            "schema": 1, "manifest_sha256": sha, "phase": "started",
            "head": doc["expected_sha"], "branch": "autodev/sample",
            "index": 0, "commits": [],
        })
        with mock.patch.object(timer.supervisor, "execute") as worker:
            with self.assertRaises(timer.supervisor.Refused):
                self.call("run", now=self.start)
            worker.assert_not_called()

    def test_next_slot_only_after_verified_checkpoint(self):
        _, _, _, doc, sha = timer.read_configuration(self.config)
        timer.supervisor.save_state(self.state, {
            "schema": 1, "manifest_sha256": sha, "phase": "ready",
            "head": "d" * 40, "branch": "autodev/sample",
            "index": 1, "commits": [{"task_id": "stage-0", "sha": "d" * 40}],
        })
        with mock.patch.object(timer.supervisor, "execute", return_value=0) as worker:
            self.assertEqual(self.call("run", now=self.start + timedelta(minutes=61)), 0)
            worker.assert_called_once()
        with mock.patch.object(timer.supervisor, "execute") as worker:
            with self.assertRaises(timer.supervisor.Refused):
                self.call("run", now=self.start + timedelta(minutes=121))
            worker.assert_not_called()

    def test_invalid_time_and_world_readable_configuration_refused(self):
        self.doc["start_utc"] = "2026-02-31T00:15:00Z"
        self.write_config()
        with self.assertRaises(timer.supervisor.Refused):
            self.call("render")
        self.doc["start_utc"] = "2026-10-21T00:15:00Z"
        self.write_config()
        self.config.chmod(0o644)
        with self.assertRaises(timer.supervisor.Refused):
            self.call("render")


if __name__ == "__main__":
    unittest.main()
