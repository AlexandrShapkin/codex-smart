# Complete offline diagnostic contracts

## Scope

Complete explicit configuration, capability compatibility, permission and index-health diagnostics.

## Non-goals

No indexing, tool execution, auth reads, global config changes or invented health.

## Acceptance

Offline inventory and version evidence are clear; unsupported, absent and unprobed states are distinguished; golden and filesystem regressions pass.

## Validation

just context doctor; just check. Golden diagnostics and isolated metadata/content snapshots.

## Context

Read [docs/tooling.md](../../docs/tooling.md), [docs/configuration.md](../../docs/configuration.md), [docs/issues/04.md](../../docs/issues/04.md). Start with `just context doctor`; follow source entry points only as needed.

## Follow-ups

Readiness requires trustworthy evidence. Unprobeable MCP/auth/index states must stay unknown.
