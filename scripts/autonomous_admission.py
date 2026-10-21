"""Explicit, inert v1 admission. Not imported by CLI, #164 or any runtime.

OperatorPolicy and binary/dependency pins come from independently trusted operator
code, never TOML/Issues/PATH. Live fixed-host TLS authenticates GitHub identity and
accepted main. Success admits inspection only, never execution, merge or deployment.
A quiescent operator-owned filesystem and pinned operator Python/module are required;
this is a bounded observation, not an OS sandbox or durable future capability.
"""
from dataclasses import dataclass
import json
import hashlib
import os
from pathlib import Path
import re
import ssl
import stat
import subprocess
import time
import urllib.error
import urllib.request

from autonomous_contract import ContractRefused, SHA, relative_path
from autonomous_profiles import POLICIES, validate_project
from autonomous_trust import (ToolPin, bounded_git, canonical, directory, executable,
                              file_bytes, owned, read_at, require, sha256)

REPOSITORY_IDS = {'codex-smart': 1407037015, 'rustcraft': 1401254066,
                  'assistant-hub': 1423108696, 'relayforge': 1424251566}
OWNER_ID = 130848312
DEPENDENCIES = {
    'codex-smart': ('Cargo.toml', 'Cargo.lock', 'justfile', 'deny.toml'),
    'rustcraft': ('Cargo.toml', 'Cargo.lock', 'justfile'),
    'assistant-hub': ('pyproject.toml',),
    'relayforge': ('Cargo.toml', 'Cargo.lock', 'justfile'),
}
TOOLS = {
    'codex-smart': {'git', 'python3', 'just', 'cargo', 'rustc', 'rustfmt', 'cargo-clippy', 'cargo-deny'},
    'rustcraft': {'git', 'python3', 'just', 'cargo', 'rustc', 'rustfmt', 'cargo-clippy'},
    'assistant-hub': {'git', 'python3', 'node'},
    'relayforge': {'git', 'python3', 'just', 'cargo', 'rustc', 'rustfmt', 'cargo-clippy'},
}
CHECKS = {
    'codex-smart': {'ci.yml': {'check'}, 'security.yml': {'review'}},
    'rustcraft': {'ci.yml': {'rust (ubuntu-latest)', 'rust (windows-latest)'}},
    'assistant-hub': {'ci.yml': {'test (3.11)', 'test (3.12)', 'test (3.13)', 'offline UI check'}},
    'relayforge': {'tests.yml': {'test'}, 'rdc-independent.yml': {'verify-offline'}},
}
MAX_FILES = 20000
MAX_TOTAL = 64 * 1024 * 1024


def strict_json(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: require(False, 'nonfinite JSON number'))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ContractRefused('GitHub redirect refused')


def github(project, suffix=''):
    require(project in REPOSITORY_IDS and (not suffix or suffix == '/git/ref/heads/main'
            or re.fullmatch(r'/issues/[1-9][0-9]{0,9}', suffix)
            or re.fullmatch(r'/actions/workflows/(ci|security|tests|rdc-independent)\.yml(?:/runs\?head_sha=[0-9a-f]{40}&per_page=100)?', suffix)
            or re.fullmatch(r'/actions/runs/[1-9][0-9]{0,17}/jobs\?filter=latest&per_page=100', suffix)), 'unrecognized GitHub query')
    # Explicit system CA file avoids SSL_CERT_FILE/SSL_CERT_DIR environment overrides.
    context = ssl.create_default_context(cafile='/etc/ssl/certs/ca-certificates.crt')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                        urllib.request.HTTPSHandler(context=context), NoRedirect())
    url = 'https://api.github.com/repos/AlexandrShapkin/' + project + suffix
    request = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json',
                                                 'User-Agent': 'codex-smart-inert-admission-v1',
                                                 'Cache-Control': 'no-cache',
                                                 'X-GitHub-Api-Version': '2022-11-28'})
    with opener.open(request, timeout=5) as response:
        require(response.status == 200 and response.geturl() == url and
                response.headers.get_content_type() == 'application/json', 'untrusted GitHub response')
        raw = response.read(131073)
        require(len(raw) <= 131072, 'GitHub response too large')
    result = strict_json(raw)
    require(type(result) is dict, 'GitHub object required')
    return result


