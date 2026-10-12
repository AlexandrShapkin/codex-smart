"""Frozen representative design and trusted-control validation; no model execution."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import sys
import tempfile

import benchmark as b
import benchmark_agent_isolation as agent_isolation
import benchmark_campaign as historical_campaign

sys.path.insert(0, str(b.ROOT))
import representative_graders as graders

MANIFEST = b.ROOT/'representative-manifest.json'
CAMPAIGN = b.ROOT/'representative-campaign-v1.json'
DOMAINS = {'Rust', 'Go', 'Python', 'infrastructure', 'repository/CI', 'exploration'}
REPRESENTATIVE_CODEX = {
    'version': '0.162.1',
    'reference': 'official OpenAI release rust-v0.162.1; x86_64-unknown-linux-musl',
    'distribution': 'upstream-release',
    'release_tag': 'rust-v0.162.1',
    'release_commit': '092d3acd6bec3e3a14bdc7e7a2810ab628ab759d',
    'release_asset': 'codex-x86_64-unknown-linux-musl.tar.gz',
    'release_asset_sha256': '86f268d81b898f3e144c5ecff2ad2fda2c5802e042d6195b72538fe0fa125057',
    'executable_sha256': '628e35487d888a28f0427fc37501da529dd3d81fcbad7a2c3421c1e8670d92e1',
}
REPRESENTATIVE_TOOLCHAINS = {
    'rustc': {'version': 'rustc 1.98.0 (88d9e12ae 2026-08-18)', 'version_arguments': ['--version']},
    'cargo': {'version': 'cargo 1.98.0 (797e8a9bc 2026-08-05)', 'version_arguments': ['--version']},
    'go': {'version': 'go version go1.27.2 linux/amd64', 'version_arguments': ['version']},
    'python3': {'version': 'Python 3.14.8', 'version_arguments': ['--version']},
}
REPRESENTATIVE_TOOLCHAIN_ARTIFACTS = {
    'rustc': {'distribution': 'upstream-release', 'artifact': 'rustc-1.98.0-x86_64-unknown-linux-gnu.tar.xz',
              'sha256': '0e37cb339f447fc44d6d781073bacacebfdc5612f2600e4c7e84c266f5f3aced'},
    'cargo': {'distribution': 'upstream-release', 'artifact': 'cargo-1.98.0-x86_64-unknown-linux-gnu.tar.xz',
              'sha256': '2f512d170d3dd23e16ababcda32ee2e6d5172d861a7af1f504e0b1e270cafab9'},
    'rust-std': {'distribution': 'upstream-release', 'artifact': 'rust-std-1.98.0-x86_64-unknown-linux-gnu.tar.xz',
                 'sha256': 'f5022e6c95a5ad23cca2513dc8281200f585fa188de6370aa37b128a43f876a3'},
    'go': {'distribution': 'upstream-release', 'artifact': 'go1.27.2.linux-amd64.tar.gz',
           'sha256': 'ecbadb99091a3f46e31f5f934b068b1864eafa7995211b39eaddf76996045fe5'},
    'python': {'distribution': 'upstream-source-build', 'artifact': 'Python-3.14.8.tar.xz',
               'sha256': 'c2215904f02b175596dc49351585104f4bc20341e1c47378b26a2c274360ce73'},
}
CARGO_VERSION = REPRESENTATIVE_TOOLCHAINS['cargo']['version']
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
    for scenario in rows: fixture(scenario)
    return m


def fixture(s):
    path = Path(s['fixture'])
    if path != Path('representative')/(s['id']+'.json') or '..' in path.parts or not path.is_relative_to('representative'):
        raise ValueError('fixture path')
    f = json.loads((b.ROOT/path).read_text())
    if set(f) != {'files','reference','wrong_controls','oracle','structure'} or not isinstance(f['wrong_controls'], list) or len(f['wrong_controls']) < 2:
        raise ValueError('independent controls required')
    for files in [f['files'], f['reference'], *f['wrong_controls']]:
        if not isinstance(files, dict) or not files:
            raise ValueError('fixture content')
        for name, content in files.items():
            p = Path(name)
            if p.is_absolute() or '..' in p.parts or type(content) is not str or re.search(r'(^|[/_.-])(oracle|independent|reference|solution|wrong)([/_.-]|$)', name.lower()):
                raise ValueError('unsafe or leaking staged file')
    if b.digest(f['files']) != s['snapshot']:
        raise ValueError('snapshot mismatch')
    visible = s['prompt'].lower() + '\n' + '\n'.join(f['files']).lower() + '\n' + '\n'.join(f['files'].values()).lower()
    if any(word in visible for word in ['wrong_control', 'oracle', 'reference solution', 'grader assertion',
                                             'initial_file_count', 'reference_changed_file_count', 'support_files', 'dependency_edges']):
        raise ValueError('benchmark leakage')
    # Nontrivial complete changed reference files must not appear in initial files
    # or prompt. This deterministic check cannot replace semantic human review.
    initial = '\n'.join(f['files'].values()) + s['prompt']
    for n, code in f['reference'].items():
        if len(code) > 40 and code != f['files'].get(n) and code in initial:
            raise ValueError('reference leakage')
    validate_structure(s, f)
    return f


def validate_structure(s, f):
    evidence = f['structure']
    if not isinstance(evidence, dict) or set(evidence) != {
            'initial_file_count','reference_changed_file_count','support_files','dependency_edges'}:
        raise ValueError('structural evidence schema')
    initial, reference = f['files'], f['reference']
    changed = {n for n,c in reference.items() if initial.get(n) != c}
    exact(evidence['initial_file_count'],len(initial),'initial file count')
    exact(evidence['reference_changed_file_count'],len(changed),'changed file count')
    support = evidence['support_files']
    if (not isinstance(support,list) or not support or any(type(n) is not str for n in support)
            or len(support) != len(set(support)) or not set(support) <= set(initial)
            or set(support) & changed):
        raise ValueError('missing or mutable support file')
    edges = evidence['dependency_edges']
    if not isinstance(edges,list) or not edges:
        raise ValueError('dependency evidence required')
    graph, pairs = {}, set()
    for e in edges:
        if not isinstance(e,dict) or set(e) != {'caller','callee','witness','symbol'}:
            raise ValueError('dependency edge schema')
        if any(type(v) is not str or not v for v in e.values()):
            raise ValueError('dependency edge values')
        a,b,witness,symbol = (e[k] for k in ['caller','callee','witness','symbol'])
        if (a not in initial or b not in initial or a == b or (a,b) in pairs
                or witness not in initial[a] or symbol not in initial[b]):
            raise ValueError('dependency evidence mismatch')
        pairs.add((a,b));graph.setdefault(a,set()).add(b)
    involved = {name for pair in pairs for name in pair}
    if not set(support) <= involved:
        raise ValueError('support outside dependency surface')
    tier = s['complexity_tier']
    # Added tests/docs do not satisfy the existing behavior/API change threshold.
    behavior = {n for n in changed & set(initial) if Path(n).suffix in {'.rs','.go','.py','.json'}}
    minimum = {'focused':(1,0), 'multi-file':(4,2), 'cross-cutting':(5,3)}[tier]
    if len(initial) < minimum[0] or len(behavior & involved) < minimum[1]:
        raise ValueError('complexity structural minimum')
    if tier != 'focused' and not any(
            any(n in changed & involved and patch.get(n) == initial[n] for n in initial)
            for patch in f['wrong_controls']):
        raise ValueError('incomplete-impact wrong control required')
    if tier == 'cross-cutting' and not any(
            graph.get(b,set()) - {a} for a,children in graph.items() for b in children):
        raise ValueError('cross-cutting dependency path required')
    if not any(Path(n).name.lower() not in s['prompt'].lower() for n in support):
        raise ValueError('supporting context must not be a named target')
    if tier == 'focused' and s['risk_dimension'] not in {'test-detection-strength','conditional-call-graph'}:
        raise ValueError('focused measurement purpose unreviewed')


def coverage_report(m=None):
    m = load_manifest() if m is None else validate_matrix(m)
    rows = []
    for s in m['scenarios']:
        structure = fixture(s)['structure']
        rows.append({'scenario':s['id'], 'domain':s['language_or_domain'],
                     'task_classes':s['task_class'], 'complexity_tier':s['complexity_tier'],
                     'initial_file_count':structure['initial_file_count'],
                     'reference_changed_file_count':structure['reference_changed_file_count'],
                     'support_file_count':len(structure['support_files']),
                     'lifecycle_requirements':s['lifecycle_requirements']})
    return rows


def load_manifest(path=MANIFEST):
    return validate_matrix(json.loads(Path(path).read_text()))


def expected_campaign(m):
    historical = historical_campaign.load()
    settings = json.loads(json.dumps(historical['settings']))
    agent_contract = agent_isolation.load_contract()
    settings['shell_environment_policy'] = agent_contract['child_environment']
    settings['disabled_features'] = agent_contract['disabled_features']
    settings['permission_profile'] = {
        'id': 'benchmark',
        'extends': ':workspace',
        'filesystem': {'~/.local/share/keyrings': 'deny'},
    }
    settings['credential_backing_store'] = agent_contract['credential_backing_store']
    return {'schema_version':1, 'campaign_id':'representative-development-v1',
            'status':'frozen-plan-isolation-blocked', 'coverage_role':'representative',
            'provenance':{'preliminary_campaign':'initial-development-v1',
                          'preliminary_sha256':hashlib.sha256((b.ROOT/'campaign-v1.json').read_bytes()).hexdigest()},
            'scenario_ids':[s['id'] for s in m['scenarios']], 'variants':['vanilla','native'],
            'unavailable_variants':{'legacy':'provenance archive absent','router-v2':'no verified decision-applying adapter'},
            'repetitions':2, 'seeds':[14], 'retries':0, 'timeout_seconds':120,
            'planned_primary_runs':len(m['scenarios'])*2*2,
            'maximum_codex_executions':len(m['scenarios'])*2*2,
            'settings':settings, 'codex':REPRESENTATIVE_CODEX, 'toolchains':REPRESENTATIVE_TOOLCHAINS,
            'toolchain_artifacts': REPRESENTATIVE_TOOLCHAIN_ARTIFACTS,
            'cold_warm':historical['cold_warm'],
            'live_contract':{'status':'inherited-execution-contract-only','source_campaign':'initial-development-v1',
                             'scope':'Codex startup/auth/JSONL only; not representative grading compatibility'},
            'readiness':{'real_runner_contract':'prepared',
                         'agent_execution_isolation_contract':'required-not-verified',
                         'grading_isolation_contract':'required-not-verified',
                         'qualified_host_contract':'required-not-verified',
                         'representative_campaign_ready':False},
            'execution_dependencies':{'agent_execution_isolation_contract':'verified',
                                      'grading_isolation_contract':'verified',
                                      'qualified_host_contract':'verified'},
            'measured_records':[],
            'runner_pins': {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in {
                'runner_sha256': Path(__file__).with_name('benchmark_representative.py'),
                'host_validator_sha256': Path(__file__).with_name('benchmark_host.py'),
                'host_contract_sha256': b.ROOT/'host-contract-v1.json',
                'grading_backend_sha256': Path(__file__).with_name('benchmark_grading_backend.py'),
                'grading_backend_contract_sha256': b.ROOT/'grading-isolation-backend-v1.json',
                'grading_backend_probe_sha256': Path(__file__).with_name('benchmark_grading_backend_probe.py'),
                'grading_backend_candidate_evidence_sha256': b.ROOT/'grading-isolation-backend-candidate-v1.json',
                'agent_isolation_sha256': Path(__file__).with_name('benchmark_agent_isolation.py'),
                'agent_isolation_contract_sha256': b.ROOT/'agent-execution-isolation-v1.json',
                'agent_source_review_sha256': b.ROOT/'agent-execution-source-review-v1.json',
                'agent_probe_sha256': Path(__file__).with_name('benchmark_agent_isolation_probe.py'),
                'agent_candidate_evidence_sha256': b.ROOT/'agent-execution-isolation-candidate-v1.json',
                'isolation_sha256': Path(__file__).with_name('benchmark_isolation.py'),
                'resource_contract_sha256': Path(__file__).with_name('benchmark_resource_contract.py'),
                'harness_sha256': Path(b.__file__)}.items()},
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
    with tempfile.TemporaryDirectory(prefix='representative-version-') as tmp:
        if not graders.command(['cargo','--version'],Path(tmp),expected_stdout=CARGO_VERSION):
            raise ValueError('Cargo version mismatch; trusted controls refused')
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
              'model_execution_enabled':False, 'representative_campaign_ready':False,
              'coverage_report':coverage_report()}
    if args.trusted_controls:
        output['controls']=trusted_controls()
    print(json.dumps(output,indent=2))
    if args.trusted_controls and not all(r['reference_pass'] and all(r['wrong_rejected']) for r in output['controls']):
        raise SystemExit(1)


if __name__ == '__main__': main()
