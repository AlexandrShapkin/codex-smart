"""Opt-in trusted-fixture observation; never imported by the frozen harness."""
import contextlib
import errno
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

LABELS = ('memory-pressure', 'storage-pressure', 'process-pressure', 'compiler-error')
ERRORS = ('tool-missing', 'memory-pressure', 'process-pressure', 'storage-pressure', 'os-error')


def markers(data):
    sample = (data or b'')[:8192].lower()
    return [label for label, marker in zip(LABELS, (
        b'cannot allocate memory', b'no space left on device',
        b'resource temporarily unavailable', b'error[e')) if marker in sample]


def install(fd, grader, digest):
    """Called only by the private startup snapshot, with literal activation data."""
    if (len(sys.argv) != 3 or sys.argv[0] != grader or sys.argv[1] != 'rust-clamp'
            or hashlib.sha256(Path(grader).read_bytes()).hexdigest() != digest):
        return
    # Compiler/oracle must not inherit the metadata descriptor.
    os.set_inheritable(fd, False)
    os.set_blocking(fd, False)
    original = subprocess.run
    count = 0

    def emit(row):
        try:
            payload = json.dumps(row, separators=(',', ':')).encode() + b'\n'
            if len(payload) <= 1024:
                os.write(fd, payload)  # One atomic, nonblocking write; never retry.
        except OSError:
            pass  # Missing evidence fails closed in the parent.

    def observed(argv, **kwargs):
        nonlocal count
        phase = ('compile', 'test')[min(count, 1)]
        caller = sys._getframe(1).f_globals.get('__file__')
        cwd = kwargs.get('cwd')
        expected = (['rustc', '--test', 'lib.rs', '-o', 'test'] if count == 0
                    else [str(cwd / 'test')] if isinstance(cwd, Path) else None)
        if (count >= 2 or caller != grader or argv != expected
                or set(kwargs) != {'cwd', 'env', 'capture_output', 'timeout'}
                or kwargs['capture_output'] is not True or kwargs['timeout'] != 25):
            return original(argv, **kwargs)
        count += 1
        emit({'event': 'start', 'phase': phase})
        started = time.monotonic()
        row = {'event': 'end', 'phase': phase, 'exit_code': None,
               'timed_out': False, 'launch_error': None, 'io_error': None, 'launched': False, 'markers': [],
               'oracle_assertion': False}
        popen = subprocess.Popen
        def launch(*args, **options):
            child = popen(*args, **options)
            row['launched'] = True
            return child
        subprocess.Popen = launch
        try:
            result = original(argv, **kwargs)
            row['launched'] = True
            row['exit_code'] = result.returncode
            row['markers'] = markers(result.stderr)
            # Trusted oracle's exact assertion plus harness failure, not any panic/101.
            oracle_output = (result.stdout or b'')[:8192] + (result.stderr or b'')[:8192]
            row['oracle_assertion'] = (phase == 'test' and result.returncode == 101
                and b"thread 'oracle'" in oracle_output
                and b'assertion `left == right` failed' in oracle_output
                and b'test oracle ... FAILED' in (result.stdout or b'')[:8192])
            return result
        except subprocess.TimeoutExpired as error:
            row['launched'] = True
            row['timed_out'] = True
            row['markers'] = markers(error.stderr)
            raise
        except OSError as error:
            field = 'io_error' if row['launched'] else 'launch_error'
            row[field] = {errno.ENOENT: 'tool-missing', errno.ENOMEM: 'memory-pressure',
                errno.EAGAIN: 'process-pressure', errno.ENOSPC: 'storage-pressure'}.get(error.errno, 'os-error')
            raise
        finally:
            subprocess.Popen = popen
            row['duration_ms'] = min(86400000, max(0, round((time.monotonic() - started) * 1000)))
            emit(row)
    subprocess.run = observed


