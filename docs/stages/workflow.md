# Bounded roadmap and documentation context

## Scope

Provide a stable just surface, machine-readable stages, bounded context, ownership and generated views. Keep GitHub Issues as live actionable state.

## Non-goals

No runtime orchestration framework, second agent, online docs-check, automatic stage advance or duplicated live issue state.

## Acceptance

just context and just context tools emit at most 8192 UTF-8 bytes offline. docs-check rejects missing ownership, cycles, broken local links, incomplete contracts and generated drift. CI runs just check.

The [workflow normalization audit](../diagnostics/2026-10-14-workflow-normalization.md)
adds verified-main task isolation and source receipts through the same command
surface. Preserve existing checkouts/deployments; diagnostics stay read-only, remote
freshness stays unknown offline, and live benchmark execution needs separate authority.

## Validation

just docs-generate; just docs-check; just check. Isolated regression tests; dogfood context on #7; verify pushed CI.

## Context

Read [docs/PROJECT_WORKFLOW.md](../../docs/PROJECT_WORKFLOW.md), [docs/development.md](../../docs/development.md), [docs/decisions/0006-bounded-context.md](../../docs/decisions/0006-bounded-context.md). Start with `just context workflow`; follow source entry points only as needed.

## Follow-ups

Only explicit docs-generate writes the two generated views. Durable contracts require owner updates; context limits require deeper targeted reads when needed. Host connectivity and legacy snapshot identity must be verified by operators before selecting any new deployment; source receipts do not qualify runtimes or authorize model calls.
