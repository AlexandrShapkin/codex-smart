# Workflow intelligence target

Status: Playbooks 0.4 is implemented and accepted; Adaptive Execution 0.5 is active. #43 bounded execution, #44 replaceable model compatibility routing and #45 bounded delegation policy are implemented; #46 lifecycle measurement remains. #14 measured benchmark and #15 aggregate telemetry are accepted. Router v2 and the single Codex launch remain production behavior. These policy contracts still do not launch adaptive retries, children or model calls.

## Objective and boundaries

Minimize expected total development lifecycle cost subject to required quality,
safety and verification. Quality must never intentionally fall below the required
threshold. Count, where observable, model input, output/reasoning, model class/cost,
context duplication, tool/bootstrap/index preparation, failed attempts, retries,
handoff, validation and latency. Missing measurements remain unknown; token
minimization alone is not the objective. Failed cheap attempts are evidence.

The control plane remains thin and deterministic: typed Rust state, explicit plans,
bounded state machines and observable transitions. Codex performs implementation
reasoning. Another unconstrained LLM planner or generic autonomous multi-agent
framework is not planned. Native Codex capabilities are the baseline; external
capabilities require a concrete workflow need and verified compatibility.

## Execution plane

Task assessment → playbook selector → resource planner → execution controller →
Codex → validator → escalation or completion.

Task/risk assessment precedes workflow selection and context/capability/tool
preparation. The implemented selector consumes only typed assessment plus optional
explicit archetype intent. It does not inspect prompt text, LOC, language or repository
size. Ambiguous assessment and generic edits without sufficient intent remain
`NeedsEvidence`. Contract and high-risk floors can raise, never lower, the planned
profile/reasoning requirements.

The implemented resource planner consumes caller-supplied native/external readiness and
prepared-resource metadata. It emits only declarative reuse/owned-prepare/owned-refresh
or native-fallback dispositions. It performs no discovery or side effect. Unknown native
requirements need evidence; unavailable/blocked required native capability blocks. An
unknown external augmentation is never treated as ready and falls back to native.
The #42 validation recipe maps each workflow-specific validation obligation to a bounded set of native capabilities and reports `Ready`, `NeedsEvidence` or `Blocked`. Optional external readiness and prepared resources never satisfy these native checks. Validation can therefore remain unresolved even when selection/resource planning is ready. Execution of the checks remains future controller work.

The implemented enum-only explain surface exposes workflow, profile, reasoning, context obligations, required native tools, declarative preparation, validation obligations, escalation conditions, cleanup and fallback. It carries no prompt/source text, credentials, arbitrary resource labels, runtime paths or execution authority. Unknown, incompatible or unavailable capabilities never become ready by assumption. Existing read-only explain/doctor side-effect boundaries remain unchanged.

## Playbook semantics

The reviewed Rust contract implements these semantics as bounded enums and versioned built-in archetypes. #41 adds pure selector/resource-plan composition and #42 adds pure validation-recipe planning plus complete explainable preparation. None of these functions executes preparation, validation commands or Codex.

| Field | Meaning |
| --- | --- |
| ID and task archetype | Versioned reusable workflow identity and developer intent |
| Applicability | Explicit task, risk and ambiguity conditions |
| Required/optional capabilities | Verified needs and native-first alternatives |
| Context obligations | Evidence to acquire before an implementation decision |
| Preparation | Bounded deterministic steps and ownership of prepared state |
| Initial execution profile | Capability class and reasoning requirements with risk floors |
| Validation | Independent checks, build/test recipes and quality obligations |
| Escalation | Observable triggers, budgets and stopping conditions |
| Cleanup and fallback | Resource disposal, recovery and safe native behavior |

The v1 built-in set is bounded to eleven archetypes: read-only inspection, focused bug
fix, failing-test repair, feature implementation, API change, refactor,
security-sensitive change, CI/config repair, dependency update, documentation change
and release preparation.
A frequent deterministic workflow should move more known preparation/validation
outside the model and delegate less routine planning to it. Built-in playbooks stay
bounded; benchmark evidence is required before any savings claim.

