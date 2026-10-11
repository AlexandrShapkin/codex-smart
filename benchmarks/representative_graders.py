"""Independent representative oracles; host execution is ONLY for trusted controls.

No model-run adapter or submission CLI. Security isolation remains a separate gate.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def command(argv, cwd, expected_stdout=None):
    env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
           'GOCACHE': str(cwd/'go-cache'), 'GOPROXY': 'off', 'GOSUMDB': 'off',
           'GOTOOLCHAIN': 'local', 'PYTHONDONTWRITEBYTECODE': '1',
           'CARGO_HOME': str(cwd/'cargo-home'), 'CARGO_NET_OFFLINE': 'true'}
    # Trusted controls use an already-installed alias, never rustup's installing
    # shorthand. Exact Cargo identity is checked before controls; unknown host
    # selectors are ignored. This wrapper is not the future isolated runtime.
    if argv[0] == 'cargo':
        selector = '1.98.0' if os.environ.get('RUSTUP_TOOLCHAIN') == '1.98.0' else 'stable'
        argv = ['rustup','run',selector,*argv]
    # A timeout/environment allowlist is not a security boundary.
    try:
        result = subprocess.run(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=25)
        return result.returncode == 0 and (expected_stdout is None or
                                          result.stdout.decode().strip() == expected_stdout)
    except (OSError, subprocess.TimeoutExpired):
        return False


def declarative_equal(actual, expected):
    # Prerequisite/event lists are sets by the fixture schema, not patch order.
    def canonical(value, key=''):
        if isinstance(value, dict):
            return {k:canonical(v,k) for k,v in value.items()}
        if isinstance(value, list):
            xs=[canonical(v) for v in value]
            if key in {'needs','events','ports','cidrs','capabilities'}:
                encoded=[json.dumps(v,sort_keys=True) for v in xs]
                if len(set(encoded)) != len(encoded): raise ValueError('duplicate declarative value')
                return sorted(xs,key=lambda v:json.dumps(v,sort_keys=True))
            return xs
        return value
    return json.dumps(canonical(actual),sort_keys=True)==json.dumps(canonical(expected),sort_keys=True)


def check(scenario, fixture, workspace):
    """Fixture/oracle comes from pinned trusted storage, never submitted files."""
    if any(p.is_symlink() for p in workspace.rglob('*')):
        return False
    domain = scenario['language_or_domain']
    sid = scenario['id']
    try:
        if domain in {'infrastructure', 'repository/CI', 'exploration'}:
            preserve = set(fixture['files']) - set(fixture['reference'])
            if any((workspace/n).read_text() != fixture['files'][n] for n in preserve):
                return False
            return all(declarative_equal(json.loads((workspace/n).read_text()), data)
                       for n, data in fixture['oracle'].items())
        with tempfile.TemporaryDirectory(prefix='representative-oracle-') as tmp:
            oracle = Path(tmp)
            # Copy only task files, never arbitrary oracle names or links. Trusted
            # oracle lives separately from submitted workspace. Future sandbox must
            # mount oracle read-only; this trusted-control path does NOT do that.
            names = set(fixture['files']) | set(fixture['reference'])
            for n in names:
                p = workspace/n
                if p.is_file():
                    dest = oracle/n
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(p.read_text())
            if domain == 'Rust':
                (oracle/'tests').mkdir(exist_ok=True)
                (oracle/'tests'/'independent.rs').write_text(fixture['oracle'])
                return (command(['cargo','check','--locked','--offline'],oracle)
                        and command(['cargo','test','--locked','--offline'],oracle))
            if domain == 'Go':
                (oracle/'independent_test.go').write_text(fixture['oracle'])
                return command(['go', 'test', '-count=1', './...'], oracle)
            if sid == 'python-config-tests':
                if any((workspace/n).read_text() != fixture['files'][n]
                       for n in ['config.py', 'service.py']):
                    return False
                mutants = [fixture['files']['config.py'],
                           'def parse_bool(value): return bool(value)\n',
                           'def parse_bool(value):\n if value == "true": return True\n if value == "false": return False\n return False\n',
                           'def parse_bool(value):\n if str(value).lower() == "true": return True\n if str(value).lower() == "false": return False\n raise ValueError("invalid")\n']
                for index, source in enumerate(mutants):
                    (oracle/'config.py').write_text(source)
                    if command([sys.executable, '-B', '-m', 'unittest', 'discover'], oracle) != (index == 0):
                        return False
                return True
            if domain == 'Python':
                (oracle/'independent.py').write_text(fixture['oracle'])
                has_tests = any(oracle.glob('test*.py'))
                return ((not has_tests or command([sys.executable, '-B', '-m', 'unittest', 'discover'], oracle))
                        and command([sys.executable, '-B', 'independent.py'], oracle))
    except (OSError, ValueError, TypeError):
        return False
    return False
