"""Frozen representative design and trusted-control validation; no model execution."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import sys
import tempfile

import benchmark as b
import benchmark_campaign as historical_campaign

sys.path.insert(0, str(b.ROOT))
import representative_graders as graders

MANIFEST = b.ROOT/'representative-manifest.json'
CAMPAIGN = b.ROOT/'representative-campaign-v1.json'
DOMAINS = {'Rust', 'Go', 'Python', 'infrastructure', 'repository/CI', 'exploration'}
CLASSES = {'bugfix', 'feature', 'API', 'tests', 'refactor', 'security', 'CI', 'inspection'}
TIERS = {'focused', 'multi-file', 'cross-cutting'}
LIFECYCLE = {'inspect', 'edit', 'test', 'build/check', 'impact-analysis'}
FIELDS = {'id', 'coverage_role', 'language_or_domain', 'task_class', 'complexity_tier',
          'lifecycle_requirements', 'risk_dimension', 'prompt', 'fixture', 'snapshot'}


def exact(actual, expected, label):
    if json.dumps(actual, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError('unreviewed ' + label)


def validate_matrix(m):
    if set(m) != {'schema_version', 'coverage_role', 'scenarios'}:
        raise ValueError('matrix schema')
    exact(m['schema_version'], 1, 'matrix version')
    exact(m['coverage_role'], 'representative', 'coverage role')
    rows = m['scenarios']
    if not isinstance(rows, list) or not 8 <= len(rows) <= 12:
        raise ValueError('bounded scenario count')
    ids, domains, classes, tiers = set(), set(), set(), set()
    for s in rows:
        if not isinstance(s, dict) or set(s) != FIELDS:
            raise ValueError('scenario metadata')
        if not isinstance(s['id'], str) or not re.fullmatch(r'[a-z][a-z0-9-]{1,63}',s['id']) or s['id'] in ids:
            raise ValueError('duplicate scenario')
        if s['coverage_role'] != 'representative' or s['language_or_domain'] not in DOMAINS or s['complexity_tier'] not in TIERS:
            raise ValueError('scenario domain/tier/role')
        for key, allowed in [('task_class', CLASSES), ('lifecycle_requirements', LIFECYCLE)]:
            xs = s[key]
            if not isinstance(xs, list) or not xs or any(type(x) is not str for x in xs) or len(set(xs)) != len(xs) or not set(xs) <= allowed:
                raise ValueError('scenario lifecycle/class')
        life = set(s['lifecycle_requirements'])
        if 'inspect' not in life or ('inspection' not in s['task_class'] and not {'edit','test'} <= life):
            raise ValueError('development lifecycle')
        if s['language_or_domain'] in {'Rust','Go'} and 'build/check' not in life:
            raise ValueError('compiled validation')
        if any(not isinstance(s[k], str) or not s[k].strip() for k in ['risk_dimension','prompt']):
            raise ValueError('missing task intent/risk')
        ids.add(s['id']); domains.add(s['language_or_domain']); classes.update(s['task_class']); tiers.add(s['complexity_tier'])
    if domains != DOMAINS or classes != CLASSES or tiers != TIERS:
        raise ValueError('missing coverage dimension')
    for domain, minimum in [('Rust',2),('Go',2),('Python',3)]:
        if sum(s['language_or_domain']==domain for s in rows) < minimum:
            raise ValueError('language balance')
    requirements = {'Rust': {'bugfix','refactor'}, 'Go': {'feature','bugfix'}, 'Python': {'tests','feature','API','refactor'}}
    for domain, required in requirements.items():
        if not required <= {c for s in rows if s['language_or_domain']==domain for c in s['task_class']}:
            raise ValueError('language task diversity')
    if sum(s['complexity_tier'] != 'focused' for s in rows) < 6:
        raise ValueError('insufficient cross-file work')
    return m


def fixture(s):
    path = Path(s['fixture'])
    if path != Path('representative')/(s['id']+'.json') or '..' in path.parts or not path.is_relative_to('representative'):
        raise ValueError('fixture path')
    f = json.loads((b.ROOT/path).read_text())
    if set(f) != {'files','reference','wrong_controls','oracle'} or not isinstance(f['wrong_controls'], list) or len(f['wrong_controls']) < 2:
        raise ValueError('independent controls required')
    for files in [f['files'], f['reference'], *f['wrong_controls']]:
        if not isinstance(files, dict) or not files:
            raise ValueError('fixture content')
        for name, content in files.items():
            p = Path(name)
            if p.is_absolute() or '..' in p.parts or type(content) is not str or any(word in name.lower() for word in ['oracle','independent','reference','solution','wrong']):
                raise ValueError('unsafe or leaking staged file')
    if b.digest(f['files']) != s['snapshot']:
        raise ValueError('snapshot mismatch')
    visible = s['prompt'].lower() + '\n' + '\n'.join(f['files']).lower()
    if any(word in visible for word in ['wrong_control', 'oracle', 'reference solution', 'grader assertion']):
        raise ValueError('benchmark leakage')
    # Nontrivial complete changed reference files must not appear in initial files
    # or prompt. This deterministic check cannot replace semantic human review.
    initial = '\n'.join(f['files'].values()) + s['prompt']
    for n, code in f['reference'].items():
        if len(code) > 40 and code != f['files'].get(n) and code in initial:
            raise ValueError('reference leakage')
    return f


def load_manifest(path=MANIFEST):
    m = validate_matrix(json.loads(Path(path).read_text()))
    for s in m['scenarios']: fixture(s)
    return m


def expected_campaign(m):
    historical = historical_campaign.load()
    return {'schema_version':1, 'campaign_id':'representative-development-v1',
            'status':'frozen-plan-isolation-blocked', 'coverage_role':'representative',
            'provenance':{'preliminary_campaign':'initial-development-v1',
                          'preliminary_sha256':hashlib.sha256((b.ROOT/'campaign-v1.json').read_bytes()).hexdigest()},
            'scenario_ids':[s['id'] for s in m['scenarios']], 'variants':['vanilla','native'],
            'unavailable_variants':{'legacy':'provenance archive absent','router-v2':'no verified decision-applying adapter'},
            'repetitions':2, 'seeds':[14], 'retries':0, 'timeout_seconds':120,
            'planned_primary_runs':len(m['scenarios'])*2*2, 'maximum_model_calls':len(m['scenarios'])*2*2,
            'settings':historical['settings'], 'codex':historical['codex'], 'toolchains':historical['toolchains'],
            'cold_warm':historical['cold_warm'],
            'live_contract':{'status':'inherited-execution-contract-only','source_campaign':'initial-development-v1',
                             'scope':'Codex startup/auth/JSONL only; not representative grading compatibility'},
            'readiness':{'real_runner_contract':'not-adapted', 'grading_isolation_contract':'required-not-verified',
                         'representative_campaign_ready':False},
            'execution_dependencies':{'grading_isolation_contract':'verified','qualified_host_contract':'verified'},
            'measured_records':[],
            'pins':{'manifest_sha256':hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
                    'grader_sha256':hashlib.sha256(Path(graders.__file__).read_bytes()).hexdigest(),
                    'coverage_validator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    'fixture_sha256':{s['id']:hashlib.sha256((b.ROOT/s['fixture']).read_bytes()).hexdigest() for s in m['scenarios']}}}


def load_campaign(path=CAMPAIGN):
    m = load_manifest()
    c = json.loads(Path(path).read_text())
    exact(c, expected_campaign(m), 'representative campaign')
    return c


def trusted_controls():
    load_campaign()  # Pin references/oracles before any trusted-control execution.
    results = []
    for s in load_manifest()['scenarios']:
        f = fixture(s)
        row = {'id':s['id'],'reference_pass':False,'wrong_rejected':[]}
        for patch in [f['reference'], *[f['reference']|w for w in f['wrong_controls']]]:
            with tempfile.TemporaryDirectory(prefix='representative-control-') as tmp:
                workspace = Path(tmp)
                b.materialize(f['files']|patch, workspace)
                passed = graders.check(s,f,workspace)
            if patch is f['reference']: row['reference_pass']=passed
            else: row['wrong_rejected'].append(not passed)
        results.append(row)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trusted-controls', action='store_true', help='execute only repository-authored reference/wrong controls')
    args = parser.parse_args()
    c = load_campaign()
    output = {'campaign_id':c['campaign_id'], 'planned_jobs':c['planned_primary_runs'],
              'model_execution_enabled':False, 'representative_campaign_ready':False}
    if args.trusted_controls:
        output['controls']=trusted_controls()
    print(json.dumps(output,indent=2))
    if args.trusted_controls and not all(r['reference_pass'] and all(r['wrong_rejected']) for r in output['controls']):
        raise SystemExit(1)


if __name__ == '__main__': main()
