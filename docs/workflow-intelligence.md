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

## Canonical validation approval envelope v1 — offline byte contract (#137)

This section narrows the **proposed** #135 approval-ingress boundary to a single
byte representation; it does not change the existing Rust
`validation_policy::Specification`, `Approval`, `CurrentAssumptions` or
`WorkflowPlan::inspect_validation` interfaces. It specifies neither a
production decoder nor an approved signing algorithm. Its fixture's proof suite
is deliberately unauthenticated. Native inspection receipt v1 is a separate
domain and format. #94 stays open; Adaptive 0.5 stays ACTIVE / production NO-GO.

### Bytes, framing and limits

All byte strings below are binary, not hex strings or JSON. Concatenation
`||` is exact byte concatenation. No whitespace, BOM, newline, base64,
percent-encoding, compression, Unicode normalization, implicit defaults or
alternate serialization is accepted. Define:

- `D = ASCII("codex-smart/validation-approval-envelope/v1") || 00`.
  The `00` is **one NUL byte**. Header `H = D || BE16(1)`; `BE16`,
  `BE32` and `BE64` are fixed-width unsigned **big-endian** integers,
  with no sign, varint, padding or textual spelling. Even though D contains
  "v1", the two version bytes are mandatory and must be exactly `00 01`.
- `TLV(tag, value) = U8(tag) || BE16(byte_length(value)) || value`.
  Exactly one field for each of the 26 **hexadecimal** tags `01` through `1a`, in *strictly increasing*
  tag order. No container field count, optional fields or extensions.
- `S` is the exact nested Specification representation below.
  `P = H || TLV(01,v01) || ... || TLV(19,v19)` is the **body preimage**.
  `E = P || TLV(1a,proof_bytes)` is the **entire envelope**.
  All TLV tags in this contract use hexadecimal notation. Tag `1a` is mandatory even when its proof is empty.
- `spec_digest = SHA256(ASCII("codex-smart/validation-specification/v1") || 00 || S)`.
  `body_digest = SHA256(ASCII("codex-smart/validation-approval-body/v1") || 00 || P)`.
  `wire_digest = SHA256(ASCII("codex-smart/validation-approval-wire/v1") || 00 || E)`.
  Every digest is 32 raw bytes. All three domain separators and the exact
  prefix inclusion are normative; there is no double hashing or hex-decoding
  step. Body digest **excludes the entire field `1a` tag, length and value**,
  but includes the context digest in field `18` and proof-suite selector in `19`. Wire digest
  includes the entire proof field. Neither digest authenticates origin.
- Maximum `len(E) = 16,384` bytes inclusive; maximum
  `len(E) + len(external_proof_input) + len(independent_policy_input)
  = 65,536` bytes inclusive. These totals count all supplied bytes;
  never count a separately supplied proof twice. For this v1 layout proof
  field `1a` is *inside* E; any independently transported additional proof is
  separate input and does not alter E or its body digest. Bound each
  individual input before concatenation/allocation, use checked addition,
  and reject oversize **before** parsing or consulting authority. Field `1a`
  is at most 4,096 bytes, including for future suites. Current suite 0
  requires zero proof bytes. A future nonzero suite and external proof framing
  require separate technical/security approval, not parser permissiveness.

The only strings permitted are nonempty ASCII bytes `21..7e` (printable
non-space; no NUL). A string is **not** case-folded, trimmed, decoded as a
filesystem path or normalized; equal identifiers mean identical bytes.
Top-level string values use their TLV length, while nested strings use
`BE16(length) || bytes`. Repository identity has the additional lexical form
`[a-z0-9_.-]{1,64}/[a-z0-9_.-]{1,64}`, and policy ID is
`[a-z0-9_.-]{1,64}`. Those bytes are labels to bind to an independently
verified repository/policy, not self-authenticating authority. Absolute
scope/executable/cwd paths and argv obey the *existing* pure validation
policy's separate lexical and semantic gates; representation validity alone
does not establish safe argv, scope or identity.

### Required ordered envelope fields

Every tag is mandatory. Raw identity values must have the stated length,
without textual names, inferred defaults or all-zero substitutions. All
identities, epochs, timestamps and decisions remain attacker-controlled
assertions until independently authenticated and compared to protected state.

