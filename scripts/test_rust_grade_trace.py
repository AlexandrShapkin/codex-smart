"""Isolated controls only: no model or campaign execution."""
import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import benchmark as b
import rust_grade_trace as trace


class TraceTests(unittest.TestCase):
    def events(self, code=0, **overrides):
        row = dict(event='end', phase='compile', exit_code=code, timed_out=False,
                   launch_error=None, io_error=None, launched=True, markers=[], oracle_assertion=False, duration_ms=1)
        row.update(overrides)
        return (json.dumps(dict(event='start', phase='compile')) + '\n' + json.dumps(row) + '\n').encode()

    def test_fixed_schema_privacy_and_bounds(self):
        for raw in (b'PRIVATE', b'x' * 8193, b'{"event":"PRIVATE","event":"start"}',
                    self.events(markers=['PRIVATE']), self.events(exit_code=True),
                    self.events(duration_ms=float('inf')), self.events(oracle_assertion=True),
                    self.events(secret='PRIVATE'), self.events(launch_error='PRIVATE')):
            with self.subTest(case=len(raw)), self.assertRaises((ValueError, TypeError)):
                trace.decode(raw)
        self.assertEqual(trace.markers(b'PRIVATE cannot allocate memory'), ['memory-pressure'])
        self.assertEqual(trace.markers(b'x' * 8192 + b'cannot allocate memory'), [])
        for code in (7, -9, 101):
            report = trace.decode(self.events(code))
            self.assertFalse(trace.valid_control(report, False))
            self.assertNotIn('PRIVATE', json.dumps(report))
            self.assertEqual(report['commands'][0]['signal'], 9 if code == -9 else None)
        for kwargs in (dict(timed_out=True), dict(launch_error='memory-pressure', launched=False)):
            self.assertFalse(trace.valid_control(trace.decode(self.events(None, **kwargs)), False))
        report = trace.decode(b'{"event":"start","phase":"compile"}\n')
        self.assertEqual(report['in_flight'], 'compile')
        self.assertFalse(trace.valid_control(report, False))
        self.assertFalse(trace.valid_control(trace.decode(b''), False))

    def run_grade(self, compiler, expected=None, timeout=30):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rustc = root / 'rustc'
            if compiler is not None:
                rustc.write_text('#!' + sys.executable + '\n' + compiler)
                rustc.chmod(0o700)
            (root / 'lib.rs').write_text('pub fn clamp(x:i32)->i32{x}\n')
            argv = [b.shutil.which('python3'), '-B', str(b.ROOT / 'graders.py'), 'rust-clamp', str(root)]
            with patch.dict(os.environ, {'PATH': tmp}):
                with trace.capture(argv) as state:
                    result = b.execute(argv, b.ROOT, timeout=timeout)
            self.assertEqual(state['launches'], 1)
            self.assertLessEqual(len(state['raw']), 8192)
            report = trace.decode(state['raw'])
            self.assertNotIn('PRIVATE', json.dumps(report))
            if expected is not None:
                self.assertEqual(trace.valid_control(report, expected), True)
            return report, result

    def test_actual_original_invocation_positive_and_negative(self):
        # Fake compiler generates only a fixed, private oracle executable.
        for expected in (True, False):
            oracle = ('#!' + sys.executable + '\n' +
                      ('raise SystemExit(0)\n' if expected else
                       'print("test oracle ... FAILED")\n'
                       'print("thread \'oracle\' panicked: assertion `left == right` failed")\n'
                       'raise SystemExit(101)\n'))
            compiler = 'import os,sys\nassert "PYTHONPATH" not in os.environ\nassert sys.argv[1:]==["--test","lib.rs","-o","test"]\nfrom pathlib import Path\np=Path("test")\np.write_text(' + repr(oracle) + ')\np.chmod(0o700)\n'
            report, result = self.run_grade(compiler, expected)
            self.assertEqual(result['exit_status'], 0 if expected else 1)
            self.assertEqual([r['phase'] for r in report['commands']], ['compile', 'test'])
            self.assertEqual(report['selected_toolchain'], 'UNKNOWN')

    def test_real_children_nonzero_signal_outer_timeout_and_resource_constraint(self):
        for compiler, code in [('raise SystemExit(7)\n', 7),
                               ('import os,signal\nos.kill(os.getpid(),signal.SIGTERM)\n', -15)]:
            report, result = self.run_grade(compiler)
            self.assertEqual(report['commands'][0]['exit_code'], code)
            self.assertFalse(trace.valid_control(report, False))
        report, _ = self.run_grade(None)
        self.assertEqual(report['commands'][0]['launch_error'], 'tool-missing')
        self.assertFalse(report['commands'][0]['launched'])
        self.assertFalse(trace.valid_control(report, False))
        report, result = self.run_grade('import time\ntime.sleep(5)\n', timeout=.7)
        self.assertTrue(result['timeout'])
        self.assertEqual(report['in_flight'], 'compile')
        self.assertFalse(trace.valid_control(report, False))
        if sys.platform == 'linux':
            report, _ = self.run_grade('import resource\nresource.setrlimit(resource.RLIMIT_FSIZE,(0,0))\n'
                'try:\n f=open("test","wb"); f.write(b"x"); f.flush()\n'
                'except OSError:\n raise SystemExit(7)\n')
            self.assertEqual(report['commands'][0]['exit_code'], 7)
            self.assertEqual(report['resource_cause'], 'UNKNOWN')

    def test_oracle_non_assertion_101_and_signal_fail_closed(self):
        for body, code in [('raise SystemExit(101)', 101),
                           ('import os,signal; os.kill(os.getpid(),signal.SIGTERM)', -15)]:
            oracle = '#!' + sys.executable + '\n' + body + '\n'
            compiler = ('from pathlib import Path\np=Path("test")\np.write_text('
                        + repr(oracle) + ')\np.chmod(0o700)\n')
            report, _ = self.run_grade(compiler)
            self.assertEqual(report['commands'][1]['exit_code'], code)
            self.assertFalse(report['commands'][1]['oracle_assertion'])
            self.assertFalse(trace.valid_control(report, False))

    def test_hook_forwards_arguments_result_and_exceptions_unchanged(self):
        grader = str(b.ROOT / 'graders.py')
        namespace = {'__file__': grader}
        exec('def call(argv, kwargs):\n return subprocess.run(argv, **kwargs)',
             dict(namespace, subprocess=subprocess), namespace)
        call = namespace['call']
        argv = ['rustc', '--test', 'lib.rs', '-o', 'test']
        kwargs = dict(cwd=Path('/synthetic'), env={'PATH': 'PRIVATE'}, capture_output=True, timeout=25)
        errors = [OSError(errno.ENOENT, 'PRIVATE'), OSError(errno.ENOMEM, 'PRIVATE'),
                  OSError(errno.EAGAIN, 'PRIVATE'), OSError(errno.ENOSPC, 'PRIVATE'),
                  subprocess.TimeoutExpired('PRIVATE', 25, stderr=b'PRIVATE')]
        for error in errors + [None]:
            read_fd, write_fd = os.pipe()
            try:
                result = subprocess.CompletedProcess(argv, 7, b'PRIVATE', b'PRIVATE')
                original = subprocess.run
                with patch.object(sys, 'argv', [grader, 'rust-clamp', '/synthetic']), \
                     patch.object(subprocess, 'run', side_effect=error, return_value=result) as run:
                    trace.install(write_fd, grader, trace.hashlib.sha256(Path(grader).read_bytes()).hexdigest())
                    if error:
                        with self.assertRaises(type(error)) as raised:
                            call(argv, kwargs)
                        self.assertIs(raised.exception, error)
                    else:
                        self.assertIs(call(argv, kwargs), result)
                    run.assert_called_once_with(argv, **kwargs)
                subprocess.run = original
                os.close(write_fd)
                write_fd = None
                report = trace.decode(os.read(read_fd, 8193))
                self.assertEqual(len(report['commands']), 1)
                self.assertNotIn('PRIVATE', json.dumps(report))
            finally:
                if write_fd is not None:
                    os.close(write_fd)
                os.close(read_fd)

    def test_post_launch_io_error_is_distinct_from_launch_failure(self):
        grader = str(b.ROOT / 'graders.py')
        namespace = {'__file__': grader, 'subprocess': subprocess}
        exec('def call():\n return subprocess.run(["rustc","--test","lib.rs","-o","test"], '
             'cwd=Path("/synthetic"),env={},capture_output=True,timeout=25)',
             dict(namespace, Path=Path), namespace)
        def run(*args, **kwargs):
            subprocess.Popen(*args, **kwargs)
            raise OSError(errno.EIO, 'PRIVATE')
        read_fd, write_fd = os.pipe()
        try:
            with patch.object(sys, 'argv', [grader, 'rust-clamp', '/synthetic']), \
                 patch.object(subprocess, 'run', side_effect=run), \
                 patch.object(subprocess, 'Popen', return_value=object()):
                trace.install(write_fd, grader, trace.hashlib.sha256(Path(grader).read_bytes()).hexdigest())
                with self.assertRaises(OSError):
                    namespace['call']()
            report = trace.decode(os.read(read_fd, 8193))
            command = report['commands'][0]
            self.assertTrue(command['launched'])
            self.assertIsNone(command['launch_error'])
            self.assertEqual(command['io_error'], 'os-error')
            self.assertFalse(trace.valid_control(report, False))
        finally:
            os.close(write_fd)
            os.close(read_fd)

    def test_no_activation_for_unrelated_python(self):
        grader = str(b.ROOT / 'graders.py')
        argv = [sys.executable, '-B', '-c', 'pass']
        with trace.capture([sys.executable, '-B', grader, 'rust-clamp', '/unused']) as state:
            result = subprocess.run(argv, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(state['launches'], 0)
        self.assertEqual(state['raw'], b'')
