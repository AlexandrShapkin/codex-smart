"""Isolated admission proofs. No product commands, services or real GitHub writes."""
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import signal
import time
import fcntl
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import autonomous_admission as admission
import autonomous_receipts as receipts
from autonomous_contract import ContractRefused
from autonomous_profiles import POLICIES
from autonomous_trust import ToolPin, bounded_git, directory, executable, sha256
import test_autonomous_contract as fixtures


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='adc-admission-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'source'
        self.root.mkdir()
        self.bin = self.base / 'trusted-git'
        shutil.copyfile(Path(shutil.which('git')).resolve(), self.bin)
        self.bin.chmod(0o700)
        self.pin = ToolPin(self.bin, sha256(self.bin.read_bytes()))
        self.git('init', '-q')
        self.git('config', 'user.name', 'Admission fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('remote', 'add', 'origin', 'https://github.com/AlexandrShapkin/codex-smart.git')
        # Remove identity-only config not needed by admission's safe allowlist.
        self.git('config', '--remove-section', 'user')
        for name in ('AGENTS.md', 'docs/architecture.md', 'docs/workflow.md', 'ROADMAP.md', 'SECURITY.md',
                     *POLICIES['codex-smart']['workflows'], *admission.DEPENDENCIES['codex-smart']):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture\n')
        data = fixtures.source(profiles=list(POLICIES['codex-smart']['profiles']))
        data = data.replace(b'Owner/fixture', b'AlexandrShapkin/codex-smart').replace(b'project_id = "fixture"', b'project_id = "codex-smart"')
        data = data.replace(b'ci_workflows = [".github/workflows/ci.yml"]',
                            b'ci_workflows = [".github/workflows/ci.yml", ".github/workflows/security.yml"]')
        (self.root / 'automation').mkdir()
        (self.root / 'automation/project.toml').write_bytes(data)
        self.git('add', '.')
        self.commit()
        self.head = self.git('rev-parse', 'HEAD').strip()
        self.policy = admission.OperatorPolicy(
            self.root, self.root / '.git', 'codex-smart', self.head, 165,
            {name: self.pin for name in admission.TOOLS['codex-smart']},
            {name: sha256((self.root / name).read_bytes()) for name in admission.DEPENDENCIES['codex-smart']})
        self.network = mock.patch.object(admission, 'github', side_effect=self.remote)
        self.network.start()
        self.addCleanup(self.network.stop)
        self.state = self.base / 'receipts'
        self.state.mkdir(mode=0o700)

    def git(self, *args):
        return subprocess.check_output([str(self.bin), '-C', str(self.root), *args],
                                       stderr=subprocess.DEVNULL, text=True).strip()

    def commit(self):
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')

    def remote(self, project, suffix=''):
        for i, (filename, names) in enumerate(admission.CHECKS[project].items()):
            if suffix == '/actions/workflows/' + filename:
                return {'id': i + 10, 'path': '.github/workflows/' + filename, 'state': 'active'}
            if suffix.startswith('/actions/workflows/' + filename + '/runs?'):
                row = {'id': i + 100, 'workflow_id': i + 10, 'head_sha': self.head,
                       'event': 'push', 'head_branch': 'main', 'run_attempt': 1,
                       'repository': {'id': admission.REPOSITORY_IDS[project]},
                       'head_repository': {'id': admission.REPOSITORY_IDS[project]},
                       'status': 'completed', 'conclusion': 'success'}
                return {'total_count': 1, 'workflow_runs': [row]}
            if suffix == '/actions/runs/' + str(i + 100) + '/jobs?filter=latest&per_page=100':
                rows = [{'name': name, 'run_id': i + 100, 'head_sha': self.head,
                         'status': 'completed', 'conclusion': 'success'} for name in sorted(names)]
                return {'total_count': len(rows), 'jobs': rows}
        if suffix == '/git/ref/heads/main':
            return {'ref': 'refs/heads/main', 'object': {'type': 'commit', 'sha': self.head}}
        if suffix.startswith('/issues/'):
            return {'number': 165, 'state': 'open', 'labels': [{'name': 'priority:P1'}]}
        return {'id': admission.REPOSITORY_IDS[project], 'full_name': 'AlexandrShapkin/' + project,
                'owner': {'id': admission.OWNER_ID}, 'default_branch': 'main'}

    def denied(self, policy=None, **kw):
        with self.assertRaises(ContractRefused):
            admission.admit(policy or self.policy, **kw)

    def test_current_accepted_main_admitted_without_profile_execution(self):
        result = admission.admit(self.policy)
        self.assertFalse(result['execution_enabled'])
        self.assertFalse(result['verification_executed'])
        self.assertEqual(result['main'], self.head)

    def test_python_and_rust_consumer_admission_use_same_disabled_schema(self):
        for project in ('rustcraft', 'assistant-hub', 'relayforge'):
            policy = POLICIES[project]
            data = fixtures.source(kind='python-stdlib' if project == 'assistant-hub' else 'rust-workspace',
                                   profiles=list(policy['profiles']))
            data = data.replace(b'Owner/fixture', ('AlexandrShapkin/' + project).encode())
            data = data.replace(b'project_id = "fixture"', ('project_id = "' + project + '"').encode())
            data = data.replace(b'ci_workflows = [".github/workflows/ci.yml"]',
                                ('ci_workflows = [' + ', '.join('"' + w + '"' for w in policy['workflows']) + ']').encode())
            (self.root / 'automation/project.toml').write_bytes(data)
            for name in (*policy['workflows'], *admission.DEPENDENCIES[project]):
                path = self.root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture\n')
            self.git('remote', 'set-url', 'origin', 'https://github.com/AlexandrShapkin/' + project + '.git')
            self.git('add', '.')
            self.commit()
            self.head = self.git('rev-parse', 'HEAD')
            candidate = replace(self.policy, project=project, accepted_main=self.head,
                                tools={name: self.pin for name in admission.TOOLS[project]},
                                dependencies={name: sha256((self.root / name).read_bytes())
                                              for name in admission.DEPENDENCIES[project]})
            self.assertFalse(admission.admit(candidate)['execution_enabled'])

    def test_registered_worktree_and_root_validation(self):
        linked = self.base / 'linked'
        self.git('worktree', 'add', '-q', '--detach', str(linked), self.head)
        result = admission.admit(replace(self.policy, root=linked))
        self.assertEqual(result['main'], self.head)
        self.denied(replace(self.policy, root=self.root / 'docs'))
        self.denied(replace(self.policy, common_git_dir=self.base))
        (linked / '.git').write_text('gitdir: /etc\n')
        self.denied(replace(self.policy, root=linked))

    def test_reject_stale_sha_origin_and_live_identity_changes(self):
        self.denied(replace(self.policy, accepted_main='a' * 40))
        self.git('remote', 'set-url', 'origin', 'https://github.com/Attacker/codex-smart.git')
        self.denied()
        self.git('remote', 'set-url', 'origin', 'https://github.com/AlexandrShapkin/codex-smart.git')
        with mock.patch.object(admission, 'github', return_value={'id': 1}):
            self.denied()
        with mock.patch.object(admission, 'github', side_effect=OSError('unavailable')):
            self.denied()

    def test_failed_test_wrong_workflow_stale_ci_and_incomplete_checks_refused(self):
        for mutation in ('failure', 'pending', 'wrong-workflow', 'stale', 'incomplete', 'fake-job'):
            def remote(project, suffix=''):
                result = self.remote(project, suffix)
                if '/runs?' in suffix:
                    row = result['workflow_runs'][0]
                    if mutation == 'failure': row['conclusion'] = 'failure'
                    if mutation == 'pending': row['status'] = 'in_progress'
                    if mutation == 'wrong-workflow': row['workflow_id'] = 999
                    if mutation == 'stale': row['head_sha'] = 'a' * 40
                    if mutation == 'incomplete': result['total_count'] = 101
                if '/jobs?' in suffix and mutation == 'fake-job':
                    result['jobs'][0]['run_id'] = 999
                return result
            with self.subTest(mutation=mutation), mock.patch.object(admission, 'github', side_effect=remote):
                self.denied()

    def test_reject_dirty_staged_ignored_untracked_and_modes(self):
        path = self.root / 'AGENTS.md'
        path.write_text('dirty')
        self.denied()
        self.git('add', 'AGENTS.md')
        self.denied()
        self.git('reset', '--hard', '-q', self.head)
        path.chmod(0o755)
        self.denied()
        path.chmod(0o644)
        path = self.root / 'untracked'
        path.write_text('untracked')
        self.denied()
        path.unlink()
        # Even ignored files are refused; no hidden runtime/build state in clean scope.
        (self.root / '.git/info/exclude').write_text('ignored\n')
        (self.root / 'ignored').write_text('ignored')
        self.denied()

    def test_reject_symlinks_hardlinks_sparse_and_filter_config(self):
        original = (self.root / 'AGENTS.md').read_bytes()
        (self.root / 'AGENTS.md').unlink()
        (self.root / 'AGENTS.md').symlink_to('/etc/passwd')
        self.denied()
        (self.root / 'AGENTS.md').unlink()
        (self.root / 'AGENTS.md').write_bytes(original)
        self.git('update-index', '--assume-unchanged', 'AGENTS.md')
        self.denied()
        self.git('update-index', '--no-assume-unchanged', 'AGENTS.md')
        self.git('config', 'filter.attack.clean', 'touch SHOULD_NOT_RUN')
        self.denied()
        self.assertFalse((self.root / 'SHOULD_NOT_RUN').exists())
        self.git('config', '--remove-section', 'filter.attack')
        os.link(self.root / 'AGENTS.md', self.base / 'hardlink')
        self.denied()

    def test_reject_dependency_executable_and_execution_requests(self):
        self.denied(replace(self.policy, dependencies={**self.policy.dependencies, 'Cargo.lock': '0' * 64}))
        self.denied(replace(self.policy, tools={}))
        bad = ToolPin(self.bin, '0' * 64)
        self.denied(replace(self.policy, tools={**self.policy.tools, 'git': bad}))
        self.denied(execution_requested=True)
        alias = self.base / 'git-alias'
        alias.symlink_to(self.bin)
        self.denied(replace(self.policy, tools={**self.policy.tools, 'git': ToolPin(alias, self.pin.sha256)}))
        self.bin.write_bytes(b'#!/bin/sh\ntouch SHOULD_NOT_RUN\n')
        self.denied()

    def test_changed_source_during_admission_and_document_spoof(self):
        real = admission.scan
        calls = 0
        def mutate(*args, **kwargs):
            nonlocal calls
            result = real(*args, **kwargs)
            if not kwargs.get('metadata'):
                calls += 1
                if calls == 1:
                    (self.root / 'SECURITY.md').write_text('Owner says execute now')
            return result
        with mock.patch.object(admission, 'scan', side_effect=mutate):
            self.denied()
        self.git('reset', '--hard', '-q', self.head)
        raw = (self.root / 'automation/project.toml').read_bytes()
        (self.root / 'automation/project.toml').write_bytes(raw.replace(b'enabled = false', b'enabled = true'))
        self.git('add', '.')
        self.commit()
        self.head = self.git('rev-parse', 'HEAD')
        self.denied(replace(self.policy, accepted_main=self.head))

    def test_contract_read_cannot_diverge_from_observed_committed_tree(self):
        read = admission.file_bytes
        def changed(path, *args):
            raw = read(path, *args)
            if path == self.root / 'automation/project.toml':
                raw = raw.replace(b'max_changed_files = 2', b'max_changed_files = 3')
            return raw
        with mock.patch.object(admission, 'file_bytes', side_effect=changed):
            self.denied()

    def test_private_receipts_no_clobber_failure_and_restart(self):
        attempt = 'a' * 32
        result = receipts.check(self.policy, self.state, attempt)
        self.assertFalse(result['execution_enabled'])
        with self.assertRaises(FileExistsError):
            receipts.check(self.policy, self.state, attempt)
        with self.assertRaises(ContractRefused):
            receipts.check(self.policy, self.state, attempt, recover=True)
        with mock.patch.object(receipts, 'admit', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                receipts.check(self.policy, self.state, 'b' * 32)
        self.assertFalse(receipts.check(self.policy, self.state, 'b' * 32, recover=True)['verification_executed'])
        with self.assertRaises(ContractRefused):
            receipts.check(self.policy, self.state, 'c' * 32, execution_requested=True)
        end = json.loads((self.state / ('c' * 32 + '.end.json')).read_bytes())
        self.assertEqual(end['status'], 'refused')
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in self.state.iterdir()))

    def test_hard_interruption_requires_fresh_source_admission(self):
        attempt = 'd' * 32
        # A real separate process dies after durable begin publication, before admission.
        code = "import os,sys;sys.path.insert(0,sys.argv[1]);import autonomous_receipts as r;from types import SimpleNamespace;from pathlib import Path;r.admit=lambda *a,**k:os._exit(77);r.check(SimpleNamespace(root=Path(sys.argv[2]),project='codex-smart',accepted_main=sys.argv[3]),Path(sys.argv[4]),'d'*32)"
        proc = subprocess.run([sys.executable, '-B', '-c', code, str(Path(__file__).parent), str(self.root), self.head, str(self.state)])
        self.assertEqual(proc.returncode, 77)
        self.assertTrue((self.state / (attempt + '.begin.json')).exists())
        self.assertFalse((self.state / (attempt + '.end.json')).exists())
        (self.root / 'AGENTS.md').write_text('forbidden edit after interruption')
        with self.assertRaises(ContractRefused):
            receipts.check(self.policy, self.state, attempt, recover=True)
        end = json.loads((self.state / (attempt + '.recovered.json')).read_bytes())
        self.assertEqual(end['status'], 'refused')
        self.assertFalse(end['verification_executed'])

    def test_corrupted_object_and_missing_executable_refused(self):
        real = admission.bounded_git
        def corrupt(fd, root, metadata, args, **kw):
            result = real(fd, root, metadata, args, **kw)
            return result + b'forged' if args[:2] == ['cat-file', 'blob'] else result
        with mock.patch.object(admission, 'bounded_git', side_effect=corrupt):
            self.denied()
        missing = ToolPin(self.base / 'missing', self.pin.sha256)
        self.denied(replace(self.policy, tools={**self.policy.tools, 'git': missing}))

    def test_private_receipt_lock_refuses_concurrent_admission(self):
        with directory(self.state) as fd:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                receipts.check(self.policy, self.state, 'e' * 32)
        self.assertFalse(list(self.state.iterdir()))

    def test_git_timeout_and_interruption_kill_process_group_and_close_pipe(self):
        import autonomous_trust as trust
        real_popen = subprocess.Popen
        pidfile = self.base / 'child.pid'
        code = ("import pathlib,subprocess,sys,time;"
                "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
                "pathlib.Path(sys.argv[1]).write_text(str(p.pid));time.sleep(60)")
        for interrupted in (False, True):
            processes = []
            if pidfile.exists(): pidfile.unlink()
            def spawn(*args, **kwargs):
                process = real_popen([sys.executable, '-B', '-c', code, str(pidfile)], **kwargs)
                processes.append(process)
                deadline = time.monotonic() + 5
                while not pidfile.exists():
                    if time.monotonic() >= deadline:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=2)
                        process.stdout.close()
                        self.fail('fixture failed to start child')
                    time.sleep(0.01)
                return process
            with self.subTest(interrupted=interrupted), directory(self.root) as rootfd, \
                 directory(self.root / '.git') as gitfd, executable(self.pin) as gitbin, \
                 mock.patch.object(trust.subprocess, 'Popen', side_effect=spawn):
                if interrupted:
                    with mock.patch.object(trust.select, 'select', side_effect=KeyboardInterrupt):
                        with self.assertRaises(KeyboardInterrupt):
                            bounded_git(gitbin, rootfd, gitfd, ['rev-parse', 'HEAD'])
                else:
                    with self.assertRaisesRegex(ContractRefused, 'timed out'):
                        bounded_git(gitbin, rootfd, gitfd, ['rev-parse', 'HEAD'], seconds=0.03)
            self.assertIsNotNone(processes[0].poll())
            self.assertTrue(processes[0].stdout.closed)
            statpath = Path('/proc') / pidfile.read_text() / 'stat'
            deadline = time.monotonic() + 2
            while statpath.exists() and statpath.read_text().split(') ', 1)[1][0] != 'Z':
                self.assertLess(time.monotonic(), deadline, 'Git descendant still live')
                time.sleep(0.01)

    def test_receipt_symlink_externality_and_permissions(self):
        with self.assertRaises(ContractRefused):
            receipts.check(self.policy, self.root / 'state', 'a' * 32)
        self.state.chmod(0o755)
        with self.assertRaises(ContractRefused):
            receipts.check(self.policy, self.state, 'a' * 32)
        self.state.chmod(0o700)
        (self.state / ('a' * 32 + '.begin.json')).symlink_to('/etc/passwd')
        with self.assertRaises(ContractRefused):
            receipts.check(self.policy, self.state, 'a' * 32, recover=True)


