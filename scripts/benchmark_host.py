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


def expected_contract():
    return {'schema_version': 1, 'contract_id': 'benchmark-qualified-host-v1',
            'platform': 'linux-x86_64',
            'required_components': list(COMPONENTS),
            'accepted_states': sorted(STATES),
            'required_state': 'verified',
            'backend': 'bubblewrap-equivalent-reviewed-unprivileged',
            'candidate_backend_version': 'bubblewrap 0.13.0',
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
            'accepted_qualification_receipts': [],
            'authorization_overrides_security': False}


def load_contract(path=CONTRACT):
    c = json.loads(Path(path).read_text())
    if json.dumps(c, sort_keys=True) != json.dumps(expected_contract(), sort_keys=True):
        raise ValueError('unreviewed qualified-host contract')
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


def _receipt_reviewed(reference):
    # Component declarations/hashes alone are not independent verification.
    # The current frozen contract accepts no runtime receipts. Adding one needs
    # separately reviewed probe/control evidence and an explicit contract update.
    return reference in load_contract()['accepted_qualification_receipts']


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
