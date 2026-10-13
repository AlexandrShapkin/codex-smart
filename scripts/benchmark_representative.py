"""Frozen representative runner adapter. Current live execution remains disabled."""
import argparse
import json
from pathlib import Path

import benchmark as b
import benchmark_agent_isolation as agent_isolation
import benchmark_campaign as primitives
import benchmark_coverage as coverage
import benchmark_host as host
import benchmark_isolation as isolation
import benchmark_submission_grading as submission_grading

CONFIG = coverage.CAMPAIGN


class PreflightRefusal(ValueError):
    model_calls = 0
    attempt_count = 0

    def as_record(self):
        return {'campaign_id': 'representative-development-v1', 'status': 'preflight-refused',
                'failure_reason': str(self), 'attempt_count': 0, 'model_calls': 0}


def load(path=CONFIG):
    return coverage.load_campaign(path)


def jobs(c):
    manifest = coverage.load_manifest()
    for s in manifest['scenarios']:
        s['allowed_variants'] = c['variants']
    return [(sid, variant, rep, seed) for seed in c['seeds']
            for sid, variant, rep in b.ordering(manifest, c['repetitions'], seed)]


def plan(path=CONFIG):
    try:
        c = load(path)
    except (ValueError, OSError):
        raise PreflightRefusal('frozen representative contract rejected') from None
    return {'campaign_id': c['campaign_id'], 'planned_primary_runs': len(jobs(c)),
            'maximum_codex_executions': c['maximum_codex_executions'], 'retries': c['retries'],
            'variants': c['variants'], 'repetitions': c['repetitions'],
            'qualified_host': host.current_host().status, 'model_calls': 0,
            'readiness': c['readiness'], 'model_execution_enabled': False}


def references(c, path):
    return {'campaign_id': c['campaign_id'], 'campaign_sha256': primitives.sha(path),
            'manifest_sha256': c['pins']['manifest_sha256'],
            'grader_sha256': c['pins']['grader_sha256'],
            'fixture_sha256': c['pins']['fixture_sha256'],
            'runner_pins': c['runner_pins'], 'model': c['settings']['model'],
            'codex': c['codex'], 'toolchains': c['toolchains'], 'cold_warm': c['cold_warm']}


def _grade_submission(s, workspace, qualification, runtime):
    # No direct representative_graders.check call, even for JSON/exploration.
    policy = (isolation.SubmissionPolicy(True, ('answer.json',))
              if s['id'] == 'explore-notification' else isolation.SubmissionPolicy())
    result = isolation.grade_representative(
        s['id'], workspace, qualification, policy=policy, runtime=runtime)
    if (type(result) is not isolation.GradeResult or result.status != 'verified'
            or type(result.quality_pass) is not bool):
        raise ValueError('grading-isolation-refused')
    return result.quality_pass


def _normalized(c, record, refs, qualification_reference, agent_isolation_reference,
                isolation_reference, production_grading_reference,
                grading_runtime_inventory_reference, execution_kind):
    attempt = record['attempts'][0]
    # Explicit whitelist; raw events, paths, prompt/source and stderr never flow here.
    return {'schema_version': 1, 'campaign_id': c['campaign_id'],
            'scenario_id': record['scenario_id'], 'variant': record['variant'],
            'repetition': record['repetition'], 'seed': record['order_seed'],
            'frozen_references': refs, 'host_qualification_reference': qualification_reference,
            'agent_execution_isolation_reference': agent_isolation_reference,
            'grading_isolation_reference': isolation_reference,
            'production_grading_reference': production_grading_reference,
            'grading_runtime_inventory_reference': grading_runtime_inventory_reference,
            'terminal_status': attempt['terminal_status'], 'process_exit_status': attempt['exit_status'],
            'parser_valid': not attempt['errors'], 'parser_errors': attempt['errors'],
            'quality_pass': record['quality_pass'], 'failure_reason': attempt['failure_reason'],
            'duration_seconds': attempt['duration'], 'observed_tokens': attempt['tokens'],
            'observed_tool_calls_lower_bound': attempt['observed_tool_calls'],
            'full_tool_calls': None, 'retry_count': 0, 'attempt_count': 1,
            'execution_kind': execution_kind,
            'model_calls': None}


