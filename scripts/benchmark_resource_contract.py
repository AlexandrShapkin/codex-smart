"""Read-only resource inspection and candidate runtime policy; no unit creation."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Literal

State = Literal['verified', 'blocked', 'unavailable', 'not-verified']
SYSTEMCTL = Path('/usr/bin/systemctl')
SYSTEMD_RUN = Path('/usr/bin/systemd-run')
CGROUP = Path('/sys/fs/cgroup')


@dataclass(frozen=True)
class ResourceEvidence:
    resource_backend: str = 'systemd-user-cgroup-v2'
    backend_version: str | None = None
    resource_status: State = 'not-verified'
    reason: str = 'enforcement-not-observed'
    memory_limit_status: State = 'not-verified'
    process_limit_status: State = 'not-verified'
    descendants_status: State = 'not-verified'
    process_cleanup_status: State = 'not-verified'
    user_manager_status: State = 'unavailable'
    memory_controller_present: bool = False
    pids_controller_present: bool = False
    direct_delegation_writable: bool = False


def assess_resources(*, manager, controllers, memory_property=False, tasks_property=False,
                     version=None, delegation=False):
    common = {'backend_version': version, 'memory_controller_present': 'memory' in controllers,
              'pids_controller_present': 'pids' in controllers,
              'direct_delegation_writable': delegation}
    if not manager:
        return ResourceEvidence(resource_status='unavailable', reason='user-manager-unavailable', **common)
    common['user_manager_status'] = 'verified'
    if 'memory' not in controllers or not memory_property:
        return ResourceEvidence(resource_status='blocked', reason='memory-limit-unsupported',
                                memory_limit_status='unavailable', **common)
    if 'pids' not in controllers or not tasks_property:
        return ResourceEvidence(resource_status='blocked', reason='process-limit-unsupported',
                                process_limit_status='unavailable', **common)
    # Properties/controller presence is capability evidence, not enforcement.
    return ResourceEvidence(resource_status='not-verified', **common)


def _query(argv, env):
    try:
        result = subprocess.run(argv, env=env, capture_output=True, text=True,
                                timeout=5, stdin=subprocess.DEVNULL, close_fds=True)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def inspect_resources():
    # Fixed local bus, no inherited DBus address, remote transport, credential or
    # proxy environment. Commands are read-only show/version, never run/start.
    runtime = Path('/run/user') / str(os.getuid())
    env = {'PATH': '/usr/bin', 'XDG_RUNTIME_DIR': str(runtime),
           'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + str(runtime/'bus')}
    version = None
    if SYSTEMD_RUN.is_file():
        observed = _query([str(SYSTEMD_RUN), '--version'], env)
        match = re.match(r'systemd ([0-9]{1,4})\b', observed or '')
        if match: version = 'systemd ' + match.group(1)
    if not SYSTEMCTL.is_file() or not SYSTEMD_RUN.is_file():
        return ResourceEvidence(resource_status='unavailable', reason='resource-backend-unavailable',
                                backend_version=version)
    try:
        controllers = (CGROUP/'cgroup.controllers').read_text().split()
        membership = Path('/proc/self/cgroup').read_text().splitlines()
        unified = next((line[3:] for line in membership if line.startswith('0::')), None)
        current = CGROUP / (unified or '').lstrip('/')
        # Restrict even kernel-provided relative names; never follow indirection
        # outside the cgroup mount or infer delegation from root writability.
        delegation = (unified is not None and current.resolve().is_relative_to(CGROUP.resolve())
                      and not (os.statvfs(CGROUP).f_flag & os.ST_RDONLY)
                      and os.access(current, os.W_OK))
    except OSError:
        controllers, delegation = [], False
    properties = _query([str(SYSTEMCTL), '--user', 'show', 'user.slice',
                         '--property=MemoryMax', '--property=MemoryHigh', '--property=TasksMax'], env)
    values = dict(line.split('=', 1) for line in (properties or '').splitlines() if '=' in line)
    memory = bool(re.fullmatch(r'(?:infinity|[0-9]+)', values.get('MemoryMax', '')))
    tasks = bool(re.fullmatch(r'(?:infinity|[0-9]+)', values.get('TasksMax', '')))
    return assess_resources(manager=properties is not None, controllers=controllers,
                            memory_property=memory, tasks_property=tasks, version=version,
                            delegation=delegation)


# These are candidate staging roles, not an accepted byte inventory. No source
# in normal HOME or broad system root may be bound by this plan. Each role needs
# a separately reviewed manifest of file digests before any grading execution.
RUNTIME_PLAN = {
    'schema_version': 1,
    'roots': {'python': '/runtime/python', 'rust': '/runtime/rust', 'go': '/runtime/go',
              'libraries': '/runtime/libraries', 'linker': '/runtime/linker', 'grader': '/trusted'},
    'read_only': True,
    'versions': {'python': 'Python 3.14.8', 'rust': 'rustc 1.98.0 (88d9e12ae 2026-08-18)',
                 'go': 'go version go1.27.2-X:nodwarf5 linux/amd64'},
    'status': 'not-verified',
}


def validate_runtime_plan(plan, staging_root, sources):
    if json.dumps(plan, sort_keys=True) != json.dumps(RUNTIME_PLAN, sort_keys=True):
        raise ValueError('unreviewed runtime inventory plan')
    root = Path(staging_root)
    if (not root.is_absolute() or root.parent != Path('/tmp') or
            not root.name.startswith('benchmark-runtime-') or root.is_symlink()):
        raise ValueError('dedicated disposable runtime staging required')
    if set(sources) != set(RUNTIME_PLAN['roots']):
        raise ValueError('runtime root set mismatch')
    for role, source in sources.items():
        source = Path(source)
        expected = root / role
        if source != expected or source.is_symlink() or source.resolve() != expected.absolute():
            raise ValueError('runtime outside accepted staging inventory')
    # Structural validation cannot verify staged bytes, recursive symlinks,
    # library closure or compiler/runtime compatibility. Never promote it.
    return 'not-verified'


REQUIRED_COMPONENTS = frozenset({
    'resource_status', 'memory_limit_status', 'process_limit_status', 'descendants_status',
    'process_cleanup_status', 'runtime_inventory_status', 'filesystem_status', 'network_status',
    'environment_status', 'privilege_status', 'trusted_source_status', 'grader_compatibility_status',
})


def complete_contract(evidence):
    """Pure conjunction of reviewed component evidence; never an execution gate."""
    return (set(evidence) == REQUIRED_COMPONENTS and
            all(type(value) is str and value == 'verified' for value in evidence.values()))
