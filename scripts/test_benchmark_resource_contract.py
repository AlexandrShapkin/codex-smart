import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import benchmark_campaign as campaign
import benchmark_resource_contract as resource
import benchmark_isolation as isolation


class ResourceContractTests(unittest.TestCase):
    def test_resource_backend_unavailable(self):
        with patch.object(Path, 'is_file', return_value=False), patch.object(resource, '_query') as query:
            evidence = resource.inspect_resources()
            self.assertEqual(evidence.resource_status, 'unavailable')
            self.assertEqual(evidence.reason, 'resource-backend-unavailable')
            query.assert_not_called()

    def test_user_manager_unavailable_never_falls_back(self):
        with patch.object(Path, 'is_file', return_value=True), \
             patch.object(resource, '_query', side_effect=['systemd 262', None]) as query:
            evidence = resource.inspect_resources()
            self.assertEqual(evidence.reason, 'user-manager-unavailable')
            self.assertEqual(evidence.memory_limit_status, 'not-verified')
            self.assertEqual(evidence.process_limit_status, 'not-verified')
            self.assertEqual(len(query.call_args_list), 2)
            for call in query.call_args_list:
                argv, env = call.args
                self.assertIn(argv[0], [str(resource.SYSTEMCTL), str(resource.SYSTEMD_RUN)])
                self.assertNotIn('start', argv)
                self.assertNotIn('--scope', argv)
                self.assertNotIn('docker', ' '.join(argv))
                self.assertEqual(set(env), {'PATH','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS'})
                self.assertTrue(env['DBUS_SESSION_BUS_ADDRESS'].startswith('unix:path=/run/user/'))
            self.assertNotIn('/run/', json.dumps(evidence.__dict__))

    def test_memory_and_tasks_unsupported(self):
        for kwargs, reason, field in [
                ({'controllers': {'pids'}, 'memory_property':True}, 'memory-limit-unsupported', 'memory_limit_status'),
                ({'controllers': {'memory','pids'}}, 'memory-limit-unsupported', 'memory_limit_status'),
                ({'controllers': {'memory'}, 'memory_property':True, 'tasks_property':True}, 'process-limit-unsupported', 'process_limit_status'),
                ({'controllers': {'memory','pids'}, 'memory_property':True}, 'process-limit-unsupported', 'process_limit_status')]:
            with self.subTest(reason=reason, kwargs=kwargs):
                evidence = resource.assess_resources(manager=True, **kwargs)
                self.assertEqual(evidence.reason, reason)
                self.assertEqual(getattr(evidence, field), 'unavailable')
                self.assertEqual(evidence.resource_status, 'blocked')

    def test_readonly_hierarchy_does_not_rule_out_user_manager(self):
        evidence = resource.assess_resources(manager=True, controllers={'memory','pids'},
                                             memory_property=True, tasks_property=True, delegation=False)
        self.assertEqual(evidence.user_manager_status, 'verified')
        self.assertEqual(evidence.resource_status, 'not-verified')
        self.assertEqual(evidence.reason, 'enforcement-not-observed')
        self.assertEqual(evidence.memory_limit_status, 'not-verified')

    def test_descendants_and_cleanup_are_mandatory_even_after_limit_results(self):
        complete = {name:'verified' for name in resource.REQUIRED_COMPONENTS}
        self.assertTrue(resource.complete_contract(complete))
        for name in resource.REQUIRED_COMPONENTS:
            for value in ['not-verified','unavailable','blocked',True]:
                with self.subTest(component=name, value=value):
                    self.assertFalse(resource.complete_contract(dict(complete, **{name:value})))
        for name in ['descendants_status','process_cleanup_status']:
            missing = dict(complete)
            del missing[name]
            self.assertFalse(resource.complete_contract(missing))

    def test_query_timeout_and_interruption_cannot_create_resource_scope(self):
        with patch.object(resource.subprocess, 'run', side_effect=subprocess.TimeoutExpired('query', 5)) as run:
            self.assertIsNone(resource._query([str(resource.SYSTEMCTL),'--user','show'], {'PATH':'/usr/bin'}))
            self.assertEqual(run.call_args.kwargs['timeout'], 5)
        with patch.object(resource.subprocess, 'run', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                resource._query([str(resource.SYSTEMCTL),'--user','show'], {'PATH':'/usr/bin'})
        # No unit was created, so cleanup is not falsely reported verified.
        self.assertEqual(resource.ResourceEvidence().process_cleanup_status, 'not-verified')

    def test_runtime_plan_drift_rejected(self):
        with tempfile.TemporaryDirectory(prefix='benchmark-runtime-') as tmp:
            sources = {role:Path(tmp)/role for role in resource.RUNTIME_PLAN['roots']}
            self.assertEqual(resource.validate_runtime_plan(resource.RUNTIME_PLAN, tmp, sources), 'not-verified')
            for key, value in [('read_only',False), ('status','verified'), ('schema_version',2)]:
                plan = copy.deepcopy(resource.RUNTIME_PLAN)
                plan[key] = value
                with self.assertRaises(ValueError): resource.validate_runtime_plan(plan, tmp, sources)
            plan = copy.deepcopy(resource.RUNTIME_PLAN)
            plan['versions']['rust'] = 'rustc other'
            with self.assertRaises(ValueError): resource.validate_runtime_plan(plan, tmp, sources)
            plan = copy.deepcopy(resource.RUNTIME_PLAN)
            plan['artifacts']['go']['sha256'] = '0'*64
            with self.assertRaises(ValueError): resource.validate_runtime_plan(plan, tmp, sources)

    def test_outside_rust_home_and_broad_mounts_rejected(self):
        with tempfile.TemporaryDirectory(prefix='benchmark-runtime-') as tmp:
            sources = {role:Path(tmp)/role for role in resource.RUNTIME_PLAN['roots']}
            for source in ['/home/synthetic/.rustup/toolchains/pinned', '/home/synthetic', '/usr', '/']:
                with self.subTest(source=source), self.assertRaises(ValueError):
                    resource.validate_runtime_plan(resource.RUNTIME_PLAN, tmp, dict(sources, rust=source))
            with self.assertRaises(ValueError):
                resource.validate_runtime_plan(resource.RUNTIME_PLAN, '/home/synthetic/runtime', sources)
            (Path(tmp)/'rust').symlink_to('/home/synthetic')
            with self.assertRaises(ValueError): resource.validate_runtime_plan(resource.RUNTIME_PLAN, tmp, sources)

    def test_typed_report_and_public_campaign_remain_unverified(self):
        evidence = resource.ResourceEvidence(resource_status='unavailable', reason='user-manager-unavailable')
        with patch.object(resource, 'inspect_resources', return_value=evidence), \
             patch.object(isolation, 'availability', return_value=isolation.IsolationAvailability('blocked','test')):
            report = isolation.inspect_contract()
            self.assertEqual(report['isolation']['resource_status'], 'unavailable')
            self.assertEqual(report['isolation']['runtime_inventory_status'], 'not-verified')
            self.assertEqual(report['isolation']['grader_compatibility_status'], 'not-verified')
        with patch.object(campaign, 'real_preflight') as preflight, \
             patch.object(campaign, 'artifact_directory') as artifacts, patch.object(campaign.b, 'execute') as execute:
            with self.assertRaisesRegex(ValueError, 'grading isolation contract is not verified'):
                campaign.real_run('/synthetic/codex', 'test', allow_preliminary_campaign=True)
            preflight.assert_not_called()
            artifacts.assert_not_called()
            execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