def authenticate(project, accepted_main, issue):
    require(type(accepted_main) is str and SHA.fullmatch(accepted_main), 'full accepted-main SHA required')
    require(type(issue) is int and 1 <= issue < 10**10, 'GitHub Issue task required')
    repo = github(project)
    require(repo.get('id') == REPOSITORY_IDS[project] and repo.get('full_name') == 'AlexandrShapkin/' + project
            and repo.get('owner', {}).get('id') == OWNER_ID and repo.get('default_branch') == 'main',
            'GitHub repository identity changed')
    ref = github(project, '/git/ref/heads/main')
    require(ref.get('ref') == 'refs/heads/main' and ref.get('object', {}).get('type') == 'commit'
            and ref['object'].get('sha') == accepted_main, 'stale or conflicting accepted main')
    task = github(project, '/issues/' + str(issue))
    require(task.get('number') == issue and task.get('state') == 'open' and 'pull_request' not in task,
            'open GitHub Issue required')
    priorities = [x.get('name') for x in task.get('labels', []) if type(x) is dict
                  and str(x.get('name', '')).startswith('priority:')]
    require(len(priorities) == 1 and priorities[0] in {'priority:P0', 'priority:P1', 'priority:P2', 'priority:P3'},
            'unambiguous P0-P3 task priority required')
    runs = {}
    for filename, required_jobs in CHECKS[project].items():
        workflow = github(project, '/actions/workflows/' + filename)
        workflow_id = workflow.get('id')
        require(type(workflow_id) is int and workflow_id > 0 and
                workflow.get('path') == '.github/workflows/' + filename and workflow.get('state') == 'active',
                'required native workflow identity mismatch')
        observed = github(project, '/actions/workflows/' + filename + '/runs?head_sha=' + accepted_main + '&per_page=100')
        rows = observed.get('workflow_runs')
        require(type(rows) is list and type(observed.get('total_count')) is int and
                len(rows) == observed['total_count'] and len(rows) <= 100, 'incomplete workflow evidence')
        candidates = []
        for row in rows:
            require(type(row) is dict and row.get('head_sha') == accepted_main and
                    row.get('workflow_id') == workflow_id, 'workflow/source SHA mismatch')
            if row.get('event') == 'push' and row.get('head_branch') == 'main':
                require(row.get('repository', {}).get('id') == REPOSITORY_IDS[project] and
                        row.get('head_repository', {}).get('id') == REPOSITORY_IDS[project] and
                        type(row.get('id')) is int and row['id'] > 0, 'workflow repository mismatch')
                candidates.append(row)
        require(candidates, 'exact-main native push run missing')
        run = max(candidates, key=lambda row: row['id'])
        require(run.get('status') == 'completed' and run.get('conclusion') == 'success' and
                type(run.get('run_attempt')) is int and run['run_attempt'] > 0, 'native verification failed or pending')
        jobs = github(project, '/actions/runs/' + str(run['id']) + '/jobs?filter=latest&per_page=100')
        rows = jobs.get('jobs')
        require(type(rows) is list and type(jobs.get('total_count')) is int and
                len(rows) == jobs['total_count'] and len(rows) <= 100, 'incomplete native jobs')
        names = []
        for row in rows:
            require(type(row) is dict and row.get('run_id') == run['id'] and
                    row.get('head_sha') == accepted_main and row.get('status') == 'completed' and
                    row.get('conclusion') == 'success', 'native job failed, skipped or stale')
            names.append(row.get('name'))
        require(required_jobs.issubset(set(names)) and len(names) == len(set(names)),
                'required native job absent or ambiguous')
        runs[filename] = {'id': run['id'], 'attempt': run['run_attempt']}
    return {'repository_id': repo['id'], 'main': accepted_main, 'issue': issue, 'priority': priorities[0],
            'native_runs': runs}



@dataclass(frozen=True)
class OperatorPolicy:
    root: Path
    common_git_dir: Path
    project: str
    accepted_main: str
    issue: int
    tools: dict[str, ToolPin]
    dependencies: dict[str, str]


def scan(fd, *, metadata=False, deadline=None):
    """Hash raw ordinary files through no-follow directory descriptors, no Git filters."""
    files = {}
    total = 0
    count = 0
    def walk(parent, prefix=''):
        nonlocal total, count
        require(len(prefix) <= 1024 and prefix.count('/') <= 32, 'directory depth bound exceeded')
        names = []
        with os.scandir(parent) as stream:
            for entry in stream:
                count += 1
                require(count <= MAX_FILES, 'filesystem entry limit exceeded')
                names.append(entry.name)
        for name in sorted(names):
            require(deadline is None or time.monotonic() < deadline, 'admission scan timed out')
            if not prefix and name == '.git' and not metadata:
                continue
            path = prefix + name
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            owned(info)
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                try:
                    walk(child, path + '/')
                finally:
                    os.close(child)
            else:
                data, mode = read_at(parent, name, MAX_TOTAL - total)
                total += len(data)
                require(total <= MAX_TOTAL, 'filesystem byte limit exceeded')
                files[path] = (sha256(data), bool(mode & 0o111))
    walk(fd)
    return files


