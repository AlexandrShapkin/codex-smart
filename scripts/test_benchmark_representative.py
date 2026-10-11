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
import benchmark_campaign as historical
import benchmark_coverage as coverage
import benchmark_host as host
import benchmark_isolation as isolation
import benchmark_representative as runner


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
            self.assertEqual(host.load_contract()['accepted_qualification_receipts'], [])
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
        self.assertFalse(p['model_execution_enabled'])
        self.assertEqual(c['readiness'], {'real_runner_contract':'prepared',
            'qualified_host_contract':'required-not-verified','grading_isolation_contract':'required-not-verified',
            'representative_campaign_ready':False})
        self.assertEqual(hashlib.sha256(historical.CONFIG.read_bytes()).hexdigest(),
                         'cfc97144156b9321555cc98937d30d85f8e7bd39a5009954ae84d294156502f7')
        self.assertEqual(len(historical.jobs(historical.load())),42)

    def test_pin_and_bounds_drift_before_any_execution(self):
        original = runner.load()
        changes = [('codex', 'executable_sha256', '0'*64), ('codex','version','1.0.0'),
                   ('readiness','grading_isolation_contract','verified'),
                   ('readiness','qualified_host_contract','verified'),
                   ('readiness','representative_campaign_ready',True)]
        with tempfile.TemporaryDirectory() as tmp, patch.object(b,'execute',side_effect=AssertionError('process')):
            path=Path(tmp)/'campaign.json'
            for parent,key,value in changes:
                c=copy.deepcopy(original); c[parent][key]=value; path.write_text(json.dumps(c))
                with self.subTest(parent=parent,key=key),self.assertRaises(ValueError): runner.load(path)
            for tool in original['toolchains']:
                for key,value in [('version','wrong'),('version_arguments',['--unsafe'])]:
                    c=copy.deepcopy(original);c['toolchains'][tool][key]=value;path.write_text(json.dumps(c))
                    with self.subTest(tool=tool,key=key),self.assertRaises(ValueError):runner.load(path)
            for key,value in [('variants',['vanilla','legacy']),('retries',1),('maximum_model_calls',41)]:
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
            # Synthetic future campaign: qualification cannot override isolation.
            c=runner.load();c['readiness']['qualified_host_contract']='verified'
            with patch.object(runner,'load',return_value=c),self.assertRaisesRegex(runner.PreflightRefusal,'grading isolation contract'):
                runner.real_run('/fake/codex','fake',verified_host(),authorized=True)
            c['readiness']['grading_isolation_contract']='verified'
            with patch.object(runner,'load',return_value=c),self.assertRaisesRegex(runner.PreflightRefusal,'backend'):
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
                    runner._grade_submission({'id':'rust-ledger'},Path('/unused'),q)
        with patch.object(isolation,'grade_representative',return_value=isolation.GradeResult('verified','synthetic',True)) as grade:
            self.assertTrue(runner._grade_submission({'id':'explore-notification'},Path('/unused'),verified_host()))
            self.assertEqual(grade.call_args.kwargs['policy'],isolation.SubmissionPolicy(True,('answer.json',)))
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
                                   qualification_reference='1'*64,isolation_reference='2'*64,artifacts=artifacts)

    def test_fake_full_plan_normalized_privacy_and_failures(self):
        for mode,reason in [('success',None),('process','process-failure'),('trace','trace-invalid'),
                            ('grading','grading-refusal'),('quality','quality-failure')]:
            report=self.fake_run(mode)
            self.assertEqual((report['planned_jobs'],report['attempted_jobs'],report['model_calls']),(40,40,0))
            self.assertNotIn('PRIVATE_SENTINEL',json.dumps(report))
            self.assertNotIn('/tmp/',json.dumps(report))
            for r in report['records']:
                self.assertEqual(r['failure_reason'],reason)
                self.assertEqual(r['retry_count'],0)
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
                    qualification_reference='1'*64,isolation_reference='2'*64,artifacts=target)
            records=list(target.glob('*.json'));self.assertEqual(len(records),1)
            self.assertEqual(json.loads(records[0].read_text())['attempt_count'],1)

    def test_settings_equivalence(self):
        c=runner.load()
        self.assertEqual(historical.command_plan(c,'vanilla','/fake/codex'),historical.command_plan(c,'native','/fake/codex'))
        s=coverage.load_manifest()['scenarios'][0]
        self.assertEqual(historical.prompt(c,s,'native'),historical.prompt(c,s,'vanilla')+historical.NATIVE_INSTRUCTION)

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

    def test_identity_refuses_before_any_model_command(self):
        c=runner.load()
        with patch.object(historical,'sha',return_value='0'*64),patch.object(b,'execute') as execute:
            with self.assertRaisesRegex(ValueError,'checksum'):runner._identity_preflight(c,'/fake/codex')
            execute.assert_not_called()
        for version,tool_status in [('codex-cli 0.162.0',{}),('codex-cli 0.162.1',{'cargo':'version-mismatch'})]:
            with patch.object(historical,'sha',return_value=c['codex']['executable_sha256']), \
                 patch.object(b,'execute',return_value={'stdout':version,'timeout':False,'exit_status':0}) as execute, \
                 patch.object(historical,'toolchains',return_value=tool_status):
                with self.assertRaises(ValueError):runner._identity_preflight(c,'/fake/codex')
                self.assertEqual(execute.call_args.args[0],['/fake/codex','--version'])

    def test_gate_order_authorization_and_artifact_rejection(self):
        c=runner.load();c['readiness']['qualified_host_contract']='verified';c['readiness']['grading_isolation_contract']='verified'
        with patch.object(runner,'load',return_value=c), \
             patch.object(isolation,'representative_contract_verified',return_value=True), \
             patch.object(runner,'_identity_preflight') as identity, \
             patch.object(historical,'artifact_directory') as artifact, \
             patch.object(runner,'_run_jobs') as execute:
            with self.assertRaisesRegex(runner.PreflightRefusal,'authorization'):
                runner.real_run('/fake/codex','fake',verified_host())
            identity.assert_called_once();artifact.assert_not_called();execute.assert_not_called()
            artifact.side_effect=ValueError('existing run evidence')
            with self.assertRaisesRegex(runner.PreflightRefusal,'artifact'):
                runner.real_run('/fake/codex','fake',verified_host(),authorized=True)
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
                qualification_reference='1'*64,isolation_reference='2'*64)
        self.assertEqual(sum(not x['quality_pass'] for x in r['records']),1)
        self.assertEqual([s['cost_samples'] for s in r['summary'].values()],[19,19])

    def test_historical_entry_cannot_become_alternate_representative_path(self):
        with patch.object(b,'execute',side_effect=AssertionError('process')), \
             self.assertRaisesRegex(ValueError,'grading isolation'):
            historical.real_run('/fake/codex','fake',allow_preliminary_campaign=True)


if __name__=='__main__':unittest.main()
