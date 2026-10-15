"""Explicit local trusted controls for #92; never accepts submitted source."""
import errno
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import benchmark
import benchmark_campaign as campaign

sys.path.insert(0, str(benchmark.ROOT))
import graders


# Emit only fixed labels: compiler stderr can echo arbitrary source and paths.
def safe_stderr(data):
    sample = (data or b'')[:8192].lower()
    labels = []
    for label, marker in (
        ('memory-pressure', b'cannot allocate memory'),
        ('storage-pressure', b'no space left on device'),
        ('process-pressure', b'resource temporarily unavailable'),
        ('compiler-error', b'error[e'),
        ('assertion-failed', b'assertion'),
    ):
        if marker in sample:
            labels.append(label)
    return labels


def observe(run, records, argv, **kwargs):
    """Preserve the exact grader invocation/result; retain no raw output or argv."""
    started = time.monotonic()
    row = {'phase': 'compile' if argv[0] == 'rustc' else 'test',
           'exit_code': None, 'timed_out': False, 'timeout_seconds': kwargs['timeout'],
           'launch_error': None, 'stderr': []}
    try:
        result = run(argv, **kwargs)
        row['exit_code'] = result.returncode
        row['stderr'] = safe_stderr(result.stderr)
        return result
    except subprocess.TimeoutExpired as error:
        row['timed_out'] = True
        row['stderr'] = safe_stderr(error.stderr)
        raise
    except OSError as error:
        row['launch_error'] = {
            errno.ENOENT: 'tool-missing', errno.ENOMEM: 'memory-pressure',
            errno.EAGAIN: 'process-pressure', errno.ENOSPC: 'storage-pressure',
        }.get(error.errno, 'os-error')
        raise
    finally:
        row['duration_ms'] = min(86400000, max(0, round((time.monotonic() - started) * 1000)))
        records.append(row)


def diagnose():
    campaign.load()  # Verify frozen campaign source pins before execution.
    scenario = next(s for s in benchmark.load_manifest()['scenarios'] if s['id'] == 'rust-clamp')
    fixture = benchmark.fixture(scenario)
    rows = []
    run = subprocess.run
    for control, files, expected in (
        ('correct', fixture['files'] | fixture['solution'], True),
        ('baseline', fixture['files'], False),
        ('wrong', fixture['files'] | fixture['wrong'], False),
    ):
        records = []
        def observed(argv, **kwargs):
            return observe(run, records, argv, **kwargs)
        with tempfile.TemporaryDirectory(prefix='rust-clamp-control-') as tmp:
            workspace = Path(tmp)
            benchmark.materialize(files, workspace)
            try:
                with patch.object(graders.subprocess, 'run', side_effect=observed):
                    passed = graders.check('rust-clamp', workspace)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                passed = False
        # A broken compiler must not count as a successful negative control.
        compiled = bool(records and records[0]['exit_code'] == 0)
        executed = (len(records) == 2 and not records[1]['timed_out']
                    and records[1]['exit_code'] == (0 if expected else 101))
        rows.append({'control': control, 'quality_pass': passed,
                     'control_ok': compiled and executed and passed == expected,
                     'commands': records})
    return {'scenario': 'rust-clamp', 'controls': rows}


def main():
    result = diagnose()
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if all(row['control_ok'] for row in result['controls']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