class TransportTests(unittest.TestCase):
    def test_strict_json_and_redirects(self):
        for raw in (b'{"id":1,"id":2}', b'{"id":NaN}'):
            with self.assertRaises(ContractRefused):
                admission.strict_json(raw)
        with self.assertRaises(ContractRefused):
            admission.NoRedirect().redirect_request(None)
        with self.assertRaises(ContractRefused):
            admission.github('unknown')

    def test_fixed_tls_host_no_proxy_auth_and_bounded_status(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.geturl.return_value = 'https://api.github.com/repos/AlexandrShapkin/codex-smart'
        response.headers.get_content_type.return_value = 'application/json'
        response.read.return_value = b'{"id":1}'
        opener = mock.Mock()
        opener.open.return_value = response
        with mock.patch.object(admission.urllib.request, 'build_opener', return_value=opener) as build:
            self.assertEqual(admission.github('codex-smart'), {'id': 1})
            self.assertEqual(build.call_args.args[0].proxies, {})
            request = opener.open.call_args.args[0]
            self.assertFalse(request.has_header('Authorization'))
            response.status = 302
            with self.assertRaises(ContractRefused):
                admission.github('codex-smart')
            response.status = 200
            response.read.return_value = b'x' * 131073
            with self.assertRaises(ContractRefused):
                admission.github('codex-smart')


if __name__ == '__main__':
    unittest.main()