## Profiles and adaptive execution

Workflow selection is separate from model identity. Economy, standard and strong
are conceptual capability classes, not fixed commercial model names. Replaceable
provider/model resolution must verify compatibility at execution time; risk floors
can forbid lower classes. Benchmark campaigns independently pin concrete models
for reproducibility.

The #43 pure adaptive controller now consumes only a `Ready` workflow plan, a `Ready` validation recipe and a bounded execution budget. It preserves the selected workflow profile/reasoning as a hard floor: economy may advance to standard and then strong/high, but no transition can lower the floor. High-risk/security plans therefore start strong/high rather than trying a cheaper profile first. Runtime failure and timeout are explicit controller triggers; playbook ambiguity/context/capability/validation triggers remain typed and inspectable. Missing evidence enters `NeedsEvidence` rather than being assumed away; unavailable or conflicting safety/validation evidence blocks.

Every started attempt is retained with its profile, reasoning, outcome, validation result and trigger. Completion is impossible until an attempt completes and independent validation passes. Retry and attempt ceilings are explicit (`MAX_ATTEMPTS=4`, `MAX_RETRIES=3`); exhaustion is terminal. The lifecycle budget also carries one bounded delegation slot; #45 consumes that slot through a separate ledger so child work cannot hide outside lifecycle accounting.

#44 separates product capability classes from provider/model identity with a pure replaceable catalog. Provider/model handles are opaque policy IDs; each descriptor independently reports verified/unknown/unsupported/unavailable/blocked availability and Medium/High reasoning compatibility. The resolver accepts only candidates at or above the controller's current profile floor, selects the smallest verified class deterministically, and can use a verified stronger candidate rather than an unknown/unavailable exact-class mapping. It never substitutes a lower class or promotes Unknown to ready. Re-resolving after #43 escalation yields progressive Economy → Standard → Strong/High routing without hardcoding benchmark or commercial model names. Concrete provider/model strings and production argv/runtime application remain a separately verified adapter; current production `run` remains passthrough.

#45 implements only a narrow delegation contract for read-only evidence and mechanical workspace changes. Context and resource scope are opaque bounded handles; child wall time, abstract cost units and output bytes have explicit ceilings; writable scope and declared validation are explicit; nested delegation is forbidden. Unknown safety remains an evidence gate, while high-risk parents plus security, concurrency, destructive migration, ambiguous API or conflicting-evidence hazards are blocked rather than assumed cheap-safe. Completed handoffs carry bounded evidence digests and still require parent review/revalidation; child failure, timeout, refusal and protocol violation remain recorded. The policy layer launches no child and carries no arbitrary source/prompt payload.

#46 now prepares that measurement as a separate benchmark-only adapter around the real
#43/#44 policy rather than duplicating the state machine in Python. Ten representative
scenarios have an explicit typed task/archetype/risk/safety mapping. Two repetitions and
at most two attempts per job bound the adaptive campaign to 20 jobs / 40 Codex executions.
The proposed benchmark profile map is Economy → `gpt-6-luna`, Standard → `gpt-6-sol` and
Strong → `gpt-6-astra`; Standard deliberately retains the accepted baseline workhorse to
reduce mapping confound. Local Codex model metadata advertises the required reasoning
levels, but that metadata is not execution evidence. The distinct three-execution
profile smoke has now passed the accepted production grader for Economy/Medium,
Standard/High and Strong/High. Execution evidence `908a97f1...` binds the exact
trace/submission hashes and is accepted, so the profile mapping is execution-verified.
The offline-tested benchmark runner is merged in #83. The comparative campaign has
not run and still requires separate explicit authorization and reviewed operational
readiness. This is distinct from the unimplemented production routing adapter.

