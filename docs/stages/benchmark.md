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
host qualification. The 40-run representative campaign is now measured; its normalized
result is the accepted measured baseline `ffd8fbbc...` and makes no winner or savings claim.

Current-host capability investigation is complete: the development host remains
non-qualified and is not a submitted-code grading target. A separate host receipt is
accepted together with exact agent-isolation evidence, the constrained grading backend,
and production submission-grading evidence `199ec772...`. The production grader uses
descriptor-relative no-follow reads into private tmpfs, a private verdict socket and
cgroup-empty cleanup. The representative runner now requires and fully rehashes the
reviewed staged runtime before the authorization gate.

`representative_campaign_ready` is true for the frozen technical contract, supported by
credential-free readiness evidence `ea86c70f...`, but this is not execution authorization:
the offline plan still reports `model_execution_enabled=false` and the only real entry
still requires explicit `--authorize-execution`, exact runtime and inventory paths,
reviewed qualification evidence, exact Codex identity, exact toolchains from the staged
runtime (never host `PATH`) and a fresh private artifact target. A separate frozen
one-execution representative smoke uses `python-billing`/`vanilla`, retries zero and its
own `--authorize-smoke-execution`; it is excluded from the 40 primary executions and
comparative metrics. The corrected split-host smoke and the authorized 40-run representative campaign have
executed. All 40 jobs reached a terminal record with zero retries; 36 submissions were
exported and all 36 passed the accepted production grader. Strict pass rates remain
95% vanilla and 85% native because failures stay in the denominator; two of the native
agent failures were provider-capacity errors and each variant had one timeout. The normalized measurement evidence `ffd8fbbc...` is accepted; it deliberately records
no winner or savings claim. The current development host is not a submitted-code
grading target. See [host/runner contract](../benchmark-host.md). #14 benchmark acceptance and #15 privacy-preserving aggregate telemetry are complete.
The accepted baseline is `ffd8fbbc...`; the sanitized telemetry snapshot is
`359b01bc...`. The next active stage is Playbooks 0.4; future model-backed measurements
remain separately authorized.
