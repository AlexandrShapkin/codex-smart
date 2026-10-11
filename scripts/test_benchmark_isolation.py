import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import benchmark_isolation as isolation


class IsolationTests(unittest.TestCase):
    def test_missing_backend_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(isolation, 'BWRAP', Path(tmp)/'missing'), \
             patch.object(isolation.subprocess, 'run') as run, patch.object(isolation, '_probe') as probe:
            evidence = isolation.availability()
            self.assertEqual(evidence.status, 'unavailable')
            report = isolation.probe()
            self.assertTrue(all(value == 'not-run' for value in report['checks'].values()))
            self.assertFalse(isolation.grade('python-api', Path(tmp)).quality_pass)
            run.assert_not_called()
            probe.assert_not_called()

    def test_version_and_privilege_drift_block(self):
        with patch.object(isolation.BWRAP.__class__, 'is_file', return_value=True), \
             patch.object(isolation.BWRAP.__class__, 'stat', return_value=SimpleNamespace(st_mode=0o755)), \
             patch.object(isolation.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='bubblewrap other')):
            self.assertEqual(isolation.availability().reason, 'backend-version-unreviewed')
            with patch.object(isolation.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=isolation.VERSION)):
                self.assertEqual(isolation.availability().status, 'blocked')
                self.assertEqual(isolation.availability().reason, 'aggregate-resource-controls-not-verified')
            with patch.object(isolation.BWRAP.__class__, 'stat', return_value=SimpleNamespace(st_mode=stat.S_ISUID|0o755)):
                self.assertEqual(isolation.availability().reason, 'privileged-backend-rejected')

    def test_all_graders_refuse_without_backend_and_never_read_submission(self):
        for status in ['unavailable', 'blocked']:
            with patch.object(isolation, 'availability', return_value=isolation.IsolationAvailability(status, 'test-blocker')), \
                 patch.object(isolation.subprocess, 'Popen') as execute, patch.object(Path, 'read_text') as read:
                for scenario in ['python-api', 'python-tests', 'rust-clamp', 'go-total', 'iac-security']:
                    result = isolation.grade(scenario, Path('/untrusted-submission'))
                    self.assertFalse(result.quality_pass)
                    self.assertEqual(result.status, status)
                execute.assert_not_called()
                read.assert_not_called()

    def test_local_synthetic_namespace_evidence_never_promotes_backend(self):
        report = isolation.probe()
        self.assertIn(report['availability']['status'], ['unavailable', 'blocked'])
        self.assertEqual(report['grader_compatibility'], 'not-verified')
        self.assertNotIn('synthetic-sentinel-only', json.dumps(report))
        self.assertNotIn('/home/', json.dumps(report))
        self.assertEqual(set(report['checks']), {'filesystem','symlink','environment','tcp','udp',
                                               'process-cleanup','immutable-probe'})
        if all(value == 'passed' for value in report['checks'].values()):
            self.assertEqual(report['resource_controls'], 'not-verified')
            self.assertEqual(report['runtime_inventory'], 'not-verified')
        else:
            # Unavailable/failed namespace tests are evidence of a blocker, never
            # counted as successful escapes or accepted grading compatibility.
            self.assertNotEqual(report['availability']['status'], 'verified')

    def test_probe_interruption_kills_controller_group_and_reaps(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(isolation.subprocess, 'Popen') as spawn, \
             patch.object(isolation.os, 'killpg') as kill:
            spawn.return_value.pid = 12345
            spawn.return_value.wait.side_effect = [KeyboardInterrupt, 0]
            with self.assertRaises(KeyboardInterrupt):
                isolation._probe('pass', Path(tmp))
            kill.assert_called_once_with(12345, isolation.signal.SIGKILL)
            self.assertEqual(spawn.return_value.wait.call_count, 2)
            self.assertEqual(spawn.call_args.kwargs['env'], {'PATH': '/usr/bin'})
            self.assertTrue(spawn.call_args.kwargs['close_fds'])


if __name__ == '__main__':
    unittest.main()
