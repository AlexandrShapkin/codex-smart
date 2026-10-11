import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import benchmark as b
import benchmark_campaign as c


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.config = c.load()
        self.scenario = b.load_manifest()['scenarios'][2]

    def test_exact_job_plan_and_order(self):
        jobs = c.jobs(self.config)
        self.assertEqual(len(jobs), 42)
        self.assertEqual(jobs, c.jobs(c.load()))
        self.assertEqual({v for _,v,_,_ in jobs}, {'vanilla','native'})
        self.assertEqual(len(set(jobs)), 42)
        self.assertEqual({r for _,_,r,_ in jobs}, {0,1,2})
        self.assertEqual({seed for _,_,_,seed in jobs}, {14})

    def test_native_environment_equivalence(self):
        self.assertEqual(c.command_plan(self.config,'vanilla','/test/codex'),
                         c.command_plan(self.config,'native','/test/codex'))
        self.assertEqual(c.prompt(self.config,self.scenario,'native'),
                         c.prompt(self.config,self.scenario,'vanilla')+c.NATIVE_INSTRUCTION)
        self.assertIn('model_reasoning_effort="low"', c.command_plan(self.config,'vanilla','/test/codex'))
        for variant in ['legacy','router-v2']:
            with self.assertRaises(ValueError): c.command_plan(self.config,variant,'/test/codex')

    def test_auth_contract_and_no_auth_files(self):
        argv = c.command_plan(self.config, 'vanilla', '/test/codex')
        self.assertIn('--ignore-user-config', argv)
        self.assertIn('cli_auth_credentials_store="keyring"', argv)
        auth = self.config['settings']['auth']
        self.assertEqual(auth, {'source': 'existing normal CODEX_HOME',
                                'credential_store': 'keyring', 'credentials_copied': False,
                                'user_config_loaded': False})
        self.assertEqual(c.references(self.config, c.CONFIG)['auth'], auth)
        for key, value in [('credential_store', 'file'), ('source', '/private/auth'),
                           ('credentials_copied', True), ('user_config_loaded', True),
                           ('credentials_copied', 0), ('user_config_loaded', 0)]:
            data = copy.deepcopy(self.config)
            data['settings']['auth'][key] = value
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)/'campaign.json'
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError): c.load(path)
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.dict('os.environ', {'CODEX_HOME': str(home)}):
                c.command_plan(self.config, 'native', '/test/codex')
                b.run(self.scenario, 'vanilla', 14, 0, b.FakeRunner())
            self.assertEqual(list(home.iterdir()), [])
            self.assertNotIn(str(home), json.dumps(c.references(self.config, c.CONFIG)))

    def test_rejects_drift_and_unreviewed_bounds(self):
        for field in ['pins','repetitions','variants','settings','seeds']:
            data = copy.deepcopy(self.config)
            if field == 'pins': data['pins']['harness_sha256'] = '0'*64
            elif field == 'repetitions': data[field] = 4
            elif field == 'variants': data[field].append('router-v2')
            elif field == 'settings': data[field]['reasoning_effort'] = 'high'
            else: data[field] = [15]
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp)/'campaign.json'
                p.write_text(json.dumps(data))
                with self.assertRaises(ValueError): c.load(p)

    def test_dry_run_fresh_snapshots_references_and_no_codex(self):
        real_fake = b.FakeRunner
        starts = []
        def fake():
            def runner(s,v,d):
                files = {str(p.relative_to(d)):p.read_text() for p in d.rglob('*') if p.is_file()}
                self.assertEqual(b.digest(files),s['snapshot'])
                starts.append((s['id'],v))
                return real_fake()(s,v,d)
            return runner
        verified = {name:'verified' for name in self.config['toolchains']}
        with patch.object(c,'toolchains',return_value=verified), patch.object(b,'FakeRunner',side_effect=fake), \
             patch.object(b,'grade',return_value=True), patch.object(b,'execute',side_effect=AssertionError('no process launch')):
            report, records = c.dry_run(self.config)
        self.assertEqual(len(starts),42)
        self.assertEqual(report['attempted_jobs'],42)
        self.assertFalse(report['live_campaign_ready'])
        expected = c.references(self.config,c.CONFIG)
        self.assertTrue(all(r['references']==expected for r in records))
        self.assertTrue(all(r['quality_pass'] and len(r['attempts'])==1 for r in records))
        self.assertNotIn('trace',json.dumps(records))

    def test_missing_toolchain_records_unavailable(self):
        status = {name:'verified' for name in self.config['toolchains']}
        status['go'] = 'unavailable'
        with patch.object(c,'toolchains',return_value=status), patch.object(b,'grade',return_value=True):
            report, records = c.dry_run(self.config)
        self.assertEqual(report['attempted_jobs'],36)
        affected = [r for r in records if r['scenario_id']=='go-total']
        self.assertEqual(len(affected),6)
        self.assertTrue(all(not r['attempts'] and not r['quality_pass'] for r in affected))

    def test_aggregation_matching_settings_and_snapshots(self):
        a = b.run(self.scenario,'vanilla',14,0,b.FakeRunner(),references={'settings':'low'})
        native = b.run(self.scenario,'native',14,0,b.FakeRunner(),references={'settings':'low'})
        self.assertEqual(b.aggregate([a,native])['vanilla']['cost_samples'],1)
        for changed in [dict(native,references={'settings':'high'}),dict(native,snapshot='different'),
                        dict(native,repetition=1),dict(native,cold_warm='warm')]:
            self.assertEqual(b.aggregate([a,changed])['vanilla']['cost_samples'],0)

    def test_aggregation_retains_failure_denominators_and_retry_usage(self):
        a = b.run(self.scenario,'vanilla',14,0,b.FakeRunner(['failure','success']),retries=1)
        native = b.run(self.scenario,'native',14,0,b.FakeRunner())
        failed = b.run(self.scenario,'vanilla',14,1,b.FakeRunner(['grader-failure']))
        report = b.aggregate([a,native,failed])['vanilla']
        self.assertEqual(report['runs'],2)
        self.assertEqual(report['failure_rate'],0.5)
        self.assertEqual(report['retry_rate'],0.5)
        self.assertEqual(report['cost_samples'],1)
        self.assertEqual(report['tokens']['input']['median'],20)
        missing = b.run(self.scenario,'native',14,0,b.FakeRunner(['missing-usage']))
        self.assertIsNone(b.aggregate([a,missing])['native']['tokens']['input']['median'])

    def test_pre_jsonl_failure_captured_without_grading(self):
        def failed_start(s,v,d):
            return {'stdout':'', 'stderr':'Error: app-server initialization: Read-only file system',
                    'exit_status':1, 'timeout':False, 'duration':0.01}
        with tempfile.TemporaryDirectory() as tmp, patch.object(b,'grade') as grader:
            artifacts = Path(tmp)
            r = b.run(self.scenario,'vanilla',14,0,failed_start,artifacts=artifacts)
            grader.assert_not_called()
            folder = artifacts/f"{self.scenario['id']}-vanilla-0-0"
            self.assertEqual((folder/'trace.jsonl').read_text(),'')
            self.assertIn('app-server',(folder/'stderr.txt').read_text())
        self.assertEqual(r['final_status'],'process-failure')
        self.assertFalse(r['quality_pass'])
        self.assertTrue(all(v is None for v in r['attempts'][0]['tokens'].values()))
        self.assertNotIn('app-server',json.dumps(r))

    def test_blocked_cli_has_no_real_or_state_override_execution(self):
        import contextlib
        import io
        import sys
        for arguments in [['--real'], ['--codex-home', '/test/state'], ['--sqlite-home', '/test/state']]:
            with patch.object(sys,'argv',['benchmark_campaign.py',*arguments]), \
                 patch.object(b,'execute') as execute, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    c.main()
                self.assertEqual(raised.exception.code,2)
                execute.assert_not_called()

    def test_startup_evidence_preserves_history_and_pins(self):
        diagnosis = self.config['startup_diagnosis']
        self.assertEqual(diagnosis['no_content_open_errno'],'EROFS (30)')
        self.assertIsNone(diagnosis['safe_writable_state_solution'])
        self.assertEqual(diagnosis['live_retry_attempts'],0)
        self.assertFalse(diagnosis['ephemeral_exemption'])
        self.assertFalse(self.config['live_contract']['ready_for_measured_campaign'])
        self.assertEqual(self.config['codex']['executable_sha256'],
                         '89cc44e820780120ba2c8bc4585c014815bdc7a1fc494c337a585a2c78dc59eb')
        self.assertEqual(len(c.jobs(self.config)),42)

    def test_frozen_state_drift_rejected(self):
        cases = [
            (('status',), 'frozen-plan-ready'),
            (('codex', 'executable_sha256'), '0'*64),
            (('codex', 'version'), '0.162.2'),
            (('cold_warm', 'protocol'), 'controlled cache'),
            (('cold_warm', 'index'), 'verified'),
            (('cold_warm', 'bootstrap'), 'measured'),
            (('cold_warm', 'classification'), 'cold'),
            (('readiness', 'grading_isolation_contract'), 'verified'),
            (('live_contract', 'status'), 'blocked'),
            (('live_contract', 'terminal_status'), 'failed'),
            (('live_contract', 'quality_pass'), False),
            (('live_contract', 'quality_pass'), 1),
            (('live_contract', 'observed_tool_calls'), 4),
            (('live_contract', 'exit_status'), False),
            (('metrics', 'input'), 58886),
            (('metrics', 'fresh_input'), 3845),
            (('metrics', 'total'), 59312),
            (('metrics', 'full_tool_calls'), 3),
            (('readiness', 'real_runner_contract'), 'verified'),
            (('readiness', 'representative_campaign_ready'), True),
            (('readiness', 'representative_campaign_ready'), 0),
            (('historical_live_attempts',), []),
            (('historical_live_attempts',), None),
        ]
        for name in ['rustc', 'go', 'python3']:
            cases.append((('toolchains', name, 'version'), 'different version'))
            cases.append((('toolchains', name, 'version_arguments'), ['--help']))
        history = self.config['historical_live_attempts'][0]
        for key, value in [('terminal_status', 'completed'), ('exit_status', 0),
                           ('grader', 'passed'), ('usage', 'observed'),
                           ('ready_for_measured_campaign', True)]:
            cases.append((('historical_live_attempts',), [dict(history, **{key:value})]))
        cases.append((('historical_live_attempts',), [history, history]))
        for keys, value in cases:
            with self.subTest(keys=keys, value=value), tempfile.TemporaryDirectory() as tmp:
                data = copy.deepcopy(self.config)
                target = data
                for key in keys[:-1]: target = target[key]
                target[keys[-1]] = value
                path = Path(tmp)/'campaign.json'
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError): c.load(path)
        for section in ['status', 'live_contract', 'metrics', 'readiness', 'historical_live_attempts']:
            with self.subTest(missing=section), tempfile.TemporaryDirectory() as tmp:
                data = copy.deepcopy(self.config)
                del data[section]
                path = Path(tmp)/'campaign.json'
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError): c.load(path)

    def test_programmatic_entry_requires_contract_and_preflight(self):
        with patch.object(c, '_real_run') as runner, patch.object(c, 'artifact_directory') as artifacts, \
             patch.object(b, 'execute') as execute:
            with self.assertRaises(ValueError): c.real_run('/fake/codex', 'test')
            with patch.object(c, 'load', side_effect=ValueError('contract drift')):
                with self.assertRaises(ValueError):
                    c.real_run('/fake/codex', 'test', allow_preliminary_campaign=True)
            with patch.object(c, 'real_preflight', side_effect=ValueError('preflight failed')):
                with self.assertRaises(ValueError):
                    c.real_run('/fake/codex', 'test', allow_preliminary_campaign=True)
            runner.assert_not_called()
            artifacts.assert_not_called()
            execute.assert_not_called()

    def test_unverified_grading_blocks_public_entry_and_cli_before_execution(self):
        import contextlib, io, sys
        with patch.object(c, 'real_preflight') as preflight, \
             patch.object(c, 'toolchains') as tools, patch.object(b, 'execute') as execute, \
             patch.object(c, 'artifact_directory') as artifacts, patch.object(c, '_real_run') as runner:
            with self.assertRaisesRegex(ValueError, 'grading isolation contract is not verified'):
                c.real_run('/fake/codex', 'test', allow_preliminary_campaign=True)
            with patch.object(sys, 'argv', ['campaign', '--real', '--allow-preliminary-campaign',
                                          '--codex', '/fake/codex']), \
                 contextlib.redirect_stderr(io.StringIO()) as stderr:
                with self.assertRaises(SystemExit) as raised: c.main()
                self.assertEqual(raised.exception.code, 2)
                self.assertIn('grading isolation contract is not verified', stderr.getvalue())
            preflight.assert_not_called()
            tools.assert_not_called()
            execute.assert_not_called()
            artifacts.assert_not_called()
            runner.assert_not_called()

    def test_verified_live_contract(self):
        live = self.config['live_contract']
        for key in ['status', 'startup', 'auth_routing']:
            self.assertEqual(live[key], 'verified')
        self.assertEqual(live['terminal_status'], 'completed')
        self.assertEqual(live['exit_status'], 0)
        self.assertEqual(live['parser_errors'], [])
        self.assertIsNone(live['final_status'])
        self.assertIs(live['quality_pass'], True)
        self.assertEqual(live['grader'], 'passed')
        self.assertEqual(live['usage'], 'observed')
        self.assertEqual(live['observed_tool_calls'], 3)
        self.assertEqual(self.config['metrics'], {'input':58885, 'cached_input':55040,
                         'output':427, 'reasoning':36, 'fresh_input':None,
                         'total':None, 'full_tool_calls':None})
        self.assertEqual(self.config['historical_live_attempts'][0]['terminal_status'], 'failed')
        self.assertFalse(self.config['readiness']['representative_campaign_ready'])
        self.assertNotIn('/home/', c.CONFIG.read_text())
        self.assertNotIn('payload', json.dumps(live))

    def test_real_preflight_guards(self):
        verified = {name:'verified' for name in self.config['toolchains']}
        version = {'stdout':'codex-cli 0.162.1', 'exit_status':0, 'timeout':False}
        with patch.object(c, 'sha', return_value=self.config['codex']['executable_sha256']), \
             patch.object(b, 'execute', return_value=version) as execute, \
             patch.object(c, 'toolchains', return_value=verified):
            c.real_preflight(self.config, '/fake/codex')
            self.assertEqual(execute.call_args.args[0], ['/fake/codex', '--version'])
            for exe in [None, 'codex']:
                execute.reset_mock()
                with self.assertRaises(ValueError): c.real_preflight(self.config, exe)
                execute.assert_not_called()
            data = copy.deepcopy(self.config)
            data['live_contract']['status'] = 'blocked'
            execute.reset_mock()
            with self.assertRaises(ValueError): c.real_preflight(data, '/fake/codex')
            execute.assert_not_called()
            with patch.object(c, 'sha', return_value='0'*64):
                with self.assertRaises(ValueError): c.real_preflight(self.config, '/fake/codex')
                execute.assert_not_called()
            with patch.object(b, 'execute', return_value=dict(version, stdout='codex-cli 0.1')):
                with self.assertRaises(ValueError): c.real_preflight(self.config, '/fake/codex')
            with patch.object(c, 'toolchains', return_value={'go':'version-mismatch'}):
                with self.assertRaises(ValueError): c.real_preflight(self.config, '/fake/codex')

    def test_plan_never_invokes_without_real(self):
        import contextlib, io, sys
        for arguments in [[], ['--allow-preliminary-campaign', '--codex', '/fake/codex']]:
            with patch.object(sys, 'argv', ['campaign', *arguments]), \
                 patch.object(b, 'execute') as execute, contextlib.redirect_stdout(io.StringIO()):
                c.main()
                execute.assert_not_called()

    def test_artifacts_refuse_overwrite_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(b, 'ROOT', Path(tmp)):
            target = c.artifact_directory('run')
            self.assertEqual(target.stat().st_mode & 0o777, 0o700)
            with self.assertRaises(ValueError): c.artifact_directory('run')
            (target.parent/'link').symlink_to(target)
            with self.assertRaises(ValueError): c.artifact_directory('link')
            with self.assertRaises(ValueError): c.artifact_directory('../escape')
        with tempfile.TemporaryDirectory() as tmp, patch.object(b, 'ROOT', Path(tmp)):
            (Path(tmp)/'.artifacts').symlink_to(Path(tmp))
            with self.assertRaises(ValueError): c.artifact_directory('run')

    def test_real_runner_fake_only_retains_completed_evidence(self):
        calls = []
        fake = b.FakeRunner()
        def run(s, v, seed, rep, runner, **kwargs):
            self.assertEqual(kwargs['retries'], 0)
            calls.append((seed, rep))
            if len(calls) == 2: raise KeyboardInterrupt
            return b.run(s, v, seed, rep, fake, **kwargs)
        original = b.run
        def wrapped(*args, **kwargs):
            with patch.object(b, 'run', original): return run(*args, **kwargs)
        with tempfile.TemporaryDirectory() as tmp, patch.object(b, 'run', wrapped), \
             patch.object(b, 'grade', return_value=True), patch.object(b, 'execute') as execute:
            with self.assertRaises(KeyboardInterrupt):
                c._real_run(self.config, '/fake/codex', Path(tmp))
            self.assertEqual(len(list(Path(tmp).glob('*.json'))), 1)
            execute.assert_not_called()

    def test_real_runner_command_with_mocked_execution(self):
        job = c.jobs(self.config)[0]
        observation = {'stdout':'{"type":"turn.completed"}\n', 'stderr':'',
                       'exit_status':0, 'timeout':False, 'duration':0.01}
        with tempfile.TemporaryDirectory() as tmp, patch.object(c, 'jobs', return_value=[job]), \
             patch.object(b, 'execute', return_value=observation) as execute, \
             patch.object(b, 'grade', return_value=False):
            report = c._real_run(self.config, '/fake/codex', Path(tmp))
            call = execute.call_args
            self.assertEqual(call.args[0], c.command_plan(self.config, job[1], '/fake/codex'))
            self.assertEqual(call.kwargs['timeout'], 120)
            self.assertEqual(execute.call_count, 1)
            record = json.loads(next(Path(tmp).glob('*.json')).read_text())
            self.assertFalse(record['quality_pass'])
            self.assertEqual(record['retry_count'], 0)
            self.assertEqual(report['summary'][job[1]]['failure_rate'], 1)


if __name__ == '__main__':
    unittest.main()
