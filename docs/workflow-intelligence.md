# Workflow intelligence target

Status: Playbooks 0.4 is implemented and accepted; Adaptive Execution 0.5 is active. #43 bounded execution, #44 replaceable model compatibility routing and #45 bounded delegation policy are implemented; #46 lifecycle measurement remains. #14 measured benchmark and #15 aggregate telemetry are accepted. Ordinary launches remain single Codex passthrough; the opt-in inspection route applies a bounded model/effort choice for one read-only attempt. These policy contracts still do not launch adaptive retries or children.

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
bytes. Decode each nested STR16 by first requiring both length bytes
(**Truncated** if incomplete); if the declared length exceeds its
applicable cap, return **MalformedValue** before reading any payload,
even when all payload bytes are absent. If a positive in-range length
is declared, require its complete payload (**Truncated** if incomplete)
before testing ASCII; a fully present zero length is **MalformedValue**.
These checks precede later S members in their written order.
`argc` is 0..32; each arg kind is precisely
1=Word, 2=Flag, 3=Path. Aggregate arg-text bytes <=4096, paths
(executable, scope, cwd and Path arguments) <=1024 bytes each; no hidden
terminators. After **each completely decoded** arg text, add its byte length
to the running aggregate with checked addition and reject immediately with
**MalformedValue** at the first total >4096, before reading the next arg.
If an arg text is itself incomplete, **Truncated** takes precedence over
that arg's unrealized aggregate addition; later missing arg members never
supersede an already detected aggregate overflow.

`version` is the **three u32 values** from `version::Version`, not a
semantic-version string. Operation enum maps:
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
2. Inspect the domain before any version bytes. With fewer than `len(D)`
   bytes, return **Truncated**. If all `len(D)` bytes are present and D
   differs, return **UnsupportedDomain**, even if both version bytes are
   absent. For matching D but fewer than two version bytes, return
   **Truncated**; for a complete non-v1 version, **UnsupportedVersion**.
3. Scan all TLV framing and tags in **wire order**, without interpreting
   values. After a completed tag `1a`, any further byte is
   **TrailingPayload**. Otherwise require the complete three-byte
   tag-plus-BE16-length header before classifying its tag: an incomplete
   header is **Truncated**, even if its first byte is an unknown tag.
   With a complete header, first check for **UnknownField** (tag outside
   `01..1a`), then **DuplicateField** (already seen), then
   **OutOfOrder** (unseen smaller tag), *before* checking whether all
   value bytes are present; a partial value of an otherwise admissible
   tag is **Truncated**. Once framing ends, any absent required tag is
   **MissingField** (before value decoding).
4. Decode framed values in **ascending tag order**. **Truncated** for a
   partial nested integer or STR16 length prefix; after a complete STR16
   length prefix, **MalformedValue** for an excessive declared length
   outranks missing/incomplete payload. In-range incomplete payload is
   **Truncated** before semantic checks. **MalformedValue** also applies
   to wrong fixed width, forbidden ASCII, zero fixed identity, malformed
   nested S, invalid enum or noncanonical number. Within S first
   require both schema-version bytes (**Truncated** if incomplete);
   a complete non-v1 schema discriminator is **UnsupportedSchema**
   immediately, even if subsequent S members are absent. For schema v1
   decode remaining members in their displayed order. **UnsupportedProofSuite**
   applies to nonzero field `19` after all field widths and values are
   valid. Suite 0 with nonempty proof is **MalformedValue**.
5. Only after successful parsing, compute the three digests exactly as
   above and return **ParseOnly**. Bytes are never silently canonicalized:
   re-encode and byte-compare before returning ParseOnly.

When multiple faults exist, priority is: size, header, first TLV framing/tag
fault in wire order, MissingField, then first invalid value in tag order,
then unsupported proof suite and nonempty fixture proof. In particular,
missing fields outrank bad earlier *values*, but do not outrank bad earlier
*framing*. The header, TLV and S schema tie-breaks above are normative:
wrong complete domain outranks missing version bytes, incomplete TLV header
outranks its invalid tag byte, complete invalid tag outranks missing value
bytes, and complete unsupported S schema outranks missing S members.
Within S inspect v1 members in their displayed order: after a complete
STR16 prefix, check its length cap before requiring payload; then apply
the per-argument aggregate limit after each complete arg, not only after
all `argc` arguments. A complete second arg causing aggregate overflow
wins over a missing third arg; an incomplete second arg remains Truncated.
No recursion, unbounded allocation or payload-bearing exception/log
messages; diagnostics
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

### Offline evidence comparison (#153)