def _run_jobs(c, path, runner, grader, *, qualification_reference,
              agent_isolation_reference, isolation_reference,
              production_grading_reference='synthetic-production-grading',
              grading_runtime_inventory_reference='synthetic-runtime-inventory',
              artifacts=None, execution_kind='synthetic-self-validation'):
    """Injection-only adapter for fake tests or the guarded entry; no process launch here."""
    refs = references(c, path)
    records, normalized = [], []
    for sid, variant, rep, seed in jobs(c):
        s = next(x for x in coverage.load_manifest()['scenarios'] if x['id'] == sid)
        s = s | {'allowed_variants': c['variants'], 'quality_gates': ['independent-quality']}
        grading_failure = False
        def checked_grade(s, workspace):
            nonlocal grading_failure
            try:
                return grader(s, workspace)
            except (ValueError, OSError):
                grading_failure = True
                return False
        record = b.run(s, variant, seed, rep, runner, retries=0, cold='unknown',
                       references=refs, grader=checked_grade, artifacts=artifacts)
        if grading_failure:
            record['attempts'][0]['failure_reason'] = 'grading-refusal'
            record['final_status'] = 'grading-refusal'
        safe = _normalized(c, record, refs, qualification_reference, agent_isolation_reference,
                           isolation_reference, production_grading_reference,
                           grading_runtime_inventory_reference, execution_kind)
        if artifacts is not None:
            # Completed normalized jobs survive interruption. Never overwrite evidence.
            with (artifacts / f'{sid}-{variant}-{rep}.json').open('x') as output:
                output.write(json.dumps(safe, indent=2) + '\n')
        records.append(record)
        normalized.append(safe)
    return {'campaign_id': c['campaign_id'], 'planned_jobs': 40,
            'model_calls': None, 'attempted_jobs': len(records),
            'summary': b.aggregate(records), 'records': normalized}


def _staged_environment(c, runtime, workspace):
    """Build the frozen shell-child environment from the fully verified runtime."""
    if type(runtime) is not submission_grading.PreparedRuntime:
        raise ValueError('prepared grading runtime required')
    workspace = Path(workspace)
    if not workspace.is_absolute() or workspace.is_symlink() or not workspace.is_dir():
        raise ValueError('absolute workspace required')
    spec = c['settings']['staged_toolchain_environment']
    root = runtime.root

    def expand(value):
        path = Path(value)
        return str(path if path.is_absolute() else root / path)

    env = dict(spec['fixed'])
    env['PATH'] = ':'.join(expand(value) for value in spec['path_roles'])
    env['COMPILER_PATH'] = ':'.join(expand(value) for value in spec['compiler_path_roles'])
    env['LIBRARY_PATH'] = ':'.join(expand(value) for value in spec['library_path_roles'])
    for name, relative in spec['workspace_relative'].items():
        rel = Path(relative)
        if rel.is_absolute() or '..' in rel.parts or '.' in rel.parts:
            raise ValueError('unsafe workspace-relative toolchain path')
        env[name] = str(workspace / rel)
    return env


def _toml_string_table(values):
    if type(values) is not dict or any(type(k) is not str or type(v) is not str
                                       for k, v in values.items()):
        raise ValueError('invalid shell environment table')
    return '{' + ','.join(f'{key}={json.dumps(values[key])}' for key in sorted(values)) + '}'


def command_plan(c, variant, executable, *, runtime=None, workspace=None):
    argv = primitives.command_plan(c, variant, executable)
    argv[-1:-1] = agent_isolation.command_overrides()
    if (runtime is None) != (workspace is None):
        raise ValueError('runtime and workspace must be supplied together')
    if runtime is not None:
        child_env = _staged_environment(c, runtime, workspace)
        argv[-1:-1] = ['-c', 'shell_environment_policy.set=' + _toml_string_table(child_env)]
    return argv


def _identity_preflight(c, executable, runtime):
    """Verify Codex and every exact staged toolchain without using host PATH."""
    if not executable or not Path(executable).is_absolute():
        raise ValueError('explicit absolute Codex executable required')
    if primitives.sha(executable) != c['codex']['executable_sha256']:
        raise ValueError('Codex checksum mismatch')
    version = b.execute([executable, '--version'], b.ROOT, timeout=10)
    if (version['timeout'] or version['exit_status'] != 0
            or version['stdout'].strip() != 'codex-cli 0.162.1'):
        raise ValueError('Codex version mismatch')
    if type(runtime) is not submission_grading.PreparedRuntime:
        raise ValueError('prepared grading runtime required')
    paths = {
        'rustc': runtime.root / 'rust/bin/rustc',
        'cargo': runtime.root / 'rust/bin/cargo',
        'go': runtime.root / 'go/bin/go',
        'python3': runtime.root / 'python/bin/python3',
    }
    for name, spec in c['toolchains'].items():
        executable_path = paths.get(name)
        if executable_path is None:
            raise ValueError('unknown staged toolchain')
        observation = b.execute(
            [str(executable_path), *spec['version_arguments']], b.ROOT, timeout=10)
        if (observation['timeout'] or observation['exit_status'] != 0
                or observation['stdout'].strip() != spec['version']):
            raise ValueError('toolchain mismatch')