| Tag | Value type | Meaning |
| --- | --- | --- |
| `01` | U8: 1=ApproveForInspectionOnly, 2=Deny | Reviewed decision; Deny never admits |
| `02` | ASCII repo label, at most 129 bytes | Reviewed repository identity |
| `03` | U8=1 | Capability: validation inspection only |
| `04` | ASCII absolute scope, at most 1,024 bytes | Approved scope; byte-equal to S.scope |
| `05` | ASCII policy ID, at most 64 bytes | Independently provisioned policy identity |
| `06` | BE64 | Policy epoch, strictly positive |
| `07` | 32 raw bytes | Root identifier |
| `08` | 32 raw bytes | Operator identifier |
| `09` | 32 raw bytes | Reviewer identifier |
| `0a` | BE64 | Reviewer delegation epoch, strictly positive |
| `0b` | BE64 | Revocation generation; zero allowed |
| `0c` | 16 raw bytes | Unique observation ID |
| `0d` | 16 raw bytes | Session ID |
| `0e` | 16 raw bytes | One-use ID |
| `0f` | 16 raw bytes | Clock-domain ID |
| `10` | BE64 | Observed-at time in authenticated clock domain |
| `11` | BE64 | Expires-at time in the same domain |
| `12` | S (defined below) | **Full** reviewed Specification, not only its digest |
| `13` | 32 raw bytes | Asserted independently current **full** Specification digest (`spec_digest` algorithm) |
| `14` | 32 raw bytes | Asserted current source identity |
| `15` | 32 raw bytes | Asserted current effective-configuration identity |
| `16` | 32 raw bytes | Asserted current selected tool and dependency-closure identity |
| `17` | 32 raw bytes | Asserted current verifier binary/schema/policy identity |
| `18` | 32 raw bytes | Full task, effective risk and validation recipe **context digest** defined below |
| `19` | BE16; only 0 currently defined | Proof suite: 0=offline parse-only fixture, all nonzero=UnsupportedProofSuite |
| `1a` | 0..4096 opaque bytes; suite 0 requires empty | Proof bytes; final field; never included in body_digest |

Nonzero 32-byte/16-byte identities are required for the format; this detects
obvious invalid fixtures, **not** credible identities. Field 13 is an asserted
digest of the current Specification, not a second representation of the
approved Specification: future independent collection must compare its own
complete current Specification with S and compare its computed digest to 13.
Fields 14 and 15 must agree with S.source_identity and
S.configuration_identity, respectively, for a *binding decision*, but
disagreement does not create an alternative parse of E. Field 16 covers more
than S.executable_pin; field 17 has no equivalent in existing Specification
and must be independently checked. Field 04 must equal S.scope before even a
hypothetical inspection-only acceptance. Field `18` is a *claimed* hash,
not observed current context: future admission must independently construct
the exact current task/risk/recipe bytes defined below, compare its computed
digest with this reviewed field and prove reviewer authorization for it.
Missing/uncertain current context stays Unknown, never a hash-match fallback.

### Nested Specification S (one exact encoding)

The bytes of tag 12 are **exactly**, without nested tags or trailing bytes:

```text
BE16(schema_version = 1)
STR16(executable) || raw32(executable_pin)
BE32(version.major) || BE32(version.minor) || BE32(version.patch)
raw32(source_identity) || raw32(configuration_identity)
U8(argc) || (U8(arg_kind) || STR16(arg_text)) repeated argc times in order
STR16(scope) || STR16(cwd) || U8(operation)
BE64(wall_seconds) || BE64(cpu_seconds) || BE64(input_bytes)
|| BE64(output_bytes) || BE64(memory_bytes) || BE64(processes)
U8(profile) || U8(reasoning)
```

`STR16(s) = BE16(byte_length(s)) || ASCII(s)` with nonempty `21..7e`
bytes. `argc` is 0..32; each arg kind is precisely
1=Word, 2=Flag, 3=Path. Aggregate arg-text bytes <=4096, paths
(executable, scope, cwd and Path arguments) <=1024 bytes each; no hidden
terminators. `version` is the **three u32 values** from
`version::Version`, not a semantic-version string. Operation enum maps:
1=ReadOnlyInvariant, 2=RelevantTests, 3=BuildOrStaticCheck,
4=CallerCompatibility, 5=ImpactReview, 6=SecurityReview,
7=CiConfigurationCheck, 8=DependencyValidation,
9=DocumentationCheck, 10=ReleaseRehearsal.
Profile: 1=Economy, 2=Standard, 3=Strong.
Reasoning: 1=Medium, 2=High. No other discriminant is defined.

