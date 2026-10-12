"""Credential-free runtime probe for the pinned representative Codex boundary.

The probe uses only synthetic values, invokes `codex sandbox` (never `codex exec`),
and emits a normalized non-secret record suitable for independent review.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import benchmark_agent_isolation as agent

EXPECTED_VERSION = 'codex-cli 0.162.1'
SYNTHETIC_API_KEY = 'benchmark-synthetic-api-key'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _sandbox(executable, overrides, code, env, cwd):
    command = [str(executable), 'sandbox', *overrides, '/usr/bin/python3', '-c', code]
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError('synthetic sandbox probe failed')
    try:
        record = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise ValueError('synthetic sandbox probe output rejected') from None
    if type(record) is not dict:
        raise ValueError('synthetic sandbox probe output rejected')
    return record


def run(executable):
    contract = agent.load_contract()
    executable = Path(executable)
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError('absolute Codex executable required')
    if sha256(executable) != contract['codex_executable_sha256']:
        raise ValueError('Codex executable checksum mismatch')
    version = subprocess.run(
        [str(executable), '--version'],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
        check=False,
    )
    if version.returncode != 0 or version.stdout.strip() != EXPECTED_VERSION:
        raise ValueError('Codex executable version mismatch')

    source_review = json.loads(agent.SOURCE_REVIEW.read_text())
    if (
        source_review.get('review_id') != 'benchmark-agent-execution-source-review-v1'
        or source_review.get('release_commit') != '092d3acd6bec3e3a14bdc7e7a2810ab628ab759d'
    ):
        raise ValueError('source review identity mismatch')

    baseline_code = (
        "import json,os,socket;"
        "p=os.path.join(os.environ['CODEX_HOME'],'auth.json');"
        "k=os.path.join(os.environ['HOME'],'.local/share/keyrings/probe.keyring');"
        "b=f'/run/user/{os.getuid()}/bus';"
        "s=socket.socket(socket.AF_UNIX);rc=s.connect_ex(b);"
        "print(json.dumps({'auth_file_readable':os.access(p,os.R_OK),"
        "'api_key_in_child_environment':'OPENAI_API_KEY' in os.environ,"
        "'credential_backing_store_readable':os.access(k,os.R_OK),"
        "'user_bus_socket_visible':os.path.exists(b),'user_bus_connectable':rc==0},"
        "sort_keys=True))"
    )
    candidate_code = (
        "import json,os,socket;"
        "k=os.path.join(os.environ['HOME'],'.local/share/keyrings/probe.keyring');"
        "b=f'/run/user/{os.getuid()}/bus';"
        "s=socket.socket(socket.AF_UNIX);rc=s.connect_ex(b);"
        "print(json.dumps({'api_key_in_child_environment':'OPENAI_API_KEY' in os.environ,"
        "'credential_backing_store_readable':os.access(k,os.R_OK),"
        "'user_bus_socket_visible':os.path.exists(b),'user_bus_connectable':rc==0},"
        "sort_keys=True))"
    )

    with tempfile.TemporaryDirectory(prefix='codex-agent-isolation-') as tmp:
        root = Path(tmp)
        codex_home = root / 'codex-home'
        codex_home.mkdir(mode=0o700)
        home = root / 'home'
        backing = home / '.local' / 'share' / 'keyrings'
        backing.mkdir(parents=True, mode=0o700)
        backing_file = backing / 'probe.keyring'
        backing_file.write_text('synthetic backing store\n')
        backing_file.chmod(0o600)
        auth_file = codex_home / 'auth.json'
        auth_file.write_text('{"synthetic":"sentinel"}\n')
        auth_file.chmod(0o600)

        env = {key: os.environ[key] for key in (
            'PATH', 'USER', 'LOGNAME', 'SHELL', 'LANG', 'TERM'
        ) if key in os.environ}
        env['HOME'] = str(home)
        env['CODEX_HOME'] = str(codex_home)
        env['OPENAI_API_KEY'] = SYNTHETIC_API_KEY
        baseline = _sandbox(executable, [], baseline_code, env, root)

        auth_file.unlink()
        auth_file_absent = not auth_file.exists()
        overrides = agent.command_overrides()
        candidate = _sandbox(executable, overrides, candidate_code, env, root)

        private_bus_path = root / 'private-credential-bus.sock'
        listener = __import__('socket').socket(__import__('socket').AF_UNIX, __import__('socket').SOCK_STREAM)
        listener.bind(str(private_bus_path))
        listener.listen(1)
        private_env = dict(env)
        private_env['DBUS_SESSION_BUS_ADDRESS'] = f'unix:path={private_bus_path}'
        private_code = (
            "import json,os,socket;"
            f"p={str(private_bus_path)!r};"
            "s=socket.socket(socket.AF_UNIX);s.settimeout(1);rc=s.connect_ex(p);"
            "print(json.dumps({'address_in_child_environment':'DBUS_SESSION_BUS_ADDRESS' in os.environ,"
            "'connectable':rc==0},sort_keys=True));s.close()"
        )
        try:
            private_bus = _sandbox(executable, overrides, private_code, private_env, root)
        finally:
            listener.close()

    expected_feature_overrides = {
        f'features.{feature}=false' for feature in contract['disabled_features']
    }
    actual_config_values = {
        overrides[index + 1]
        for index, value in enumerate(overrides[:-1])
        if value == '-c'
    }
    external_surface_disabled = expected_feature_overrides <= actual_config_values

    payload = {
        'codex_executable_sha256': contract['codex_executable_sha256'],
        'auth_file_absent': auth_file_absent,
        'api_key_in_child_environment': bool(candidate.get('api_key_in_child_environment')),
        'user_bus_connectable': bool(candidate.get('user_bus_connectable')),
        'private_bus_address_in_child_environment': bool(private_bus.get('address_in_child_environment')),
        'private_bus_connectable': bool(private_bus.get('connectable')),
        'credential_backing_store_readable': bool(candidate.get('credential_backing_store_readable')),
        'external_tool_surface_disabled': external_surface_disabled,
        'command_paths_reviewed': True,
    }
    reference = agent.evidence_reference(payload)
    return {
        'schema_version': 1,
        'contract_id': contract['contract_id'],
        'probe_kind': 'credential-free-synthetic',
        'codex_version': EXPECTED_VERSION,
        'codex_executable_sha256': contract['codex_executable_sha256'],
        'source_review_sha256': contract['source_review_sha256'],
        'baseline_default': {
            'auth_file_readable': bool(baseline.get('auth_file_readable')),
            'api_key_in_child_environment': bool(baseline.get('api_key_in_child_environment')),
            'credential_backing_store_readable': bool(baseline.get('credential_backing_store_readable')),
            'user_bus_socket_visible': bool(baseline.get('user_bus_socket_visible')),
            'user_bus_connectable': bool(baseline.get('user_bus_connectable')),
        },
        'candidate': payload,
        'evidence_reference': reference,
        'model_calls': 0,
        'real_credentials_used': False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex', required=True)
    args = parser.parse_args(argv)
    print(json.dumps(run(args.codex), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
