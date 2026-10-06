# Complete offline diagnostic contracts

## Scope

Complete offline typed evidence, explicit single-file Codex configuration analysis, separate filesystem/Git/network access checks and conservative index markers.

## Non-goals

No indexing, tool execution, auth reads, global config changes or invented health.

## Acceptance

Offline inventory and version evidence are clear; unsupported, absent and unprobed states are distinguished; golden and filesystem regressions pass.

## Validation

just context doctor; just check; just nextest; just deny. Human/JSON goldens and isolated filesystem/privacy regressions; just docs-sync/check with idempotence.

## Context

Read [docs/doctor.md](../../docs/doctor.md), [docs/tooling.md](../../docs/tooling.md), [docs/configuration.md](../../docs/configuration.md), [docs/issues/04.md](../../docs/issues/04.md). Start with `just context doctor`; follow source entry points only as needed.

## Follow-ups

Readiness requires trustworthy evidence. Unprobeable MCP/auth/index states stay unknown; no active probes until reviewed read-only contracts exist. Evidence: [Doctor validation](../diagnostics/2026-10-06-doctor.md).
