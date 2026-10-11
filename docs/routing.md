# Routing

Reference policy is deterministic Rust. Native tools are the default. Explicit task hints select architecture/impact → CodeGraph, symbol refactoring → Serena, external API → Context7, remote CI → GitHub. A missing capability yields an explicit native fallback and lower confidence, never a false availability claim.

Medium reasoning is the default. Architecture, migration, security and refactoring select High. Repository size alone never selects reasoning. This initial preview does not enable MCP or change Codex profiles. Router v2 pure policy composition is validated; production launch integration remains deferred.

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
#12 fallback/escalation execution and #13 Rhai remain separate. Reasoning composition
is documented below; Router activation and capability probes are not delivered.

## Router v2 reasoning-effort selection (#11)

`routing::reasoning::select_reasoning` consumes the authoritative #9 assessment
(including when preserved in #10 RouterDecision), a resolved explicit override and
normalized ReasoningCompatibility. It does not recompute risk or capability selection.
The existing Reasoning enum is reused: project policy is only Medium/High.

Clear Low/Medium risk defaults to Medium. High risk or typed Ambiguous evidence selects
High from Policy; no hazard-category inference or DecisionReason reclassification is
added. Refactor's Medium floor alone keeps Medium in Router v2, unlike the unchanged
legacy preview's task-based High. Explicit Medium/High wins over automatic risk and
ambiguity, with Explicit origin. Candidate selection precedes compatibility validation;
Unknown/Unsupported never silently downgrade or substitute an override. Other
codex-smart effort strings remain rejected by the existing parser.

ReasoningCompatibility independently records normalized CLI-contract and effective
model Medium/High support as Supported/Unsupported/Unknown. CLI Supported asserts
that the reviewed Codex 0.160 config argv contract applies to the target; it cannot
be inferred from a declaration, reference contract or checksum. Per-effort model
support is independent; a CLI accepting a value does not prove the model supports it.
Unsupported in either dimension yields Unsupported; otherwise any Unknown yields
Unknown. Both dimensions must be Supported for an accepted effort. There is no
production verified compatibility producer, model catalog, live probe or API call.

ReasoningDecision exposes candidate, origin (Explicit/Policy/Default), typed
compatibility and stable reasons: ExplicitOverride, HighRisk, Ambiguity, MediumDefault,
CompatibilitySupported/Unknown/Unsupported. `accepted()` returns an effort only when
supported. Rendered explanations contain enum values only, with deterministic ordering.
Repository size, language, cost and workspace statistics are absent from the API.

Configuration resolution remains built-in < user < project < CLI. Callers pass the
already resolved reasoning only when its origin is explicit (User/Project/Cli);
BuiltIn origin passes None so the new risk policy can select automatically. Neither
config discovery nor precedence resolution occurs inside this policy. Config/preview
and production `run` remain unchanged.

`routing::reasoning_args::plan_reasoning_args` is a separate pure fake-launch adapter,
not production injection. It accepts at most 256 input OS args and 16 KiB of argument
bytes, without filesystem/environment/network/subprocess access. It supports reviewed
interactive/exec (including `e`) option prefixes using config/model/profile options;
payload begins after `--`. Plain positional prompts, other commands and unknown
option grammar defer as UnsupportedInvocation rather than guess flag/value boundaries.
This bounded subset is a known limit, not a claim to parse all Codex argv.

When the candidate is compatible and no user reasoning or target override exists,
the plan prepends exactly two OS args: `--config` and
`model_reasoning_effort="medium"` or `model_reasoning_effort="high"`. Original bytes
and order remain unchanged. Existing relevant --config/-c forms (separate, equals,
or attached short form) prevent a synthetic override. Quoted TOML and simple raw
string values are recognized; malformed/non-string/ambiguous values prevent injection.
Equivalent repeats preserve user argv; conflicting values produce ConflictingUserOverrides
without a hidden last-wins choice. Config key aliases are not invented.

A forwarded user Medium/High is checked against the retained compatibility snapshot;
a different valid string remains user-owned with Unknown support, outside project
policy vocabulary. Unsupported user effort is reported as typed Unsupported without
substitution or injection. These plans describe/reject synthetic application, not a
change to existing passthrough execution. An explicit --model/-m, --profile/-p or known
model/provider/catalog/profile config override invalidates effective-target evidence:
no injection, and any user reasoning support becomes Unknown. No profiles/config stores
are read. Unrelated config args and all payload bytes remain intact, including non-UTF8
and shell metacharacters. Planning summaries/Debug omit arbitrary argument values.

Validation covers policy/override and independent CLI/model compatibility matrices,
refactor/size independence, stable reasons/rendering, and in-memory fake argv capture
through facts → assessment → Router decision → reasoning → argv plan. No automatic
fallback (#12), Rhai (#13) or production Router activation is included. See
[version/model source evidence](tool-compatibility.md#reasoning-argv-reference-evidence).

## Router v2 fallback and bounded evidence plan (#12)

`routing::fallback::plan_fallback` consumes #10 RouterDecision (including the #9
assessment), #11 ReasoningDecision and caller-collected PlanEvidence. It returns a
finite typed RoutingPlan; it does not execute fallback or escalation. There is no
capability snapshot lookup, reasoning reselection, retry, file/command planning,
network, tool activation, index creation or second agent. Production run remains
passthrough. Codex chooses how to satisfy the plan's obligations in its one session.

Modes have monotonic precedence: Proceed < ProceedWithFallback < NeedsEvidence <
Blocked. Proceed permits the selected route subject to its retained obligations; it
never certifies tests already completed. ProceedWithFallback offers native targeted
repository/source evidence in place of a degraded augmentation. NeedsEvidence requires
additional prerequisite evidence before proceeding. Blocked means a known prerequisite
cannot be satisfied under the current contract, or required reasoning is incompatible.
No alternative heavy backend is guessed. A blocked augmentation alone does not block
the whole task if a native path and required evidence remain sufficient.

Every Edit/Refactor retains RelevantTests and BuildOrStaticValidation. RelevantTests
includes applicable behavior/regression checks, without prescribing commands or an
entire test suite. Refactor and every StructuralImpact request retain ImpactAnalysis.
Unknown/ambiguous tasks conservatively retain all three until clarified, preventing
ambiguity from erasing verification. Symbol requests retain SymbolReferences (adequate
symbol, caller and reference evidence), even when Serena is unavailable. Need obligations
come from #10's normalized decision reasons, including unselected requests; the engine
is not run twice and existing degraded reasons are preserved verbatim as typed codes.

High risk retains AdditionalVerification: substantiate correctness beyond the ordinary
checks in proportion to the known risk. Authoritative #9 SecuritySensitive,
MigrationSensitive and ConcurrencySensitive reasons add SecurityReview,
MigrationRollbackValidation (rollback/idempotency/transaction evidence where applicable)
and ConcurrencyReview (race/locking/shared-state evidence). No hazard inference or
migration/concurrency mechanism is introduced here. Tests and impact analysis survive
all fallback/escalation modes.

PlanEvidence separates capability readiness from prerequisite evidence. Satisfied is
a trusted caller assertion, Unknown requires more evidence and Unavailable blocks the
current contract. Native fallback feasibility is explicit; absent proof yields
NeedsEvidence, known impossibility yields Blocked. An unavailable/unknown/blocked/
ambiguity-deferred direct backend can use a feasible native path without selecting
another backend. The legacy CodeGraphWrapper remains unsupported and never becomes
a rescue path; malformed router input purporting to use it is blocked.

External API needs retain ExternalReferenceValidation and require authoritative
reference evidence (for example already present local official docs). Current remote
needs retain RemoteStateValidation and require an adequate remote-state snapshot;
local history alone cannot replace current remote issue/PR/CI evidence. The caller
explicitly chooses LocalHistory or CurrentRemoteState for repository intent. LocalHistory
retains LocalRepositoryEvidence and may use native git/source evidence. Even a Verified
Context7/GitHub backend does not certify the required evidence was obtained. Missing
reference/remote prerequisites produce NeedsEvidence; known inability produces Blocked.
No authoritative facts are invented and no fetch/auth/probe is executed.

Explicit verification entries are prerequisite gates as well as retained obligations:
Unknown yields NeedsEvidence and Unavailable yields Blocked. Satisfied duplicates cannot
cancel failures; equivalent entry ordering/duplicates leave the plan unchanged. Empty
entries do not assert verification completed; ordinary edit plans keep verification as
mandatory session work. Context insufficiency yields NeedsEvidence without dropping
any obligation; context budgets never waive evidence. Repository size/cost metadata
are absent from the API.

ReasoningApplication distinguishes advisory Passthrough, RequiredSyntheticOverride and
UserOwned compatibility. Required synthetic Unknown yields NeedsEvidence; Unsupported
blocks, with ReasoningCompatibilityValidation retained and no effort substitution.
UserOwned uses the user's own normalized support status, not automatic candidate support,
and never rewrites argv; Unknown/Unsupported likewise require evidence/block. Passthrough
reports advisory compatibility degradation without gating on an unapplied candidate.
This does not activate #11's fake argv planner or expand its supported grammar.

RoutingPlan contains mode, native-fallback offer, a deterministic ordered obligation
set, stable reasons (including reused #10 reasons) and relevant reasoning support.
Render includes escalation status and omits paths, prompts, config, argv values,
credentials and tool output. A fallback offer can coexist with NeedsEvidence/Blocked;
mode determines whether proceeding is permitted. MoreEvidenceRequired marks unresolved
prerequisites, including blocked current contracts, without initiating any execution.

Validation includes pure prerequisite precedence tests and in-memory failure/degraded
sessions across #9 → #10 → #11 → #12 → explanation; invariant loops cover capability
and risk degradation, ambiguity, additional needs, prerequisite failures, ordering,
duplicates, external size metadata and context insufficiency. #13 is satisfied by the accepted [ADR-0004](decisions/0004-rhai-deferred.md):
Router v2 remains Rust-only and its policy composition is validated. No production
Verified producer, probes, automatic evidence execution or production Router
activation is delivered. Independent benchmark evidence is next; Rhai is deferred
pending demonstrated need and is not a benchmark variant.
