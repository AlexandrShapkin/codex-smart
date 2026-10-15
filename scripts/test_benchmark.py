import copy
import json
from pathlib import Path
import shutil
import tempfile
import sys
import math
import traceback
import unittest
from unittest.mock import patch

import benchmark as b
import rust_grade_trace as rust_trace


def validated_rust_report(raw, control):
    """Reject arbitrary child JSON; return newly built, bounded safe metadata."""
    def require(condition):
        if not condition:
            raise ValueError('diagnostic-invalid')

    def keys(value, expected):
        require(type(value) is dict and set(value) == set(expected))

    def integer(value, low, high):
        require(type(value) is int and low <= value <= high)
        return int(value)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result)
            result[key] = value
        return result

    require(type(raw) is str and len(raw) <= 8192)
    require(len(raw.encode('utf-8')) <= 8192)
    report = json.loads(raw, object_pairs_hook=unique)
    keys(report, ('scenario', 'controls'))
    require(report['scenario'] == 'rust-clamp')
    require(type(report['controls']) is list and len(report['controls']) == 1)
    row = report['controls'][0]
    keys(row, ('control', 'quality_pass', 'control_ok', 'commands'))
    require(row['control'] == control and control in ('correct', 'wrong'))
    require(type(row['quality_pass']) is bool and type(row['control_ok']) is bool)
    require(type(row['commands']) is list and len(row['commands']) <= 2)
    commands = []
    for index, command in enumerate(row['commands']):
        keys(command, ('phase', 'exit_code', 'timed_out', 'timeout_seconds',
                       'launch_error', 'stderr', 'duration_ms'))
        phase = 'compile' if index == 0 else 'test'
        require(command['phase'] == phase)
        code = command['exit_code']
        if code is not None:
            code = integer(code, -2147483648, 2147483647)
        require(type(command['timed_out']) is bool)
        require(type(command['timeout_seconds']) is int and command['timeout_seconds'] == 25)
        launch = command['launch_error']
        require(launch is None or type(launch) is str and launch in (
            'tool-missing', 'memory-pressure', 'process-pressure', 'storage-pressure', 'os-error'))
        labels = command['stderr']
        allowed = ('memory-pressure', 'storage-pressure', 'process-pressure',
                   'compiler-error', 'assertion-failed')
        require(type(labels) is list and len(labels) <= len(allowed))
        require(all(type(label) is str and label in allowed for label in labels))
        commands.append({'phase': phase, 'exit_code': code, 'timed_out': command['timed_out'],
                         'timeout_seconds': 25, 'launch_error': launch,
                         'stderr': [label for label in allowed if label in labels],
                         'duration_ms': integer(command['duration_ms'], 0, 86400000)})
    if row['control_ok']:
        require(row['quality_pass'] == (control == 'correct') and len(commands) == 2)
        require([c['exit_code'] for c in commands] == [0, 0 if control == 'correct' else 101])
        require(all(not c['timed_out'] and c['launch_error'] is None for c in commands))
    return {'scenario': 'rust-clamp', 'controls': [{
        'control': control, 'quality_pass': row['quality_pass'],
        'control_ok': row['control_ok'], 'commands': commands}]}


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.m = b.load_manifest()
        self.s = self.m['scenarios'][2]

    def test_legacy_real_cli_is_disabled(self):
        import contextlib, io, sys
        for arguments in [['--real'], ['--real', '--codex', '/fake/codex', '--model', 'gpt-6-sol']]:
            with self.subTest(arguments=arguments), \
                 patch.object(sys, 'argv', ['benchmark.py', *arguments]), \
                 patch.object(b, 'execute') as execute, patch.object(b, 'run') as run, \
                 patch.object(b, 'load_manifest') as manifest, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised: b.main()
                self.assertEqual(raised.exception.code, 2)
                execute.assert_not_called()
                run.assert_not_called()
                manifest.assert_not_called()
        self.assertFalse(hasattr(b, 'real_run'))

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
                    '', '{"type":"turn.completed","usage":{"input_tokens":true}}'):
            with self.subTest(raw=raw):
                x = b.parse_trace(raw)
                self.assertTrue(x['errors'])
                self.assertIsNone(x['tokens']['input'])

    def test_terminal_contract(self):
        prefix = [{'type': 'thread.started'}, {'type': 'turn.started'}]
        failed = [{'type': 'error'}, {'type': 'error'}, {'type': 'item.completed'},
                  {'type': 'error'}, {'type': 'turn.failed'}]
        def parse(events):
            return b.parse_trace('\n'.join(json.dumps(e) for e in events))
        for events, status in [(prefix + [{'type': 'turn.completed'}], 'completed'),
                               (prefix + failed, 'failed'),
                               (prefix + [{'type': 'error'}, {'type': 'turn.completed'}], 'completed')]:
            result = parse(events)
            self.assertEqual(result['errors'], [])
            self.assertEqual(result['terminal_status'], status)
            self.assertTrue(all(v is None for v in result['tokens'].values()))
        for first in ['turn.completed', 'turn.failed']:
            for second in ['turn.completed', 'turn.failed', 'error', 'item.completed']:
                with self.subTest(first=first, second=second):
                    result = parse(prefix + [{'type': first}, {'type': second}])
                    self.assertIn('late-event', result['errors'])
                    self.assertTrue(all(v is None for v in result['tokens'].values()))
        self.assertEqual(parse(prefix)['terminal_status'], 'missing')
        self.assertTrue(parse(prefix)['errors'])

    def test_failed_turn_runner_skips_grader_and_redacts(self):
        raw = '\n'.join(json.dumps(e) for e in [
            {'type': 'thread.started'}, {'type': 'turn.started'}, {'type': 'error'},
            {'type': 'turn.failed', 'error': {'message': 'PRIVATE'}}])
        for exit_status in [0, 1]:
            with patch.object(b, 'grade') as grader:
                result = b.run(self.s, 'vanilla', 14, 0, lambda *args: {
                    'stdout': raw, 'stderr': '', 'exit_status': exit_status,
                    'timeout': False, 'duration': 0.01})
                grader.assert_not_called()
            attempt = result['attempts'][0]
            self.assertEqual(result['final_status'], 'agent-failure')
            self.assertFalse(result['quality_pass'])
            self.assertEqual(attempt['exit_status'], exit_status)
            self.assertEqual(attempt['errors'], [])
            self.assertTrue(all(v is None for v in attempt['tokens'].values()))
            self.assertNotIn('PRIVATE', json.dumps(result))

    def test_completed_turn_grader_controls_quality(self):
        for quality in [False, True]:
            with patch.object(b, 'grade', return_value=quality) as grader:
                result = b.run(self.s, 'vanilla', 14, 0, b.FakeRunner())
                grader.assert_called_once()
            self.assertEqual(result['quality_pass'], quality)
            self.assertEqual(result['attempts'][0]['tokens']['input'], 10)

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
                        if s['id'] == 'rust-clamp':
                            self.assert_rust_grade(s, d, expected)
                        else:
                            self.assertEqual(b.grade(s,d),expected, (s['id'],kind))

    def assert_rust_grade(self, scenario, workspace, expected):
        execute = b.execute
        observations = []

        def observed(*args, **kwargs):
            with rust_trace.capture(args[0]) as trace_state:
                result = execute(*args, **kwargs)
            try:
                inner = rust_trace.decode(trace_state['raw'])
            except (ValueError, TypeError, RecursionError, UnicodeError):
                raise ValueError('trace-invalid') from None
            # Keep only validated metadata from the actual frozen grade invocation.
            code = result.get('exit_status')
            duration = result.get('duration')
            if (type(code) is not int or not -2147483648 <= code <= 2147483647
                    or type(result.get('timeout')) is not bool
                    or type(duration) not in (int, float) or not math.isfinite(duration)
                    or duration < 0):
                raise ValueError('outer-metadata-invalid')
            observations.append({'exit_code': code, 'timeout': result['timeout'],
                                 'duration_ms': round(min(86400, duration) * 1000),
                                 'signal': -code if code < 0 else None,
                                 'deadline_seconds': 30, 'cleanup': 'UNKNOWN',
                                 'inner': inner})
            return result

        try:
            with patch.object(b, 'execute', side_effect=observed):
                passed = b.grade(scenario, workspace)
        except (OSError, ValueError):
            raise self.failureException('rust-clamp grade: outer-error; inner=UNKNOWN') from None
        self.assertEqual(len(observations), 1, 'rust-clamp grade: observation-invalid')
        outer = observations[0]
        message = ('rust-clamp grade: inner=' +
                   ('observed' if outer['inner']['commands'] else 'UNKNOWN') + '; ' +
                   json.dumps(outer, sort_keys=True))
        self.assertFalse(outer['timeout'], message)
        self.assertIn(outer['exit_code'], (0, 1), message)
        self.assertEqual(passed, expected, message)
        self.assertTrue(rust_trace.valid_control(outer['inner'], expected), message)

    def test_supplementary_rust_controls(self):
        if shutil.which('rustc') is None:
            self.skipTest('rustc unavailable')
        for control in ('correct', 'wrong'):
            with self.subTest(control=control):
                self.assert_rust_control(control)

    def assert_rust_control(self, control):
        # Observe this invocation, never rerun a failed Boolean grade as evidence.
        try:
            result = b.execute([sys.executable, '-B',
                                str(Path(__file__).with_name('diagnose_rust_clamp.py')),
                                '--control', control], b.ROOT, timeout=30)
        except OSError:
            raise self.failureException('rust-clamp control: outer-launch-error') from None
        if result['timeout']:
            self.fail('rust-clamp control: outer-timeout (30 seconds)')
        try:
            report = validated_rust_report(result.get('stdout'), control)
        except (ValueError, TypeError, RecursionError):
            raise self.failureException('rust-clamp control: diagnostic-invalid') from None
        # Only reconstructed allowlisted metadata can reach an assertion.
        message = 'rust-clamp control: ' + json.dumps(report, sort_keys=True)
        self.assertEqual(result['exit_status'], 0, message)
        self.assertTrue(report['controls'][0]['control_ok'], message)

    def test_rust_control_failures_are_not_negative_control_success(self):
        for result, label in [
            ({'timeout': True}, 'outer-timeout'),
            ({'timeout': False, 'exit_status': -9, 'stdout': 'PRIVATE'},
             'diagnostic-invalid'),
            ({'timeout': False, 'exit_status': 1, 'stdout': json.dumps({
                'controls': [{'control': 'wrong', 'control_ok': False,
                              'commands': [{'phase': 'compile', 'exit_code': 1}]}]})},
             'diagnostic-invalid'),
        ]:
            with self.subTest(label=label), patch.object(b, 'execute', return_value=result) as execute:
                with self.assertRaises(AssertionError) as raised:
                    self.assert_rust_control('wrong')
                self.assertIn(label, str(raised.exception))
                self.assertNotIn('PRIVATE', str(raised.exception))
                execute.assert_called_once()
        with patch.object(b, 'execute', side_effect=OSError('PRIVATE')):
            with self.assertRaisesRegex(AssertionError, 'outer-launch-error') as raised:
                self.assert_rust_control('correct')
            rendered = ''.join(traceback.format_exception(raised.exception))
            self.assertNotIn('PRIVATE', rendered)

    def test_rust_diagnostic_json_is_bounded_and_allowlisted(self):
        report = {'scenario': 'rust-clamp', 'controls': [{
            'control': 'wrong', 'quality_pass': False, 'control_ok': False,
            'commands': [{'phase': 'compile', 'exit_code': 7, 'timed_out': False,
                          'timeout_seconds': 25, 'launch_error': None, 'stderr': [],
                          'duration_ms': 1}]}]}
        self.assertEqual(validated_rust_report(json.dumps(report), 'wrong'), report)
        adversarial = []
        for target, field, value in [
            ('report', 'PRIVATE', 'PRIVATE'),
            ('report', 'scenario', 'PRIVATE'),
            ('row', 'control', 'PRIVATE'),
            ('row', 'quality_pass', 'PRIVATE'),
            ('command', 'stderr', ['PRIVATE']),
            ('command', 'launch_error', 'PRIVATE'),
            ('command', 'duration_ms', 'PRIVATE'),
            ('command', 'exit_code', {'PRIVATE': True}),
            ('command', 'phase', 'PRIVATE'),
        ]:
            changed = copy.deepcopy(report)
            obj = (changed if target == 'report' else changed['controls'][0]
                   if target == 'row' else changed['controls'][0]['commands'][0])
            obj[field] = value
            adversarial.append(json.dumps(changed))
        adversarial.extend(['PRIVATE' * 2000, '{"scenario":"PRIVATE","scenario":"rust-clamp"}',
                            '["PRIVATE"]', '"PRIVATE"'])
        for raw in adversarial:
            with self.subTest(case=adversarial.index(raw)):
                result = {'timeout': False, 'exit_status': 1, 'stdout': raw}
                with patch.object(b, 'execute', return_value=result):
                    with self.assertRaisesRegex(AssertionError, 'diagnostic-invalid') as raised:
                        self.assert_rust_control('wrong')
                self.assertNotIn('PRIVATE', ''.join(traceback.format_exception(raised.exception)))
        with patch.object(b, 'execute', return_value={
                'timeout': False, 'exit_status': 1, 'stdout': json.dumps(report)}):
            with self.assertRaisesRegex(AssertionError, 'compile'):
                self.assert_rust_control('wrong')

    def test_rust_grade_observes_original_call_and_fails_closed_on_outer_errors(self):
        scenario = next(s for s in self.m['scenarios'] if s['id'] == 'rust-clamp')
        for code, timeout, expected, fails in [
            (0, False, True, True), (1, False, False, True),
            (1, False, True, True), (-9, False, False, True),
            (1, True, False, True), (2, False, False, True),
        ]:
            with self.subTest(code=code, timeout=timeout, expected=expected):
                result = {'exit_status': code, 'timeout': timeout, 'duration': .125,
                          'stdout': 'PRIVATE', 'stderr': 'PRIVATE'}
                with patch.object(b, 'execute', return_value=result) as execute:
                    if fails:
                        with self.assertRaisesRegex(AssertionError, 'inner=UNKNOWN') as raised:
                            self.assert_rust_grade(scenario, Path('/synthetic'), expected)
                        self.assertNotIn('PRIVATE', ''.join(traceback.format_exception(raised.exception)))
                    else:
                        self.assert_rust_grade(scenario, Path('/synthetic'), expected)
                    execute.assert_called_once_with(
                        [shutil.which('python3'), '-B', str(b.ROOT / 'graders.py'),
                         'rust-clamp', '/synthetic'], b.ROOT, timeout=30)
        with patch.object(b, 'execute', side_effect=OSError('PRIVATE')):
            with self.assertRaisesRegex(AssertionError, 'inner=UNKNOWN') as raised:
                self.assert_rust_grade(scenario, Path('/synthetic'), False)
            self.assertNotIn('PRIVATE', ''.join(traceback.format_exception(raised.exception)))

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
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(b.execute([sys.executable,'-c','raise SystemExit(2)'],tmp)['exit_status'],2)
            self.assertTrue(b.execute([sys.executable,'-c','import time; time.sleep(5)'],tmp,timeout=0.05)['timeout'])


if __name__ == '__main__':
    unittest.main()
