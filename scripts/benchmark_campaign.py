"""Pinned campaign planning and credential-free self-validation; no model execution."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import benchmark as b

CONFIG = b.ROOT / 'campaign-v1.json'
NATIVE_INSTRUCTION = '\nUse native local tools first. No MCP, external indexing, installation or network.'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path=CONFIG):
    c = json.loads(Path(path).read_text())
    if c['schema_version'] != 1 or c['campaign_id'] != 'initial-development-v1':
        raise ValueError('unsupported campaign')
    expected = {'manifest_sha256': b.ROOT/'manifest.json', 'grader_sha256': b.ROOT/'graders.py',
                'harness_sha256': Path(b.__file__), 'campaign_runner_sha256': Path(__file__)}
    if any(c['pins'][key] != sha(file) for key, file in expected.items()):
        raise ValueError('campaign source mismatch; explicitly review and repin')
    if c['codex']['version'] != '0.162.1' or len(c['codex']['executable_sha256']) != 64:
        raise ValueError('unsupported Codex reference')
    if c['variants'] != ['vanilla', 'native'] or c['repetitions'] != 3 or c['retries'] != 0:
        raise ValueError('initial campaign bounds')
    if c['seeds'] != [14] or c['timeout_seconds'] != 120 or c['planned_primary_runs'] != 42:
        raise ValueError('initial campaign ordering/bounds')
    if c['settings'] != {'model': 'gpt-6-sol', 'reasoning_effort': 'low', 'sandbox': 'workspace-write',
                         'ignore_user_config': True, 'ignore_rules': True, 'ephemeral': True,
                         'auth': 'existing Codex authentication; unchanged between variants'}:
        raise ValueError('unreviewed settings')
    if c['cold_warm']['classification'] != 'unknown':
        raise ValueError('cache protocol mismatch')
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
            'live_campaign_ready': c['live_contract']['status'] == 'verified',
            'summary': b.aggregate(records)}, records


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dry-run', action='store_true', help='execute only local fake agents and graders')
    args = p.parse_args()
    c = load()
    if not args.dry_run:
        print(json.dumps({'planned_jobs': len(jobs(c)), 'live_contract': c['live_contract'],
                          'model_execution_enabled': False}, indent=2))
        return
    artifacts = b.ROOT/'.artifacts'/'campaign-v1-dryrun'
    if artifacts.parent.is_symlink():
        p.error('symlink artifacts rejected')
    artifacts.mkdir(mode=0o700, exist_ok=False)
    report, _ = dry_run(c, artifacts=artifacts)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
