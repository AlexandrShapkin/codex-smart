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

    def test_blocked_live_contract_never_claims_observable_usage(self):
        self.assertEqual(self.config['live_contract']['jsonl_events'],0)
        self.assertFalse(self.config['live_contract']['ready_for_measured_campaign'])
        self.assertTrue(all(self.config['metrics'][k]=='not observed' for k in ['input','cached_input','output','reasoning']))
        self.assertNotIn('/home/',c.CONFIG.read_text())


if __name__ == '__main__':
    unittest.main()
