# Router v2 composition and controlled integration

## Scope

Compose explicit task/risk hints and cheap facts; validate selected tool surface, reasoning overrides and bounded evidence escalation.

## Non-goals

No size-only policy, mandatory heavy MCP, hidden profile changes, custom agent or Rhai without demonstrated need.

## Acceptance

All P0 safety acceptance gates are satisfied before activation. Deterministic auditable decisions preserve supported explicit overrides, tests and escalation under missing capabilities.

## Validation

just context router; just check. Pure decision tables and stubbed sessions for failure, ambiguity and supported argv.

## Context

Read [docs/routing.md](../../docs/routing.md), [docs/architecture.md](../../docs/architecture.md), [docs/decisions/0003-policy-preview.md](../../docs/decisions/0003-policy-preview.md), [docs/decisions/0004-rhai-deferred.md](../../docs/decisions/0004-rhai-deferred.md). Start with `just context router`; follow source entry points only as needed.

## Follow-ups

Current reasoning/config remain preview. Rhai requires a separate ADR and enforced sandbox only if justified.
