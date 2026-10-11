# Workflow intelligence target

Status: future design, not delivered behavior. The active stage remains benchmark;
#14 owns measurement and #15 owns separate aggregate telemetry. The current Router
contract and single Codex launch remain implemented behavior. This target does not
enable adaptive execution, delegation, prepared resources or model calls.

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
preparation. The initial profile must be minimally sufficient for the workflow,
then deterministic validation supplies evidence for bounded escalation or
completion. Selection is not a heuristic based on LOC, language or repository size.

A future explain contract exposes the chosen workflow, initial model/profile,
reasoning effort, context sources, capabilities/tools, preparation, validation
obligations, escalation conditions and fallback. Unknown, incompatible or
unavailable capabilities never become ready by assumption. Read-only explain and
doctor retain their existing side-effect boundaries.

## Playbook semantics

The future typed contract may describe the following semantics; exact Rust APIs
remain for reviewed implementation work.

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

Initial archetypes may include read-only inspection, focused bug fix, failing-test
repair, feature implementation, API change, refactor, security-sensitive change,
CI/config repair, dependency update, documentation change and release preparation.
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
workflow requires. Prepared state needs identity/version, scope, owner, validity,
invalidation, privacy and cleanup. Invalidate on repository identity, relevant
HEAD/config changes, tool/playbook/capability/schema version changes and explicit
reset. Inspect and reset must be possible; stale state cannot silently remain ready.

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
implementations exist. No variants or results are fabricated. Historical preliminary
42-job and representative 40-call plans remain unchanged and unexecuted; submitted-code
grading still requires a separately qualified isolation host. Representative readiness
remains false. No savings or winner claim exists.

#15 stays separate. Optional aggregate evaluation may record workflow/profile,
escalation yes/no, validation pass/fail, retry counts and bounded token/cost/latency
counters. Adaptive routing must function when private telemetry collection is disabled.
Neither optimization nor telemetry requires source, prompts, credentials or arbitrary
tool payload storage. Privacy review precedes any new collection contract.