def real_run(executable, run_id, qualification, *, grading_runtime_root=None,
             grading_inventory_dir=None, authorized=False, path=CONFIG):
    """Only production-facing representative model entry. Gate order is deliberate."""
    try:
        c = load(path)
    except (ValueError, OSError):
        raise PreflightRefusal('frozen representative contract rejected') from None
    if type(qualification) is not host.QualifiedHostContract or qualification.status != 'verified':
        raise PreflightRefusal('qualified host contract is not verified')
    if c['readiness']['qualified_host_contract'] != 'verified':
        raise PreflightRefusal('qualified host contract is not verified')
    if c['readiness']['agent_execution_isolation_contract'] != 'verified':
        raise PreflightRefusal('agent execution isolation contract is not verified')
    if not agent_isolation.representative_contract_verified(qualification):
        raise PreflightRefusal('agent execution isolation evidence is not verified')
    if c['readiness']['grading_isolation_contract'] != 'verified':
        raise PreflightRefusal('grading isolation contract is not verified')
    if not isolation.representative_contract_verified(qualification):
        raise PreflightRefusal('grading isolation backend is not verified')
    if c['readiness']['production_grading_contract'] != 'verified':
        raise PreflightRefusal('production grading contract is not verified')
    if not submission_grading.contract_verified(qualification):
        raise PreflightRefusal('production grading evidence is not verified')
    if c['readiness']['representative_campaign_ready'] is not True:
        raise PreflightRefusal('representative campaign is not ready')
    try:
        runtime = submission_grading.prepare_runtime(
            grading_runtime_root, grading_inventory_dir, qualification)
    except (TypeError, ValueError, OSError):
        raise PreflightRefusal('production grading runtime is not prepared') from None
    try:
        _identity_preflight(c, executable, runtime)
    except (ValueError, OSError):
        raise PreflightRefusal('executable or staged toolchain identity rejected') from None
    try:
        agent_isolation.runtime_preflight()
    except (ValueError, OSError):
        raise PreflightRefusal('agent execution isolation runtime rejected') from None
    if authorized is not True:
        raise PreflightRefusal('explicit representative execution authorization required')
    try:
        artifacts = primitives.artifact_directory(run_id)
    except (ValueError, OSError):
        raise PreflightRefusal('private artifact target rejected') from None
    def runner(s, variant, workspace):
        return b.execute(command_plan(c, variant, executable, runtime=runtime, workspace=workspace),
                         workspace, primitives.prompt(c, s, variant),
                         timeout=c['timeout_seconds'])
    agent_reference = next(
        row.evidence_sha256 for row in qualification.evidence.components
        if row.component == agent_isolation.COMPONENT
    )
    production_reference = submission_grading.load_candidate_evidence()['evidence_reference']
    return _run_jobs(c, path, runner,
                     lambda s, w: _grade_submission(s, w, qualification, runtime),
                     qualification_reference=qualification.reference,
                     agent_isolation_reference=agent_reference,
                     isolation_reference=c['runner_pins']['isolation_sha256'],
                     production_grading_reference=production_reference,
                     grading_runtime_inventory_reference=runtime.inventory_reference,
                     artifacts=artifacts, execution_kind='real-representative')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--real', action='store_true')
    parser.add_argument('--authorize-execution', action='store_true')
    parser.add_argument('--codex')
    parser.add_argument('--run-id', default='representative-development-v1')
    parser.add_argument('--qualification-evidence', help='non-secret independently verified component receipt')
    parser.add_argument('--grading-runtime-root', help='reviewed staged grading runtime under /tmp')
    parser.add_argument('--grading-inventory-dir', help='reviewed runtime inventory manifest directory')
    args = parser.parse_args(argv)
    try:
        if args.real:
            qualification = (host.load_evidence(args.qualification_evidence)
                             if args.qualification_evidence else host.current_host())
            result = real_run(
                args.codex, args.run_id, qualification,
                grading_runtime_root=args.grading_runtime_root,
                grading_inventory_dir=args.grading_inventory_dir,
                authorized=args.authorize_execution)
        else:
            result = plan()
    except PreflightRefusal as error:
        print(json.dumps(error.as_record()))
        parser.error(str(error))
    except (ValueError, OSError):
        # Fixed refusal categories only; exceptions never include submitted event payloads.
        parser.error('representative contract or qualification receipt rejected')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
