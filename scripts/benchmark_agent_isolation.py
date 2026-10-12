"""Pinned whole-agent credential and child-execution isolation contract.

This module defines representative-run security requirements. It does not qualify
the current machine and cannot enable execution from self-asserted runtime state.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / 'benchmarks/agent-execution-isolation-v1.json'
SOURCE_REVIEW = ROOT / 'benchmarks/agent-execution-source-review-v1.json'
CANDIDATE_EVIDENCE = ROOT / 'benchmarks/agent-execution-isolation-candidate-v1.json'
COMPONENT = 'agent_execution_isolation'
DISABLED_FEATURES = (
    'multi_agent', 'multi_agent_v2', 'multi_agent_mode',
    'apps', 'plugins', 'remote_plugin', 'tool_suggest', 'recommended_plugins',
    'enable_mcp_apps', 'standalone_web_search', 'web_search_request', 'web_search_cached',
    'search_tool', 'browser_use', 'browser_use_external', 'computer_use',
    'image_generation', 'in_app_browser', 'in_app_local_automation',
    'skill_mcp_dependency_install', 'skill_search', 'code_mode',
)


def expected_contract():
    return {
        'schema_version': 1,
        'contract_id': 'benchmark-agent-execution-isolation-v1',
        'codex_version': '0.162.1',
        'codex_executable_sha256': '628e35487d888a28f0427fc37501da529dd3d81fcbad7a2c3421c1e8670d92e1',
        'source_review_sha256': 'bca3f3d35779f809d46e37da6a808fba4cef59ecaeb499cc05efa5c765e4c6d6',
        'credential_store': 'keyring',
        'file_fallback_allowed': False,
        'auth_file_must_be_absent': True,
        'parent_openai_api_key_must_be_absent': True,
        'credential_backing_store': {
            'child_unreadable_paths': ['~/.local/share/keyrings'],
        },
        'child_environment': {
            'inherit': 'core',
            'ignore_default_excludes': False,
        },
        'disabled_features': list(DISABLED_FEATURES),
        'user_bus': {
            'socket_may_be_visible': True,
            'connectivity_required': 'blocked',
        },
        'private_credential_ipc': {
            'address_in_child_environment_required': False,
            'connectivity_required': 'blocked',
        },
        'required_evidence': [
            'exact-codex-identity',
            'keyring-mode-no-file-fallback-reviewed',
            'auth-file-absent-at-preflight',
            'synthetic-api-key-not-in-child-environment',
            'child-user-bus-connect-blocked',
            'child-private-credential-bus-address-not-inherited',
            'child-private-credential-bus-connect-blocked',
            'child-credential-backing-store-unreadable',
            'external-account-backed-tool-surface-disabled',
            'model-reachable-command-paths-reviewed',
        ],
        'accepted_evidence_sha256': [],
        'authorization_overrides_security': False,
    }


def load_contract(path=CONTRACT):
    actual = json.loads(Path(path).read_text())
    if json.dumps(actual, sort_keys=True) != json.dumps(expected_contract(), sort_keys=True):
        raise ValueError('unreviewed agent execution isolation contract')
    source_review_sha = hashlib.sha256(SOURCE_REVIEW.read_bytes()).hexdigest()
    if source_review_sha != actual['source_review_sha256']:
        raise ValueError('agent execution source review mismatch')
    return actual


def command_overrides():
    contract = load_contract()
    overrides = [
        '-c', 'default_permissions="benchmark"',
        '-c', 'permissions.benchmark.extends=":workspace"',
        '-c', 'permissions.benchmark.filesystem={"~/.local/share/keyrings"="deny"}',
        '-c', 'shell_environment_policy.inherit=core',
        '-c', 'shell_environment_policy.ignore_default_excludes=false',
    ]
    for feature in contract['disabled_features']:
        overrides.extend(['-c', f'features.{feature}=false'])
    return overrides


def runtime_preflight(environ=None):
    """Check non-secret runtime facts immediately before representative execution."""
    contract = load_contract()
    env = os.environ if environ is None else environ
    if contract['parent_openai_api_key_must_be_absent'] and 'OPENAI_API_KEY' in env:
        raise ValueError('parent API-key environment is forbidden')
    configured = env.get('CODEX_HOME')
    codex_home = Path(configured) if configured else Path.home() / '.codex'
    if not codex_home.is_absolute():
        raise ValueError('CODEX_HOME must resolve to an absolute path')
    if contract['auth_file_must_be_absent'] and (codex_home / 'auth.json').exists():
        raise ValueError('file auth is forbidden for representative execution')
    return codex_home


def evidence_reference(payload):
    """Hash a fixed boolean/string probe record without accepting it as verification."""
    allowed = {
        'codex_executable_sha256',
        'auth_file_absent',
        'api_key_in_child_environment',
        'user_bus_connectable',
        'private_bus_address_in_child_environment',
        'private_bus_connectable',
        'credential_backing_store_readable',
        'external_tool_surface_disabled',
        'command_paths_reviewed',
    }
    if type(payload) is not dict or set(payload) != allowed:
        raise ValueError('invalid agent isolation evidence')
    if payload['codex_executable_sha256'] != expected_contract()['codex_executable_sha256']:
        raise ValueError('agent isolation Codex identity mismatch')
    if any(type(payload[key]) is not bool for key in (
        'auth_file_absent', 'api_key_in_child_environment',
        'user_bus_connectable', 'private_bus_address_in_child_environment',
        'private_bus_connectable', 'credential_backing_store_readable',
        'external_tool_surface_disabled',
        'command_paths_reviewed',
    )):
        raise ValueError('agent isolation evidence must use typed booleans')
    normalized = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(normalized).hexdigest()



def load_candidate_evidence(path=CANDIDATE_EVIDENCE):
    record = json.loads(Path(path).read_text())
    required = {
        'schema_version', 'contract_id', 'probe_kind', 'codex_version',
        'codex_executable_sha256', 'source_review_sha256', 'baseline_default',
        'candidate', 'evidence_reference', 'model_calls', 'real_credentials_used',
    }
    if type(record) is not dict or set(record) != required:
        raise ValueError('invalid agent isolation candidate evidence')
    contract = load_contract()
    if (
        record['schema_version'] != 1
        or record['contract_id'] != contract['contract_id']
        or record['probe_kind'] != 'credential-free-synthetic'
        or record['codex_version'] != 'codex-cli 0.162.1'
        or record['codex_executable_sha256'] != contract['codex_executable_sha256']
        or record['source_review_sha256'] != contract['source_review_sha256']
        or record['model_calls'] != 0
        or record['real_credentials_used'] is not False
    ):
        raise ValueError('agent isolation candidate evidence identity mismatch')
    if evidence_reference(record['candidate']) != record['evidence_reference']:
        raise ValueError('agent isolation candidate evidence reference mismatch')
    return record

def representative_contract_verified(qualification):
    """Accepted evidence is necessary in addition to a verified host receipt."""
    import benchmark_host as host

    contract = load_contract()
    if type(qualification) is not host.QualifiedHostContract or qualification.status != 'verified':
        return False
    component = next(
        (row for row in qualification.evidence.components if row.component == COMPONENT),
        None,
    )
    return (
        component is not None
        and component.state == 'verified'
        and component.evidence_sha256 in contract['accepted_evidence_sha256']
    )
