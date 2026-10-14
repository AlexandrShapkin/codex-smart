"""Fake-only qualification and representative boundary regression tests."""
import copy
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

import benchmark as b
import benchmark_agent_isolation as agent_isolation
import benchmark_campaign as historical
import benchmark_coverage as coverage
import benchmark_host as host
import benchmark_grading_backend as grading_backend
import benchmark_isolation as isolation
import benchmark_representative as runner
import benchmark_submission_grading as submission_grading


def verified_host():
    # Synthetic unit-test evidence, never a runtime qualification receipt.
    return host.qualify(host.HostQualificationEvidence('benchmark-qualified-host-v1', tuple(
        host.ComponentEvidence(n, 'verified', '1' * 64) for n in host.COMPONENTS)))


class RepresentativeRunnerTests(unittest.TestCase):
    def setUp(self):
        # Synthetic reviewed receipts for unit tests only; no host probes performed.
        receipt = patch.object(host, '_receipt_reviewed', return_value=True)
        receipt.start()
        self.addCleanup(receipt.stop)

    def test_self_asserted_verified_components_are_not_qualified(self):
        with patch.object(host, '_receipt_reviewed', return_value=False):
            q = verified_host()
            self.assertEqual(q.status, 'not-verified')
            self.assertEqual(host.load_contract()['accepted_qualification_receipts'],
                             ['d2af64ce237de72c9c0ee2659723e2d2858c9e19982cc85dd4420a6c6592d265'])
            with patch.object(b,'execute',side_effect=AssertionError('process')),self.assertRaises(runner.PreflightRefusal):
                runner.real_run('/fake/codex','fake',q,authorized=True)

    def test_current_host_offline_and_unqualified(self):
        with patch.object(b, 'execute', side_effect=AssertionError('process')):
            q = host.current_host()
        self.assertEqual(q.status, 'not-verified')
        self.assertEqual({c.state for c in q.evidence.components if c.component.startswith('aggregate')}, {'blocked'})

    def test_every_missing_or_nonverified_component_blocks(self):
        good = verified_host().evidence
        for component in host.COMPONENTS:
            for state in ['blocked', 'unavailable', 'not-verified']:
                evidence = host.HostQualificationEvidence(good.contract_id, tuple(
                    host.ComponentEvidence(c.component, state if c.component == component else c.state,
                                           c.evidence_sha256) for c in good.components))
                with self.subTest(component=component, state=state):
                    self.assertEqual(host.qualify(evidence).status, 'not-verified')
            missing = host.HostQualificationEvidence(good.contract_id, tuple(
                c for c in good.components if c.component != component))
            with self.assertRaises(ValueError): host.qualify(missing)
        for state in ['unknown', True, None]:
            bad = host.HostQualificationEvidence(good.contract_id, (
                host.ComponentEvidence(host.COMPONENTS[0], state), *good.components[1:]))
            with self.assertRaises(ValueError): host.qualify(bad)
        bad = host.HostQualificationEvidence(good.contract_id, tuple(
            host.ComponentEvidence(n, 'verified') for n in host.COMPONENTS))
        with self.assertRaises(ValueError): host.qualify(bad)

    def test_host_contract_and_references_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'contract.json'
            c = host.expected_contract(); c['authorization_overrides_security'] = True
            p.write_text(json.dumps(c))
            with self.assertRaises(ValueError): host.load_contract(p)
        q = verified_host().evidence
        for value in ['/private/sentinel', 'secret', 'X'*64]:
            e = host.HostQualificationEvidence(q.contract_id, (
                host.ComponentEvidence(host.COMPONENTS[0], 'verified', value), *q.components[1:]))
            with self.assertRaises(ValueError): host.qualify(e)

    def test_plan_bounds_and_historical_bytes(self):
        c = runner.load(); p = runner.plan()
        self.assertEqual(len(runner.jobs(c)), 40)
        self.assertEqual(len(set(runner.jobs(c))), 40)
        self.assertEqual(c['variants'], ['vanilla','native'])
        self.assertEqual((c['repetitions'], c['seeds'], c['retries'], c['timeout_seconds']), (2,[14],0,120))
        self.assertEqual(p['model_calls'], 0)
        self.assertEqual(p['maximum_codex_executions'], 40)
        self.assertNotIn('maximum_model_calls', p)
        self.assertFalse(p['model_execution_enabled'])
        self.assertEqual(c['readiness'], {'real_runner_contract':'verified',
            'agent_execution_isolation_contract':'verified',
            'grading_isolation_contract':'verified',
            'production_grading_contract':'verified',
            'qualified_host_contract':'verified',
            'representative_campaign_ready':True})
        self.assertEqual(hashlib.sha256(historical.CONFIG.read_bytes()).hexdigest(),
                         'cfc97144156b9321555cc98937d30d85f8e7bd39a5009954ae84d294156502f7')
        historical_codex = historical.load()['codex']
        self.assertEqual(historical_codex['executable_sha256'],
                         '89cc44e820780120ba2c8bc4585c014815bdc7a1fc494c337a585a2c78dc59eb')
        self.assertEqual(c['codex']['distribution'], 'upstream-release')
        self.assertEqual(c['codex']['release_asset'], 'codex-x86_64-unknown-linux-musl.tar.gz')
        self.assertEqual(c['codex']['release_asset_sha256'],
                         '86f268d81b898f3e144c5ecff2ad2fda2c5802e042d6195b72538fe0fa125057')
        self.assertEqual(c['codex']['executable_sha256'],
                         '628e35487d888a28f0427fc37501da529dd3d81fcbad7a2c3421c1e8670d92e1')
        self.assertNotEqual(c['codex']['executable_sha256'], historical_codex['executable_sha256'])
        self.assertEqual(len(historical.jobs(historical.load())),42)

    def test_pin_and_bounds_drift_before_any_execution(self):
        original = runner.load()
        changes = [('codex', 'executable_sha256', '0'*64), ('codex','version','1.0.0'),
                   ('readiness','real_runner_contract','prepared'),
                   ('readiness','agent_execution_isolation_contract','required-not-verified'),
                   ('readiness','grading_isolation_contract','required-not-verified'),
                   ('readiness','production_grading_contract','required-not-verified'),
                   ('readiness','qualified_host_contract','required-not-verified'),
                   ('readiness','representative_campaign_ready',False)]
        with tempfile.TemporaryDirectory() as tmp, patch.object(b,'execute',side_effect=AssertionError('process')):
            path=Path(tmp)/'campaign.json'
            for parent,key,value in changes:
                c=copy.deepcopy(original); c[parent][key]=value; path.write_text(json.dumps(c))
                with self.subTest(parent=parent,key=key),self.assertRaises(ValueError): runner.load(path)
            for tool in original['toolchains']:
                for key,value in [('version','wrong'),('version_arguments',['--unsafe'])]:
                    c=copy.deepcopy(original);c['toolchains'][tool][key]=value;path.write_text(json.dumps(c))
                    with self.subTest(tool=tool,key=key),self.assertRaises(ValueError):runner.load(path)
            for key,value in [('variants',['vanilla','legacy']),('retries',1),('maximum_codex_executions',41)]:
                c=copy.deepcopy(original);c[key]=value;path.write_text(json.dumps(c))
                with self.assertRaises(ValueError):runner.load(path)
            c=copy.deepcopy(original);c['runner_pins']['runner_sha256']='0'*64;path.write_text(json.dumps(c))
            with self.assertRaises(ValueError):runner.load(path)

    def test_public_entry_refuses_before_artifacts_and_process(self):
        with patch.object(b,'execute',side_effect=AssertionError('process')), \
             patch.object(runner,'_identity_preflight',side_effect=AssertionError('identity')), \
             patch.object(historical,'artifact_directory',side_effect=AssertionError('artifacts')):
            for authorized in [False,True]:
                for q in [host.current_host(), verified_host(), None]:
                    with self.assertRaises(runner.PreflightRefusal) as caught:
                        runner.real_run('/fake/codex','fake',q,authorized=authorized)
                    self.assertEqual(caught.exception.model_calls,0)
                    self.assertEqual(caught.exception.attempt_count,0)
            # Frozen readiness and accepted evidence remain independent gates.
            base=runner.load()
            c=copy.deepcopy(base);c['readiness']['qualified_host_contract']='required-not-verified'
            with patch.object(runner,'load',return_value=c),self.assertRaisesRegex(runner.PreflightRefusal,'qualified host contract'):
                runner.real_run('/fake/codex','fake',verified_host(),authorized=True)
            c=copy.deepcopy(base);c['readiness']['agent_execution_isolation_contract']='required-not-verified'
            with patch.object(runner,'load',return_value=c),self.assertRaisesRegex(runner.PreflightRefusal,'agent execution isolation contract'):
                runner.real_run('/fake/codex','fake',verified_host(),authorized=True)
            with patch.object(runner,'load',return_value=base), \
                 patch.object(agent_isolation,'representative_contract_verified',return_value=False), \
                 self.assertRaisesRegex(runner.PreflightRefusal,'agent execution isolation evidence'):
                runner.real_run('/fake/codex','fake',verified_host(),authorized=True)
            c=copy.deepcopy(base);c['readiness']['grading_isolation_contract']='required-not-verified'
            with patch.object(runner,'load',return_value=c), \
                 patch.object(agent_isolation,'representative_contract_verified',return_value=True), \
                 self.assertRaisesRegex(runner.PreflightRefusal,'grading isolation contract'):
                runner.real_run('/fake/codex','fake',verified_host(),authorized=True)
            with patch.object(runner,'load',return_value=base), \
                 patch.object(agent_isolation,'representative_contract_verified',return_value=True), \
                 patch.object(isolation,'representative_contract_verified',return_value=False), \
                 self.assertRaisesRegex(runner.PreflightRefusal,'backend'):
                runner.real_run('/fake/codex','fake',verified_host(),authorized=True)
            c=copy.deepcopy(base);c['readiness']['production_grading_contract']='required-not-verified'
            with patch.object(runner,'load',return_value=c), \
                 patch.object(agent_isolation,'representative_contract_verified',return_value=True), \
                 patch.object(isolation,'representative_contract_verified',return_value=True), \
                 self.assertRaisesRegex(runner.PreflightRefusal,'production grading contract'):
                runner.real_run('/fake/codex','fake',verified_host(),authorized=True)
            with patch.object(runner,'load',return_value=base), \
                 patch.object(agent_isolation,'representative_contract_verified',return_value=True), \
                 patch.object(isolation,'representative_contract_verified',return_value=True), \
                 patch.object(runner.submission_grading,'contract_verified',return_value=False), \
                 self.assertRaisesRegex(runner.PreflightRefusal,'production grading evidence'):
                runner.real_run('/fake/codex','fake',verified_host(),authorized=True)
            c=copy.deepcopy(base);c['readiness']['representative_campaign_ready']=False
            with patch.object(runner,'load',return_value=c), \
                 patch.object(agent_isolation,'representative_contract_verified',return_value=True), \
                 patch.object(isolation,'representative_contract_verified',return_value=True), \
                 patch.object(runner.submission_grading,'contract_verified',return_value=True), \
                 self.assertRaisesRegex(runner.PreflightRefusal,'campaign is not ready'):
                runner.real_run('/fake/codex','fake',verified_host(),authorized=True)

    def test_cli_no_bypass_no_default_execution(self):
        with patch.object(b,'execute',side_effect=AssertionError('process')), \
             patch.object(historical,'artifact_directory',side_effect=AssertionError('artifacts')), \
             contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            runner.main([])
            for args in [['--real'],['--real','--authorize-execution','--codex','/fake/codex'],['--force'],['--unsafe']]:
                with self.assertRaises(SystemExit) as e: runner.main(args)
                self.assertEqual(e.exception.code,2)

    def test_isolation_adapter_never_direct_host_grades(self):
        with patch.object(coverage.graders,'check',side_effect=AssertionError('host grader')), \
             patch.object(b,'execute',side_effect=AssertionError('process')):
            for q in [host.current_host(),verified_host()]:
                with self.assertRaisesRegex(ValueError,'grading-isolation-refused'):
                    runner._grade_submission({'id':'rust-ledger'},Path('/unused'),q,'runtime')
        with patch.object(isolation,'grade_representative',return_value=isolation.GradeResult('verified','synthetic',True)) as grade:
            self.assertTrue(runner._grade_submission({'id':'explore-notification'},Path('/unused'),verified_host(),'runtime'))
            self.assertEqual(grade.call_args.kwargs['policy'],isolation.SubmissionPolicy(True,('answer.json',)))
            self.assertEqual(grade.call_args.kwargs['runtime'],'runtime')
        self.assertEqual(isolation.grade_representative('explore-notification',Path('/unused'),verified_host()).reason,
                         'submission-policy-mismatch')

    def fake_run(self, mode='success', artifacts=None):
        def fake(s,variant,workspace):
            b.materialize(coverage.fixture(s)['reference'],workspace)
            raw = '{bad' if mode=='trace' else json.dumps({'type':'turn.completed','usage':{'input_tokens':12},
                       'arbitrary_payload':'PRIVATE_SENTINEL'})+'\n'
            return {'stdout':raw,'stderr':'PRIVATE_SENTINEL','exit_status':1 if mode=='process' else 0,
                    'timeout':False,'duration':0.001}
        def grade(s,w):
            if mode=='grading': raise ValueError('PRIVATE_SENTINEL')
            return mode!='quality'
        with patch.object(b,'execute',side_effect=AssertionError('process')), \
             patch.object(coverage.graders,'check',side_effect=AssertionError('host grader')):
            return runner._run_jobs(runner.load(),runner.CONFIG,fake,grade,
                                   qualification_reference='1'*64,agent_isolation_reference='3'*64,
                                   isolation_reference='2'*64,artifacts=artifacts)

    def test_fake_full_plan_normalized_privacy_and_failures(self):
        for mode,reason in [('success',None),('process','process-failure'),('trace','trace-invalid'),
                            ('grading','grading-refusal'),('quality','quality-failure')]:
            report=self.fake_run(mode)
            self.assertEqual((report['planned_jobs'],report['attempted_jobs'],report['model_calls']),(40,40,None))
            self.assertNotIn('PRIVATE_SENTINEL',json.dumps(report))
            self.assertNotIn('/tmp/',json.dumps(report))
            for r in report['records']:
                self.assertEqual(r['failure_reason'],reason)
                self.assertEqual(r['retry_count'],0)
                self.assertEqual(r['production_grading_reference'],'synthetic-production-grading')
                self.assertEqual(r['grading_runtime_inventory_reference'],'synthetic-runtime-inventory')
                self.assertIsNone(r['observed_tokens']['fresh_input'])
                self.assertIsNone(r['observed_tokens']['total'])
                self.assertIsNone(r['full_tool_calls'])
            for s in report['summary'].values():
                self.assertEqual(s['runs'],20)
                self.assertEqual(s['cost_samples'],20 if mode=='success' else 0)
                self.assertEqual(s['failure_rate'],0 if mode=='success' else 1)

    def test_interruption_retains_completed_normalized_evidence(self):
        count=0
        def fake(s,v,w):
            nonlocal count
            count+=1
            if count==2:raise KeyboardInterrupt
            return {'stdout':'{"type":"turn.completed"}\n','stderr':'','exit_status':0,'timeout':False,'duration':0.001}
        with tempfile.TemporaryDirectory() as tmp,patch.object(b,'execute',side_effect=AssertionError('process')):
            target=Path(tmp)
            with self.assertRaises(KeyboardInterrupt):
                runner._run_jobs(runner.load(),runner.CONFIG,fake,lambda s,w:True,
                    qualification_reference='1'*64,agent_isolation_reference='3'*64,
                    isolation_reference='2'*64,artifacts=target)
            records=list(target.glob('*.json'));self.assertEqual(len(records),1)
            self.assertEqual(json.loads(records[0].read_text())['attempt_count'],1)

    def test_settings_equivalence(self):
        c=runner.load()
        historical_vanilla = historical.command_plan(c,'vanilla','/fake/codex')
        historical_native = historical.command_plan(c,'native','/fake/codex')
        self.assertEqual(historical_vanilla,historical_native)
        representative_vanilla = runner.command_plan(c,'vanilla','/fake/codex')
        representative_native = runner.command_plan(c,'native','/fake/codex')
        self.assertEqual(representative_vanilla,representative_native)
        self.assertEqual(c['settings']['shell_environment_policy'],
                         {'inherit':'core','ignore_default_excludes':False})
        self.assertEqual(c['settings']['disabled_features'], list(agent_isolation.DISABLED_FEATURES))
        self.assertEqual(c['settings']['permission_profile'], {'id':'benchmark','extends':':workspace',
                         'filesystem':{'~/.local/share/keyrings':'deny'}})
        self.assertEqual(c['settings']['credential_backing_store'],
                         {'child_unreadable_paths':['~/.local/share/keyrings']})
        self.assertIn('default_permissions="benchmark"', representative_vanilla)
        self.assertIn('permissions.benchmark.extends=":workspace"', representative_vanilla)
        self.assertIn('permissions.benchmark.filesystem={"~/.local/share/keyrings"="deny"}', representative_vanilla)
        self.assertIn('shell_environment_policy.inherit=core', representative_vanilla)
        self.assertIn('shell_environment_policy.ignore_default_excludes=false', representative_vanilla)
        for feature in agent_isolation.DISABLED_FEATURES:
            self.assertIn(f'features.{feature}=false', representative_vanilla)
        self.assertNotEqual(representative_vanilla,historical_vanilla)
        s=coverage.load_manifest()['scenarios'][0]
        self.assertEqual(historical.prompt(c,s,'native'),historical.prompt(c,s,'vanilla')+historical.NATIVE_INSTRUCTION)

    def test_agent_candidate_rehashed_unsafe_outcomes_remain_unaccepted(self):
        # Fake reviewed components isolate the downstream gate from receipt review.
        # This does not qualify a real host or change any accepted contract bytes.
        safe = agent_isolation.load_candidate_evidence()
        accepted = 'ae2840a92172e46eedf574885bf2d68a31043f5d0ad9a586fc8a9921aea848cb'
        self.assertEqual(safe['evidence_reference'], accepted)
        outcomes = {
            'auth_file_absent': True,
            'api_key_in_child_environment': False,
            'user_bus_connectable': False,
            'private_bus_address_in_child_environment': False,
            'private_bus_connectable': False,
            'credential_backing_store_readable': False,
            'external_tool_surface_disabled': True,
            'command_paths_reviewed': True,
        }
        self.assertEqual({key: safe['candidate'][key] for key in outcomes}, outcomes)

        def qualification(reference):
            return host.qualify(host.HostQualificationEvidence(
                'benchmark-qualified-host-v1', tuple(
                    host.ComponentEvidence(name, 'verified',
                        reference if name == agent_isolation.COMPONENT else '1' * 64)
                    for name in host.COMPONENTS)))

        self.assertTrue(agent_isolation.representative_contract_verified(qualification(accepted)))
        self.assertFalse(agent_isolation.representative_contract_verified(qualification('0' * 64)))
        missing = host.HostQualificationEvidence('benchmark-qualified-host-v1', tuple(
            row for row in qualification(accepted).evidence.components
            if row.component != agent_isolation.COMPONENT))
        with self.assertRaisesRegex(ValueError, 'missing or unordered'):
            host.qualify(missing)

        loader = agent_isolation.load_candidate_evidence
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'synthetic-agent.json'
            for key, value in outcomes.items():
                with self.subTest(outcome=key):
                    changed = copy.deepcopy(safe)
                    changed['candidate'][key] = not value
                    # Independently normalize/re-hash, rather than relying on the loader.
                    changed['evidence_reference'] = hashlib.sha256(json.dumps(
                        changed['candidate'], sort_keys=True, separators=(',', ':')
                    ).encode()).hexdigest()
                    path.write_text(json.dumps(changed))
                    loaded = loader(path)
                    self.assertEqual(loaded, changed)  # Loader does not reject safe-value drift.
                    reference = loaded['evidence_reference']
                    self.assertNotIn(reference, agent_isolation.load_contract()['accepted_evidence_sha256'])
                    with patch.object(agent_isolation, 'load_candidate_evidence', return_value=loaded):
                        # Even a matching independently reviewed synthetic component cannot
                        # turn an unaccepted rehashed candidate into accepted evidence.
                        self.assertFalse(agent_isolation.representative_contract_verified(
                            qualification(reference)))
                        self.assertFalse(agent_isolation.representative_contract_verified(
                            qualification(accepted)))

    def test_agent_execution_isolation_contract_fail_closed(self):
        contract = agent_isolation.load_contract()
        self.assertEqual(contract['accepted_evidence_sha256'],
                         ['ae2840a92172e46eedf574885bf2d68a31043f5d0ad9a586fc8a9921aea848cb'])
        self.assertFalse(agent_isolation.representative_contract_verified(verified_host()))
        payload = {'codex_executable_sha256':contract['codex_executable_sha256'],
                   'auth_file_absent':True,'api_key_in_child_environment':False,
                   'user_bus_connectable':False,
                   'private_bus_address_in_child_environment':False,
                   'private_bus_connectable':False,'credential_backing_store_readable':False,
                   'external_tool_surface_disabled':True,
                   'command_paths_reviewed':True}
        self.assertRegex(agent_isolation.evidence_reference(payload), r'^[0-9a-f]{64}$')
        candidate = agent_isolation.load_candidate_evidence()
        self.assertEqual(candidate['evidence_reference'], agent_isolation.evidence_reference(candidate['candidate']))
        self.assertIn(candidate['evidence_reference'], contract['accepted_evidence_sha256'])
        self.assertFalse(candidate['real_credentials_used'])
        self.assertEqual(candidate['model_calls'], 0)
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)/'.codex'; home.mkdir()
            self.assertEqual(agent_isolation.runtime_preflight({'CODEX_HOME':str(home)}), home)
            with self.assertRaisesRegex(ValueError,'API-key'):
                agent_isolation.runtime_preflight({'CODEX_HOME':str(home),'OPENAI_API_KEY':'synthetic'})
            (home/'auth.json').write_text('{"synthetic":true}')
            with self.assertRaisesRegex(ValueError,'file auth'):
                agent_isolation.runtime_preflight({'CODEX_HOME':str(home)})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'agent.json'
            changed=agent_isolation.expected_contract();changed['authorization_overrides_security']=True
            path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):agent_isolation.load_contract(path)

    def test_imported_receipt_cannot_enable_execution(self):
        q = verified_host().evidence
        data = {'contract_id':q.contract_id,'components':[
            {'component':c.component,'state':c.state,'evidence_sha256':c.evidence_sha256}
            for c in q.components]}
        with tempfile.TemporaryDirectory() as tmp, patch.object(b,'execute',side_effect=AssertionError('process')):
            path = Path(tmp)/'receipt.json';path.write_text(json.dumps(data))
            self.assertEqual(host.load_evidence(path).status,'verified')
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    runner.main(['--real','--authorize-execution','--qualification-evidence',str(path)])
            data['status']='verified';path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):host.load_evidence(path)
            link=Path(tmp)/'link';link.symlink_to(path)
            with self.assertRaises(ValueError):host.load_evidence(link)

    def test_identity_refuses_before_any_model_command_and_uses_staged_tools(self):
        c=runner.load()
        runtime=submission_grading.PreparedRuntime(Path('/tmp/staged-runtime'),'9'*64,(1,2),())
        with patch.object(historical,'sha',return_value='0'*64),patch.object(b,'execute') as execute:
            with self.assertRaisesRegex(ValueError,'checksum'):
                runner._identity_preflight(c,'/fake/codex',runtime)
            execute.assert_not_called()

        with patch.object(historical,'sha',return_value=c['codex']['executable_sha256']), \
             patch.object(b,'execute',return_value={'stdout':'codex-cli 0.162.0','timeout':False,'exit_status':0}) as execute, \
             patch.object(historical,'toolchains',side_effect=AssertionError('host PATH toolchains')):
            with self.assertRaisesRegex(ValueError,'Codex version'):
                runner._identity_preflight(c,'/fake/codex',runtime)
            self.assertEqual(execute.call_args.args[0],['/fake/codex','--version'])

        expected={name:spec['version'] for name,spec in c['toolchains'].items()}
        def observe(argv, *_args, **_kwargs):
            if argv==['/fake/codex','--version']:
                stdout='codex-cli 0.162.1'
            else:
                name={'rustc':'rustc','cargo':'cargo','go':'go','python3':'python3'}[Path(argv[0]).name]
                stdout=('wrong' if name=='cargo' else expected[name])
            return {'stdout':stdout,'stderr':'','timeout':False,'exit_status':0,'duration':0.0}
        with patch.object(historical,'sha',return_value=c['codex']['executable_sha256']), \
             patch.object(b,'execute',side_effect=observe), \
             patch.object(historical,'toolchains',side_effect=AssertionError('host PATH toolchains')):
            with self.assertRaisesRegex(ValueError,'toolchain mismatch'):
                runner._identity_preflight(c,'/fake/codex',runtime)

    def test_real_command_uses_frozen_staged_child_environment(self):
        c=runner.load()
        with tempfile.TemporaryDirectory() as root_tmp, tempfile.TemporaryDirectory() as work_tmp:
            runtime=submission_grading.PreparedRuntime(Path(root_tmp),'9'*64,(1,2),())
            workspace=Path(work_tmp)
            env=runner._staged_environment(c,runtime,workspace)
            self.assertTrue(env['PATH'].startswith(str(runtime.root/'rust/bin')+':'))
            self.assertIn(str(runtime.root/'linker/bin'),env['PATH'])
            self.assertEqual(env['GOTOOLCHAIN'],'local')
            self.assertEqual(env['CARGO_NET_OFFLINE'],'true')
            self.assertEqual(env['CARGO_HOME'],str(workspace/'.cargo-home'))
            argv=runner.command_plan(c,'vanilla','/fake/codex',runtime=runtime,workspace=workspace)
        setting=next(value for value in argv if value.startswith('shell_environment_policy.set='))
        self.assertIn('GOPROXY=\"off\"',setting)
        self.assertIn('PATH=\"',setting)
        self.assertNotIn('OPENAI_API_KEY',setting)

    def test_gate_order_authorization_and_artifact_rejection(self):
        c=runner.load()
        prepared=Mock(inventory_reference='9'*64)
        with patch.object(runner,'load',return_value=c), \
             patch.object(agent_isolation,'representative_contract_verified',return_value=True), \
             patch.object(agent_isolation,'runtime_preflight') as agent_runtime, \
             patch.object(isolation,'representative_contract_verified',return_value=True), \
             patch.object(runner.submission_grading,'contract_verified',return_value=True), \
             patch.object(runner.submission_grading,'prepare_runtime',return_value=prepared) as grading_runtime, \
             patch.object(runner,'_identity_preflight') as identity, \
             patch.object(historical,'artifact_directory') as artifact, \
             patch.object(runner,'_run_jobs') as execute:
            with self.assertRaisesRegex(runner.PreflightRefusal,'authorization'):
                runner.real_run('/fake/codex','fake',verified_host(),
                                grading_runtime_root='/tmp/benchmark-runtime-test',
                                grading_inventory_dir='/tmp/inventory')
            identity.assert_called_once();agent_runtime.assert_called_once();grading_runtime.assert_called_once()
            artifact.assert_not_called();execute.assert_not_called()
            artifact.side_effect=ValueError('existing run evidence')
            with self.assertRaisesRegex(runner.PreflightRefusal,'artifact'):
                runner.real_run('/fake/codex','fake',verified_host(),
                                grading_runtime_root='/tmp/benchmark-runtime-test',
                                grading_inventory_dir='/tmp/inventory',authorized=True)
            execute.assert_not_called()

    def test_one_failed_run_excludes_both_matching_cost_samples(self):
        count=0
        def fake(s,v,w):
            nonlocal count
            count+=1
            return {'stdout':'{"type":"turn.completed"}\n','stderr':'','exit_status':int(count==1),
                    'timeout':False,'duration':0.001}
        with patch.object(b,'execute',side_effect=AssertionError('process')):
            r=runner._run_jobs(runner.load(),runner.CONFIG,fake,lambda s,w:True,
                qualification_reference='1'*64,agent_isolation_reference='3'*64,
                isolation_reference='2'*64)
        self.assertEqual(sum(not x['quality_pass'] for x in r['records']),1)
        self.assertEqual([s['cost_samples'] for s in r['summary'].values()],[19,19])

    def test_historical_entry_cannot_become_alternate_representative_path(self):
        with patch.object(b,'execute',side_effect=AssertionError('process')), \
             self.assertRaisesRegex(ValueError,'grading isolation'):
            historical.real_run('/fake/codex','fake',allow_preliminary_campaign=True)


