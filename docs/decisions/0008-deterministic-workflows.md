# ADR 0008: Deterministic workflow playbooks and bounded adaptive execution

Status: accepted planning direction; implementation and evidence remain future work.

## Context

Router v2 currently assesses task/risk and composes a native-first Codex launch.
The product objective spans completed development tasks: minimize expected total
lifecycle cost subject to required quality, safety and verification. A lower-price
model call can increase total cost through failed attempts, context duplication,
handoffs or insufficient validation. Benchmark acceptance is still partial and no
comparative savings have been demonstrated.

## Decision

Pursue deterministic workflow playbooks, lazy resource planning and bounded adaptive
execution around Codex. Prefer typed Rust state, explicit plans, validation recipes
and observable escalation conditions over a second autonomous LLM planner. Keep
current implemented behavior separate from this target. See the semantic contract
in [workflow intelligence](../workflow-intelligence.md).

Task assessment selects a playbook; resource planning prepares only verified needs;
the execution controller chooses a minimally sufficient risk-constrained profile;
Codex executes; deterministic validation supplies completion/escalation evidence.
Cheap-first is not universal. Required quality is never intentionally reduced.
Bounded delegation is a possible narrow mechanism, not a generic multi-agent platform.

Model/provider mapping remains replaceable and evidence-gated. Policy describes
capability classes and risk floors, while reproducible benchmark campaigns pin
concrete models independently. External tools, CodeGraph, Serena, Rhai, multiple
models and subagents are not required for 1.0 without evidence of benefit.

Keep install/update/migration/rollback/compatibility/doctor in a separate lifecycle
plane. No hidden installs, authentication mutation, opaque source learning or
required prompt/source/payload logging. Prepared state is versioned, scoped,
inspectable, invalidatable and disposable. Unknown evidence fails closed.

## Consequences

Add planned playbooks, adaptive, automation and distribution stages before hardening.
Implementation needs bounded contracts, isolated negative controls and lifecycle
benchmarks before savings claims. #14 remains the measurement foundation and #15
remains separate optional aggregate telemetry; neither current campaign is changed
or executed. Exact APIs, backend/model resolution and authenticity mechanisms await
reviewed stage work rather than being frozen in this roadmap decision.

## Alternatives

Static pre-launch routing alone cannot optimize repeated preparation or validation
feedback. A general autonomous planning agent adds opaque decisions and unbounded
handoff cost. Universal cheap-first ignores risk and required quality. This direction
instead makes known workflow work deterministic and preserves Codex as the
implementation reasoning engine.
