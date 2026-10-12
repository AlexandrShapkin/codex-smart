"""Pure reviewed host-qualification semantics. No discovery, probes or execution."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

STATES = frozenset({'verified', 'blocked', 'unavailable', 'not-verified'})
COMPONENTS = (
    'platform', 'codex_identity', 'toolchains', 'cargo_identity', 'isolation_backend',
    'aggregate_memory', 'aggregate_tasks', 'descendants', 'cleanup', 'network',
    'filesystem', 'environment', 'agent_execution_isolation', 'privilege',
    'trusted_grader_immutability', 'runtime_inventory', 'grader_compatibility',
)
CONTRACT = Path(__file__).resolve().parent.parent / 'benchmarks/host-contract-v1.json'
CANDIDATE_EVIDENCE = Path(__file__).resolve().parent.parent / 'benchmarks/qualified-host-candidate-v1.json'


def expected_contract():
    return {'schema_version': 1, 'contract_id': 'benchmark-qualified-host-v1',
            'platform': 'linux-x86_64',
            'required_components': list(COMPONENTS),
            'accepted_states': sorted(STATES),
            'required_state': 'verified',
            'backend': 'bubblewrap-equivalent-reviewed-unprivileged',
            'candidate_backend_version': 'ubuntu-bubblewrap-0.11.1-1ubuntu0.3-constrained-v1',
            'candidate_backend_contract_sha256': '2d998155b44bace387a52d3368fab6c1e08410bce24cab1ef51562e0df1a0970',
            'candidate_backend_evidence_sha256': '269bef23c21e419216028a44611c36c4c32d2c33b1a32ba02d71dc5259c5e638',
            'codex_version': '0.162.1',
            'codex_distribution': 'upstream-release',
            'codex_release_tag': 'rust-v0.162.1',
            'codex_release_commit': '092d3acd6bec3e3a14bdc7e7a2810ab628ab759d',
            'codex_release_asset': 'codex-x86_64-unknown-linux-musl.tar.gz',
            'codex_release_asset_sha256': '86f268d81b898f3e144c5ecff2ad2fda2c5802e042d6195b72538fe0fa125057',
            'codex_executable_sha256': '628e35487d888a28f0427fc37501da529dd3d81fcbad7a2c3421c1e8670d92e1',
            'toolchain_versions': {
                'rustc': 'rustc 1.98.0 (88d9e12ae 2026-08-18)',
                'go': 'go version go1.27.2 linux/amd64',
                'python3': 'Python 3.14.8',
                'cargo': 'cargo 1.98.0 (797e8a9bc 2026-08-05)'},
            'toolchain_artifacts': {
                'rustc': {'artifact': 'rustc-1.98.0-x86_64-unknown-linux-gnu.tar.xz',
                          'sha256': '0e37cb339f447fc44d6d781073bacacebfdc5612f2600e4c7e84c266f5f3aced'},
                'cargo': {'artifact': 'cargo-1.98.0-x86_64-unknown-linux-gnu.tar.xz',
                          'sha256': '2f512d170d3dd23e16ababcda32ee2e6d5172d861a7af1f504e0b1e270cafab9'},
                'rust-std': {'artifact': 'rust-std-1.98.0-x86_64-unknown-linux-gnu.tar.xz',
                             'sha256': 'f5022e6c95a5ad23cca2513dc8281200f585fa188de6370aa37b128a43f876a3'},
                'go': {'artifact': 'go1.27.2.linux-amd64.tar.gz',
                       'sha256': 'ecbadb99091a3f46e31f5f934b068b1864eafa7995211b39eaddf76996045fe5'},
                'python': {'artifact': 'Python-3.14.8.tar.xz',
                           'sha256': 'c2215904f02b175596dc49351585104f4bc20341e1c47378b26a2c274360ce73'}},
            'verification': 'independent bounded probes and grader controls; reviewed immutable runtime inventory',
            'candidate_qualification_evidence_sha256': '5b8c88467c36758c083782bb9546af3aee098b48369bd2231e846dafd6086f76',
            'accepted_qualification_receipts': ['d2af64ce237de72c9c0ee2659723e2d2858c9e19982cc85dd4420a6c6592d265'],
            'authorization_overrides_security': False}


def load_contract(path=CONTRACT):
    c = json.loads(Path(path).read_text())
    if json.dumps(c, sort_keys=True) != json.dumps(expected_contract(), sort_keys=True):
        raise ValueError('unreviewed qualified-host contract')
    root = Path(__file__).resolve().parent.parent / 'benchmarks'
    backend_contract = root / 'grading-isolation-backend-v1.json'
    backend_evidence = root / 'grading-isolation-backend-candidate-v1.json'
    if hashlib.sha256(backend_contract.read_bytes()).hexdigest() != c['candidate_backend_contract_sha256']:
        raise ValueError('grading backend contract pin mismatch')
    if hashlib.sha256(backend_evidence.read_bytes()).hexdigest() != c['candidate_backend_evidence_sha256']:
        raise ValueError('grading backend evidence pin mismatch')
    if hashlib.sha256(CANDIDATE_EVIDENCE.read_bytes()).hexdigest() != c['candidate_qualification_evidence_sha256']:
        raise ValueError('qualified-host candidate evidence pin mismatch')
    return c


@dataclass(frozen=True)
class ComponentEvidence:
    component: str
    state: str
    evidence_sha256: str | None = None


@dataclass(frozen=True)
class HostQualificationEvidence:
    contract_id: str
    components: tuple[ComponentEvidence, ...]


@dataclass(frozen=True)
class QualifiedHostContract:
    """Computed conjunction, never an operator-supplied overall status."""
    evidence: HostQualificationEvidence

    @property
    def status(self):
        validate_evidence(self.evidence)
        return ('verified' if all(c.state == 'verified' for c in self.evidence.components)
                and _receipt_reviewed(self.reference)
                else 'not-verified')

    @property
    def reference(self):
        # Safe opaque reference; no machine identifiers, paths or arbitrary payloads.
        payload = [[c.component, c.state, c.evidence_sha256] for c in self.evidence.components]
        return hashlib.sha256(json.dumps(payload, separators=(',', ':')).encode()).hexdigest()


def validate_evidence(e):
    if type(e) is not HostQualificationEvidence or e.contract_id != 'benchmark-qualified-host-v1':
        raise ValueError('invalid qualification evidence')
    if (type(e.components) is not tuple
            or any(type(c) is not ComponentEvidence for c in e.components)
            or tuple(c.component for c in e.components) != COMPONENTS):
        raise ValueError('missing or unordered required host component')
    for c in e.components:
        if type(c) is not ComponentEvidence or type(c.state) is not str or c.state not in STATES:
            raise ValueError('unknown qualification state')
        if c.evidence_sha256 is not None and (type(c.evidence_sha256) is not str
                                            or not re.fullmatch('[0-9a-f]{64}', c.evidence_sha256)):
            raise ValueError('unsafe qualification reference')
        if c.state == 'verified' and c.evidence_sha256 is None:
            raise ValueError('verified component requires independent evidence reference')


def qualify(evidence):
    load_contract()
    validate_evidence(evidence)
    return QualifiedHostContract(evidence)


def _normalized_evidence_reference(payload):
    if type(payload) is not dict:
        raise ValueError('invalid normalized host evidence')
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def load_candidate_evidence(path=CANDIDATE_EVIDENCE):
    record = json.loads(Path(path).read_text())
    required = {
        'schema_version', 'contract_id', 'probe_kind', 'repository_head', 'model_calls',
        'real_credentials_used', 'source_bundle_manifest_sha256', 'components',
        'receipt_reference', 'supplemental_exact_bwrap_0_13_crosscheck',
    }
    if type(record) is not dict or set(record) != required:
        raise ValueError('invalid qualified-host candidate evidence')
    if (record['schema_version'] != 1
            or record['contract_id'] != 'benchmark-qualified-host-v1'
            or record['probe_kind'] != 'bounded-independent-host-qualification'
            or record['model_calls'] != 0
            or record['real_credentials_used'] is not False
            or not re.fullmatch('[0-9a-f]{40}', record['repository_head'])
            or not re.fullmatch('[0-9a-f]{64}', record['source_bundle_manifest_sha256'])
            or type(record['components']) is not list
            or len(record['components']) != len(COMPONENTS)):
        raise ValueError('qualified-host candidate identity mismatch')

    normalized_rows = []
    external = {'isolation_backend', 'agent_execution_isolation'}
    for expected, row in zip(COMPONENTS, record['components'], strict=True):
        if (type(row) is not dict
                or set(row) != {'component', 'state', 'reference_kind', 'evidence_sha256', 'evidence'}
                or row['component'] != expected
                or row['state'] != 'verified'
                or row['reference_kind'] not in {'normalized', 'accepted-contract'}
                or not re.fullmatch('[0-9a-f]{64}', row['evidence_sha256'])
                or type(row['evidence']) is not dict):
            raise ValueError('invalid qualified-host candidate component')
        if expected in external:
            if row['reference_kind'] != 'accepted-contract':
                raise ValueError('security contract reference required')
        elif (row['reference_kind'] != 'normalized'
              or _normalized_evidence_reference(row['evidence']) != row['evidence_sha256']):
            raise ValueError('normalized host evidence reference mismatch')
        normalized_rows.append([row['component'], row['state'], row['evidence_sha256']])

    import benchmark_agent_isolation as agent
    import benchmark_grading_backend as grading
    grading_candidate = grading.load_candidate_evidence()
    agent_candidate = agent.load_candidate_evidence()
    refs = {row['component']: row['evidence_sha256'] for row in record['components']}
    if (refs['isolation_backend'] != grading_candidate['evidence_reference']
            or refs['isolation_backend'] not in grading.load_contract()['accepted_evidence_sha256']):
        raise ValueError('grading isolation evidence not accepted')
    if (refs['agent_execution_isolation'] != agent_candidate['evidence_reference']
            or refs['agent_execution_isolation'] not in agent.load_contract()['accepted_evidence_sha256']):
        raise ValueError('agent isolation evidence not accepted')

    receipt = hashlib.sha256(json.dumps(normalized_rows, separators=(',', ':')).encode()).hexdigest()
    if receipt != record['receipt_reference']:
        raise ValueError('qualified-host receipt reference mismatch')
    supplemental = record['supplemental_exact_bwrap_0_13_crosscheck']
    if (type(supplemental) is not dict
            or supplemental.get('used_for_receipt') is not False):
        raise ValueError('invalid supplemental qualification evidence')
    return record


def _receipt_reviewed(reference):
    # Acceptance is tied both to the frozen receipt hash and the exact reviewed
    # candidate evidence file; arbitrary all-verified declarations remain blocked.
    contract = load_contract()
    candidate = load_candidate_evidence()
    return (reference == candidate['receipt_reference']
            and reference in contract['accepted_qualification_receipts'])


def load_evidence(path):
    """Strict non-secret receipt import; never accepts an overall status override."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise ValueError('invalid qualification receipt file')
    data = json.loads(path.read_text())
    if (type(data) is not dict or set(data) != {'contract_id', 'components'}
            or type(data['components']) is not list or len(data['components']) != len(COMPONENTS)):
        raise ValueError('invalid qualification receipt schema')
    components = []
    for row in data['components']:
        if type(row) is not dict or set(row) != {'component', 'state', 'evidence_sha256'}:
            raise ValueError('invalid qualification receipt component')
        components.append(ComponentEvidence(**row))
    return qualify(HostQualificationEvidence(data['contract_id'], tuple(components)))


def current_host():
    # Retained #37/#38 outcome only. Never repeat current-host capability investigation.
    unavailable = {'aggregate_memory', 'aggregate_tasks', 'descendants', 'cleanup'}
    return qualify(HostQualificationEvidence('benchmark-qualified-host-v1', tuple(
        ComponentEvidence(name, 'blocked' if name in unavailable else 'not-verified')
        for name in COMPONENTS)))