def decode(raw):
    """Strictly rebuild fixed-schema events; never render child JSON directly."""
    def require(ok):
        if not ok:
            raise ValueError('trace-invalid')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result)
            result[key] = value
        return result
    require(type(raw) is bytes and len(raw) <= 8192)
    rows = []
    active = None
    for line in raw.splitlines():
        row = json.loads(line, object_pairs_hook=unique)
        require(type(row) is dict)
        phase = ('compile', 'test')[min(len(rows), 1)]
        require(len(rows) < 2 and row.get('phase') == phase)
        if active is None:
            require(row == {'event': 'start', 'phase': phase})
            active = phase
            continue
        require(set(row) == {'event', 'phase', 'exit_code', 'timed_out', 'launch_error',
                             'markers', 'oracle_assertion', 'duration_ms', 'launched', 'io_error'})
        require(row['event'] == 'end')
        code = row['exit_code']
        require(code is None or type(code) is int and -2147483648 <= code <= 2147483647)
        require(type(row['timed_out']) is bool and type(row['oracle_assertion']) is bool)
        require(row['launch_error'] is None or type(row['launch_error']) is str
                and row['launch_error'] in ERRORS)
        require(type(row['launched']) is bool)
        require(row['io_error'] is None or type(row['io_error']) is str and row['io_error'] in ERRORS)
        require(not row['launch_error'] or not row['launched'])
        require(not row['io_error'] or row['launched'])
        require(type(row['duration_ms']) is int and 0 <= row['duration_ms'] <= 86400000)
        labels = row['markers']
        require(type(labels) is list and len(labels) <= len(LABELS)
                and all(type(x) is str and x in LABELS for x in labels))
        require(not row['oracle_assertion'] or phase == 'test' and code == 101)
        require((code is not None) == (not row['timed_out'] and row['launch_error'] is None
                                     and row['io_error'] is None))
        require(code is None or row['launched'])
        require(not row['timed_out'] or row['launched'])
        rows.append({'phase': phase, 'exit_code': code,
                     'signal': -code if code is not None and code < 0 else None,
                     'launched': row['launched'], 'timeout_seconds': 25, 'io_error': row['io_error'],
                     'timed_out': row['timed_out'], 'launch_error': row['launch_error'],
                     'duration_ms': row['duration_ms'], 'markers': [x for x in LABELS if x in labels],
                     'oracle_assertion': row['oracle_assertion']})
        active = None
    return {'commands': rows, 'in_flight': active, 'selected_toolchain': 'UNKNOWN',
            'host_toolchain': 'not-probed', 'resource_cause': 'UNKNOWN'}


@contextlib.contextmanager
def capture(argv):
    """Scope activation to exactly one outer launch; keep grade/execute argv intact."""
    import tempfile
    from unittest.mock import patch

    import benchmark_campaign
    benchmark_campaign.load()  # Existing frozen source contracts, no execution.
    grader = argv[2]
    digest = hashlib.sha256(Path(grader).read_bytes()).hexdigest()
    original = subprocess.Popen
    read_fd, write_fd = os.pipe()
    state = {'raw': b'', 'launches': 0}
    try:
        os.set_blocking(read_fd, False)
        with tempfile.TemporaryDirectory(prefix='rust-grade-trace-') as tmp:
            root = Path(tmp)
            # Snapshot both files: no import from workspace, PATH or existing PYTHONPATH.
            module = root / '_rust_grade_trace.py'
            module.write_bytes(Path(__file__).read_bytes())
            startup = root / 'sitecustomize.py'
            startup.write_text('from _rust_grade_trace import install\n'
                               f'install({write_fd!r}, {grader!r}, {digest!r})\n')
            module.chmod(0o400)
            startup.chmod(0o400)
            root.chmod(0o500)
            def launch(arguments, *args, **kwargs):
                if arguments == argv:
                    state['launches'] += 1
                    if state['launches'] != 1 or 'env' in kwargs or 'pass_fds' in kwargs:
                        raise ValueError('trace-launch-invalid')
                    kwargs['env'] = dict(os.environ, PYTHONPATH=tmp)
                    kwargs['pass_fds'] = (write_fd,)
                return original(arguments, *args, **kwargs)
            try:
                with patch.object(subprocess, 'Popen', side_effect=launch):
                    yield state
            finally:
                root.chmod(0o700)
    finally:
        os.close(write_fd)
        try:
            state['raw'] = os.read(read_fd, 8193)
        except BlockingIOError:
            state['raw'] = b''
        finally:
            os.close(read_fd)


def valid_control(trace, expected):
    rows = trace['commands']
    return (trace['in_flight'] is None and len(rows) == 2
            and all(r['launched'] and not r['timed_out'] and r['launch_error'] is None
                    and r['io_error'] is None for r in rows)
            and [r['exit_code'] for r in rows] == [0, 0 if expected else 101]
            and (expected or rows[1]['oracle_assertion']))