The existing Rust `ValidationObligation` has **ten** variants, not eleven.
Each budget has its own BE64; format decoding accepts exact integers, while
the existing pure policy separately requires wall 1..60, CPU 1..wall,
input/output 1..1,048,576, memory 1..536,870,912, processes 1..8.
A well-formed S can therefore fail structural policy, risk floor or semantic
argv review; its bytes must not be rewritten or "fixed up" by the decoder.
The v1 schema in S is mandatory and is independent from the envelope header
version; neither may silently upgrade the other.

### Canonical validation context digest (field `18`)

Let `K` be the unique binary encoding of the **complete** reviewed assessment,
selected workflow risk floor and validation recipe below. The field value is
`SHA256(ASCII("codex-smart/validation-context/v1") || 00 || K)`; the
literal suffix `00` is one NUL, and `K` is never transmitted as a
second copy in this envelope. The digest binds exact future independently held
context, but does not authenticate that context. Exact encoding is:

```text
U8(task_kind) || U8(caller_risk) || U8(selected_workflow_risk)
|| U8(effective_risk) || U8(ambiguity)
U8(reason_count) || U8(reason)[reason_count]
U8(recipe_readiness) || U8(check_count)
|| (U8(obligation) || U8(check_readiness) || U8(native_count)
    || U8(native_capability)[native_count]) repeated check_count times
```

Each `U8` is exactly one byte. `task_kind`: 0=Unknown, 1=Inspect,
2=Edit, 3=Refactor. Risk: 1=Low, 2=Medium, 3=High.
`effective_risk` **must equal** max(caller_risk,selected_workflow_risk);
the future authenticated evaluator must retain the stronger workflow floor.
`ambiguity`: 1=Clear, 2=Ambiguous. The nine
`routing::assessment::Reason` values in Rust declaration order are
1=ExplicitTask, 2=KnownOperation, 3=ExplicitRisk, 4=SecuritySensitive,
5=MigrationSensitive, 6=ConcurrencySensitive, 7=StructuralChange,
8=ConflictingTaskEvidence, 9=InsufficientTaskEvidence.
`reason_count` is 0..9; reasons are strictly increasing, unique,
and include the full set, not a subset.

`recipe_readiness` and `check_readiness`: 1=Ready,
2=NeedsEvidence, 3=Blocked. `check_count`: 0..16.
Checks stay in **original ValidationRecipe.checks Vec order**, including
repetitions; no sorting or dropping. Obligation uses the ten codes defined
for S.operation. `native_count`: 0..6. `NativeCapability` codes in Rust
declaration order: 1=ReadFiles, 2=Search, 3=Git, 4=Edit, 5=Build,
6=Tests. Each check's native capabilities are strictly ascending and
unique (canonical BTreeSet), including zero length when empty. No other
values, omitted members, padded counts or trailing bytes are allowed.
Maximum length is 161 bytes (5 fixed fields, reason count, up to nine
reasons, recipe readiness/check count and 16*(3+6) check bytes).
The formatter must reject invalid enum values and oversized counts, not
hash an alternate representation.

Current `TaskRiskAssessment`, `WorkflowPlan.selection.effective_risk`
and the *complete current ValidationRecipe* must be independently established
and re-evaluated at consumption. A mismatch of their canonical K digest
with field `18` is a binding rejection, not a parse failure; absent
independent context is Unknown. K and all digest bytes can be attacker
declared, so even a matching hash never proves policy, reviewer authority,
semantic argv safety, clock, revocation, replay or readiness. The approved
policy lease/freshness remains separately protected under #135, not
bootstrapped by candidate input.

### Decoder precedence, trust boundary and non-authority

A proposed bounded decoder must return only a fixed enum and optionally a
private, non-serializing parsed record. Exact deterministic first failure:

1. **Oversize** if either checked total exceeds its inclusive limit.
2. **Truncated** for a partial D/header; otherwise **UnsupportedDomain**
   for complete wrong D, then **UnsupportedVersion** for complete non-v1 header.
