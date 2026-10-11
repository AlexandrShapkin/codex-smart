import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import benchmark as b


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.m = b.load_manifest()
        self.s = self.m['scenarios'][2]

    def test_manifest(self):
        self.assertEqual(len(self.m['scenarios']), 7)
        self.assertEqual({s['domain'] for s in self.m['scenarios']}, {'Rust','Go','Python','IaC'})
        self.assertFalse(self.m['variants']['legacy']['available'])
        self.assertFalse(self.m['variants']['router-v2']['available'])

    def test_manifest_rejects_contract(self):
        for change in ('schema', 'snapshot', 'duplicate', 'path', 'variant'):
            m = copy.deepcopy(self.m)
            if change == 'schema': m['schema_version'] = 2
            if change == 'snapshot': m['scenarios'][0]['snapshot'] = 'wrong'
            if change == 'duplicate': m['scenarios'].append(m['scenarios'][0])
            if change == 'path': m['scenarios'][0]['fixture'] = '../bad'
            if change == 'variant': m['scenarios'][0]['allowed_variants'] = ['invented']
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp)/'manifest.json'
                p.write_text(json.dumps(m))
                with self.assertRaises(ValueError): b.load_manifest(p)

    def test_setup_rejects_dirty_and_wrong_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            s = dict(self.s, snapshot='wrong')
            with self.assertRaises(ValueError): b.setup(s,d)
            b.setup(self.s,d)
            with self.assertRaises(ValueError): b.setup(self.s,d)

    def test_ordering(self):
        a = b.ordering(self.m,3,14)
        self.assertEqual(a,b.ordering(self.m,3,14))
        self.assertNotEqual(a,b.ordering(self.m,3,15))
        self.assertEqual(len(a),84)
        with self.assertRaises(ValueError): b.ordering(self.m,0,14)

    def test_parser_documentation_fixture(self):
        parsed = b.parse_trace((b.ROOT/'fixtures'/'official-example.jsonl').read_text())
        self.assertFalse(parsed['errors'])
        self.assertEqual(parsed['tokens']['input'],24763)
        self.assertEqual(parsed['tokens']['reasoning'],0)
        self.assertIsNone(parsed['tokens']['total'])
        self.assertIsNone(parsed['tool_calls'])

    def test_parser_missing_unknown_fields(self):
        x = b.parse_trace('{"type":"future.event","secret":"PRIVATE"}\n{"type":"turn.completed","usage":{"new_counter":33}}\n')
        self.assertFalse(x['errors'])
        self.assertTrue(all(v is None for v in x['tokens'].values()))
        self.assertNotIn('PRIVATE',json.dumps(x))

    def test_parser_malformed_truncated_duplicate_late(self):
        done = '{"type":"turn.completed","usage":{"input_tokens":5}}\n'
        for raw in ('bad\n'+done, '{"type":', done+done, done+'{"type":"future"}\n',
                    '{"type":"turn.failed"}\n', '{"type":"turn.completed","usage":{"input_tokens":true}}'):
            with self.subTest(raw=raw):
                x = b.parse_trace(raw)
                self.assertTrue(x['errors'])
                self.assertIsNone(x['tokens']['input'])

    def test_duplicate_tool_event(self):
        item = '{"type":"item.completed","item":{"type":"command_execution","id":"a"}}\n'
        done = '{"type":"turn.completed"}\n'
        self.assertEqual(b.parse_trace(item+done)['observed_tool_calls'],1)
        self.assertTrue(b.parse_trace(item+item+done)['errors'])

    def test_wrong_implementations_and_positive_controls(self):
        for s in self.m['scenarios']:
            with self.subTest(s=s['id']):
                if any(shutil.which(c) is None for c in s['required_capabilities']):
                    continue  # Availability recorded by runner; CI need not install toolchains.
                for kind, expected in [('solution',True),('wrong',False)]:
                    with tempfile.TemporaryDirectory() as tmp:
                        d = Path(tmp)
                        b.setup(s,d)
                        b.materialize(b.fixture(s)[kind],d)
                        self.assertEqual(b.grade(s,d),expected, (s['id'],kind))

    def test_fake_failures_and_missing_usage(self):
        for mode, reason in [('failure','process-failure'),('timeout','timeout'),
                             ('malformed','trace-invalid'),('grader-failure','quality-failure'),
                             ('success',None),('missing-usage',None)]:
            r = b.run(self.s,'vanilla',14,0,b.FakeRunner([mode]))
            self.assertEqual(r['final_status'],reason)
            self.assertEqual(r['quality_pass'],reason is None)
            if mode == 'missing-usage': self.assertIsNone(r['attempts'][0]['tokens']['input'])

    def test_retry_retention_and_clean_setup(self):
        r = b.run(self.s,'vanilla',14,0,b.FakeRunner(['failure','success']),1)
        self.assertEqual(r['retry_count'],1)
        self.assertEqual(r['initial_failure'],'process-failure')
        self.assertEqual(len(r['attempts']),2)
        self.assertTrue(r['quality_pass'])
        self.assertEqual(json.loads(json.dumps(r)),r)

    def test_quality_before_cost_and_failure_denominators(self):
        a = b.run(self.s,'vanilla',14,0,b.FakeRunner())
        c = b.run(self.s,'native',14,0,b.FakeRunner(['grader-failure']))
        report = b.aggregate([a,c])
        self.assertEqual(report['vanilla']['cost_samples'],0)
        self.assertEqual(report['native']['failure_rate'],1)
        c = b.run(self.s,'native',14,0,b.FakeRunner(['missing-usage']))
        report = b.aggregate([a,c])
        self.assertEqual(report['vanilla']['cost_samples'],1)
        self.assertEqual(report['native']['tokens']['input']['samples'],0)

    def test_privacy(self):
        def runner(s,v,d):
            obs = b.FakeRunner()(s,v,d)
            obs['stderr'] = 'PRIVATE password source prompt'
            obs['stdout'] = '{"type":"agent.message","text":"PRIVATE"}\n'+obs['stdout']
            return obs
        r = b.run(self.s,'vanilla',14,0,runner)
        self.assertNotIn('PRIVATE',json.dumps(r))
        self.assertNotIn('password',json.dumps(r))

    def test_plan_no_shell_or_router_activation(self):
        argv = b.plan('native','/usr/bin/codex','model')
        self.assertIn('--ignore-user-config',argv)
        self.assertIn('--json',argv)
        for v in ['router-v2','legacy','unknown']:
            with self.assertRaises(ValueError): b.plan(v,'/usr/bin/codex','model')

    def test_schema_field_contract(self):
        schema = json.loads((b.ROOT/'schema'/'record.schema.json').read_text())
        r = b.run(self.s,'vanilla',14,0,b.FakeRunner())
        self.assertLessEqual(set(r),set(schema['properties']))
        self.assertLessEqual(set(schema['required']),set(r))
        attempt = schema['properties']['attempts']['items']
        self.assertEqual(set(r['attempts'][0]),set(attempt['properties']))
        self.assertEqual(set(r['attempts'][0]['tokens']),set(attempt['properties']['tokens']['properties']))

    def test_missing_fixture_and_unsupported_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                b.setup(dict(self.s,fixture='scenarios/absent.json'),Path(tmp))
        with self.assertRaises(ValueError):
            b.run(self.s,'router-v2',14,0,b.FakeRunner())

    def test_launch_failure_retained(self):
        def broken(s,v,d):
            raise OSError('PRIVATE diagnostic')
        r = b.run(self.s,'vanilla',14,0,broken)
        self.assertEqual(r['initial_failure'],'launch-failure')
        self.assertIsNone(r['attempts'][0]['exit_status'])
        self.assertNotIn('PRIVATE',json.dumps(r))

    def test_unavailable_rows_do_not_disable_baselines(self):
        a = b.run(self.s,'vanilla',14,0,b.FakeRunner())
        c = b.run(self.s,'native',14,0,b.FakeRunner())
        unavailable = dict(a,variant='legacy',attempts=[],quality_pass=False,
                           initial_failure='not-runnable',final_status='not-runnable')
        report = b.aggregate([a,c,unavailable])
        self.assertEqual(report['vanilla']['cost_samples'],1)
        self.assertEqual(report['legacy']['not_runnable'],1)

    def test_existing_evidence_rejected_before_execution(self):
        def forbidden(s,v,d):
            self.fail('runner must not execute')
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp)
            (artifacts/f"{self.s['id']}-vanilla-0-0").mkdir()
            with self.assertRaises(ValueError):
                b.run(self.s,'vanilla',14,0,forbidden,artifacts=artifacts)

    def test_execution_timeout_and_exit(self):
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(b.execute([sys.executable,'-c','raise SystemExit(2)'],tmp)['exit_status'],2)
            self.assertTrue(b.execute([sys.executable,'-c','import time; time.sleep(5)'],tmp,timeout=0.05)['timeout'])


if __name__ == '__main__':
    unittest.main()
