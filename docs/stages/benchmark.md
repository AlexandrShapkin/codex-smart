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

Harness/component coverage retains seven fixtures and the historical 42-job plan,
unchanged and unexecuted. The successful JSON-only IaC smoke verifies the Codex
execution contract; it is not comparative evidence. Ten distinct development tasks
now form a separate representative-development-v1 design with independent trusted
controls and a 40-primary-execution maximum (vanilla/native, two repetitions, zero retries).
Structural realism is strengthened with functional supporting context, hidden
dependency evidence, tier thresholds and pinned Cargo check/test controls. This is
purpose-built representative synthetic coverage, not large real-world repository
evidence. Coverage metadata is measurement-only. Review matrix acceptance independently of
host qualification; no measured result, winner or savings exists.

Current-host capability investigation is complete: systemd/cgroup-v2 present but
user resource manager/delegation unavailable and aggregate memory/tasks unverified.
Qualify a separate host with enforced aggregate limits, descendant cleanup, immutable
runtime inventory and complete filesystem/network/environment isolation. Submitted
code must not run on the authenticated host. Grading isolation remains required-not-verified,
representative_campaign_ready false, public real execution disabled. The matrix is
accepted and representative runner adapter prepared with fake-only
tests and pins. The typed host contract accepts no qualification receipts; both host
and grading isolation remain required-not-verified. Next qualify a separate host and
verify its isolated runtime/grader boundary before any separately authorized spending.
The current development host is not a candidate for further qualification work unless
its capabilities materially change. See [host/runner contract](../benchmark-host.md).
Benchmark stays partial, #14 open and #15 separate. See docs/benchmarking.md.