3. Scan all TLV framing and tags in **wire order**, without interpreting
   values. The first tag outside `01..1a` is **UnknownField**; a
   repeated seen tag is **DuplicateField**, an unseen smaller tag is
   **OutOfOrder**, and any partial TLV tag/length/value is **Truncated**.
   Bytes after complete tag `1a` are **TrailingPayload**. Once framing
   ends, any absent required tag is **MissingField** (before value decoding).
4. Decode framed values in **ascending tag order**. **Truncated** for a
   partial nested integer/string; **MalformedValue** for wrong fixed width,
   forbidden ASCII, zero fixed identity, malformed nested S, excessive
   per-field length, invalid enum or noncanonical number. **UnsupportedSchema**
   for complete S with schema !=1. **UnsupportedProofSuite** for nonzero
   field `19`, after all field widths and values are valid. Suite 0
   with nonempty proof is **MalformedValue**.
5. Only after successful parsing, compute the three digests exactly as
   above and return **ParseOnly**. Bytes are never silently canonicalized:
   re-encode and byte-compare before returning ParseOnly.

When multiple faults exist, priority is: size, header, first TLV framing/tag
fault in wire order, MissingField, then first invalid value in tag order,
then unsupported proof suite and nonempty fixture proof. In particular,
missing fields outrank bad earlier *values*, but do not outrank bad earlier
*framing*. Within S inspect members in their displayed order. No recursion,
unbounded allocation or payload-bearing exception/log messages; diagnostics
are enum-only and do not emit argv, paths, proof bytes or secrets.

**ParseOnly is not an approval.** Independent proof authentication, reviewer
delegation and actual root/operator authority, policy authorization/epochs,
decision, complete current snapshot, trusted clock and bounded freshness,
protected rollback/revocation/replay store, stable held snapshots and atomic
consume must *all* be established by separate independently reviewed
mechanisms. With known authenticated contradictions, future ingress
`Rejected(reason)`; with absent/unobservable prerequisites,
`Unknown(reason)`; only fully checked evidence can ever be
`AcceptedForInspectionOnly`, which still authorizes **zero execution**.
Body digest is an unkeyed binding target for a *future reviewed* proof
scheme. For a future operator-pinned **exact-envelope** allowlist, compare
the independently delivered `wire_digest`, not merely body_digest;
changing proof bytes leaves body_digest unchanged but changes wire_digest.
Neither suite 0, digest equality, a declared key nor fake test policy
constitutes cryptographic authenticity or reviewer authority. Trusted
clock, independent identity collector, enrollment, revocation, replay,
rollback and TOCTOU protection remain UNKNOWN. No existing runtime
implements this parser, proof or ingress.

### Reproducible byte-level offline vectors

The fixture script below specifies complete positive bytes by construction,
and each mutation is independent of all other mutations. It prints SHA-256
goldens and verifies the size/format constraints with no external library or
key. The table reports **format-only** expected results, not authenticated
ingress, and gives the exact mutation to apply to `E0`. An identity or
epoch change with structurally valid bytes must remain ParseOnly (different
digest); a separately held *original* trusted snapshot would later reject
the binding. Rejecting such a change as malformed would conflate decoding
with trust.

The following standard-library script is a fully specified reference builder and
bounded *offline format-only* checker. Save its contents as a temporary Python
file and run with `python3 -B`; expected output is pinned below. No product
source, real signing key, trusted policy or verifier is invoked.

