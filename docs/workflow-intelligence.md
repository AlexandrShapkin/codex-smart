# Workflow intelligence target

Status: Playbooks 0.4 is implemented and accepted; Adaptive Execution 0.5 is the next active stage. #14 measured benchmark and #15 aggregate telemetry are accepted. Router v2 and the single Codex launch remain production behavior. Playbooks now provides typed workflow semantics, pure deterministic selection/resource planning, bounded native validation recipes and enum-only explanation. These contracts do not prepare resources, execute tools, enable adaptive execution/delegation or authorize model calls.

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

The controller may escalate reasoning effort or model capability on ambiguity,
failure, risk or validation evidence. Cheap/low → medium → strong/high describes a
possible path, not a universal starting rule. Architecture, security, ambiguity or
high-risk changes may start strong. Planned controls include bounded retries,
validation-driven escalation, compressed handoffs and strong final review where
required. Budgets and terminal outcomes must be explicit and inspectable.

Future bounded delegation may suit narrow read-only inspection, mechanical
transformation, selected-context summarization, simple deterministic repair or
search. It must not assume cheap delegation is suitable for security decisions,
concurrency reasoning, destructive migrations, ambiguous API design or conflicting
final evidence. Each delegation needs bounded authority, context, cost/time,
validation and evidence-preserving handoff. No delegation is implemented here.

Measure quality, total lifecycle tokens, estimated cost, latency, escalation rate,
failed-cheap-attempt rate, strong-model-avoided rate and handoff overhead. Price
alone cannot select a policy that compromises required quality.

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
