# Router v2 composition and controlled integration

## Scope

Compose explicit task/risk hints and cheap facts; validate selected tool surface, reasoning overrides and bounded evidence escalation.

## Non-goals

No size-only policy, mandatory heavy MCP, hidden profile changes, custom agent or Rhai without demonstrated need.

## Acceptance

Router v2 Rust policy composition is validated: deterministic auditable decisions preserve supported explicit overrides, tests and impact analysis under missing capabilities. #13 is completed by the accepted ADR-0004 deferral. This acceptance does not claim production readiness or activation; all P0 safety gates still apply before future activation.

## Validation

just context router; just check. Pure decision tables and stubbed sessions for failure, ambiguity and supported argv.

## Context

Read [docs/routing.md](../../docs/routing.md), [docs/architecture.md](../../docs/architecture.md), [docs/decisions/0003-policy-preview.md](../../docs/decisions/0003-policy-preview.md), [docs/decisions/0004-rhai-deferred.md](../../docs/decisions/0004-rhai-deferred.md). Start with `just context router`; follow source entry points only as needed.

## Follow-ups

The #9 pure task/risk foundation is implemented separately from the existing preview;
see the [routing contract](../routing.md#router-v2-taskrisk-foundation-9).
The #10 pure capability decision engine is implemented with normalized readiness,
native baseline, typed explanations and stubbed sessions; see the
[routing contract](../routing.md#router-v2-capability-decision-engine-10).
The #11 pure reasoning policy and fake OS-argv planner are implemented separately
from production launch; see the
[reasoning contract](../routing.md#router-v2-reasoning-effort-selection-11).
The #12 pure fallback/evidence plan preserves verification under degraded decisions;
see the [fallback contract](../routing.md#router-v2-fallback-and-bounded-evidence-plan-12).
No automatic evidence execution or production Router activation is delivered.
The accepted [ADR-0004](../decisions/0004-rhai-deferred.md) completes #13 through
evaluation and documented deferral: Router v2 remains Rust-only. Merged policy
slices are [#27](https://github.com/AlexandrShapkin/codex-smart/pull/27),
[#28](https://github.com/AlexandrShapkin/codex-smart/pull/28),
[#29](https://github.com/AlexandrShapkin/codex-smart/pull/29) and
[#30](https://github.com/AlexandrShapkin/codex-smart/pull/30).

Production run remains passthrough. No automatic backend activation or production
Verified capability producer is delivered; reasoning argv planning stays separate
from launch. Independent benchmark evidence is next, with quality gates that can
reject the policy; no benchmark success or Rhai variant is assumed. Future
activation/hardening depends on measured evidence. Reconsidering Rhai requires the
evidence and safety gates in ADR-0004.