```python
# Offline reference vectors only. NOT a product parser, authority or crypto verifier.
import hashlib
import re

D = b"codex-smart/validation-approval-envelope/v1\x00"
def n(v, size): return v.to_bytes(size, "big")
def t(tag, raw): return bytes([tag]) + n(len(raw), 2) + raw
def s(raw): return n(len(raw), 2) + raw
def hash_d(domain, raw): return hashlib.sha256(domain + b"\x00" + raw).digest()
def spec():
    return (n(1, 2) + s(b"/bin/true") + b"\x11"*32
            + n(1, 4) + n(2, 4) + n(3, 4)
            + b"\x22"*32 + b"\x33"*32 + b"\x03"
            + b"\x01" + s(b"check") + b"\x02" + s(b"--offline")
            + b"\x03" + s(b"src") + s(b"/work") + s(b"/work/repo")
            + b"\x02" + b"".join(n(v, 8) for v in (30, 15, 1024, 1024, 1048576, 1))
            + b"\x03\x02")
S = spec()
# Full reviewed risk/recipe K: Inspect, caller High, selected High,
# effective High, Clear, zero reasons, Ready recipe, one Ready RelevantTests
# check requiring the native capability Tests (6).
K = bytes((1, 3, 3, 3, 1, 0, 1, 1, 2, 1, 1, 6))
context_hash = hash_d(b"codex-smart/validation-context/v1", K)
spec_hash = hash_d(b"codex-smart/validation-specification/v1", S)
F = [
    (1,b"\x01"), (2,b"example/repo"), (3,b"\x01"), (4,b"/work"),
    (5,b"offline-v1"), (6,n(7,8)), (7,b"A"*32), (8,b"O"*32),
    (9,b"R"*32), (10,n(7,8)), (11,n(3,8)),
    (12,b"X"*16), (13,b"S"*16), (14,b"U"*16), (15,b"T"*16),
    (16,n(100,8)), (17,n(400,8)), (18,S), (19,spec_hash),
    (20,b"\x22"*32), (21,b"\x33"*32), (22,b"\x44"*32),
    (23,b"\x55"*32), (24,context_hash), (25,n(0,2)), (26,b""),
]
def build(fields=F, version=1, domain=D):
    return domain + n(version,2) + b"".join(t(k,v) for k,v in fields)
E0 = build()
def change(k,v): return build([(tag,v if tag==k else raw) for tag,raw in F])
def remove(k): return build([(tag,raw) for tag,raw in F if tag!=k])
def insert_before(before,k,v):
    out=[]
    for tag,raw in F:
        if tag==before: out.append((k,v))
        out.append((tag,raw))
    return build(out)
def swap(a,b):
    f=list(F); ia=next(i for i,x in enumerate(f) if x[0]==a)
    ib=next(i for i,x in enumerate(f) if x[0]==b)
    f[ia],f[ib]=f[ib],f[ia]
    return build(f)

class Invalid(Exception): pass
def fail(name): raise Invalid(name)
def text_value(v,limit=None):
    if not v or (limit is not None and len(v)>limit) or not all(33<=c<=126 for c in v):
        fail("MalformedValue")
def read(p,count,pos):
    if pos+count>len(p): fail("Truncated")
    return p[pos:pos+count],pos+count
def parse_spec(p):
    ix=0
    def get(count):
        nonlocal ix
        raw,ix=read(p,count,ix)
        return raw
    def string(limit=None):
        length=int.from_bytes(get(2),"big")
        if limit is not None and length>limit: fail("MalformedValue")
        raw=get(length)
        text_value(raw)
        return raw
    if int.from_bytes(get(2),"big")!=1: fail("UnsupportedSchema")
    string(1024)
    if get(32)==b"\0"*32: fail("MalformedValue")
    for _ in range(3): get(4)
    for _ in range(2):
        if get(32)==b"\0"*32: fail("MalformedValue")
    argc=get(1)[0]
    if argc>32: fail("MalformedValue")
    used=0
    for _ in range(argc):
        kind=get(1)[0]
        if kind not in (1,2,3): fail("MalformedValue")
        arg=string(1024 if kind==3 else 4096)
        used+=len(arg)
    if used>4096: fail("MalformedValue")
    string(1024); string(1024)
    if get(1)[0] not in range(1,11): fail("MalformedValue")
    for _ in range(6): get(8)
    if get(1)[0] not in (1,2,3): fail("MalformedValue")
    if get(1)[0] not in (1,2): fail("MalformedValue")
    if ix!=len(p): fail("MalformedValue")
def parse(e, external=b"", policy=b""):
    if len(e)>16384 or len(e)+len(external)+len(policy)>65536:
        fail("Oversize")
    if len(e)<len(D): fail("Truncated")
    if not e.startswith(D): fail("UnsupportedDomain")
    if len(e)<len(D)+2: fail("Truncated")
    if e[len(D):len(D)+2]!=b"\x00\x01": fail("UnsupportedVersion")
    ix=len(D)+2
    last=0; seen=set(); fields={}
    while ix<len(e):
        if last==26: fail("TrailingPayload")
        if len(e)-ix<3: fail("Truncated")
        tag=e[ix]; size=int.from_bytes(e[ix+1:ix+3],"big")
        ix+=3
        if not 1<=tag<=26: fail("UnknownField")
        if tag in seen: fail("DuplicateField")
        if tag<last: fail("OutOfOrder")
        raw,ix=read(e,size,ix)
        seen.add(tag); last=tag; fields[tag]=raw
    if len(fields)!=26: fail("MissingField")
    for tag in range(1,27):
        if tag not in fields: fail("MissingField")
        v=fields[tag]
        if tag in (1,3):
            if len(v)!=1 or (tag==1 and v[0] not in (1,2)) or (tag==3 and v!=b"\x01"):
                fail("MalformedValue")
        if tag in (2,4,5):
            text_value(v,129 if tag==2 else (1024 if tag==4 else 64))
            if tag==2 and not re.fullmatch(rb"[a-z0-9_.-]{1,64}/[a-z0-9_.-]{1,64}",v):
                fail("MalformedValue")
            if tag==5 and not re.fullmatch(rb"[a-z0-9_.-]{1,64}",v):
                fail("MalformedValue")
        if tag in (6,10,11,16,17):
            if len(v)!=8 or (tag in (6,10) and v==b"\x00"*8): fail("MalformedValue")
        if tag in (7,8,9,19,20,21,22,23):
            if len(v)!=32 or v==b"\x00"*32: fail("MalformedValue")
        if tag in (12,13,14,15):
            if len(v)!=16 or v==b"\x00"*16: fail("MalformedValue")
        if tag==18: parse_spec(v)
        if tag==24 and (len(v)!=32 or v==b"\x00"*32): fail("MalformedValue")
        if tag==25 and len(v)!=2: fail("MalformedValue")
        if tag==26 and len(v)>4096: fail("MalformedValue")
    if fields[25]!=b"\x00\x00": fail("UnsupportedProofSuite")
    if fields[26]: fail("MalformedValue")
    reencoded=build([(k,fields[k]) for k in range(1,27)])
    if e!=reencoded: fail("MalformedValue")
    return ("ParseOnly",hash_d(b"codex-smart/validation-approval-body/v1",
                              e[:len(e)-3-len(fields[26])]).hex(),
            hash_d(b"codex-smart/validation-approval-wire/v1",e).hex())

CASES = [
 ("V00", E0, b"", b"", "ParseOnly"),
 ("V01", E0+b"x"*(16385-len(E0)),b"",b"", "Oversize"),
 ("V02", E0,b"",b"x"*(65537-len(E0)), "Oversize"),
 ("V03", insert_before(4,3,b"\x01"),b"",b"", "DuplicateField"),
 ("V04", insert_before(26,27,b""),b"",b"", "UnknownField"),
 ("V05", remove(2),b"",b"", "MissingField"),
 ("V06", swap(3,4),b"",b"", "OutOfOrder"),
 ("V07", change(6,b"\x00"+n(7,8)),b"",b"", "MalformedValue"),
 ("V08", E0+b"\x00",b"",b"", "TrailingPayload"),
 ("V09", build(version=2),b"",b"", "UnsupportedVersion"),
 ("V10", D[:-1],b"",b"", "Truncated"),
 ("V11", E0[:-2]+b"\x00\x01",b"",b"", "Truncated"),
 ("V12", build(domain=D[:-1]+b"?"),b"",b"", "UnsupportedDomain"),
 ("V13", change(2,b"example/\xff"),b"",b"", "MalformedValue"),
 ("V14", change(25,n(1,2)),b"",b"", "UnsupportedProofSuite"),
 ("V15", change(26,b"\x00"),b"",b"", "MalformedValue"),
 ("V16", change(1,b"\x02"),b"",b"", "ParseOnly"),
 ("V17", change(22,b"\x45"*32),b"",b"", "ParseOnly"),
 ("V18", change(6,n(8,8)),b"",b"", "ParseOnly"),
 ("V19", change(18,S[:-2]+b"\x02"+S[-1:]),b"",b"", "ParseOnly"),
 ("V20", change(18,b"\x00\x02"+S[2:]),b"",b"", "UnsupportedSchema"),
 ("V21", change(24,b"\x66"*32),b"",b"", "ParseOnly"),
 ("V22", change(24,b"\x00"*32),b"",b"", "MalformedValue"),
]
for name,e,ex,pol,expected in CASES:
    try: actual=parse(e,ex,pol)[0]
    except Invalid as err: actual=str(err)
    assert actual==expected,(name,actual,expected)
print("vectors",len(CASES),"OK")
print("length(E0)",len(E0),"length(S)",len(S))
print("spec_digest",spec_hash.hex())
print("context_digest",context_hash.hex())
print("body_digest",parse(E0)[1])
print("wire_digest",parse(E0)[2])
print("prefix(E0,hex)", E0[:len(D)+2].hex())
for name, e, ex, pol, expected in CASES:
    print(name,len(e),len(ex),len(pol),expected)

```