`validation_approval_decode::compare_evidence` compares a decoded v1 record
against separate `ReviewEvidence` (exact wire digest and authorization claims),
current `BindingClaims`, supplied time and an optional prior-use observation.
These are all untrusted assumptions, including `ExternallyVerifiedAssumption`;
copying or self-hashing a fixture supplies no independent review. The strongest
result is the enum-only `NeedsIndependentAuthority`, with no approval conversion
or runtime caller. Trust-root, genuine provenance, protected state/clock, current
collection and anti-replay remain Unknown; a prior-use match is only a supplied
repeat claim, and absent history proves nothing. No state is consumed.

A bounded private projection retains labels and fixed identities, including nested
S.scope/source/configuration, without argv or raw source. Public format digests
remain available; comparison uses private decoded copies. First-failure order is:
Deny; internal scope/spec/source/config conflicts; missing review/current/time;
review/current label bounds; review wire and claims; current claims; clock domain;
invalid interval; future observation; expiry; backward supplied time; repeated
observation or one-use ID. Claim order is specification, repo/scope/policy,
epoch/root/operator/reviewer/delegation/generation, observation/session/use/clock,
observation/expiry times, source/config/tool closure/verifier/context. Diagnostics
carry enums only. Labels are byte-equal with the existing caps; no allocation,
I/O, authentication or host observation occurs. Matching full spec/context digests
compares claims only; actual complete current specification/context collection,
semantic policy and reviewer authorization still require independent proof.

### Bounded offline current identity observation — qualification (#155)

