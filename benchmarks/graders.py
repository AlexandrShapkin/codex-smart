"""Independent fixed oracles. Run only in disposable isolated benchmark environments."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def command(argv, cwd):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GOCACHE": str(cwd / "go-cache"),
           "GOPROXY": "off", "GOSUMDB": "off", "GOTOOLCHAIN": "local"}
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=25).returncode == 0


def check(sid, workspace):
    # Do not follow agent-created links into external data.
    if any(p.is_symlink() for p in workspace.rglob('*')):
        return False
    with tempfile.TemporaryDirectory(prefix='oracle-') as tmp:
        oracle = Path(tmp)
        if sid == 'rust-clamp':
            source = (workspace / 'lib.rs').read_text()
            tests = '\n#[test] fn oracle(){for x in [i32::MIN,-100,-1,0,1,9,10,11,i32::MAX]{assert_eq!(clamp(x), x.clamp(0,10));}}'
            (oracle / 'lib.rs').write_text(source + tests)
            return command(['rustc', '--test', 'lib.rs', '-o', 'test'], oracle) and command([str(oracle/'test')], oracle)
        if sid == 'go-total':
            (oracle / 'main.go').write_text((workspace / 'main.go').read_text())
            (oracle / 'oracle.go').write_text('package main\nfunc main(){for _,xs:=range [][]int{nil,{}, {1,2,3},{-4,2},{100,0,-1}}{want:=0;for _,x:=range xs{want+=x};if Total(xs)!=want{panic("sum")}}}\n')
            return command(['go', 'run', 'main.go', 'oracle.go'], oracle)
        if sid == 'iac-security':
            data = json.loads((workspace/'deployment.json').read_text())
            return data == {'replicas':2,'securityContext':{'runAsNonRoot':True,'privileged':False},'image':'example/app:1.2.3'}
        if sid == 'python-explore':
            f = json.loads((Path(__file__).parent/'scenarios'/f'{sid}.json').read_text())
            return (all((workspace/n).read_text() == c for n,c in f['files'].items()) and
                    json.loads((workspace/'answer.json').read_text()) == {'call_chain':['entry.py','service.handle','storage.save']})
        if sid == 'python-tests':
            # Mutation validation of submitted tests: baseline passes, both mutants fail.
            (oracle/'test_calc.py').write_text((workspace/'test_calc.py').read_text())
            for code, expected in [('def divide(a,b): return a/b\n', True),
                                   ('def divide(a,b): return 0\n', False),
                                   ('def divide(a,b): return a/b if b else 0\n', False)]:
                (oracle/'calc.py').write_text(code)
                if command([sys.executable, '-B', '-m', 'unittest', 'discover'], oracle) != expected:
                    return False
            return (workspace/'calc.py').read_text() == 'def divide(a,b):\n    return a/b\n'
        if sid == 'python-refactor':
            script = 'from names import canonical\nfrom service import key\nimport names\nassert not hasattr(names,"normalize")\nfor x in ["AbC","","HELLO","Other"]: assert canonical(x)==x.lower() and key(x)==x.lower()\n'
        elif sid == 'python-api':
            script = 'from api import lookup\nfrom client import fetch\nfor x in ["a", "", 42, None]: assert lookup(x)=={"value":x} and fetch(x)==x\n'
        else:
            return False
        for p in workspace.glob('*.py'):
            (oracle/p.name).write_text(p.read_text())
        (oracle/'oracle.py').write_text(script)
        return command([sys.executable, '-B', 'oracle.py'], oracle)


if __name__ == '__main__':
    try:
        result = check(sys.argv[1], Path(sys.argv[2]))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        result = False
    sys.exit(0 if result else 1)