The exact positive fixture is `E0` (765 bytes) built from the explicit ordered
`F` values above; nested `S` is 218 bytes. Its mandatory header hex is
`636f6465782d736d6172742f76616c69646174696f6e2d617070726f76616c2d656e76656c6f70652f7631000001`.
The golden `spec_digest`, `context_digest`, `body_digest` and `wire_digest` are respectively:

```text
db38c03a0a016932acd0a2ee195e03af7abae7b76730801658c9a8b05bbfcd67
d3ce91a75b3afe19b677e90ef9eb77d9e16a9a4f3221b055530fa98d06233c30
f9733c27521a922f8bf20e1b421781393bc61a62c6e3fb900a84248788393cec
f224303817cc78770d4ff88fc6e40f49305c675da4aa3a30080135ce7706dccb
```

| Vector | Independent byte-level mutation relative to E0 | Expected format result |
| --- | --- | --- |
| V00 | No mutation, exact 765 bytes; empty external proof and policy | ParseOnly |
| V01 | Append `x` bytes until len(E)=16385 | Oversize |
| V02 | Retain E0; external policy is 64772 bytes `x` (combined 65537) | Oversize |
| V03 | Duplicate `TLV(03,01)` immediately before tag 04 | DuplicateField |
| V04 | Insert unknown `TLV(1b,empty)` before final tag `1a` | UnknownField |
| V05 | Remove entire TLV 02 | MissingField |
| V06 | Swap complete TLV 03 and TLV 04 | OutOfOrder |
| V07 | Change tag 06 from 8-byte BE64(7) to 9 bytes `00 || BE64(7)` | MalformedValue |
| V08 | Append literal `00` after final proof field | TrailingPayload |
| V09 | Change only the two-byte header version to `00 02` | UnsupportedVersion |
| V10 | Truncate header to all but final byte of D | Truncated |
| V11 | Change final TLV `1a` length from `00 00` to `00 01`, with no byte appended | Truncated |
| V12 | Replace final NUL byte of D with ASCII `?` | UnsupportedDomain |
| V13 | Change repository bytes from `example/repo` to `example/\xff` (length re-encoded) | MalformedValue |
| V14 | Change proof-suite tag `19` value to BE16(1) | UnsupportedProofSuite |
| V15 | Change proof tag `1a` to one raw `00` byte | MalformedValue |
| V16 | Change tag 01 from Approve to Deny (`02`) | ParseOnly; later authenticated decision would reject |
| V17 | Change tag 16 tool-closure identity to 32 bytes `45` | ParseOnly; digest changes, later identity comparison rejects |
| V18 | Change tag 06 policy epoch from BE64(7) to BE64(8) | ParseOnly; digest changes, protected epoch must be checked |
| V19 | Change nested S.profile from Strong (`03`) to Standard (`02`) | ParseOnly; spec/body/wire digests change, current/risk binding must be checked |
| V20 | Change S.schema_version from BE16(1) to BE16(2) | UnsupportedSchema |
| V21 | Change context digest tag `18` to 32 bytes `66` | ParseOnly; separate current K must reject |
| V22 | Replace context digest with 32 zero bytes | MalformedValue |

The deterministic reference output is `vectors 23 OK`; each vector is
built independently from E0, and no test asserts authenticated success.
One-byte data mutation with a recomputed unkeyed digest is **not** proof of
tamper resistance; authenticated protection requires independently trusted
proof material and authorization. This offline script is proposed contract
test evidence only, not an installed parser or tested production ingress.
All existing #135 scenario requirements and its production NO-GO apply.

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
