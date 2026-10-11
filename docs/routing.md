# Routing

Reference policy is deterministic Rust. Native tools are the default. Explicit task hints select architecture/impact → CodeGraph, symbol refactoring → Serena, external API → Context7, remote CI → GitHub. A missing capability yields an explicit native fallback and lower confidence, never a false availability claim.

Medium reasoning is the default. Architecture, migration, security and refactoring select High. Repository size alone never selects reasoning. This initial preview does not enable MCP or change Codex profiles. Router v2 with risk composition, validated integration and bounded context remains pending.

## Router v2 task/risk foundation (#9)

`routing::assessment::assess(&RoutingFacts)` is a separate pure core API, not wired
into the preview or CLI. It accepts already collected, bounded structured task hints,
known operations, an optional risk hint and safety facts. It performs no filesystem,
environment, subprocess, network, indexing or configuration access.

TaskKind is Inspect, Edit, Refactor or Unknown. Inspect includes explanation and
read-only debugging/test investigation; Edit includes fixes and test changes.
Refactor preserves structural-change evidence for future policy. Migration and
security describe safety dimensions rather than mutually exclusive task categories.
External API, architecture and GitHub capability intents remain legacy preview hints;
this model does not choose a capability. Rich interpretation belongs to Codex.

RiskLevel has the explicit ordering Low < Medium < High. Known ordinary Inspect/Edit
operations are Low absent other evidence. Refactor imposes a Medium floor. Typed
SecuritySensitive, MigrationSensitive and ConcurrencySensitive facts impose High
for any task, including Inspect. Security includes authentication, authorization,
credentials, cryptography, permissions, sandboxing, untrusted process/input handling
and dependency provenance. Migration includes schema/configuration conversion,
persistent-state transformation and rollback-sensitive mutation. Concurrency includes
threads, async coordination, shared mutable state, locks and race-sensitive or
parallel filesystem mutation. Callers must supply these semantic facts; there is no
keyword classifier, path scanner or implicit fact collector.

Precedence is safety floors, explicit risk, structural/ambiguity floors, then Low
for a known ordinary operation. Explicit High always stays High; explicit Low cannot
suppress a floor. Independent explicit sources must agree with known operations:
multiple distinct known kinds produce Unknown + Ambiguous. No known kind also
produces Unknown + Ambiguous. Unknown entries mean absent evidence and do not
contradict a known hint. A known explicit hint survives missing optional facts.
Configuration-layer precedence must be resolved before supplying independent hints.
Ambiguous assessments have at least Medium risk and signal a need for more evidence;
they do not execute escalation. Clear means task evidence agrees, not verified safety.

Reasons are typed enum codes in a deterministic deduplicated set: ExplicitTask,
KnownOperation, ExplicitRisk, SecuritySensitive, MigrationSensitive,
ConcurrencySensitive, StructuralChange, ConflictingTaskEvidence and
InsufficientTaskEvidence. Equivalent fact order and duplicates cannot change output.
Repository size, cost metadata, language and capability inventory are excluded from
the API. Task and risk remain independent; no reasoning-effort mapping is introduced.

Additional signals such as compatibility boundaries, deployment and unknown impact
radius await a demonstrated downstream contract. The assessment does not infer safety
from their absence or implement capability decisions, reasoning, fallback or Rhai.

## Router v2 capability decision engine (#10)

`routing::engine::decide` accepts the #9 TaskRiskAssessment, structured capability
needs and one normalized immutable CapabilitySurface. No discovery occurs inside
policy. The engine stays separate from legacy preview/config/CLI; `run` remains
passthrough. Decisions do not activate tools or grant execution authority.

Every decision retains native shell/git/search/build/test as its baseline, subject to
host availability. External backends are augmentations. Needs map deterministically:
StructuralImpact → direct CodeGraph, SymbolNavigation → Serena, ExternalApiReference
→ Context7, RemoteRepository → GitHub. A structural need never also selects Serena;
separate explicit needs can select multiple verified backends. Task kind and risk do
not infer capability intent. High risk adds AdditionalSafetyEvidenceRequired without
selecting a backend or reasoning effort.

CapabilityState is a normalized usable-state assertion: Verified, Unknown,
Unavailable or Blocked. Verified means the caller has separately established runtime
compatibility and applicable transport/auth/project/index readiness. It is not an
executable-presence flag. The existing Availability, Compatibility and Readiness
contracts remain unchanged; `CapabilitySurface::from_offline` can never produce
Verified. ReferenceOnly, digest Match and discovered executables still do not attest
runtime readiness. Context7 remains Unknown until separate session integration can
prove usability. There is no production verified-evidence producer in this slice.
Tests use explicit synthetic assertions; future controlled integration owns real ones.

The surface constructor normalizes each backend once. Duplicate equivalent records
collapse; conflicting records choose the most restrictive state, ordered Blocked >
Unavailable > Unknown > Verified for this normalization only. Missing records mean
Unknown. The unsupported CodeGraphWrapper is always Blocked, even if a caller supplies
Verified; it never satisfies a direct CodeGraph need. Native developer tools do not
become external augmentations.

Known unambiguous tasks with a requested Verified backend select that backend only.
Unknown/ambiguous tasks defer even Verified requests. Unknown, Unavailable and Blocked
requests remain unselected with their own typed reason. No alternate backend is guessed,
no retry/probe occurs and no automatic evidence collection follows. Explicit needs
are deduplicated before reading the surface, so repeated needs do not duplicate a
backend. Repository size, cost metadata and language are absent from decision inputs.

RouterDecision preserves the assessment, a sorted set of verified augmentations and
stable DecisionReason codes: NativeBaseline, NoExternalNeed, AmbiguousTask,
AdditionalSafetyEvidenceRequired, VerifiedCapabilitySelected(backend),
CapabilityUnknown(backend), CapabilityUnavailable(backend), CapabilityBlocked(backend)
and CapabilityDeferredForAmbiguity(backend). Rendered explanations contain enum values
only, in deterministic order, including assessment reasons. No paths, credentials,
raw config or tool output enter them.

Validation includes a 64-case pure task/intent/state matrix, offline evidence and
wrapper regressions, normalization/order/duplicate invariants, and five in-memory
stubbed E2E sessions across facts → assessment → decision → full human explanation.
No real network, subprocess, MCP, index or backend launch is used in those sessions.
#11 reasoning, #12 fallback/escalation execution and #13 Rhai remain separate. Router
activation and capability probes are not delivered; the stage remains partial.