This **documentation-only proposal** for [#155](https://github.com/AlexandrShapkin/codex-smart/issues/155),
child of #94, qualifies a possible local observer; no collector is implemented or
accepted here. Adaptive 0.5 remains **ACTIVE; production NO-GO**. #135/#137,
[ADR 0010](decisions/0010-native-inspection-trust-boundary.md) and
[ADR 0011](decisions/0011-operator-reviewer-authority.md) retain their independent
authority, host qualification and use-boundary obligations.

**Observation boundary and adversary.** A future collector MAY read explicitly
nominated local bytes and metadata and compare them with separately held inputs.
Repository contents, Git metadata, config, PATH, candidate/review transport and the
host itself MAY be candidate controlled, including concurrent writers, replacement
files, mounts and a compromised kernel. Independent collection means acquiring
bytes without trusting candidate claims; it does **not** mean authentication,
trustworthy origin or a trustworthy host. A collector cannot detect every lie by
its kernel. Independently qualified kernel/filesystem isolation is a prerequisite
for a stable observation; absent that evidence, return Unknown(UnstableSnapshot).
Reading owner/ACL metadata, an embedded key or a provenance enum cannot supply it.
Root/operator/reviewer authority, protected policy/delegation/revocation generations,
trusted time/clock continuity and protected session/use/replay state MUST remain
separate external prerequisites. Reading their alleged files establishes bytes
only; it MUST NOT turn them into authority or prove unseen offline revocations.

**Required coverage, not a hash-only checklist.** The following maps every
`BindingClaims` member to its obligation. E tags are hexadecimal as in #137.
Locally observable rows require complete independently held inputs and qualified
coverage; external rows MUST NOT be synthesized from candidate declarations.

| Claim / E tag | Required independently held coverage and limit of observation |
| --- | --- |
| `repository` / `02` | Bind the exact repository label to the prior independently nominated repository root/worktree and Git identity. A remote URL, directory name or HEAD label alone cannot establish repository identity or ownership. |
| `scope` / `04`, S.scope | Compare exact lexical bytes and component containment of S.cwd and path operands; separately establish actual descriptor/mount containment for every relevant input. Lexical equality is not filesystem confinement. |
| `spec_digest` / `12` S, `13` | Hold the **entire current Specification** independently of reviewed S: schema_version, executable absolute path, executable_pin, all three Version components, source_identity, configuration_identity, ordered argv with every Word/Flag/Path tag and byte, scope, cwd, operation, wall_seconds, cpu_seconds, input_bytes, output_bytes, memory_bytes, processes, profile and reasoning. Compare every member to reviewed S and compute the #137 spec_digest for comparison to `13`; a digest cannot reconstruct S. Declared budgets are not enforced resource controls; tool-specific argv semantics still need independent review. |
| `source` / `14`, S.source_identity | Cover relevant current source bytes and repository state: worktree, referenced Git tree and index, staged/unstaged changes, relevant untracked and ignored/generated inputs. HEAD or a source receipt cannot substitute for current dirty-state coverage. |
| `configuration` / `15`, S.configuration_identity | Cover actual effective configuration, defaults, load order/precedence, overrides and relevant environment, including implicit tool config. Missing environment/default semantics is incomplete coverage, even when config files match. |
| `tool_closure` / `16` | Identify the actual selected executable artifact and relevant interpreter, loader, libraries, scripts, plugins and dependency closure, not only S.executable_pin or a PATH/version declaration. No execution probe is permitted; unobservable runtime selection/version/closure remains Unknown. |
| `verifier` / `17` | Identify the **running** collector/verifier artifact and its active schema/policy implementation and configuration, not a candidate-nominated binary on disk. S has no equivalent verifier member. Policy bytes do not prove policy authority or freshness. |
| `context` / `18` | Independently hold complete current K: task kind, caller risk, selected workflow risk, effective risk=max of both, ambiguity, full ordered canonical reason set, recipe readiness and every check in original order including repetitions, obligation/readiness/native capabilities. Reconstruct exact #137 K and compare its context digest; a hash cannot recover K or establish semantic task truth. High retains Strong/High. |
| `policy`, `policy_epoch` / `05`, `06` | External independently authorized policy identity and current protected epoch/lease; locally read policy bytes are insufficient. |
| `root`, `operator`, `reviewer`, `delegation_epoch`, `revocation_generation` / `07`–`0b` | External authenticated authority, scope/delegation and protected current generations; no candidate-selected anchor or local matching record qualifies them. |
| `observation`, `session`, `one_use` / `0c`–`0e` | External observation/session binding and protected one-use history/continuity. A local identifier or absent prior-use claim proves no uniqueness or non-replay. |
| `clock_domain`, `observed_at`, `expires_at` / `0f`–`11` | External trusted clock/domain, interval and freshness evidence, with rollback continuity. A local wall clock or scan deadline cannot authenticate these claims. |
| `provenance` / no E tag | Caller assertion only, including ExternallyVerifiedAssumption; never upgraded by collection, matching hashes or copying review evidence. |

File bytes/metadata can be locally re-read; S.argv, budgets, profile/reasoning,
selected operation, and K's task/risk/reasons/recipe are **control-plane facts**,
not derivable from a filesystem scan. Their current values require separately
held, non-candidate-selected invocation/assessment evidence, with source and
continuity qualified in a future integration. Reading a process command line or
self-declared plan does not authenticate that evidence. A filesystem-only collector
MUST report Unknown(UnqualifiedCoverage) for full S/K, not infer or copy them.

`ReviewEvidence.wire_digest` additionally binds exact E bytes, not reviewer authority;
`TimeObservation` and `PriorUse` remain supplied assertions. Decision/capability and
proof-suite/proof fields retain #137 gates. No S/K reconstruction from `ParseOnly`
is available: its private comparison projection is not a retained full descriptor.
Only #137 defines canonical S/K and their digest algorithms here. Exact source,
configuration, closure and verifier byte manifests/encodings still require separate
acceptance; this subsection selects no new digest encoding or algorithm for them.
Unknown, zero, unreadable or excluded required coverage MUST remain Unknown, never
a positive observation; an empty scan cannot establish complete source coverage.

**Proposed finite local read budgets (not enforced by current Rust).** One attempt
MUST use at most 4,096 entries total (directories, files and excluded entries
included), 16 MiB per regular file, 128 MiB aggregate bytes read including rereads
and metadata/manifest buffers, 64 directory components and 30 seconds elapsed.
All roots and auxiliary inputs share these caps; callers MAY lower, never raise
them. Counters/lengths MUST use checked arithmetic before reads/allocation; byte
or counter overflow and any exceeded cap reject, without partial positive output.
Zero/unknown budget configuration is Unknown(UnqualifiedCoverage). A bounded local
monotonic deadline limits work only; unavailable deadline enforcement is Unknown.
Symlink traversal budget is **zero**: reject symlinks, including ancestors and
magic links; do not resolve them. No crossing the independently pinned allowed
local mount, external devices, network filesystems/network I/O, special files,
privileged scans or arbitrary process launches is permitted. Do not run Git,
version commands, interpreters, hooks, filters, package managers or discovered tools.
The existing decoder caps remain separately **16,384 bytes for E** and **65,536
bytes combined E/external proof/independent policy**, with checked addition before
parsing. These scan budgets neither replace those caps nor change S's policy limits
or existing preparation acquisition limits.

**Held snapshot requirements.** Before reading, require prior explicit independent
root/scope nomination and a pinned allowed local mount, including any required
auxiliary roots on that mount; project config MUST NOT expand the nomination.
Walk read-only with held directory/file descriptors and no-follow operations for
every component. Bind fd/object identity, inode, device, mount identity, relevant
metadata and content digests; a pathname, inode or mtime alone is insufficient.
An ephemeral opaque snapshot identity SHOULD bind the nominated roots/mounts,
sorted complete inclusion/exclusion manifest, current S/K and config/tool/verifier
identities and the local scan generation. It is not the envelope observation or
one-use ID, not an authenticated provenance token, and not a substitute for
coherence or use-time revalidation. Any bound-member change invalidates it.
Retain a bounded private inclusion/exclusion manifest with reasons and required
coverage, including worktree/Git tree/index differences. Submodules and LFS require
actual relevant content and nominated containment: a gitlink, LFS pointer or absent
object is not that content. Relevant ignored/generated inputs MUST be included or
coverage is Unknown; exclusions cannot silently mean irrelevant. Missing semantic
knowledge about which inputs matter is also Unknown(UnqualifiedCoverage).

A read-only fd does not freeze in-place writes, directory membership, hard-link
aliases or replacement/mount changes. Before/after hashes or matching mtimes do
not prove a coherent snapshot, nor exclude mutation followed by restoration.
Require separately qualified kernel/FS snapshot or writer-exclusion guarantees
covering the entire held set and its membership; otherwise Unknown(UnstableSnapshot).
Hold that set through assessment and any future use; revalidate content/object,
mount and external policy generations at use. Observed drift invalidates the
observation. No pathname reopen may silently replace the held object. This proposal
implements no atomic consume; #135's separately protected transaction must still
couple revalidation to use, or admission remains Unknown.

**Proposed enum-only outcomes and deterministic failure order.** These conceptual
statuses are **not Rust APIs** and do not replace #153 or #135 results:

```text
ObservedUntrusted                     // complete qualified local observation only
Unknown(MissingNomination | UnqualifiedCoverage | UnreadableInput
        | UnobservableInput | UnstableSnapshot)
Reject(OverBudget | UnsafeTraversal | Conflict | IdentityMismatch
       | GenerationChanged | PrivacyViolation)
```

For this collector only, select first failure by: (1) invalid/overflow/exceeded
resource caps (`OverBudget`); (2) established unsafe traversal, then privacy
violation; (3) prerequisite/coverage Unknown reasons in the displayed order;
(4) established Conflict, IdentityMismatch, GenerationChanged in that order;
(5) ObservedUntrusted. Zero/unknown budgets follow stage 3 as specified above.
Within a stage use coverage-table order, then bytewise relative manifest-entry
order, never directory enumeration order. Missing prerequisites may mask later
comparisons; they never imply success. This ordering does not alter decoder or
`compare_evidence` precedence. Emit fixed enums only, with no raw paths, source,
argv, environment, hashes, proof material or secrets; keep held bytes/manifests
private, bounded and ephemeral, with no logging/serialization/export by default.

| Negative/failure case (future isolated fake controls) | Required proposed outcome |
| --- | --- |
| Omit full S/K, dirty/untracked/config/default/environment/closure/verifier coverage; supply zero identity or relevant exclusion | Unknown(UnqualifiedCoverage); unreadable required input instead gives Unknown(UnreadableInput). No digest-only fallback. |
| Copy candidate/review/current or self-assert provenance/authority/time/use | Cannot qualify missing independent nomination/coverage; Unknown as applicable. Even complete observed bytes remain ObservedUntrusted, with authority external. |
| Duplicate/conflicting manifests or distinct known bytes assigned the same identity (including a demonstrated digest collision) | Reject(Conflict); never merge, last-writer select or treat hash equality as byte equality. |
| Escape via ancestor/leaf symlink, mount substitution/crossing, device or special file | Reject(UnsafeTraversal); no target reads. Unobservable mount confinement is Unknown(UnstableSnapshot). |
| Replace/overwrite a held file or mutate concurrently | Proven content/object mismatch: Reject(IdentityMismatch); proven snapshot/generation drift: Reject(GenerationChanged). Inability to exclude transient writes/restoration: Unknown(UnstableSnapshot). |
| Exceed entry/file/aggregate/depth/deadline cap or overflow byte arithmetic | Reject(OverBudget); discard partial positive result. |
| Reuse stale collected claims after known source/config/tool/verifier or protected generation change | Reject(IdentityMismatch) or Reject(GenerationChanged), respectively; unavailable continuity is Unknown. Expiry/replay remain external #135 gates, never solved by rescanning. |
| Attempt to emit private paths, hashes, argv, environment or secret-bearing errors | Reject(PrivacyViolation); suppress payload, no partial diagnostic export. |

**Minimal future slice and prerequisites.** Only after separate architecture/security
acceptance of exact coverage/encodings, finite budgets, independent nomination,
qualified host isolation and the negative controls above MAY a native read-only
collector hold nominated descriptors, construct full current S/K and private
manifests, then offer bounded comparison inputs. Unobservable version, runtime
loading, effective defaults or task semantics MUST stop positive coverage; no probe
or candidate assertion repairs them. Existing `preparation` acquisition and
`native_inspection::assess`/`assess_canonical` do not supply these missing guarantees.
A complete collector result would be ObservedUntrusted; a matching #153 comparison
still returns `BindingResult::NeedsIndependentAuthority`. The current absent-input
result is exactly `BindingResult::Missing(EvidenceKind::Current)` (often abbreviated
Missing(Current)), not a new collector Unknown variant. No conversion is added to
`Approval`, `CurrentAssumptions`, `NativeSurface::Verified` or a runtime caller.
No Ready/Accepted/Verified status, enrollment, authentication, trusted time, replay
protection, validation/model/Codex execution, runtime adapter or product readiness
is delivered or authorized. #94 retains integration/trust gaps; #95 retains separate
measurement acceptance. This qualification leaves every production gate closed.

### Canonical current source identity manifest v1 — docs-only qualification (#157)

**Threat model and independent scope closure.** The candidate can control source,
Git/index/config/tool bytes, names, exclusions, aliases and concurrent writers;
its host/kernel can lie. This **NEW PROPOSED offline source manifest v1** is
**proposal/docs only**: no collector, host qualification, runtime join or authority.
An independently authorized policy MUST bind root handles, opaque root labels,
requested scope, relevant pinned commits and a finite directed closure graph.
Vertices identify required source/tool/config/generated inputs; edges identify
all known selection, inclusion and dependency relations. Independent semantic
review MUST attest that every known relevant input and edge is covered, including
implicit configuration and generated inputs, and that no unresolved dependency
remains. Unknown relevance/selection semantics yields Unknown(UnqualifiedCoverage).
A candidate manifest, empty graph or declaration of completeness cannot attest
itself. Source-only success cannot establish full S/K or #155 observation coverage.

Policy MUST enumerate included directory boundaries and required files, and assign
every observed child either inclusion or a fixed independently justified exclusion.
Known relevant files MUST be included; ignored/untracked/generated status is never
an exclusion reason. Exclusion codes are exactly 1=IndependentlyIrrelevant,
2=OutsideAuthorizedScope, 3=ProtectedPrivateIrrelevant. Reasons and attestations stay
private. An excluded directory seals an independently proved irrelevant subtree;
without that proof its descendants MUST be enumerated within budget or coverage
is Unknown(UnqualifiedCoverage). Relevant private data that cannot safely be read
is Unknown(UnqualifiedCoverage), never silently excluded; attempted forbidden
access/disclosure is Reject(PrivacyViolation). Candidate rules cannot shrink scope.

**Git views are separate observations.** For each relevant repository, policy MUST
pin the relevant commit(s), their complete relevant tree/blob object closure and
object format, and independently bind current HEAD/ref state, index and worktree.
Only relevant pinned commits are traversed: other branches require coverage only
when independently known relevant, then MUST also be pinned. Missing required Git
objects, including shallow/partial-clone omissions, are Unknown(UnobservableInput);
no fetch. Read/decode objects and index offline without Git commands, hooks,
filters, attributes execution, interpreters or tools. Verify object type, claimed
object ID and bytes, with bounded decompression and independent SHA-256 framing.
Git object IDs alone are not content/identity evidence or collision protection.
Index stage 0 paths/modes/blob bytes are included separately from current worktree;
stages 1–3/unmerged entries reject Conflict. Sparse checkout is
Unknown(UnqualifiedCoverage) in v1; no inferred completeness from sparse indexes.
Staged, unstaged, deleted and relevant untracked/ignored/generated paths MUST be
reconciled explicitly. Expected absent paths are private policy obligations, not
invented file records; inability to observe a required path is Unknown(UnreadableInput).
HEAD/tree/index/status never replace reading current bytes and directory membership.
If policy references `.git` metadata, its exact bytes MUST additionally be included
as explicit metadata entries under the same bounds; linked worktree Git directories
need separate independent nomination. No automatic `.git` traversal or root expansion.

**Canonical byte grammar (new format, no implicit encoding).** All integers are
unsigned big-endian: U8/U16/U32/U64 are exactly 1/2/4/8 bytes. `B(x)=U32(len(x))||x`;
`L(xs)=U32(count(xs))||B(x1)||...||B(xn)`; `||` is concatenation.
No padding, optional fields, implicit terminator, alternate representation or
trailing bytes is allowed. Invalid framing/version/enum/order is Reject(Conflict),
after higher-priority failures below. Roots and policy_bytes MUST be nonempty.
Checked bounds apply before decoding/allocation.

```text
F = ASCII("codex-smart/current-source-file/v1") || 00
D = ASCII("codex-smart/current-source-manifest/v1") || 00
content(bytes) = SHA256(F || U64(len(bytes)) || bytes)
path = L(raw_components)                         // no text conversion
root = B(root_id) || U8(view) || B(selector)
entry = U8(role) || B(root_id) || B(path) || U8(kind) || B(payload)
file_payload = U8(executable) || U64(size) || B(content_digest)
member = B(raw_child_name) || U8(child_record_kind)
dir_payload = L(members)
excluded_payload = U8(actual_kind) || U8(reason)
M = D || U16(1) || B(policy_bytes) || L(roots) || L(entries)
manifest_digest = SHA256(M)
```

Domain strings contain exactly the shown single final NUL, with no extra NUL.
SHA-256 separation prevents file/manifest cross-domain substitution; it supplies
integrity only. `policy_bytes` are exact independently held versioned closure-policy
bytes, including scope, graph and completeness attestation, not a candidate hash.
Their semantic interpretation MUST already be independently qualified; this section
defines no policy parser or provisioning protocol. A hash cannot recover that policy.

Root IDs are unique nonempty opaque byte strings, at most 64 bytes, independently
bound to actual private root paths/handles and logical views. Views are 1=current
filesystem, 2=committed tree, 3=index stage 0. Selector is empty for view 1; for
view 2 it is U8(object_format)||B(commit_id), format 1=SHA-1 (20-byte ID),
2=SHA-256 (32-byte ID); for view 3 it is the independently bound repository's
view-1 root ID. Roots sort by raw root_id bytes, lexicographic unsigned comparison,
shorter prefix first. Each root defines one namespace; no duplicate root/view
aliases. Git views of one repository have distinct root IDs; physical view-1 roots
MUST NOT overlap or alias. Multi-role files use one record with role 8, not duplicate paths.
Roles are 1=source, 2=tool, 3=config, 4=generated, 5=Git-tree, 6=Git-index,
7=explicit-Git-metadata, 8=multiple; exact role obligations are in held policy.
Views 2/3 require roles 5/6 respectively; view 1 permits 1–4,7,8.

Kinds are 1=regular-file, 2=directory, 3=exclusion. Every included regular file
MUST carry file_payload, with executable exactly 0 or 1, actual logical byte size
and a 32-byte digest. In view 1 executable is 1 iff any POSIX execute mode bit
is set; unobservable mode semantics is Unknown(UnobservableInput).
Every included directory, including each root, MUST carry
its complete immediate membership, sorted by unsigned raw name bytes and unique.
Members refer to exactly one child record at that parent path, with matching kind;
there are no missing, extra or orphan records. Exclusions carry actual_kind 1 or 2
and reason 1–3; no bytes/digest or arbitrary reason text. Excluded roots are forbidden.
Git directories are explicit logical records; Git modes must be regular 100644 or
100755 (executable 0/1), or tree 040000; other modes require refusal below.
Directories use their policy-assigned role; membership covers children of all roles.

Entries sort uniquely by `(role, root_id, raw_relative_path, kind)`, comparing role
and kind numerically, byte strings lexicographically as above. Raw relative path is
components joined by byte 2f, used only for ordering, never as an alternative wire
encoding. A `(root_id,path)` has exactly one record regardless of role/kind; duplicate
or conflicting paths reject Conflict. Zero components denotes the root directory
only; no other empty path, empty component, slash byte, NUL byte, `.` or `..`
component is allowed. Invalid path components/absolute paths reject UnsafeTraversal.
Non-UTF8 components are preserved byte-for-byte; no normalization, replacement or casefolding.
A host unable to expose exact names is Unknown(UnobservableInput). Case-insensitive
or normalization-aliasing filesystems are unsupported: Unknown(UnobservableInput);
known name/object aliases or competing spellings reject Conflict. No sorting by hash.

**Filesystem identity and coherence.** Walk from independently held anchored roots
with no-follow handles for every ancestor/child and verified containment in the
pinned allowed local mount. Symlinks/magic links, escape, mount substitution/crossing,
network mounts, special nodes and regular files with link count other than one
reject UnsafeTraversal; never open special nodes for content. Track held opaque
object identities independently of digest (including device, inode, mount and
reuse-safe generation where available); repeated objects under different paths
reject Conflict. Unavailable containment/object evidence is Unknown(UnobservableInput).
Submodule gitlinks and LFS pointer-only coverage are Unknown(UnqualifiedCoverage):
actual relevant checked-out content, separately nominated roots and complete pinned
object/content closure are mandatory. If containment cannot be provided, refuse;
never initialize submodules, smudge pointers or fetch. A known digest/object-ID
collision rejects Conflict; digest equality MUST NOT override differing held bytes
or opaque object identities. No cross-host snapshot identity is qualified here.

Keep a private opaque snapshot handle binding descriptors, root/view selectors,
complete membership, policy/closure, bytes, executable bits and all relevant metadata
(including ownership/ACLs, link/device/mount IDs, size and modification/change data)
and local/external generations. Metadata beyond executable/size is held separately,
not silently omitted from snapshot identity; unknown relevant metadata semantics
is Unknown(UnqualifiedCoverage). Same bytes on a replacement inode are not the same
snapshot. A read-only descriptor and two equal scans cannot exclude in-place writes,
alias writes or mutate-and-restore. Separately qualified kernel/FS snapshot or writer
exclusion over the entire closure and membership is required; absent it return
Unknown(UnstableSnapshot), even when every digest matches. No host independence or
stable observation is established by this proposal or the synthetic vector.

At revalidation compare held content, metadata, membership, objects, mounts, policy
and generations without pathname substitution. An internally malformed or
self-contradictory canonical record rejects Conflict; a well-formed observation
whose included/missing/extra relevant entries, content, index, type, metadata or
membership differ from the held baseline rejects IdentityMismatch. Known generation
change rejects GenerationChanged and invalidates the handle (both mismatch and
generation findings select IdentityMismatch by precedence).
Unknown coherence invalidates it with Unknown(UnstableSnapshot). Hold through any
future assessment/use; this section provides no atomic use/consume transaction.
Matching digest is neither race-free observation nor provenance/authentication,
reviewer authority, validation readiness, execution permission or replay protection.

**Bounds and outcomes.** Inherit #155 unchanged: at most 4,096 entries including
all directories/exclusions across all views/roots, 16 MiB per file, 128 MiB aggregate
reads including rereads, decoded Git bytes and metadata/manifest buffers, 64 path
components and 30 seconds elapsed. Root/graph/membership/buffer storage also counts
toward the aggregate budget; no streaming or compression loophole. Use checked
addition/multiplication before reads/allocation; overflow/excess rejects OverBudget.
Policy MAY lower but MUST NOT enlarge caps; zero/unknown caps mean
Unknown(UnqualifiedCoverage). Unavailable deadline enforcement is
Unknown(UnobservableInput). A failed attempt emits no partial positive result.

Public results are exactly #155's enum-only `ObservedUntrusted`,
`Unknown(MissingNomination|UnqualifiedCoverage|UnreadableInput|UnobservableInput|UnstableSnapshot)`
and `Reject(OverBudget|UnsafeTraversal|Conflict|IdentityMismatch|GenerationChanged|PrivacyViolation)`.
Select (1) OverBudget; (2) UnsafeTraversal then PrivacyViolation; (3) Unknown reasons
in displayed order; (4) Conflict, IdentityMismatch, GenerationChanged; (5)
ObservedUntrusted. Within a stage use #155 coverage-table order, then canonical
entry order; never enumeration order. Only established findings participate; do not
probe unsafe inputs to discover later failures. No public hashes, source, real paths,
prompts, argv, environment, credentials or private policy; retain bounded ephemeral
private state only. This does not change #153 comparison/decoder precedence.

**Synthetic reference vector (offline model only).** The following executable
Python pseudocode defines every byte of one positive framing vector: independent
fake policy `p`, nongit root `r`, root directory and nonexecutable file `a` containing
`x`. Its fake external closure/host/metadata guarantees are assumed, never inferred
from `p`. With these separate assumptions it models ObservedUntrusted only.

```python
from hashlib import sha256
u8 = lambda n: n.to_bytes(1, 'big')
u16 = lambda n: n.to_bytes(2, 'big')
u32 = lambda n: n.to_bytes(4, 'big')
u64 = lambda n: n.to_bytes(8, 'big')
B = lambda x: u32(len(x)) + x
L = lambda xs: u32(len(xs)) + b''.join(B(x) for x in xs)
F = b'codex-smart/current-source-file/v1\0'
D = b'codex-smart/current-source-manifest/v1\0'
c = sha256(F + u64(1) + b'x').digest()
root = B(b'r') + u8(1) + B(b'')
entry = lambda p,k,v: u8(1) + B(b'r') + B(L(p)) + u8(k) + B(v)
e0 = entry([], 2, L([B(b'a') + u8(1)]))
e1 = entry([b'a'], 1, u8(0) + u64(1) + B(c))
M = D + u16(1) + B(b'p') + L([root]) + L([e0,e1])
assert len(M) == 178
assert c.hex() == 'c2586d2caf753b40fd3dfeef9547a73545ecafdfd501c8d43021d412b1bf16a8'
assert sha256(M).hexdigest() == '3a90e011e2e94c4a9a61f9ff7ec591860a1c54df0eca87c487b41f0f7016f31b'
```

| Single mutation of qualified fake baseline (other prerequisites held) | Expected enum |
| --- | --- |
| Remove independent nomination / semantic completeness evidence | Unknown(MissingNomination) / Unknown(UnqualifiedCoverage) |
| Self-inconsistent member/record set, duplicate path/role or invalid encoding | Reject(Conflict) |
| Remove/add a relevant entry or directory member against a prior held baseline | Reject(IdentityMismatch) |
| Required file absent/unreadable; required Git object missing | Unknown(UnreadableInput); Unknown(UnobservableInput) |
| Relevant ignored/generated input excluded or missing from policy closure | Unknown(UnqualifiedCoverage) |
| Stale index claim vs held index bytes; changed staged blob or mode | Reject(IdentityMismatch) |
| Malformed framing/Git/index, wrong version/enum/order, trailing bytes | Reject(Conflict) |
| Index stages 1–3; sparse checkout | Reject(Conflict); Unknown(UnqualifiedCoverage) |
| Case/path alias, known collision, duplicate root or object identity | Reject(Conflict) |
| Slash/NUL/dot/dot-dot component, symlink/ancestor link, escape | Reject(UnsafeTraversal) |
| File becomes directory vs held snapshot; executable/ACL/other bound metadata changes | Reject(IdentityMismatch) |
| Hardlink count >1, FIFO/device/socket, crossed/substituted mount | Reject(UnsafeTraversal) |
| Submodule gitlink only; LFS pointer without relevant content | Unknown(UnqualifiedCoverage) |
| Changed file bytes; same bytes but replaced object | Reject(IdentityMismatch) |
| Non-UTF8 name exposed exactly (reframe member/path consistently) | ObservedUntrusted |
| Unsupported name/case semantics or mount/object observation API | Unknown(UnobservableInput) |
| 4,097 entries, 16 MiB+1 file, 128 MiB+1 total, 65 components, >30s or overflow | Reject(OverBudget) |
| Candidate write race without qualified isolation, even two equal scans | Unknown(UnstableSnapshot) |
| Generation changes between capture/revalidation; TOCTOU after revalidation | Reject(GenerationChanged); Unknown(UnstableSnapshot) without atomic-use evidence |
| Forbidden private access/output; overbudget plus missing nomination | Reject(PrivacyViolation); Reject(OverBudget) |

These are proposed vectors, not implemented collector tests. This new manifest's
limits/bytes are separate from #137 envelope v1's 16 KiB E / 64 KiB combined caps,
S/K encoding and existing receipt digest. `BindingClaims.source` (E tag `14`) remains
an untrusted 32-byte claim: no automatic manifest conversion is specified.
`ParseOnly`, evidence binding and `compare_evidence` are unchanged; independent
policy, host qualification and atomic-use evidence remain blockers, not promises.

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
# S schema + executable STR16 + pin + three versions + two identities,
# immediately before its argc. The compound variants keep argc=3 but
# change the first two Word arguments; the third is deliberately absent.
S_ARG_PREFIX = 2 + len(s(b"/bin/true")) + 32 + 12 + 64
assert S[S_ARG_PREFIX] == 3
S_AGG_OVERFLOW = (S[:S_ARG_PREFIX] + b"\x03"
                  + b"\x01" + s(b"A"*3000) + b"\x01" + s(b"B"*2000))
S_TRUNC_ARG = (S[:S_ARG_PREFIX] + b"\x03"
               + b"\x01" + s(b"A"*3000) + b"\x01" + n(2000,2) + b"B"*1000)
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
 ("V23", D[:-1]+b"?",b"",b"", "UnsupportedDomain"),
 ("V24", change(18,b"\x00\x02"),b"",b"", "UnsupportedSchema"),
 ("V25", E0[:len(D)+2]+b"\x1b",b"",b"", "Truncated"),
 ("V26", E0[:len(D)+2]+b"\x1b\x00\x01",b"",b"", "UnknownField"),
 ("V27", D+b"\x00",b"",b"", "Truncated"),
 ("V28", change(18,S_AGG_OVERFLOW),b"",b"", "MalformedValue"),
 ("V29", change(18,S_TRUNC_ARG),b"",b"", "Truncated"),
 ("V30", change(18,b"\x00\x01\x04\x01"),b"",b"", "MalformedValue"),
 ("V31", change(18,b"\x00\x01\x04\x00"),b"",b"", "Truncated"),
 ("V32", change(18,b"\x00\x01\x04"),b"",b"", "Truncated"),
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
| V23 | Wrong complete D (replace terminal NUL by `?`), with both version bytes absent | UnsupportedDomain, not Truncated |
| V24 | Replace S with only the two-byte non-v1 schema `00 02` and no remaining S members | UnsupportedSchema, not Truncated |
| V25 | Supply a lone unknown tag `1b` after H, omitting both length bytes | Truncated, not UnknownField |
| V26 | Supply unknown tag `1b` and complete length `00 01` after H, but omit the value | UnknownField, not Truncated |
| V27 | Supply matching D and only the first header-version byte `00` | Truncated |
| V28 | In S, declare 3 args; decode complete Word texts of 3000 then 2000 bytes, with third arg absent | MalformedValue: aggregate exceeds 4096 before later truncation |
| V29 | In S, declare 3 args; decode complete 3000-byte Word, then 2000-byte Word length with only 1000 bytes supplied | Truncated: incomplete second arg precedes its aggregate addition |
| V30 | Replace S with schema `00 01`, declared executable STR16 length 1025 (`04 01`) and no payload | MalformedValue: length exceeds 1024 before missing payload |
| V31 | Replace S with schema `00 01`, declared executable STR16 length 1024 (`04 00`) and no payload | Truncated: in-range declared payload absent |
| V32 | Replace S with schema `00 01`, just first executable STR16 length byte `04` | Truncated: incomplete length prefix |

The deterministic reference output is `vectors 33 OK`; each vector is
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
