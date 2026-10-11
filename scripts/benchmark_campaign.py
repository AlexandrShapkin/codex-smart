"""Pinned preliminary campaign; real execution requires two explicit opt-ins."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import re

import benchmark as b
import benchmark_isolation as isolation

CONFIG = b.ROOT / 'campaign-v1.json'
NATIVE_INSTRUCTION = '\nUse native local tools first. No MCP, external indexing, installation or network.'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_frozen(actual, expected, label):
    # JSON comparison preserves scalar types (False != 0, True != 1).
    if json.dumps(actual, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError(f'unreviewed {label}')


def load(path=CONFIG):
    c = json.loads(Path(path).read_text())
    if c['schema_version'] != 1 or c['campaign_id'] != 'initial-development-v1':
        raise ValueError('unsupported campaign')
    expected = {'manifest_sha256': b.ROOT/'manifest.json', 'grader_sha256': b.ROOT/'graders.py',
                'harness_sha256': Path(b.__file__), 'campaign_runner_sha256': Path(__file__)}
    if any(c['pins'][key] != sha(file) for key, file in expected.items()):
        raise ValueError('campaign source mismatch; explicitly review and repin')
    require_frozen(c['codex']['version'], '0.162.1', 'Codex version')
    require_frozen(c['codex']['executable_sha256'],
                   '89cc44e820780120ba2c8bc4585c014815bdc7a1fc494c337a585a2c78dc59eb',
                   'Codex executable SHA')
    require_frozen(c.get('toolchains'), {
        'rustc': {'version': 'rustc 1.98.0 (88d9e12ae 2026-08-18)', 'version_arguments': ['--version']},
        'go': {'version': 'go version go1.27.2-X:nodwarf5 linux/amd64', 'version_arguments': ['version']},
        'python3': {'version': 'Python 3.14.8', 'version_arguments': ['--version']}}, 'toolchains')
    if c['variants'] != ['vanilla', 'native'] or c['repetitions'] != 3 or c['retries'] != 0:
        raise ValueError('initial campaign bounds')
    if c['seeds'] != [14] or c['timeout_seconds'] != 120 or c['planned_primary_runs'] != 42:
        raise ValueError('initial campaign ordering/bounds')
    if c['settings'] != {'model': 'gpt-6-sol', 'reasoning_effort': 'low', 'sandbox': 'workspace-write',
                         'ignore_user_config': True, 'ignore_rules': True, 'ephemeral': True,
                         'auth': {'source': 'existing normal CODEX_HOME', 'credential_store': 'keyring',
                                  'credentials_copied': False, 'user_config_loaded': False}}:
        raise ValueError('unreviewed settings')
    if any(c['settings']['auth'][key] is not False
           for key in ('credentials_copied', 'user_config_loaded')):
        raise ValueError('auth evidence must use typed booleans')
    require_frozen(c.get('cold_warm'), {
        'classification': 'unknown',
        'protocol': 'fresh disposable fixture per attempt; inherited host caches not controlled; do not claim cold or warm',
        'index': 'not applicable: no indexing requested', 'bootstrap': 'unknown'}, 'cache protocol')
    require_frozen(c.get('status'), 'frozen-plan-live-contract-verified', 'campaign status')
    require_frozen(c.get('live_contract'), {
        'status': 'verified', 'startup': 'verified', 'auth_routing': 'verified',
        'scenario': 'iac-security', 'variant': 'vanilla', 'repetition': 0, 'seed': 14,
        'retries': 0, 'cold_warm': 'unknown', 'terminal_status': 'completed',
        'exit_status': 0, 'final_status': None, 'parser_errors': [], 'quality_pass': True,
        'grader': 'passed', 'usage': 'observed', 'observed_tool_calls': 3,
        'ready_for_measured_campaign': False}, 'live contract')
    require_frozen(c.get('metrics'), {
        'input': 58885, 'cached_input': 55040, 'output': 427, 'reasoning': 36,
        'fresh_input': None, 'total': None, 'full_tool_calls': None}, 'smoke metrics')
    require_frozen(c.get('readiness'), {
        'real_runner_contract': 'prepared', 'representative_campaign_ready': False,
        'grading_isolation_contract': 'required-not-verified',
        'reason': 'representative task coverage has not yet been accepted'}, 'readiness')
    history = c.get('historical_live_attempts')
    if not isinstance(history, list) or len(history) != 1 or not isinstance(history[0], dict):
        raise ValueError('retained historical live evidence required')
    historical_fields = {'terminal_status': 'failed', 'exit_status': 1,
                         'grader': 'not executed', 'usage': 'not observed',
                         'ready_for_measured_campaign': False}
    require_frozen({key: history[0].get(key) for key in historical_fields},
                   historical_fields, 'historical live evidence')
    m = b.load_manifest()
    if c['scenario_ids'] != [s['id'] for s in m['scenarios']]:
        raise ValueError('scenario set mismatch')
    return c


def jobs(c):
    m = b.load_manifest()
    for s in m['scenarios']:
        s['allowed_variants'] = c['variants']
    return [(sid, variant, rep, seed) for seed in c['seeds']
            for sid, variant, rep in b.ordering(m, c['repetitions'], seed)]


def prompt(c, s, variant):
    if variant not in c['variants']:
        raise ValueError('unavailable variant')
    return s['prompt'] + (NATIVE_INSTRUCTION if variant == 'native' else '')


def command_plan(c, variant, executable):
    if variant not in c['variants']:
        raise ValueError('unavailable variant')
    argv = b.plan(variant, executable, c['settings']['model'])
    argv[-1:-1] = ['-c', 'model_reasoning_effort="low"']
    return argv


def toolchains(c):
    # Explicit benchmark setup only; never invokes Codex or installs anything.
    result = {}
    for name, spec in c['toolchains'].items():
        exe = shutil.which(name)
        if exe is None:
            result[name] = 'unavailable'
            continue
        observation = b.execute([exe, *spec['version_arguments']], b.ROOT, timeout=10)
        actual = observation['stdout'].strip()
        result[name] = ('verified' if observation['exit_status'] == 0 and not observation['timeout']
                        and actual == spec['version'] else 'version-mismatch')
    return result


def references(c, path):
    return {**c['pins'], 'campaign_sha256': sha(path), 'campaign_id': c['campaign_id'],
            'codex_version': c['codex']['version'], 'executable_sha256': c['codex']['executable_sha256'],
            'auth': c['settings']['auth'],
            'model': c['settings']['model'], 'settings': 'isolated-exec-v2-low',
            'runner': 'fake-v1', 'execution_kind': 'synthetic-self-validation',
            'toolchains': {k: v['version'] for k, v in c['toolchains'].items()}}


def dry_run(c, path=CONFIG, artifacts=None):
    refs = references(c, path)
    status = toolchains(c)
    manifest = b.load_manifest()
    records = []
    for sid, variant, rep, seed in jobs(c):
        s = next(s for s in manifest['scenarios'] if s['id'] == sid)
        missing = any(status.get(name) != 'verified' for name in s['required_capabilities'])
        if missing:
            record = {'schema_version': 1, 'scenario_id': sid, 'variant': variant, 'repetition': rep,
                      'order_seed': seed, 'snapshot': s['snapshot'], 'references': refs,
                      'cold_warm': 'unknown', 'quality_pass': False, 'attempts': [], 'retry_count': 0,
                      'initial_failure': 'not-runnable', 'final_status': 'not-runnable',
                      'failure_reason': 'missing-or-mismatched-toolchain'}
        else:
            record = b.run(s, variant, seed, rep, b.FakeRunner(), retries=0, cold='unknown', references=refs)
        records.append(record)
        if artifacts is not None:
            (artifacts/'records.json').write_text(json.dumps(records, indent=2)+'\n')
    return {'execution_kind': 'synthetic-self-validation', 'planned_jobs': len(records),
            'attempted_jobs': sum(bool(r['attempts']) for r in records), 'toolchains': status,
            'live_campaign_ready': c['readiness']['representative_campaign_ready'],
            'summary': b.aggregate(records)}, records


def real_preflight(c, executable):
    if c['live_contract']['status'] != 'verified':
        raise ValueError('live contract not verified')
    if not executable or not Path(executable).is_absolute():
        raise ValueError('explicit absolute Codex executable required')
    if sha(executable) != c['codex']['executable_sha256']:
        raise ValueError('Codex checksum mismatch')
    version = b.execute([executable, '--version'], b.ROOT, timeout=10)
    if version['timeout'] or version['exit_status'] != 0 or version['stdout'].strip() != 'codex-cli 0.162.1':
        raise ValueError('Codex version mismatch')
    if any(value != 'verified' for value in toolchains(c).values()):
        raise ValueError('toolchain mismatch')


def artifact_directory(run_id):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', run_id):
        raise ValueError('invalid run identifier')
    root = b.ROOT / '.artifacts'
    if root.is_symlink():
        raise ValueError('symlink artifacts rejected')
    root.mkdir(mode=0o700, exist_ok=True)
    root.chmod(0o700)
    target = root / run_id
    if target.exists() or target.is_symlink():
        raise ValueError('existing run evidence')
    target.mkdir(mode=0o700)
    return target


def real_run(executable, run_id, path=CONFIG, *, allow_preliminary_campaign=False):
    if allow_preliminary_campaign is not True:
        raise ValueError('explicit preliminary campaign acknowledgement required')
    c = load(path)
    if c['readiness']['grading_isolation_contract'] != 'verified':
        raise ValueError('grading isolation contract is not verified')
    real_preflight(c, executable)
    artifacts = artifact_directory(run_id)
    return _real_run(c, executable, artifacts, path)


def _real_run(c, executable, artifacts, path=CONFIG):
    refs = {**references(c, path), 'runner': 'real-v1', 'execution_kind': 'real-preliminary'}
    manifest = b.load_manifest()
    records = []
    def runner(s, variant, directory):
        return b.execute(command_plan(c, variant, executable), directory,
                         prompt(c, s, variant), timeout=c['timeout_seconds'])
    for sid, variant, rep, seed in jobs(c):
        s = next(s for s in manifest['scenarios'] if s['id'] == sid)
        record = b.run(s, variant, seed, rep, runner, retries=0, cold='unknown',
                       references=refs, artifacts=artifacts, grader=_grade_submission)
        # One immutable normalized record per completed job survives interruption.
        with (artifacts / f'{sid}-{variant}-{rep}.json').open('x') as output:
            output.write(json.dumps(record, indent=2) + '\n')
        records.append(record)
    return {'execution_kind': 'real-preliminary', 'planned_jobs': len(jobs(c)),
            'summary': b.aggregate(records)}


def _grade_submission(s, directory):
    return isolation.grade(s['id'], directory).quality_pass


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dry-run', action='store_true', help='execute only local fake agents and graders')
    p.add_argument('--real', action='store_true')
    p.add_argument('--allow-preliminary-campaign', action='store_true')
    p.add_argument('--codex', help='explicit absolute pinned executable')
    p.add_argument('--run-id', default='campaign-v1-real')
    args = p.parse_args()
    c = load()
    if args.real and args.dry_run:
        p.error('--real and --dry-run are mutually exclusive')
    if not args.dry_run and (not args.real or not args.allow_preliminary_campaign):
        print(json.dumps({'planned_jobs': len(jobs(c)), 'live_contract': c['live_contract'],
                          'model_execution_enabled': False}, indent=2))
        if args.real:
            p.error('real execution requires --allow-preliminary-campaign; representative coverage not accepted')
        return
    try:
        if args.real:
            report = real_run(args.codex, args.run_id,
                              allow_preliminary_campaign=args.allow_preliminary_campaign)
        else:
            artifacts = artifact_directory('campaign-v1-dryrun')
            report, _ = dry_run(c, artifacts=artifacts)
    except (ValueError, OSError) as error:
        p.error(str(error))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