def git_layout(policy, rootfd, deadline):
    """Accept ordinary clones or exact registered linked worktrees, never arbitrary gitfiles."""
    root = policy.root
    common = canonical(policy.common_git_dir)
    owned(os.fstat(rootfd))
    info = os.stat('.git', dir_fd=rootfd, follow_symlinks=False)
    if stat.S_ISDIR(info.st_mode):
        require(common == root / '.git', 'unexpected common Git directory')
        gitdir = common
    else:
        raw = read_at(rootfd, '.git', 4096)[0]
        require(raw.startswith(b'gitdir: ') and raw.endswith(b'\n'), 'invalid worktree Git pointer')
        gitdir = canonical(Path(raw[8:-1].decode('utf-8')))
        require(gitdir.parent == common / 'worktrees' and gitdir.name not in {'.', '..'},
                'unregistered or redirected worktree')
        require(file_bytes(gitdir / 'commondir', 4096) == b'../..\n' and
                file_bytes(gitdir / 'gitdir', 4096) == (str(root / '.git') + '\n').encode(),
                'worktree registration mismatch')
    with directory(common) as commonfd:
        owned(os.fstat(commonfd))
        scan(commonfd, metadata=True, deadline=deadline)  # Refuse metadata symlinks, devices and hardlinks before Git reads.
    for name in ('shallow', 'info/grafts', 'objects/info/alternates', 'info/sparse-checkout'):
        require(not (common / name).exists(), 'unsupported Git object/index topology')
    require(not any(common.glob('sharedindex.*')) and not any(gitdir.glob('sharedindex.*')),
            'split index unsupported')
    return gitdir


def observe(policy):
    root = canonical(policy.root)
    deadline = time.monotonic() + 30
    with directory(root) as rootfd:
        gitdir = git_layout(policy, rootfd, deadline)
        with directory(gitdir) as gitfd, executable(policy.tools['git']) as gitbin:
            def git(*args):
                require(time.monotonic() < deadline, 'source observation timed out')
                return bounded_git(gitbin, rootfd, gitfd, list(args),
                                   seconds=min(10, deadline - time.monotonic()))
            # No includes: even configuration inspection must not follow repository redirects.
            config = git('config', '--local', '--no-includes', '--null', '--list')
            origin = []
            allowed = {'core.repositoryformatversion', 'core.filemode', 'core.bare',
                       'core.logallrefupdates', 'remote.origin.url', 'remote.origin.fetch'}
            for entry in config.split(b'\0'):
                if not entry:
                    continue
                key, _, value = entry.partition(b'\n')
                name = key.decode('ascii').lower()
                require(name in allowed or re.fullmatch(r'branch\.[A-Za-z0-9/_.-]+\.(remote|merge)', name),
                        'unsupported repository configuration')
                if name == 'remote.origin.url':
                    origin.append(value)
                if name == 'core.repositoryformatversion':
                    require(value == b'0', 'unsupported Git format')
                if name == 'core.bare':
                    require(value == b'false', 'bare repository refused')
            canonical_origin = 'https://github.com/AlexandrShapkin/' + policy.project
            require(origin in [[canonical_origin.encode()], [(canonical_origin + '.git').encode()],
                               [('git@github.com:AlexandrShapkin/' + policy.project + '.git').encode()]],
                    'local repository identity mismatch')
            head = git('rev-parse', '--verify', 'HEAD').decode().strip()
            require(head == policy.accepted_main, 'checkout is not independently accepted main')
            # Authenticate the commit/tree/blob graph ourselves. Git cat-file
            # alone does not check object hashes; fsck may launch helper programs.
            entries = {}
            total = 0
            objects = 0
            def object_bytes(kind, oid):
                nonlocal total, objects
                require(SHA.fullmatch(oid), 'invalid Git object ID')
                raw = git('cat-file', kind, oid)
                total += len(raw)
                objects += 1
                require(total <= MAX_TOTAL and objects <= MAX_FILES, 'Git graph bound exceeded')
                header = kind.encode() + b' ' + str(len(raw)).encode() + b'\0'
                require(hashlib.sha1(header + raw, usedforsecurity=False).hexdigest() == oid,
                        'Git object content hash mismatch')
                return raw
            commit = object_bytes('commit', head)
            tree_line = commit.split(b'\n', 1)[0]
            require(tree_line.startswith(b'tree '), 'invalid commit tree')
            def tree(oid, prefix=''):
                raw = object_bytes('tree', oid)
                offset = 0
                while offset < len(raw):
                    end = raw.index(b'\0', offset)
                    mode, name = raw[offset:end].split(b' ', 1)
                    offset = end + 21
                    require(offset <= len(raw), 'truncated Git tree')
                    oid = raw[end + 1:offset].hex()
                    path = relative_path(prefix + name.decode('utf-8'))
                    if mode == b'40000':
                        tree(oid, path + '/')
                    else:
                        require(mode in {b'100644', b'100755'} and path not in entries,
                                'symlink/submodule/ambiguous tree entry')
                        data = object_bytes('blob', oid)
                        entries[path] = (sha256(data), mode == b'100755', oid)
            tree(tree_line[5:].decode('ascii'))
            index = git('ls-files', '--stage', '-z')
            expected_index = b''.join((b'100755' if entry[1] else b'100644') + b' ' +
                                      entry[2].encode() + b' 0\t' + name.encode() + b'\0'
                                      for name, entry in sorted(entries.items()))
            require(entries and index == expected_index, 'staged, unmerged or ambiguous index')
            entries = {name: entry[:2] for name, entry in entries.items()}
            flags = git('ls-files', '-v', '-z').split(b'\0')
            require(all(not x or x.startswith(b'H ') for x in flags), 'assume-unchanged/sparse index refused')
            actual = scan(rootfd, deadline=deadline)
            require(actual == entries, 'dirty, untracked, ignored or mode-changed checkout')
            # A second observation detects mutation during the scan; no concurrent writer is supported.
            require(config == git('config', '--local', '--no-includes', '--null', '--list') and
                    head == git('rev-parse', '--verify', 'HEAD').decode().strip() and
                    index == git('ls-files', '--stage', '-z') and actual == scan(rootfd, deadline=deadline),
                    'repository changed during admission')
            return entries


