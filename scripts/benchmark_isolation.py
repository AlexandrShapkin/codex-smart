"""Explicit Linux namespace probes, never a submitted-code grading fallback.

Bubblewrap is a candidate, not an accepted backend. This host cannot provide
verified aggregate resource controls; production grading therefore fails closed.
"""
import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import tempfile
import time
from typing import Literal

import benchmark_resource_contract as resource_contract

BWRAP = Path('/usr/bin/bwrap')
VERSION = 'bubblewrap 0.13.0'


@dataclass(frozen=True)
class IsolationAvailability:
    status: Literal['verified', 'unavailable', 'blocked']
    reason: str
    backend: str = 'bubblewrap-candidate'
    version: str | None = None


@dataclass(frozen=True)
class GradeResult:
    status: Literal['verified', 'unavailable', 'blocked']
    reason: str
    quality_pass: bool = False


def availability():
    if not BWRAP.is_file():
        return IsolationAvailability('unavailable', 'backend-not-installed')
    if BWRAP.stat().st_mode & (stat.S_ISUID | stat.S_ISGID):
        return IsolationAvailability('blocked', 'privileged-backend-rejected')
    try:
        result = subprocess.run([str(BWRAP), '--version'], env={'PATH': '/usr/bin'},
                                capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return IsolationAvailability('blocked', 'backend-version-unavailable')
    if result.returncode or result.stdout.strip() != VERSION:
        return IsolationAvailability('blocked', 'backend-version-unreviewed')
    # No writable cgroup delegation is provisioned by this implementation. Even
    # on another host, presence/writability must not promote it to verified.
    return IsolationAvailability('blocked', 'aggregate-resource-controls-not-verified', version=VERSION)


def grade(scenario, workspace):
    # Do not read or execute any submitted file until a complete backend exists.
    evidence = availability()
    return GradeResult(evidence.status, evidence.reason)


@dataclass(frozen=True)
class SubmissionPolicy:
    task_files_immutable: bool = False
    allowed_answer_artifacts: tuple[str, ...] = ()


def representative_contract_verified(qualification):
    # No accepted implementation/runtime receipt exists. A host evidence object
    # cannot turn candidate namespace probes into a verified grading backend.
    return False


def grade_representative(scenario, workspace, qualification, *, policy=SubmissionPolicy()):
    """Submission boundary; qualification is required, never a host-grader fallback.

    The accepted isolated backend is not implemented/verified yet. This refusal
    reads no submitted file and performs no host capability investigation.
    """
    import benchmark_host as host
    if type(qualification) is not host.QualifiedHostContract or qualification.status != 'verified':
        return GradeResult('blocked', 'qualified-host-not-verified')
    expected = (SubmissionPolicy(True, ('answer.json',)) if scenario == 'explore-notification'
                else SubmissionPolicy())
    if policy != expected:
        return GradeResult('blocked', 'submission-policy-mismatch')
    return GradeResult('blocked', 'grading-isolation-contract-not-verified')


def _probe(script, workspace, timeout=5):
    """Run repository-owned synthetic probe code only; no grader/operator CLI."""
    with tempfile.TemporaryDirectory(prefix='isolation-probe-') as tmp:
        source = Path(tmp) / 'probe.py'
        source.write_text(script)
        argv = [str(BWRAP), '--unshare-user', '--unshare-all', '--disable-userns',
                '--assert-userns-disabled', '--uid', '1000', '--gid', '1000',
                '--cap-drop', 'ALL', '--die-with-parent', '--new-session', '--clearenv',
                '--ro-bind', '/usr', '/usr', '--symlink', 'usr/lib', '/lib',
                '--symlink', 'usr/lib64', '/lib64', '--proc', '/proc', '--dev', '/dev',
                '--size', '16777216', '--tmpfs', '/tmp', '--dir', '/empty-home',
                '--setenv', 'HOME', '/empty-home', '--setenv', 'CODEX_HOME', '/empty-home',
                '--setenv', 'PATH', '/usr/bin', '--ro-bind', str(source), '/probe.py',
                '--bind', str(workspace), '/work', '--chdir', '/work',
                '--', '/usr/bin/python3', '-B', '/probe.py']
        try:
            child = subprocess.Popen(argv, env={'PATH': '/usr/bin'}, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     start_new_session=True, close_fds=True)
        except OSError:
            return False
        try:
            return child.wait(timeout=timeout) == 0
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            return False
        except KeyboardInterrupt:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            raise


def probe():
    evidence = availability()
    checks = {name: 'not-run' for name in ('filesystem', 'symlink', 'environment',
                                         'tcp', 'udp', 'process-cleanup', 'immutable-probe')}
    if evidence.version != VERSION:
        return {'availability': asdict(evidence), 'checks': checks, 'grader_compatibility': 'not-verified'}
    with tempfile.TemporaryDirectory(prefix='isolation-sentinels-') as tmp:
        external = Path(tmp) / 'external'
        external.write_text('synthetic-sentinel-only')
        work = Path(tmp) / 'work'
        work.mkdir()
        (work / 'escape').symlink_to(external)
        def record(name, script, timeout=5):
            checks[name] = 'passed' if _probe(script, work, timeout) else 'failed'
        record('filesystem', f'''from pathlib import Path
p=Path({str(external)!r})
assert not p.exists()
try: p.write_text('changed')
except OSError: pass
else: raise AssertionError
assert not Path('/home').exists()
assert not Path('/benchmarks/.artifacts').exists()
''')
        record('symlink', "from pathlib import Path\nassert not Path('/work/escape').exists()\n")
        previous = os.environ.get('BENCHMARK_SYNTHETIC_SECRET')
        os.environ['BENCHMARK_SYNTHETIC_SECRET'] = 'synthetic-only'
        try:
            record('environment', """import os
from pathlib import Path
assert 'BENCHMARK_SYNTHETIC_SECRET' not in os.environ
assert set(os.environ) <= {'PATH','HOME','CODEX_HOME','LC_CTYPE','PWD'}
assert not list(Path(os.environ['HOME']).iterdir())
assert not list(Path(os.environ['CODEX_HOME']).iterdir())
""")
        finally:
            if previous is None: os.environ.pop('BENCHMARK_SYNTHETIC_SECRET', None)
            else: os.environ['BENCHMARK_SYNTHETIC_SECRET'] = previous
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            port = listener.getsockname()[1]
            record('tcp', f'''import socket
for address in [('127.0.0.1',{port}),('192.0.2.1',9)]:
 s=socket.socket(); s.settimeout(.3)
 try: s.connect(address)
 except OSError: pass
 else: raise AssertionError
 s.close()
''')
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as listener:
            listener.bind(('127.0.0.1', 0))
            listener.settimeout(.1)
            port = listener.getsockname()[1]
            record('udp', f'''import socket
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
try: s.sendto(b'synthetic',('127.0.0.1',{port}))
except OSError: pass
try: s.sendto(b'synthetic',('192.0.2.1',9))
except OSError: pass
else: raise AssertionError
''')
            try:
                listener.recvfrom(32)
                checks['udp'] = 'failed'
            except socket.timeout:
                pass
        record('immutable-probe', """from pathlib import Path
try: Path('/probe.py').write_text('changed')
except OSError: pass
else: raise AssertionError
""")
        _probe("""import os,time
from pathlib import Path
if os.fork()==0:
 os.setsid()
 Path('/work/ready').touch()
 time.sleep(2)
 Path('/work/survived').touch()
else: time.sleep(10)
""", work, timeout=.8)
        time.sleep(2.2)
        checks['process-cleanup'] = ('passed' if (work/'ready').exists() and not (work/'survived').exists()
                                     else 'failed')
        if external.read_text() != 'synthetic-sentinel-only': checks['filesystem'] = 'failed'
    if any(value != 'passed' for value in checks.values()):
        evidence = IsolationAvailability('blocked', 'namespace-probes-failed', version=VERSION)
    return {'availability': asdict(evidence), 'checks': checks,
            'resource_controls': 'not-verified', 'runtime_inventory': 'not-verified',
            'grader_compatibility': 'not-verified'}


@dataclass(frozen=True)
class IsolationEvidence:
    backend: str = 'bubblewrap-candidate'
    backend_version: str | None = None
    resource_backend: str = 'systemd-user-cgroup-v2'
    resource_status: resource_contract.State = 'not-verified'
    memory_limit_status: resource_contract.State = 'not-verified'
    process_limit_status: resource_contract.State = 'not-verified'
    runtime_inventory_status: resource_contract.State = 'not-verified'
    filesystem_status: resource_contract.State = 'not-verified'
    network_status: resource_contract.State = 'not-verified'
    environment_status: resource_contract.State = 'not-verified'
    process_cleanup_status: resource_contract.State = 'not-verified'
    grader_compatibility_status: resource_contract.State = 'not-verified'


def inspect_contract():
    resource = resource_contract.inspect_resources()
    backend = availability()
    evidence = IsolationEvidence(backend_version=backend.version,
                                 resource_status=resource.resource_status,
                                 memory_limit_status=resource.memory_limit_status,
                                 process_limit_status=resource.process_limit_status)
    return {'isolation': asdict(evidence), 'resource': asdict(resource),
            'reason': 'grading isolation blocked: host lacks verified unprivileged aggregate resource containment'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--resources', action='store_true', help='read-only local user-resource inspection')
    group.add_argument('--probe', action='store_true', help='run fixed synthetic namespace probes only')
    args = parser.parse_args()
    result = (inspect_contract() if args.resources else probe() if args.probe
              else {'availability': asdict(availability())})
    print(json.dumps(result, indent=2))
    # Successful component probes never represent acceptance of the backend.
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
