"""Linux-only bounded trust primitives for inert Contract v1 admission.

No discovery, profile execution or Git transport. The independently trusted
operator pins this module, native binaries and a quiescent owned filesystem.
Descriptor traversal prevents symlink redirection, not concurrent inode writers.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import select
import signal
import stat
import subprocess
import sys
import time

from autonomous_contract import ContractRefused

MAX_FILE = 128 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ContractRefused(message)


def canonical(path):
    require(isinstance(path, Path) and path.is_absolute() and '..' not in path.parts,
            'canonical absolute path required')
    return path


@contextmanager
def directory(path):
    canonical(path)
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            other = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = other
        yield fd
    finally:
        os.close(fd)


def owned(meta, private=False):
    require(meta.st_uid in ({os.getuid()} if private else {0, os.getuid()}) and
            not meta.st_mode & (0o077 if private else 0o022), 'unsafe ownership or permissions')


def stable(meta):
    return (meta.st_dev, meta.st_ino, meta.st_size, meta.st_mtime_ns, meta.st_ctime_ns,
            meta.st_mode, meta.st_uid, meta.st_nlink)


def read_at(parent, name, limit=MAX_FILE):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit,
                'bounded single-link regular file required')
        owned(before)
        chunks = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        require(remaining > 0 and stable(os.fstat(fd)) == stable(before), 'file changed or exceeded limit')
        return b''.join(chunks), before.st_mode
    finally:
        os.close(fd)


def file_bytes(path, limit=MAX_FILE):
    canonical(path)
    with directory(path.parent) as parent:
        return read_at(parent, path.name, limit)[0]


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ToolPin:
    path: Path
    sha256: str


@contextmanager
def executable(pin):
    require(sys.platform == 'linux' and Path('/proc/self/fd').is_dir(), 'Linux procfs required')
    require(type(pin) is ToolPin and type(pin.sha256) is str and
            re.fullmatch('[0-9a-f]{64}', pin.sha256), 'external executable pin required')
    canonical(pin.path)
    with directory(pin.path.parent) as parent:
        fd = os.open(pin.path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    try:
        meta = os.fstat(fd)
        require(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1 and meta.st_mode & 0o111
                and not meta.st_mode & 0o6000 and meta.st_size <= MAX_FILE,
                'bounded native executable required')
        owned(meta)
        digest = hashlib.sha256()
        magic = os.pread(fd, 4, 0)
        offset = 0
        while chunk := os.pread(fd, 65536, offset):
            digest.update(chunk)
            offset += len(chunk)
            require(offset <= MAX_FILE, 'executable grew beyond limit')
        require(magic == b'\x7fELF' and digest.hexdigest() == pin.sha256 and
                stable(os.fstat(fd)) == stable(meta), 'native executable pin mismatch')
        yield fd
    finally:
        os.close(fd)


def bounded_git(fd, root_fd, git_fd, args, *, seconds=10, limit=16 * 1024 * 1024):
    """Only internal fixed read commands use this primitive; never a TOML argv."""
    env = {
        'PATH': '/nonexistent', 'LC_ALL': 'C', 'GIT_CONFIG_NOSYSTEM': '1',
        'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_SYSTEM': '/dev/null',
        'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0',
        'GIT_NO_REPLACE_OBJECTS': '1', 'GIT_NO_LAZY_FETCH': '1',
        'GIT_ALLOW_PROTOCOL': '', 'GIT_PROTOCOL_FROM_USER': '0',
        'GIT_EXEC_PATH': '/nonexistent', 'GIT_LFS_SKIP_SMUDGE': '1',
    }
    command = [f'/proc/self/fd/{fd}', '--no-optional-locks',
               '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
               '-c', 'core.untrackedCache=false', '-c', 'maintenance.auto=false',
               '-c', 'gc.auto=0', '--git-dir=' + f'/proc/self/fd/{git_fd}',
               '--work-tree=' + f'/proc/self/fd/{root_fd}', *args]
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, env=env, cwd='/',
                            pass_fds=(fd, root_fd, git_fd), start_new_session=True)
    success = False
    try:
        deadline = time.monotonic() + seconds
        output = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            require(remaining > 0, 'Git observation timed out')
            ready, _, _ = select.select([proc.stdout], [], [], remaining)
            require(ready, 'Git observation timed out')
            chunk = os.read(proc.stdout.fileno(), min(65536, limit + 1 - len(output)))
            if not chunk:
                break
            output.extend(chunk)
            require(len(output) <= limit, 'Git output limit exceeded')
        require(proc.wait(timeout=max(0.001, deadline - time.monotonic())) == 0,
                'Git observation refused')
        success = True
        return bytes(output)
    finally:
        if not success:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.wait(timeout=2)
        proc.stdout.close()
