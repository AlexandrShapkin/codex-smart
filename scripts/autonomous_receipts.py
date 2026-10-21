"""Private admission-attempt evidence only; no execution/replay/resume facility."""
import fcntl
import json
import os
import re
import secrets

from autonomous_admission import admit, strict_json
from autonomous_trust import canonical, directory, owned, read_at, require, sha256


def publish(fd, name, doc):
    raw = (json.dumps(doc, sort_keys=True) + '\n').encode()
    require(len(raw) <= 16384, 'receipt exceeds bound')
    temporary = '.pending-' + secrets.token_hex(16)
    output = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
    try:
        with os.fdopen(output, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic, no-clobber publication, same directory/filesystem.
        os.link(temporary, name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
    finally:
        os.unlink(temporary, dir_fd=fd)
        os.fsync(fd)


def private_record(fd, name):
    owned(os.stat(name, dir_fd=fd, follow_symlinks=False), private=True)
    return strict_json(read_at(fd, name, 16384)[0])


def check(policy, receipts, attempt, *, recover=False, execution_requested=False):
    """Explicit check, optionally recovering an interrupted CHECK, never a command.

    Receipts directory must already exist, be external, owner-private and pinned
    by the operator. An interrupted begin record is never evidence of admission.
    Recovery fresh-authenticates GitHub, source and tools and consumes this ID;
    stale authority, mutated dependencies and already completed IDs refuse.
    """
    canonical(receipts)
    require(not receipts.is_relative_to(policy.root) and not policy.root.is_relative_to(receipts),
            'receipts must be external to checkout')
    require(type(attempt) is str and re.fullmatch('[0-9a-f]{32}', attempt), 'bounded attempt ID required')
    with directory(receipts) as fd:
        owned(os.fstat(fd), private=True)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(len(os.listdir(fd)) < 254, 'receipt directory capacity exceeded')
        begin_name = attempt + '.begin.json'
        end_name = attempt + ('.recovered.json' if recover else '.end.json')
        begin = {'format': 1, 'attempt': attempt, 'project': policy.project,
                 'main': policy.accepted_main, 'status': 'checking', 'execution_enabled': False}
        if recover:
            previous = private_record(fd, begin_name)
            require(previous == begin, 'receipt identity or accepted main changed')
            names = os.listdir(fd)
            require(attempt + '.recovered.json' not in names, 'recovery ID already consumed')
            if attempt + '.end.json' in names:
                end = private_record(fd, attempt + '.end.json')
                require(end == {**begin, 'status': 'interrupted',
                                'prior_check_interrupted': False, 'observation_sha256': None,
                                'verification_executed': False}, 'attempt already finished; create a new ID')
        else:
            publish(fd, begin_name, begin)
        status = 'interrupted'
        try:
            result = admit(policy, execution_requested=execution_requested)
            status = 'admitted'
            return result
        except Exception:
            status = 'refused'
            raise
        finally:
            publish(fd, end_name, {**begin, 'status': status,
                                   'prior_check_interrupted': recover,
                                   'observation_sha256': sha256(json.dumps(result, sort_keys=True).encode())
                                   if status == 'admitted' else None,
                                   'verification_executed': False})
