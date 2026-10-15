import errno
import json
import subprocess
import unittest
from unittest.mock import patch

import diagnose_rust_clamp as diagnostic


class DiagnosticsTests(unittest.TestCase):
    def test_exit_and_privacy(self):
        records = []
        result = subprocess.CompletedProcess([], -9, b'private stdout',
                                            b'private source\nerror[E0308]\nCannot allocate memory')
        with patch.object(diagnostic.time, 'monotonic', side_effect=[1, 1.125]):
            self.assertIs(diagnostic.observe(lambda *a, **k: result, records,
                                            ['rustc', 'private-path'], timeout=25), result)
        self.assertEqual(records[0]['exit_code'], -9)
        self.assertEqual(records[0]['duration_ms'], 125)
        self.assertEqual(records[0]['stderr'], ['memory-pressure', 'compiler-error'])
        self.assertNotIn('private', json.dumps(records))
        self.assertEqual(diagnostic.safe_stderr(b'x' * 8192 + b'assertion'), [])

    def test_timeout_and_launch_failure_retained(self):
        for error in [subprocess.TimeoutExpired('private', 25, stderr=b'private assertion'),
                      OSError(errno.EAGAIN, 'private')]:
            records = []
            def fail(*args, **kwargs):
                raise error
            with self.assertRaises(type(error)):
                diagnostic.observe(fail, records, ['rustc'], timeout=25)
            self.assertEqual(len(records), 1)
            self.assertIsNone(records[0]['exit_code'])
            self.assertNotIn('private', json.dumps(records))
            self.assertEqual(records[0]['timed_out'], isinstance(error, subprocess.TimeoutExpired))

    def test_controls_and_compiler_failure(self):
        for broken in (False, True):
            def run(argv, **kwargs):
                self.assertEqual(kwargs['timeout'], 25)
                if argv[0] == 'rustc':
                    return subprocess.CompletedProcess(argv, 1 if broken else 0, b'', b'')
                # Correct reference first, then both negative controls.
                run.tests += 1
                return subprocess.CompletedProcess(argv, 0 if run.tests == 1 else 101, b'', b'assertion')
            run.tests = 0
            with patch.object(diagnostic.subprocess, 'run', side_effect=run):
                result = diagnostic.diagnose()
            self.assertEqual([r['control_ok'] for r in result['controls']], [not broken] * 3)
            if broken:
                self.assertTrue(all(not r['quality_pass'] for r in result['controls']))

    def test_signals_and_timeouts_do_not_validate_negative_controls(self):
        for failure in (-9, 'timeout'):
            def run(argv, **kwargs):
                if argv[0] == 'rustc':
                    return subprocess.CompletedProcess(argv, 0, b'', b'')
                if failure == 'timeout':
                    raise subprocess.TimeoutExpired(argv, 25, stderr=b'private')
                return subprocess.CompletedProcess(argv, failure, b'', b'private')
            with patch.object(diagnostic.subprocess, 'run', side_effect=run):
                result = diagnostic.diagnose()
            self.assertTrue(all(not r['control_ok'] for r in result['controls']))
            self.assertNotIn('private', json.dumps(result))
