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


def _grade_submission(s, workspace, qualification):
    # No direct representative_graders.check call, even for JSON/exploration.
    policy = (isolation.SubmissionPolicy(True, ('answer.json',))
              if s['id'] == 'explore-notification' else isolation.SubmissionPolicy())
    result = isolation.grade_representative(s['id'], workspace, qualification, policy=policy)
    if (type(result) is not isolation.GradeResult or result.status != 'verified'
            or type(result.quality_pass) is not bool):
        raise ValueError('grading-isolation-refused')
    return result.quality_pass


def _normalized(c, record, refs, qualification_reference, agent_isolation_reference,
                isolation_reference, execution_kind):
    attempt = record['attempts'][0]
    # Explicit whitelist; raw events, paths, prompt/source and stderr never flow here.
    return {'schema_version': 1, 'campaign_id': c['campaign_id'],
            'scenario_id': record['scenario_id'], 'variant': record['variant'],
            'repetition': record['repetition'], 'seed': record['order_seed'],
            'frozen_references': refs, 'host_qualification_reference': qualification_reference,
            'agent_execution_isolation_reference': agent_isolation_reference,
            'grading_isolation_reference': isolation_reference,
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
                           isolation_reference, execution_kind)
        if artifacts is not None:
            # Completed normalized jobs survive interruption. Never overwrite evidence.
            with (artifacts / f'{sid}-{variant}-{rep}.json').open('x') as output:
                output.write(json.dumps(safe, indent=2) + '\n')
        records.append(record)
        normalized.append(safe)
    return {'campaign_id': c['campaign_id'], 'planned_jobs': 40,
            'model_calls': None, 'attempted_jobs': len(records),
            'summary': b.aggregate(records), 'records': normalized}


def command_plan(c, variant, executable):
    argv = primitives.command_plan(c, variant, executable)
    argv[-1:-1] = agent_isolation.command_overrides()
    return argv


def _identity_preflight(c, executable):
    # Reuse frozen auth/argv settings and exact identity checks, with inherited smoke scope.
    checked = c | {'live_contract': {'status': 'verified'}}
    primitives.real_preflight(checked, executable)


def real_run(executable, run_id, qualification, *, authorized=False, path=CONFIG):
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
    try:
        _identity_preflight(c, executable)
    except (ValueError, OSError):
        raise PreflightRefusal('executable or toolchain identity rejected') from None
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
        return b.execute(command_plan(c, variant, executable), workspace,
                         primitives.prompt(c, s, variant), timeout=c['timeout_seconds'])
    agent_reference = next(
        row.evidence_sha256 for row in qualification.evidence.components
        if row.component == agent_isolation.COMPONENT
    )
    return _run_jobs(c, path, runner, lambda s, w: _grade_submission(s, w, qualification),
                     qualification_reference=qualification.reference,
                     agent_isolation_reference=agent_reference,
                     isolation_reference=c['runner_pins']['isolation_sha256'], artifacts=artifacts,
                     execution_kind='real-representative')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--real', action='store_true')
    parser.add_argument('--authorize-execution', action='store_true')
    parser.add_argument('--codex')
    parser.add_argument('--run-id', default='representative-development-v1')
    parser.add_argument('--qualification-evidence', help='non-secret independently verified component receipt')
    args = parser.parse_args(argv)
    try:
        if args.real:
            qualification = (host.load_evidence(args.qualification_evidence)
                             if args.qualification_evidence else host.current_host())
            result = real_run(args.codex, args.run_id, qualification, authorized=args.authorize_execution)
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