The lifecycle report must measure quality, summed attempt tokens, total lifecycle latency,
escalation count, failed-cheap attempts, strong-model-avoided and handoff count/overhead.
No reviewed price table exists, so estimated cost remains unknown rather than invented.
Failed attempts remain in denominators; quality equivalence is required before any savings
claim. Price alone cannot select a policy that compromises required quality.

Issue #129 adds `validation_policy::evaluate`, a separate pure offline contract
for one typed validation specification. It reuses recipe readiness and
obligations, requires a known unambiguous task and High-risk Strong/High, and
compares the full candidate with separate reviewed and current specifications
(executable path/pin/version, source/config identities, argv, scope/cwd,
operation, budgets and profile/reasoning). Caller-only provenance,
absent/mismatched identities or approvals, stale/future observations and
rollback against the supplied previous clock fail closed. Approval and current
observation have independent validity intervals, each capped at 300 seconds,
with observed_at <= now < expires_at. This is separate from recipe readiness,
executable identity, execution authority and validation success.

The strongest status is `ConditionallyPolicyAdmissible`: it assumes externally
verified provenance and clock inputs, but authenticates none of them. Forging
the provenance enum and copying a specification cannot create attestation.
Every status reports admitted=false, attested=false, runtime_ready=false and
execution_authorized=false. No authorized trust root is established. There is
no trusted ingress, launch conversion or execution adapter;
ordinary run/plan/prepare behavior is unchanged.

The fixed policy permits at most 32 arguments / 4096 aggregate argument bytes
and 1024 bytes per path, with at most 16 ready recipe checks. The explicit
descriptor schema_version must equal SCHEMA_V1 (1); executable version is
separate. All three specifications undergo the same bounded structure
validation before comparison. Invalid approval/current evidence has distinct
typed reasons from valid but mismatched specifications. Arguments have
restrictive ASCII word, long-flag or relative path roles; absolute executable,
scope and cwd paths reject dot components, repeated separators and platform
ambiguity. Cwd containment is lexical and component-bounded. Budgets require
positive wall time (at most 60 seconds), CPU time (at most wall time),
input/output (each at most 1 MiB), memory (at most 512 MiB) and processes (at
most 8). These are policy ceilings, not installed resource controls. Exact
review must establish tool-specific argument semantics: lexical safety cannot
prove a flag harmless or stop an approved tool interpreting words as code.
Filesystem identity, symlinks, mounts, runtime version, isolation, clock
integrity and replay history are not inspected. Sensitive input types omit
Debug and results contain only fixed enums; no argv/path/source/prompt payload
is returned.

Issue #133 adds the explicitly invoked typed inspection interface
`WorkflowPlan::inspect_validation` in `validation_inspection`. It derives the
existing workflow validation recipe from the separately supplied native surface,
retains the selected workflow risk floor, and calls `validation_policy::evaluate`
once when a recipe and current assumptions are available. No recipe or no current
assumptions yields an enum-only missing-evidence finding. Policy refusals retain
the original reason; missing approval, unverified evidence and an unready recipe
map to NeedsEvidence, other policy refusals to Blocked. The strongest structural
finding still maps to NeedsEvidence and provenance Unknown. There is no operational
Ready state, candidate payload in the result, or execution authority.

The candidate descriptor, optional separate Approval and optional
CurrentAssumptions (current specification, provenance and identity/time interval)
are separate typed arguments. The API authenticates none of them. ExternallyVerifiedAssumption
remains a hypothetical pure-policy input, even when a caller copies all three
specifications. Revocation/unverifiable approval must be represented by withholding
approval or supplying CallerDeclared evidence; no revocation provider is implemented.
Clock continuity and current identities are supplied assumptions, not host observations.
Missing prerequisites cannot be repaired by copying a receipt or asserting provenance.

