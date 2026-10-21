"""Negative security tests for inert project-policy reconciliation."""
from unittest import mock
import unittest

from autonomous_contract import ContractRefused
from autonomous_profiles import POLICIES, validate_project
import test_autonomous_contract as fixtures


class ProfileTests(unittest.TestCase):
    setUp = fixtures.PassiveContractTests.setUp
    def project(self, profiles=None, workflows=None, project_id='codex-smart'):
        policy = POLICIES[project_id]
        data = fixtures.source(profiles=profiles or list(policy['profiles']))
        data = data.replace(b'Owner/fixture', ('AlexandrShapkin/' + project_id).encode())
        data = data.replace(b'project_id = "fixture"', ('project_id = "' + project_id + '"').encode())
        ci = workflows if workflows is not None else policy['workflows']
        for name in ci:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture\n')
        data = data.replace(b'".github/workflows/ci.yml"', ', '.join('"' + p + '"' for p in ci).encode())
        return data

    def check_project(self, data, project_id='codex-smart'):
        facts = {k: v for k, v in self.kw.items() if k not in (
            'expected_repository', 'expected_project_id', 'trusted_profile_ids')}
        return validate_project(data, project_id=project_id, **facts)

    def test_full_project_profiles_remain_disabled_without_processes(self):
        with mock.patch('subprocess.Popen', side_effect=AssertionError('execution')):
            for project in POLICIES:
                data = self.project(project_id=project)
                if project == 'assistant-hub':
                    data = data.replace(b'rust-workspace', b'python-stdlib')
                self.assertIs(self.check_project(data, project)['execution']['enabled'], False)

    def test_weak_native_profile_and_missing_security_workflow_refused(self):
        for data in (self.project(profiles=['rust-tests']),
                     self.project(workflows=['.github/workflows/ci.yml'])):
            with self.assertRaises(ContractRefused):
                self.check_project(data)

    def test_unknown_project_and_repository_spoof_refused(self):
        for data, project in ((self.project(), 'other'),
                              (self.project().replace(b'AlexandrShapkin/', b'Attacker/'), 'codex-smart')):
            with self.assertRaises(ContractRefused):
                self.check_project(data, project)

    def test_extra_workflow_cannot_replace_required_ci(self):
        with self.assertRaises(ContractRefused):
            self.check_project(self.project(workflows=['.github/workflows/spoof.yml']))


if __name__ == '__main__':
    unittest.main()
