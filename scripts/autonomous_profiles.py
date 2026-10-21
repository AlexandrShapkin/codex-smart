"""Fixed, declarative verification mappings for disabled Contract v1.

Independently pin/review this module before trusting it. These argv templates
are NOT executable admission: no PATH lookup, dependency probing or execution
occurs here. Host CI and device evidence remain externally verified facts.
"""
from autonomous_contract import ContractRefused, validate_contract

# Repository text cannot add a profile or substitute a weaker native gate.
# Relative executables are documentation templates, never trusted binary pins.
POLICIES = {
    'codex-smart': {
        'profiles': ('rust-ci', 'rust-tests', 'rust-format', 'rust-clippy', 'docs-check', 'security-check'),
        'workflows': ('.github/workflows/ci.yml', '.github/workflows/security.yml'),
        'required_argv': (('just', 'check'), ('just', 'security')),
        'hosted_evidence': ('CI/check', 'Security/review'),
    },
    'rustcraft': {
        'profiles': ('rust-ci', 'rust-tests', 'rust-format', 'rust-clippy', 'docs-check', 'linux-ci', 'windows-ci'),
        'workflows': ('.github/workflows/ci.yml',),
        'required_argv': (('just', 'ci'),),
        'hosted_evidence': ('ci/ubuntu-latest', 'ci/windows-latest'),
    },
    'assistant-hub': {
        'profiles': ('python-tests', 'python-compile', 'python-doctor', 'public-tree', 'ui-tests'),
        'workflows': ('.github/workflows/ci.yml',),
        # Tests/doctor require independently controlled PYTHONPATH=src.
        # UI glob expansion is the adapter's responsibility, never shell input.
        'required_argv': (
            ('python3', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-v'),
            ('python3', '-B', '-m', 'compileall', '-q', 'src', 'tests', 'scripts'),
            ('python3', '-B', '-m', 'assistant_hub', 'doctor'),
            ('python3', '-B', 'scripts/check_public_tree.py', '--include-untracked'),
            ('node', '--test', 'web/tests/*.test.mjs'),
        ),
        'hosted_evidence': ('Python 3.11', 'Python 3.12', 'Python 3.13', 'offline UI'),
    },
    'relayforge': {
        'profiles': ('rust-format', 'rust-clippy', 'rust-tests', 'rust-release'),
        'workflows': ('.github/workflows/tests.yml', '.github/workflows/rdc-independent.yml'),
        # Release compilation/smoke requires separate authority; never run here.
        # Every actual Cargo call must supply an isolated CARGO_TARGET_DIR.
        'required_argv': (
            ('cargo', 'fmt', '--all', '--', '--check'),
            ('cargo', 'clippy', '--workspace', '--all-targets', '--locked', '--', '-D', 'warnings'),
            ('cargo', 'test', '--workspace', '--locked'),
            ('cargo', 'build', '--release', '--locked', '-p', 'relayforge-agent', '-p', 'relayforge-mcp'),
        ),
        'hosted_evidence': ('Rust checks', 'RDC-independent development verification'),
    },
}


def validate_project(data, *, project_id, **facts):
    """Reconcile strict metadata with a separately pinned project policy.

    Facts retain validate_contract's independent-caller trust requirement.
    Neither the return value nor its argv is permission to execute anything.
    A future executor still needs authenticated Git/worktree, immutable executable
    admission, dependency checks, sandboxing and independent exact-head CI.
    """
    if type(project_id) is not str or project_id not in POLICIES:
        raise ContractRefused('unknown project policy')
    policy = POLICIES[project_id]
    doc = validate_contract(
        data, expected_repository='AlexandrShapkin/' + project_id,
        expected_project_id=project_id,
        trusted_profile_ids=frozenset(policy['profiles']), **facts)
    if set(doc['verification']['profiles']) != set(policy['profiles']):
        raise ContractRefused('complete project-native profile set required')
    if set(doc['verification']['ci_workflows']) != set(policy['workflows']):
        raise ContractRefused('complete project-native workflow set required')
    return doc
