"""Benchmark-local orchestration. No product runtime imports or telemetry."""
import argparse
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import signal
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1] / 'benchmarks'
VARIANTS = {'vanilla', 'legacy', 'native', 'router-v2'}
METRICS = {'input': 'input_tokens', 'cached_input': 'cached_input_tokens',
           'output': 'output_tokens', 'reasoning': 'reasoning_output_tokens'}


def digest(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def fixture(s):
    return json.loads((ROOT / s['fixture']).read_text())


def load_manifest(path=ROOT / 'manifest.json'):
    m = json.loads(Path(path).read_text())
    if m['schema_version'] != 1 or set(m['variants']) != VARIANTS:
        raise ValueError('manifest version/variants')
    ids = set()
    for s in m['scenarios']:
        required = {'id', 'domain', 'task_class', 'source', 'snapshot', 'fixture', 'setup',
                    'prompt', 'grader', 'allowed_variants', 'required_capabilities', 'quality_gates'}
        if set(s) != required or s['id'] in ids or s['grader'] != s['id']:
            raise ValueError('scenario contract')
        ids.add(s['id'])
        p = Path(s['fixture'])
        if p.is_absolute() or '..' in p.parts or not set(s['allowed_variants']) <= VARIANTS:
            raise ValueError('fixture/variant contract')
        f = fixture(s)
        if digest(f['files']) != s['snapshot']:
            raise ValueError('snapshot mismatch')
        for name in f['files'] | f['solution'] | f['wrong']:
            if Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('unsafe fixture path')
    return m


def materialize(files, directory):
    for name, content in files.items():
        p = directory / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def setup(s, directory):
    if any(directory.iterdir()):
        raise ValueError('dirty initial state')
    f = fixture(s)
    if digest(f['files']) != s['snapshot']:
        raise ValueError('snapshot mismatch')
    materialize(f['files'], directory)
    observed = {str(p.relative_to(directory)): p.read_text() for p in directory.rglob('*') if p.is_file()}
    if digest(observed) != s['snapshot']:
        raise ValueError('setup failure')


def ordering(m, repetitions, seed):
    if repetitions < 1:
        raise ValueError('repetitions must be positive')
    jobs = [(s['id'], v, r) for r in range(repetitions) for s in m['scenarios']
            for v in sorted(s['allowed_variants'])]
    random.Random(seed).shuffle(jobs)
    return jobs


def parse_trace(raw):
    """Single exec turn contract. Ambiguous/invalid streams fail closed."""
    tokens = dict.fromkeys([*METRICS, 'fresh_input', 'total'])
    errors, terminals, calls = [], 0, set()
    terminal_status = 'missing'
    for line in raw.splitlines():
        try:
            e = json.loads(line)
            if not isinstance(e, dict) or not isinstance(e.get('type'), str):
                raise ValueError()
        except (ValueError, TypeError):
            errors.append('malformed-jsonl')
            continue
        typ = e['type']
        if terminals:
            errors.append('late-event')
        if typ in ('turn.completed', 'turn.failed'):
            terminals += 1
            terminal_status = 'completed' if typ == 'turn.completed' else 'failed'
        if typ == 'turn.completed':
            usage = e.get('usage', {})
            if not isinstance(usage, dict):
                errors.append('invalid-usage')
                usage = {}
            for name, field in METRICS.items():
                value = usage.get(field)
                if value is not None and (type(value) is not int or value < 0):
                    errors.append('invalid-counter')
                    value = None
                tokens[name] = value
        if typ == 'item.completed':
            item = e.get('item', {})
            if not isinstance(item, dict):
                errors.append('invalid-item')
            elif item.get('type') in ('command_execution', 'mcp_tool_call', 'web_search'):
                ident = item.get('id')
                if not isinstance(ident, str) or ident in calls:
                    errors.append('duplicate-or-missing-item-id')
                else:
                    calls.add(ident)
    if terminals != 1:
        errors.append('incomplete-or-duplicate-turn')
    if errors:
        tokens = dict.fromkeys(tokens)
    # No documented total counter; do not derive one. Tool count is a lower bound only.
    return {'terminal_status': terminal_status, 'tokens': tokens, 'observed_tool_calls': len(calls) if not errors else None,
            'tool_calls': None, 'errors': sorted(set(errors))}


def execute(argv, directory, prompt='', timeout=60):
    started = time.monotonic()
    p = subprocess.Popen(argv, cwd=directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, start_new_session=True)
    timed_out = False
    try:
        out, err = p.communicate(prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(p.pid, signal.SIGKILL)
        out, err = p.communicate()
    except KeyboardInterrupt:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        raise
    return {'stdout': out, 'stderr': err, 'exit_status': p.returncode,
            'timeout': timed_out, 'duration': time.monotonic() - started}


def plan(variant, executable, model):
    if variant not in ('vanilla', 'native'):
        raise ValueError('unsupported variant')
    if not Path(executable).is_absolute() or not model:
        raise ValueError('explicit executable/model required')
    return [executable, 'exec', '--json', '--ephemeral', '--ignore-user-config', '--ignore-rules',
            '-c', 'cli_auth_credentials_store="keyring"', '--skip-git-repo-check', '--sandbox', 'workspace-write', '--model', model, '-']


def grade(s, directory):
    # Trusted grader lives outside agent workspace; fixed oracle, no agent test verdicts.
    return execute([shutil.which('python3'), '-B', str(ROOT / 'graders.py'), s['id'], str(directory)],
                   ROOT, timeout=30)['exit_status'] == 0


class FakeRunner:
    def __init__(self, modes=('success',)):
        self.modes = iter(modes)

    def __call__(self, s, variant, directory):
        mode = next(self.modes)
        if mode in ('success', 'missing-usage'):
            materialize(fixture(s)['solution'], directory)
        elif mode == 'grader-failure':
            materialize(fixture(s)['wrong'], directory)
        raw = '{bad' if mode == 'malformed' else json.dumps(
            {'type': 'turn.completed', **({} if mode == 'missing-usage' else
             {'usage': {'input_tokens': 10, 'output_tokens': 2}})}) + '\n'
        return {'stdout': raw, 'stderr': '', 'exit_status': 1 if mode == 'failure' else 0,
                'timeout': mode == 'timeout', 'duration': 0.001}


def run(s, variant, seed, repetition, runner, retries=0, cold='unknown', references=None, artifacts=None, grader=None):
    if variant not in ('vanilla', 'native') or variant not in s['allowed_variants']:
        raise ValueError('unsupported variant')
    if retries < 0:
        raise ValueError('invalid retries')
    attempts = []
    for index in range(retries + 1):
        start = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with tempfile.TemporaryDirectory(prefix='benchmark-') as tmp:
            directory = Path(tmp)
            before = time.monotonic()
            setup(s, directory)
            overhead = time.monotonic() - before
            if artifacts is not None:
                target = artifacts / f"{s['id']}-{variant}-{repetition}-{index}"
                if target.exists() or target.is_symlink():
                    raise ValueError('existing attempt evidence')
            execution_start = time.monotonic()
            try:
                observation = runner(s, variant, directory)
            except OSError:
                observation = {'stdout': '', 'stderr': '', 'exit_status': None,
                               'timeout': False, 'duration': time.monotonic() - execution_start, 'launch_failure': True}
            parsed = parse_trace(observation['stdout'])
            reason = ('launch-failure' if observation.get('launch_failure') else 'timeout' if observation['timeout'] else 'agent-failure' if not parsed['errors'] and parsed['terminal_status'] == 'failed'
                      else 'process-failure' if observation['exit_status']
                      else 'trace-invalid' if parsed['errors'] else None)
            quality = (grader or grade)(s, directory) if reason is None else False
            if reason is None and not quality:
                reason = 'quality-failure'
            if artifacts is not None:
                folder = artifacts / f"{s['id']}-{variant}-{repetition}-{index}"
                folder.mkdir(parents=True, exist_ok=False)
                folder.chmod(0o700)
                (folder / 'trace.jsonl').write_text(observation['stdout'])
                (folder / 'stderr.txt').write_text(observation['stderr'])
            attempts.append({'start': start, 'end': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                             'duration': observation['duration'], 'exit_status': observation['exit_status'],
                             'quality_gates': {g: quality for g in s['quality_gates']},
                             'quality_pass': quality, 'failure_reason': reason,
                             'setup_seconds': overhead, **parsed})
        if quality:
            break
    return {'schema_version': 1, 'scenario_id': s['id'], 'variant': variant, 'repetition': repetition,
            'order_seed': seed, 'snapshot': s['snapshot'], 'references': references,
            'cold_warm': cold, 'index_seconds': None, 'bootstrap_seconds': None,
            'retry_count': len(attempts) - 1, 'attempts': attempts,
            'initial_failure': attempts[0]['failure_reason'], 'final_status': attempts[-1]['failure_reason'],
            'quality_pass': attempts[-1]['quality_pass']}


def aggregate(records):
    result = {}
    # Only matched scenario/repetition/seed/reference strata with every runnable variant passing.
    runnable = {r['variant'] for r in records if r['attempts']}
    strata = collections.defaultdict(list)
    for r in records:
        if not r['attempts']:
            continue
        strata[(r['scenario_id'], r['repetition'], r['order_seed'], r['snapshot'],
                json.dumps(r['references'], sort_keys=True), r['cold_warm'])].append(r)
    qualified = {id(r) for rows in strata.values()
                 if {r['variant'] for r in rows} == runnable and all(r['quality_pass'] for r in rows)
                 for r in rows}
    for variant in sorted({r['variant'] for r in records}):
        rows = [r for r in records if r['variant'] == variant]
        eligible = [r for r in rows if id(r) in qualified]
        durations = [sum(a['duration'] for a in r['attempts']) for r in eligible]
        # Retry usage must include every attempt; any missing counter makes sum unknown.
        counters = {}
        for metric in [*METRICS, 'fresh_input', 'total']:
            values = [[a['tokens'][metric] for a in r['attempts']] for r in eligible]
            known = [sum(v) for v in values if all(x is not None for x in v)]
            counters[metric] = {'samples': len(known), 'median': statistics.median(known) if known else None}
        result[variant] = {'runs': len(rows), 'not_runnable': sum(not r['attempts'] for r in rows), 'quality_pass_rate': sum(r['quality_pass'] for r in rows)/len(rows),
                           'failure_rate': sum(not r['quality_pass'] for r in rows)/len(rows),
                           'retry_rate': sum(r['retry_count'] > 0 for r in rows)/len(rows),
                           'initial_failure_rate': sum(r['initial_failure'] is not None for r in rows)/len(rows),
                           'cost_samples': len(durations), 'duration_median': statistics.median(durations) if durations else None,
                           'duration_range': [min(durations), max(durations)] if durations else None, 'tokens': counters}
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repetitions', type=int, default=1)
    p.add_argument('--seed', type=int, default=14)
    p.add_argument('--real', action='store_true')
    p.add_argument('--timeout', type=int, default=60)
    p.add_argument('--retries', type=int, default=0)
    p.add_argument('--cold-warm', choices=['cold', 'warm', 'unknown'], default='unknown')
    p.add_argument('--artifacts', type=Path, default=ROOT / '.artifacts')
    args = p.parse_args()
    if args.real:
        p.error('legacy real execution disabled; use scripts/benchmark_campaign.py (grading isolation required)')
    m = load_manifest()
    if args.retries < 0 or args.timeout < 1:
        p.error('invalid retries/timeout')
    protocol_refs = {'manifest_sha256': hashlib.sha256((ROOT / 'manifest.json').read_bytes()).hexdigest(),
                     'grader_sha256': hashlib.sha256((ROOT / 'graders.py').read_bytes()).hexdigest(),
                     'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    refs = {**protocol_refs, 'runner': 'fake-v1'}
    def runner(s, v, d):
        return FakeRunner()(s, v, d)
    # Raw artifacts restricted to ignored repository-local directory.
    if args.artifacts.resolve() != (ROOT / '.artifacts').resolve():
        p.error('artifacts must use benchmarks/.artifacts')
    if args.artifacts.is_symlink():
        p.error('symlink artifacts rejected')
    args.artifacts.mkdir(exist_ok=True, mode=0o700)
    args.artifacts.chmod(0o700)
    records = []
    for sid, v, rep in ordering(m, args.repetitions, args.seed):
        s = next(s for s in m['scenarios'] if s['id'] == sid)
        missing = any(shutil.which(c) is None for c in s['required_capabilities'])
        if not m['variants'][v]['available'] or missing:
            records.append({'schema_version': 1, 'scenario_id': sid, 'variant': v, 'repetition': rep,
                            'order_seed': args.seed, 'snapshot': s['snapshot'], 'references': refs,
                            'cold_warm': args.cold_warm, 'quality_pass': False, 'attempts': [], 'retry_count': 0,
                            'initial_failure': 'not-runnable', 'final_status': 'not-runnable',
                            'failure_reason': 'missing-capability' if missing else m['variants'][v]['reason']})
            continue
        records.append(run(s, v, args.seed, rep, runner, args.retries, args.cold_warm, refs, args.artifacts))
    (args.artifacts / 'records.json').write_text(json.dumps(records, indent=2) + '\n')
    print(json.dumps({'execution_kind': 'synthetic-self-validation',
                      'summary': aggregate(records)}, indent=2))


if __name__ == '__main__':
    main()
