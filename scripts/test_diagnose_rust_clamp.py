import errno
import json
from pathlib import Path
import sys
import tempfile
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

    def test_selected_control_and_real_constrained_compiler(self):
        # A real child under a zero file-size limit fails to write its output.
        # This is a synthetic constraint, not evidence about historical CI hosts.
        if sys.platform != 'linux':
            self.skipTest('Linux resource limits required')
        with tempfile.TemporaryDirectory() as tmp:
            compiler = Path(tmp) / 'rustc'
            compiler.write_text('#!' + sys.executable + '\n'
                                'import resource\n'
                                'resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))\n'
                                'try:\n'
                                '    with open("test", "wb") as f: f.write(b"x"); f.flush()\n'
                                'except OSError:\n'
                                '    raise SystemExit(7)\n')
            compiler.chmod(0o700)
            child = subprocess.run(
                [sys.executable, '-B', diagnostic.__file__, '--control', 'wrong'],
                env={'PATH': tmp}, capture_output=True, timeout=30)
            self.assertEqual(child.returncode, 1)
            result = json.loads(child.stdout)
        self.assertEqual(len(result['controls']), 1)
        row = result['controls'][0]
        self.assertFalse(row['control_ok'])
        self.assertEqual(len(row['commands']), 1)
        self.assertEqual(row['commands'][0]['phase'], 'compile')
        self.assertEqual(row['commands'][0]['exit_code'], 7)
        self.assertEqual(row['commands'][0]['stderr'], [])

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