class ReviewedQualificationTests(unittest.TestCase):
    def test_committed_candidate_receipt_is_reviewed_and_verified(self):
        candidate = host.load_candidate_evidence()
        receipt_path = Path(__file__).resolve().parent.parent / 'benchmarks/qualified-host-receipt-v1.json'
        q = host.load_evidence(receipt_path)
        self.assertEqual(candidate['receipt_reference'],
                         'd2af64ce237de72c9c0ee2659723e2d2858c9e19982cc85dd4420a6c6592d265')
        self.assertEqual(q.reference, candidate['receipt_reference'])
        self.assertEqual(q.status, 'verified')
        self.assertTrue(agent_isolation.representative_contract_verified(q))
        self.assertTrue(grading_backend.representative_contract_verified(q))
        self.assertTrue(submission_grading.contract_verified(q))
        grading_candidate=submission_grading.load_candidate_evidence()
        self.assertEqual(grading_candidate['evidence_reference'],
                         '199ec7721ec56c57f1e09f19267e8888cc3f1ee31a8ccf754a4b0af0742bf602')
        self.assertIn(grading_candidate['evidence_reference'],
                      submission_grading.load_contract()['accepted_evidence_sha256'])
        self.assertEqual(candidate['model_calls'], 0)
        self.assertFalse(candidate['real_credentials_used'])
        self.assertFalse(candidate['supplemental_exact_bwrap_0_13_crosscheck']['used_for_receipt'])

    def test_reviewed_receipt_still_requires_prepared_runtime_before_authorization(self):
        receipt_path = Path(__file__).resolve().parent.parent / 'benchmarks/qualified-host-receipt-v1.json'
        q = host.load_evidence(receipt_path)
        with patch.object(runner,'_identity_preflight'), \
             patch.object(agent_isolation,'runtime_preflight'), \
             patch.object(historical,'artifact_directory',side_effect=AssertionError('artifacts')), \
             patch.object(b,'execute',side_effect=AssertionError('model execution')):
            with self.assertRaisesRegex(runner.PreflightRefusal,'production grading runtime is not prepared'):
                runner.real_run('/fake/codex','fake',q,authorized=True)

    def test_all_verified_but_unreviewed_receipt_remains_blocked(self):
        receipt_path = Path(__file__).resolve().parent.parent / 'benchmarks/qualified-host-receipt-v1.json'
        q = host.load_evidence(receipt_path)
        changed = host.HostQualificationEvidence(q.evidence.contract_id, tuple(
            host.ComponentEvidence(
                c.component, c.state,
                ('0' * 64 if c.component == 'platform' else c.evidence_sha256))
            for c in q.evidence.components))
        self.assertEqual(host.qualify(changed).status, 'not-verified')

    def test_candidate_evidence_tamper_fails_closed(self):
        candidate = json.loads(host.CANDIDATE_EVIDENCE.read_text())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'candidate.json'
            changed = copy.deepcopy(candidate)
            changed['components'][0]['evidence']['architecture'] = 'tampered'
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, 'normalized host evidence reference mismatch'):
                host.load_candidate_evidence(path)

            changed = copy.deepcopy(candidate)
            changed['receipt_reference'] = '0' * 64
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, 'receipt reference mismatch'):
                host.load_candidate_evidence(path)

    def test_contract_pins_exact_candidate_file(self):
        contract = host.load_contract()
        self.assertEqual(
            hashlib.sha256(host.CANDIDATE_EVIDENCE.read_bytes()).hexdigest(),
            contract['candidate_qualification_evidence_sha256'])
        self.assertEqual(contract['accepted_qualification_receipts'],
                         ['d2af64ce237de72c9c0ee2659723e2d2858c9e19982cc85dd4420a6c6592d265'])


if __name__=='__main__':unittest.main()
