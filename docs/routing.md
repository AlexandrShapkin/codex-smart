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
radius await a demonstrated downstream contract. This slice does not infer safety
from their absence or implement #10 decisions, #11 reasoning, #12 fallback or #13 Rhai.
