# Full development benchmark and aggregate telemetry

## Scope

Compare full bugfix/feature/test/refactor/API/CI/exploration lifecycles across Rust/Go/Python/IaC with independent quality and aggregate cost evidence.

## Non-goals

No performance claims from retrieval-only numbers; no private prompts/source/secrets in telemetry.

## Acceptance

Pinned scenarios, models and settings; wrong implementations fail independent tests; failures/retries/cold overhead retained; missing counters unknown; old baseline only when verified.

## Validation

just context benchmark; just check. Independent benchmark acceptance and privacy tests before cost comparisons.

## Context

Read [docs/benchmarking.md](../../docs/benchmarking.md), [docs/provenance.md](../../docs/provenance.md). Start with `just context benchmark`; follow source entry points only as needed.

## Follow-ups

The #14 harness supplies pinned public fixtures, independent graders and fake-run validation; no measured cost reduction is claimed. Progress remains partial. Writable startup and a real failed turn are now verified by the first writable-host smoke. Isolated config omitted keyring auth routing; the campaign explicitly pins that routing while preserving normal CODEX_HOME. Parser semantics accept non-terminal error events before exactly one completed or failed terminal turn. One additional bounded host smoke of the corrected command is required; live readiness remains blocked and the 42-run campaign unexecuted. Historical read-only startup diagnosis remains documented. #14 stays open; #15 production telemetry is separate.
