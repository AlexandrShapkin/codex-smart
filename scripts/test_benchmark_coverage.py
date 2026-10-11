import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import benchmark as b
import benchmark_campaign as historical
import benchmark_coverage as coverage


class RepresentativeTests(unittest.TestCase):
    def setUp(self):
        self.m = coverage.load_manifest()

    def test_matrix_and_arithmetic(self):
        c = coverage.load_campaign()
        self.assertEqual(len(self.m['scenarios']),10)
        self.assertEqual(c['planned_primary_runs'],10*2*2)
        self.assertEqual(c['maximum_model_calls'],40)
        self.assertEqual(c['variants'],['vanilla','native'])
        self.assertEqual(c['retries'],0)
        self.assertEqual(c['readiness']['grading_isolation_contract'],'required-not-verified')
        self.assertIs(c['readiness']['representative_campaign_ready'],False)
        self.assertEqual(c['execution_dependencies']['grading_isolation_contract'],'verified')
        self.assertEqual(c['measured_records'],[])
        self.assertNotIn('metrics',c)

    def test_each_domain_required(self):
        for domain in coverage.DOMAINS:
            with self.subTest(domain=domain):
                m = copy.deepcopy(self.m)
                for s in m['scenarios']:
                    if s['language_or_domain']==domain: s['language_or_domain']='Rust' if domain=='Python' else 'Python'
                with self.assertRaises(ValueError): coverage.validate_matrix(m)

    def test_each_task_class_required(self):
        for cls in coverage.CLASSES:
            with self.subTest(cls=cls):
                m=copy.deepcopy(self.m)
                for s in m['scenarios']:
                    s['task_class']=[x for x in s['task_class'] if x!=cls] or ['bugfix' if cls!='bugfix' else 'feature']
                with self.assertRaises(ValueError): coverage.validate_matrix(m)

    def test_each_tier_required(self):
        for tier in coverage.TIERS:
            m=copy.deepcopy(self.m)
            for s in m['scenarios']:
                if s['complexity_tier']==tier: s['complexity_tier']='focused' if tier!='focused' else 'multi-file'
            with self.assertRaises(ValueError): coverage.validate_matrix(m)

    def test_duplicate_unknown_and_lifecycle_rejected(self):
        for mutation in ['duplicate','metadata','lifecycle','role','unknown-class','unknown-tier']:
            m=copy.deepcopy(self.m)
            s=m['scenarios'][0]
            if mutation=='duplicate': m['scenarios'].append(copy.deepcopy(s))
            if mutation=='metadata': s['router_hint']='high'
            if mutation=='lifecycle': s['lifecycle_requirements']=['inspect']
            if mutation=='role': s['coverage_role']='harness'
            if mutation=='unknown-class': s['task_class']=['saving-tokens']
            if mutation=='unknown-tier': s['complexity_tier']='large'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError): coverage.validate_matrix(m)

    def test_pins_leakage_and_staged_inventory(self):
        for s in self.m['scenarios']:
            f=coverage.fixture(s)
            self.assertEqual(b.digest(f['files']),s['snapshot'])
            with tempfile.TemporaryDirectory() as tmp:
                b.materialize(f['files'],Path(tmp))
                actual={str(p.relative_to(tmp)) for p in Path(tmp).rglob('*') if p.is_file()}
                self.assertEqual(actual,set(f['files']))
                self.assertNotIn('answer.json',actual)
            leaked=dict(s,prompt=s['prompt']+' reference solution')
            with self.assertRaises(ValueError): coverage.fixture(leaked)
        with self.assertRaises(ValueError): coverage.fixture(dict(self.m['scenarios'][0],fixture='../secret'))
        with self.assertRaises(ValueError): coverage.fixture(dict(self.m['scenarios'][0],snapshot='drift'))

    def test_campaign_bounds_and_isolation_drift_rejected(self):
        c=coverage.load_campaign()
        cases=[('variants',['vanilla','native','router-v2']),('retries',1),('repetitions',3),
               ('maximum_model_calls',42),('planned_primary_runs',42),('status','ready')]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'campaign.json'
            for key,value in cases:
                modified=copy.deepcopy(c);modified[key]=value
                path.write_text(json.dumps(modified))
                with self.subTest(key=key),self.assertRaises(ValueError): coverage.load_campaign(path)
            for key,value in [('grading_isolation_contract','verified'),('representative_campaign_ready',True)]:
                modified=copy.deepcopy(c);modified['readiness'][key]=value
                path.write_text(json.dumps(modified))
                with self.assertRaises(ValueError): coverage.load_campaign(path)
            modified=copy.deepcopy(c);modified['execution_dependencies']['grading_isolation_contract']='optional'
            path.write_text(json.dumps(modified))
            with self.assertRaises(ValueError): coverage.load_campaign(path)

    def test_historical_evidence_unchanged(self):
        for name,sha in [('campaign-v1.json','cfc97144156b9321555cc98937d30d85f8e7bd39a5009954ae84d294156502f7'),
                         ('manifest.json','02fec44267b796412b5a471822d86a779fe6e9e4e83dfb86b9767fab94b0d47d')]:
            self.assertEqual(hashlib.sha256((b.ROOT/name).read_bytes()).hexdigest(),sha)
        old=historical.load()
        self.assertEqual(len(historical.jobs(old)),42)
        self.assertEqual(old['metrics']['input'],58885)
        self.assertEqual(len(old['historical_live_attempts']),1)
        self.assertEqual(len(b.load_manifest()['scenarios']),7)

    def test_plan_cli_never_executes(self):
        with patch('sys.argv',['benchmark_coverage.py']), patch.object(b,'execute') as execute, \
             patch.object(coverage.graders,'command') as command, contextlib.redirect_stdout(io.StringIO()) as output:
            coverage.main()
            execute.assert_not_called();command.assert_not_called()
            self.assertFalse(json.loads(output.getvalue())['model_execution_enabled'])
        with patch('sys.argv',['benchmark_coverage.py','--real']),patch.object(b,'execute') as execute, \
             contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): coverage.main()
            execute.assert_not_called()

    def test_control_pin_failure_precedes_execution(self):
        with patch.object(coverage,'load_campaign',side_effect=ValueError('pin drift')), \
             patch.object(coverage.graders,'check') as check:
            with self.assertRaises(ValueError): coverage.trusted_controls()
            check.assert_not_called()

    def test_declarative_equivalence_and_typed_security(self):
        equal=coverage.graders.declarative_equal
        self.assertTrue(equal({'needs':['lint','unit']},{'needs':['unit','lint']}))
        self.assertFalse(equal({'runAsNonRoot':1},{'runAsNonRoot':True}))
        with self.assertRaises(ValueError): equal({'needs':['unit','unit']},{'needs':['unit']})
        self.assertFalse(equal({'path':['a','b']},{'path':['b','a']}))

    def test_trusted_reference_and_wrong_controls(self):
        with patch.object(b,'execute',side_effect=AssertionError('model/harness process forbidden')):
            rows=coverage.trusted_controls()
        self.assertEqual(len(rows),10)
        for row in rows:
            with self.subTest(scenario=row['id']):
                self.assertTrue(row['reference_pass'])
                self.assertEqual(row['wrong_rejected'],[True,True])


if __name__=='__main__': unittest.main()
