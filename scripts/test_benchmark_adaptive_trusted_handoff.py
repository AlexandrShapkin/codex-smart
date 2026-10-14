"""Fake-only authentication/transport tests for the adaptive grading handoff."""

import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import benchmark_adaptive_campaign as live
import benchmark_adaptive_trusted_handoff as handoff


class TrustedHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        d = self.root / ".ssh"
        d.mkdir(mode=0o700)
        self.known_hosts = d / "known_hosts"
        self.known_hosts.write_text("fake-ed25519-pinned-key\n")
        self.known_hosts.chmod(0o600)
        self.remote = "/tmp/adaptive-lifecycle-graded-round1/summary.json"
        self.digest = "a" * 64

    def fake_run(self, *, fingerprint=None, digest=None, failure=None):
        observed = []
        def run(argv, **kwargs):
            observed.append(argv)
            if failure and (failure in argv or failure == "all"):
                return subprocess.CompletedProcess(argv, 255, "", "refused")
            if "-G" in argv:
                stdout = "hostname 192.168.88.128\nport 22128\n"
            elif argv[0] == handoff.SSH_KEYGEN:
                sha = fingerprint if fingerprint is not None else handoff.TRUSTED_ED25519_SHA256
                stdout = (
                    "# Host [192.168.88.128]:22128 found: line 12\n"
                    f"[192.168.88.128]:22128 ED25519 {sha}\n"
                )
            else:
                stdout = (digest if digest is not None else self.digest) + "\n"
            return subprocess.CompletedProcess(argv, 0, stdout, "")
        return run, observed

    def verified(self, run):
        with patch.object(handoff.Path, "home", return_value=self.root):
            return handoff.pinned_srv0_summary_sha256(self.remote, run=run)

    def test_valid_pinned_ssh_response_is_the_only_accepted_digest(self):
        fake, calls = self.fake_run()
        self.assertEqual(self.verified(fake), self.digest)
        self.assertEqual(len(calls), 3)
        self.assertIn(f"HostKeyAlias=[192.168.88.128]:22128", calls[2])
        self.assertIn("StrictHostKeyChecking=yes", calls[2])
        self.assertIn("HostKeyAlgorithms=ssh-ed25519", calls[2])
        self.assertIn("BatchMode=yes", calls[2])
        self.assertIn("realpath", calls[2][-1])
        self.assertIn(self.remote, calls[2][-1])
        self.assertEqual(calls[2][-2], handoff.TRUSTED_ALIAS)

    def test_forwarding_is_disabled_even_when_fake_config_enables_it(self):
        config = self.root / "offline-ssh-config"
        config.write_text("Host fake-grader\n Hostname 127.0.0.1\n CanonicalizeHostname no\n ForwardAgent yes\n ForwardX11 yes\n")
        # -G resolves ONLY a disposable fixture: no connection or campaign credentials.
        reply = subprocess.run([handoff.SSH, "-F", str(config), *handoff._ssh_options(self.known_hosts),
                                "-G", "fake-grader"], check=True, capture_output=True, text=True, timeout=5)
        values = dict(line.split(" ", 1) for line in reply.stdout.splitlines() if " " in line)
        self.assertEqual(values["forwardagent"], "no")
        self.assertEqual(values["forwardx11"], "no")

    def test_bad_host_key_and_missing_known_hosts_refuse(self):
        fake, _ = self.fake_run(fingerprint="SHA256:malicious")
        with self.assertRaisesRegex(handoff.GradingHandoffRefusal, "pin mismatch"):
            self.verified(fake)
        self.known_hosts.unlink()
        with self.assertRaisesRegex(handoff.GradingHandoffRefusal, "known_hosts missing"):
            self.verified(fake)

    def test_world_writable_known_hosts_refused_before_ssh(self):
        self.known_hosts.chmod(0o666)
        fake, calls = self.fake_run()
        with self.assertRaisesRegex(handoff.GradingHandoffRefusal, "ownership or mode"):
            self.verified(fake)
        self.assertEqual(calls, [])

    def test_untrusted_path_refused_before_ssh(self):
        fake, calls = self.fake_run()
        bad = (
            "summary.json", "/home/user/summary.json",
            "/tmp/../etc/passwd/summary.json",
            "/tmp/ab/summary.json;touch injected",
            "/tmp/ab/summary.json\nmalicious",
            "/tmp/ab/x\"/summary.json",
            "/tmp/ab/summary.json/other",
        )
        for remote in bad:
            with self.subTest(remote=remote):
                with patch.object(handoff.Path, "home", return_value=self.root):
                    with self.assertRaisesRegex(handoff.GradingHandoffRefusal, "unsafe remote"):
                        handoff.pinned_srv0_summary_sha256(remote, run=fake)
        self.assertEqual(calls, [])

    def test_ssh_failure_or_malformed_digest_refused(self):
        for response in ("not-digest", "a"*64+"\n"+"b"*64, ""):
            fake, _ = self.fake_run(digest=response)
            with self.subTest(digest=response):
                with self.assertRaisesRegex(handoff.GradingHandoffRefusal, "invalid trusted"):
                    self.verified(fake)
        fake, _ = self.fake_run(failure="all")
        with self.assertRaisesRegex(handoff.GradingHandoffRefusal, "SSH command rejected"):
            self.verified(fake)

    def test_local_grade_and_supplied_digest_must_match_authenticated_remote(self):
        grades = self.root / "grades"
        grades.mkdir()
        (grades / "summary.json").write_text("legitimate grade\n")
        digest = live._sha256(grades / "summary.json")
        with patch.object(live.trusted_handoff, "pinned_srv0_summary_sha256", return_value=digest) as remote:
            self.assertEqual(live._trusted_grade_digest(self.remote, grades), digest)
            with self.assertRaisesRegex(live.AdaptiveCampaignRefusal, "supplied digest"):
                live._trusted_grade_digest(self.remote, grades, "0"*64)
            (grades / "summary.json").write_text("modified\n")
            with self.assertRaisesRegex(live.AdaptiveCampaignRefusal, "differs"):
                live._trusted_grade_digest(self.remote, grades)
            remote.assert_called()

    def test_cli_retry_refuses_manual_hash_without_authenticated_origin(self):
        with patch.object(live, "run_retry", side_effect=AssertionError("would execute")):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as refused:
                    live.main([
                        "--retry-agent", "--authorize-execution",
                        "--initial-grades", "/tmp/fake-round1",
                        "--initial-grades-sha256", "a"*64,
                    ])
        self.assertEqual(refused.exception.code, 2)

    def test_cli_refuses_before_ssh_without_authorization(self):
        with patch.object(live, "_trusted_grade_digest", side_effect=AssertionError("called")):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as refused:
                    live.main(["--retry-agent", "--trusted-initial-remote-summary", self.remote])
        self.assertEqual(refused.exception.code, 2)

    def test_cli_pins_retry_and_finalization_from_authenticated_receipts(self):
        with patch.object(live, "_trusted_grade_digest", side_effect=["1"*64, "2"*64]) as verify:
            with patch.object(live, "finalize", return_value={"safe": True}) as finish:
                with contextlib.redirect_stdout(io.StringIO()):
                    live.main([
                        "--finalize", "--initial-grades", "/tmp/local-initial",
                        "--retry-grades", "/tmp/local-retry",
                        "--agent-artifacts", "/tmp/agent", "--output-dir", "/tmp/final",
                        "--trusted-initial-remote-summary", self.remote,
                        "--trusted-retry-remote-summary", "/tmp/adaptive-lifecycle-graded-round2/summary.json",
                    ])
                self.assertEqual(finish.call_args.kwargs["initial_grades_sha256"], "1"*64)
                self.assertEqual(finish.call_args.kwargs["retry_grades_sha256"], "2"*64)
                self.assertEqual(verify.call_count, 2)
        with patch.object(live, "_trusted_grade_digest", return_value="b"*64) as verify:
            with patch.object(live, "run_retry", return_value={"safe": True}) as retry:
                with contextlib.redirect_stdout(io.StringIO()):
                    live.main([
                        "--retry-agent", "--authorize-execution",
                        "--initial-grades", "/tmp/local-initial",
                        "--trusted-initial-remote-summary", self.remote,
                    ])
                self.assertEqual(retry.call_args.kwargs["initial_grades_sha256"], "b"*64)
                self.assertEqual(verify.call_count, 1)


if __name__ == "__main__":
    unittest.main()
