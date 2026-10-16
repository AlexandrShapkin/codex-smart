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
