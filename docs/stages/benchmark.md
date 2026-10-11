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

The #14 harness supplies compact pinned fixtures, independent graders and fake-run validation. One successful corrected bounded writable-host smoke now verifies startup, keyring auth routing, terminal parsing and independent grading. Live contract is verified and real runner prepared; representative_campaign_ready remains false because representative task coverage has not yet been accepted. All 42 planned jobs remain unexecuted and preliminary. Recommend accepting or expanding representative coverage before spending on those runs; see docs/benchmarking.md. Historical startup/auth failures remain documented. Progress remains partial, #14 open, and #15 production telemetry separate. No savings or winner is claimed.