def admit(policy, *, execution_requested=False):
    """Authenticate and validate a current snapshot, returning NO executable capability."""
    try:
        require(type(policy) is OperatorPolicy and policy.project in POLICIES,
                'independently trusted operator policy required')
        require(execution_requested is False, 'v1 never admits execution requests')
        require(type(policy.tools) is dict and set(policy.tools) == TOOLS[policy.project],
                'complete fixed native dependency tool set required')
        require(type(policy.dependencies) is dict and set(policy.dependencies) == set(DEPENDENCIES[policy.project]),
                'complete independently pinned dependency files required')
        for pin in policy.tools.values():
            require(not canonical(pin.path).is_relative_to(canonical(policy.root)),
                    'repository-owned executable refused')
            with executable(pin):
                pass  # Presence/integrity admission only; no --version or verification execution.
        authority = authenticate(policy.project, policy.accepted_main, policy.issue)
        files = observe(policy)
        for name, pin in policy.dependencies.items():
            require(type(pin) is str and re.fullmatch('[0-9a-f]{64}', pin)
                    and name in files and files[name][0] == pin, 'dependency lock or recipe pin mismatch')
        raw = file_bytes(policy.root / 'automation/project.toml', 16384)
        require('automation/project.toml' in files and
                sha256(raw) == files['automation/project.toml'][0], 'contract changed after source observation')
        doc = validate_project(raw, project_id=policy.project, root=policy.root,
                               accepted_main_sha=policy.accepted_main, checkout_sha=policy.accepted_main,
                               checkout_clean=True)
        for name in [*doc['context'].values(), *doc['verification']['ci_workflows']]:
            if name != 'github-issues':
                require(name in files, 'untracked context or workflow pointer')
        require(authority == authenticate(policy.project, policy.accepted_main, policy.issue),
                'GitHub authority changed during admission')
        return {'format': 1, 'project': policy.project, **authority,
                'source_sha256': sha256(json.dumps(files, sort_keys=True).encode()),
                'contract_sha256': sha256(raw), 'execution_enabled': False,
                'tool_pins': {k: v.sha256 for k, v in sorted(policy.tools.items())},
                'dependency_pins': dict(policy.dependencies), 'verification_executed': False}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError, urllib.error.URLError, subprocess.SubprocessError) as exc:
        if isinstance(exc, ContractRefused):
            raise
        raise ContractRefused('admission unavailable or unsupported; no execution performed') from None