This is the narrow core inspection path only: no new CLI descriptor ingestion,
flags, file parser, worker protocol or preparation subprocess join is introduced.
CLI declarations cannot establish independent approval with the accepted infrastructure.
Explicit callers can exercise positive structural fixtures with separately supplied
synthetic evidence, never runtime readiness. Existing #100 CLI and normal passthrough
remain unchanged. The fixed enum result carries no paths, argv, source, worker payload,
stderr or secrets, and no launch conversion. Policy input bounds are reused rather
than replaced; no filesystem, host clock, shell, network or model is consulted.
ADR-0010/0011 trust roots, authentication, authoritative current identity/time,
revocation and protected state remain unimplemented; Adaptive remains **NO-GO**.

## Offline qualification of independent validation approval ingress (#135)

This is a documentation-only proposal for [#135](https://github.com/AlexandrShapkin/codex-smart/issues/135),
qualified against source base `4f05706cc4a4b59c8e3d8da72e9e641a1da3f0e0`.
It extends the #129/#133 inspection question without implementing an ingress.
[ADR 0008](decisions/0008-deterministic-workflows.md) owns workflow/risk semantics;
[ADR 0010](decisions/0010-native-inspection-trust-boundary.md) and
[ADR 0011](decisions/0011-operator-reviewer-authority.md) own independent trust and
bootstrap obligations. Their broader contracts remain applicable. This section
specifies validation-specific offline qualification, not enrollment or runtime authority.

**Current pure assumptions versus proposed authentication.**
`validation_policy::evaluate` accepts caller-controlled candidate, Approval,
current Specification, provenance and time. `ExternallyVerifiedAssumption` is an
assertion that a caller can forge. Copying the candidate into approval/current can
produce `ConditionallyPolicyAdmissible`, never attestation, readiness or authority.
`WorkflowPlan::inspect_validation` retains the workflow risk floor, returns
NeedsEvidence even for that positive finding, and always reports provenance Unknown.
Neither module authenticates a reviewer, observes a host, parses an envelope,
checks revocation or consumes replay state. The future boundary below would have
to authenticate separate evidence before supplying assumptions to these pure APIs;
no new API or conversion is delivered here.

Treat candidate, approval transport and alleged current data as attacker-controlled,
along with repository files, source receipts, config, PATH, embedded keys/digests,
reviewer names and self-declared provenance. An attacker may copy, substitute,
replay or restore these bytes. The operator administers independently authorized
policy and updates; the reviewer independently decides on the exact validation
scope; the root anchors operator/reviewer authority outside candidate control;
the verifier strictly interprets policy and compares independently observed current
identities. Delivery authenticates sender/bytes but does not confer reviewer
permission. These roles require distinct evidence even if a future authorized
policy permits one person to hold multiple roles. No actual operator, reviewer,
root or authenticated provisioning channel is established by this document.

**Exact reviewed coverage.** Approval must bind the complete Specification, not
just a command name or candidate digest. Equality includes schema_version (currently
SCHEMA_V1=1), executable absolute path, executable_pin, executable Version,
source_identity, configuration_identity, ordered argv including each Word/Flag/Path
tag and exact bytes, absolute scope and cwd, operation/ValidationObligation, all
six budgets (wall_seconds, cpu_seconds, input_bytes, output_bytes, memory_bytes,
processes), profile and reasoning. Unknown/ambiguous task facts cannot be repaired
by approval. Effective risk is at least the selected workflow risk; **High requires
Strong/High**. The ready recipe and its exact checks/obligations must also be bound
to the reviewed policy context, with the requested operation present.

Current verified source-code ceilings remain 32 arguments, 4096 aggregate argument
bytes, 1024 bytes per path, 16 ready recipe checks, positive wall time <=60 seconds,
positive CPU time <=wall time, input and output each <=1 MiB, memory <=512 MiB and
processes <=8. These are structural policy limits, not enforced runtime controls.
Word is a nonempty restrictive ASCII atom without a leading dash; Flag is a
restrictive long flag; Path is relative and excludes dot components, empty segments,
leading-dash components and platform ambiguity. Executable/scope/cwd use restrictive
absolute paths; cwd containment is lexical and component-bounded. Independent review
must additionally establish tool-specific argument semantics: option/value pairing,
ordering, subcommands, path operands, implicit config loading, scripts/plugins and
code-interpreting flags. A lexically valid word or flag can still request unsafe work.
Symlinks, mounts and dependency loading require actual identity/scope evidence;
lexical containment cannot establish filesystem confinement.

Independently held current evidence must cover repository identity and relevant
source bytes including dirty/untracked inputs, effective configuration with defaults,
precedence, overrides and relevant environment, the actual selected executable/tool
artifact, runtime version and interpreter/dependency closure, and the actual running
verifier artifact plus policy/schema identity. A declared path, version, HEAD or
copied source snapshot receipt is insufficient. The current Specification has no
separate verifier field: the proposed ingress must bind and compare reviewed versus
actual current verifier independently before the pure call. Exact identity byte
coverage and bounded acquisition remain approval prerequisites, not implemented hashes.

**Proposed strict v1 envelope and independent delivery.** One canonical record would
bind a validation-specific domain and envelope version 1; the complete Specification
and its canonical digest; recipe/task/effective-risk context; root, operator and
reviewer identities; explicit Approve decision; repository/capability/scope;
reviewed source/config/selected-tool/verifier identities; policy/schema identity;
policy epoch and revocation epoch; unique observation, session and use IDs; clock
domain, observed_at and expires_at; and the independently authenticated proof.
The proof authenticates every field except its own proof bytes, with that exclusion
fixed by the future format. This is a separate validation envelope, not a change
to native-inspection receipt v1. No concrete encoding or cryptographic algorithm is
selected. Future format review must fix canonical bytes before implementation.
Require fixed digest widths, bounded nonrecursive fields, exact integer forms,
no duplicates, unknown fields, alternate/noncanonical encodings or trailing payload;
reject oversize before decoding. Proposed envelope maximum is **16 KiB**, and
combined envelope/proof/policy input maximum is **64 KiB**; these are new proposal
bounds, distinct from the implemented Specification limits above.

Exactly two delivery options remain open: (A) an independently anchored allowlist of
exact reviewed-envelope digests plus authenticated reviewer authorization metadata,
or (B) an independently enrolled verification key and signed canonical envelope.
A candidate-supplied digest/key cannot anchor either. Both require independently
provisioned operator/root policy, reviewer identity and delegation covering this
repository, capability, complete scope, decision and epoch. A correct digest or
signature with a Deny decision, unauthorized reviewer or revoked authority rejects.
Policy updates/rotation require the existing independent update authority; transport
through untrusted files is permissible only after that anchor exists. No algorithm,
key, credential, store, enrollment or channel is created or selected here.

**Deterministic proposed result and precedence.** Conceptual inputs are bounded
untrusted bytes plus separate protected authority/policy, trusted clock, protected
persistent state, held current identity snapshot and atomic consume outcome.
Protected handles are conceptual, not existing Rust APIs or proof of host protection;
future private constructors must be backed by independently qualified host evidence.
Results carry fixed enum reasons only:

```text
AcceptedForInspectionOnly
Rejected(reason)  // established violation
Unknown(reason)   // absent, uncertain or unobservable prerequisite
```

Fixed first-failure order is (1) size, strict parse, supported envelope/Specification
schema and policy structure; (2) prerequisite availability in authority, clock,
protected-state, current-identity, transaction order; (3) known violations in root,
reviewer, decision, revocation, authorization scope, proof, rollback, clock-domain
mismatch, interval, replay, identity, generation, argument semantics, task/risk,
recipe, structural policy order; (4) pure policy consistency, then successful
atomic consume of the same held evidence generation.
Within each group use the written field order above (Specification budgets in their
listed order); never input/map iteration order. Missing evidence at step 2 takes
precedence over later known failures; malformed bytes at step 1 still reject first.
Conflicting authenticated records for one observation reject Conflict at policy
structure checking; do not choose the more permissive record. A transaction of
uncertain outcome is Unknown(UncertainConsume), not a retryable fresh grant.
This proposed ordering does not alter the existing evaluator's refusal order or
#133 mapping. Unknown != ready. Even AcceptedForInspectionOnly grants no
NativeSurface::Verified, health, semantic sufficiency, validation success,
production admission or execution rights. **NO runtime execution**, tool probes,
model calls, subprocesses or launch argv conversion are part of qualification.

A trusted clock in the authenticated domain must establish positive observation
and `0 < expires_at - observed_at <= 300`, with `observed_at <= now < expires_at`
for approval and independent current observation separately. The effective deadline
is the earliest envelope, current-evidence or policy-lease expiry; no grace period.
An absent/unverifiable clock or continuity is Unknown(MissingClock); a proven
mismatch with the authenticated clock domain is Rejected(ClockDomainMismatch).
Protected state must retain last-seen
time, monotone policy/revocation epochs, root/reviewer changes and observation/session/
use consumption. Known backward time or restored epochs/ledger reject Rollback;
missing continuity is Unknown(MissingProtectedState). Offline revocation requires
an independently refreshed short policy lease: unseen revocations cannot be inferred.

Pure structural checks run before any consumption; a refused pure policy never
consumes an approval. Atomic compare-and-consume must bind one observation to one
session/use and compare all generations before releasing inspection evidence. A double use, including the
same ID, rejects Replay; parallel submissions release at most one result. Restart
requires durable protected continuity; failed/uncertain consumption cannot mint a
new use without protected reconciliation. Hold stable bounded snapshots through
assessment and consumption, recheck identities/generations at use, and invalidate
on source/config/tool/verifier drift, expiry, rotation or revocation. A known race
rejects GenerationChanged; inability to exclude TOCTOU is Unknown(UnstableSnapshot).
No pathname re-open or stale inspection result may become a reusable bearer grant.

**Reproducible synthetic offline qualification matrix (proposed, unimplemented).**
Start every row independently with finite fake policy root A/operator O/reviewer R,
epochs 7/3, session S/use U/observation X, all nonzero fixed identity bytes, matching
separate Specifications, ready recipe, unambiguous task, Strong/High, observations
100, expiries 400 and trusted fake now 150. Supply known held snapshots and successful
atomic transaction. Model A with a separate fake allowlist; model B with injected
proof-verification outcomes, never real keys. Mutate only the listed input unless
specified. All rows assert zero execution and bounded enum-only diagnostics. These
methods specify future tests; they are not claims of implemented authentication.

| Scenario | Reproducible finite mutation / expected proposed result |
| --- | --- |
| Forged self-provenance | Copy candidate into approval/current and set every provenance enum; omit independent authority: Unknown(MissingAuthority). |
| Project-selected anchor | Put a matching digest or replacement key only in fake project config: Unknown(MissingAuthority). |
| Wrong root | Replace envelope A with B against protected A: Rejected(RootMismatch). |
| Wrong reviewer | Replace R with undelegated Q: Rejected(ReviewerUnauthorized). |
| Non-approval decision | Authenticate Deny instead of Approve: Rejected(Decision). |
| Revocation / scope | Revoke R at epoch 3, then separately change repository/capability/scope outside delegation: Rejected(Revoked), then Rejected(ScopeMismatch). |
| Forged delivery | Flip an envelope identity byte without changing independent A entry or B proof: Rejected(ProofMismatch). |
| Conflicting approvals | Supply Approve and Deny for X in one fake policy snapshot: Rejected(Conflict); no last-writer choice. |
| Every descriptor dimension | Table-loop executable, pin, Version, source, config, argv tag/bytes/order, scope, cwd, operation, each of six budgets, profile and reasoning; change reviewed or current copy separately within valid limits: Rejected(IdentityMismatch). Schema 0/2 separately: Rejected(UnsupportedSchema). |
| Lexical paths/argv | Inject traversal, absolute Path operand, repeated separator, leading-dash path component, shell punctuation or short/ambiguous flag: Rejected(StructuralPolicy). |
| Semantic argv/scope | Keep lexical atoms valid but inject a fake tool grammar's code-interpreting flag, wrong option pairing or out-of-scope resolved symlink: Rejected(ArgumentSemantics). Remove semantic evidence instead: Unknown(MissingCurrentIdentity). |
| Resource bounds | Independently try 33 args, 4097 arg bytes, 1025 path bytes, 17 checks, wall 61, CPU above wall, either I/O 1 MiB+1, memory 512 MiB+1, processes 9 or zero budgets: Rejected(StructuralPolicy). |
| Missing current / verifier | Remove held current snapshot, then only actual verifier identity: Unknown(MissingCurrentIdentity) in each case; matching candidate declarations do not repair it. |
| Identity drift | Change actual selected executable, dependency, effective config or running verifier separately: Rejected(IdentityMismatch). |
| Altered source snapshot | Retain HEAD/receipt but flip a source byte or add relevant dirty/untracked input in fake held snapshot: Rejected(IdentityMismatch). |
| Untrusted clock | Remove clock authority or make continuity uncertain: Unknown(MissingClock). Supply authenticated domain A but proven current domain B: Rejected(ClockDomainMismatch). |
| Future / expired intervals | Set observed=151, then now=400, then expiry=401 with observed=100; test approval/current independently: Rejected(InvalidInterval). |
| Rollback | Restore last time 151 or epochs 6/2 or an old consumed ledger against protected watermark: Rejected(Rollback). |
| Double / cross-session replay | Consume X/S/U, repeat it, then submit X under S2/U2: Rejected(Replay) for both later requests. |
| Parallel replay | Interleave two fake compare-and-consume calls at a barrier for X: exactly one AcceptedForInspectionOnly and one Rejected(Replay). |
| Restart / uncertain consume | Drop durable continuity after fake restart: Unknown(MissingProtectedState); inject indeterminate commit outcome: Unknown(UncertainConsume), with no fresh retry grant. |
| Strict parser | Independently duplicate a field, append bytes, use alternate number/digest encoding or unknown field: Rejected(Malformed). Unsupported domain/version: Rejected(UnsupportedSchema). |
| Envelope/policy size | Feed 16385 envelope bytes or 65537 combined bytes: Rejected(Oversize) before decode, even with absent authority. |
| TOCTOU | Hook a generation change between snapshot and consume: Rejected(GenerationChanged); remove ability to hold snapshot: Unknown(UnstableSnapshot). |
| Risk floor / task / recipe | Retain High workflow risk but supply low caller risk and Economy or Medium: Rejected(RiskFloor); ambiguous task: Rejected(UnclearTask); unready/missing required check: Rejected(Recipe). |
| Leakage | Place unique synthetic private markers in argv/path/source and malformed payload; force parse refusal: Rejected(Malformed), rendering contains no marker, payload, proof or secret. |
| Precedence / false positive | Combine oversize with absent authority: Rejected(Oversize); absent authority plus wrong reviewer: Unknown(MissingAuthority). A copied valid-looking descriptor alone must never be AcceptedForInspectionOnly. |
| Positive control | Supply all separate fake anchors/current/time/state and one successful consume: AcceptedForInspectionOnly once, no readiness/authority; next identical call Rejected(Replay). |

Existing `crates/codex-smart-core/tests/validation_policy.rs` cover
pure structural equality, bounds, interval arithmetic, task/risk/recipe refusals and
non-authoritative positive status. Existing `crates/codex-smart-core/tests/validation_inspection.rs`
cover #133 mapping, missing assumptions, workflow risk retention and private-input
non-disclosure. Their fake provenance/time and verified native surface do not test
authenticated ingress. Withholding a revoked approval in a pure test is not a
revocation implementation. The entire ingress matrix above remains unimplemented
and unexecuted by this documentation task.

**Unknown prerequisites and decision.** Actual operator/reviewer identities and
delegation, independent root/channel provisioning, protected store ancestry/ownership/
ACL/mount guarantees, signing custody/verification if chosen, exact canonical format,
identity coverage/acquisition budgets, trusted time/domain/continuity, durable
anti-rollback state, atomic replay protection, crash recovery, revocation freshness
and race-safe snapshots are unqualified. Operator-equivalent attackers or compromised
kernel/verifier can defeat same-host protection; excluding them is an unqualified
host assumption. Synthetic tests cannot establish these properties.
As in **#119/#121, NO-GO for actual enrollment, host ingress, production admission
or runtime integration** until independent authority/security and host evidence
qualify all prerequisites. Architecture/security own format and authority review;
operator owns protected host evidence; engineering under #94 owns any separately
authorized implementation; #94/#95 retain runtime/measurement acceptance. Adaptive
remains active. This proposal adds no source/tests/config/runtime/benchmark/model
execution, credentials, CLI or governance authority, and authorizes no enrollment.

## Reusable preparation and automation

Recurring workflows may reuse repository facts, verified toolchain availability
and executable pins, dependency metadata, selected indexes, local caches, known
validation commands and explicit workflow profiles. Prepare only what the selected
workflow requires. The #41 planner now preserves typed identity/version, scope, owner,
validity, invalidation, privacy and cleanup in every reusable resource plan. Its minimum
invalidation set covers repository identity, relevant HEAD/config, capability version,
playbook schema and explicit reset. Duplicate, incomplete, unknown or mismatched metadata
never becomes reusable state. Only Codex-Smart-owned absent/stale resources can receive
a declarative prepare/refresh disposition; other ownership falls back without mutation.
Inspect/reset execution remains later work; stale state cannot silently remain ready.

Versioned repository profiles support recurring dependency updates, generated-client
refreshes, CI repair, regression tests, release preparation and issue → implementation
→ validation → PR workflows. Deterministic shell steps handle known routine work;
the LLM handles only reasoning-dependent parts. OS argument and trust boundaries
remain applicable; profiles must not turn untrusted configuration into shell code.

Explicit user-defined profiles must always be possible. Any automatic promotion
must be local, explainable, versioned, reversible, privacy-reviewed and evidence-gated.
No opaque learning from user source, global arbitrary source/prompt caching,
daemon or background agent is planned. Preparation never silently installs
software, mutates authentication or changes global configuration.

## Lifecycle plane

Installer, updater, migration, rollback, release metadata, compatibility verification
and doctor form a separate lifecycle plane. It does not participate in task/model
routing. See [distribution](distribution.md) for its future transactional contract.

## Measurement and privacy

#14 remains the measurement foundation. Future comparisons may add playbook-enabled
and adaptive codex-smart to vanilla and static/native codex-smart only after genuine
implementations exist. No variants or results are fabricated. The historical 42-job
plan remains unchanged and unexecuted; the representative 40-primary-execution campaign
produced accepted baseline `ffd8fbbc...` through the reviewed split-host boundary. No
savings or winner claim exists.

#15 is accepted. Its benchmark-local aggregate boundary consumes only normalized
records and requires explicit invocation; scenario detail is separately opted in and
there is no network export. Future workflow/profile aggregates may add
escalation yes/no, validation pass/fail, retry counts and bounded token/cost/latency
counters under the same privacy boundary. Adaptive routing must function when telemetry
collection is disabled. Neither optimization nor telemetry requires source, prompts, credentials or arbitrary
tool payload storage. Privacy review precedes any new collection contract.
