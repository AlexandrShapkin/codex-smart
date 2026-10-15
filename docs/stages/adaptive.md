# Adaptive model routing and runtime escalation

Status: active 0.5 Adaptive Execution. #43 bounded execution state, #44 pure replaceable model/profile resolution and #45 bounded delegation/handoff policy are implemented. Profile-smoke evidence is accepted (#82), and an offline-tested benchmark runner is merged (#83). The comparative adaptive campaign has not run; production execution remains passthrough.

## Goal

Begin with the least expensive reasonably capable profile and escalate only on evidence, subject to required quality and risk floors.

## Context

Read [workflow intelligence](../workflow-intelligence.md), [architecture](../architecture.md), [ADR 0008](../decisions/0008-deterministic-workflows.md) and [distribution](../distribution.md). Start with `just context adaptive`; live actionable state remains in GitHub Issues.

## Current state

Pure Router v2 policy, the passthrough Codex launcher and Playbooks 0.4 contracts are delivered; native-first instruction results belong to the separate accepted benchmark. #43 now adds a pure bounded adaptive controller contract on top of a ready workflow plus ready validation recipe. It preserves workflow profile/reasoning floors, starts high-risk/security work at `Strong/High`, records every attempt outcome, requires independent validation before completion, and exposes explicit `Ready`/`Running`/`AwaitingValidation`/`NeedsEvidence`/`Completed`/`Blocked`/`Exhausted` states. #44 now adds a pure replaceable compatibility resolver: product policy keeps opaque `Economy`/`Standard`/`Strong` classes separate from provider/model identity; caller-supplied model descriptors must independently verify availability and Medium/High reasoning support. Resolution chooses the minimally sufficient verified class, may use a verified stronger class as a quality-safe fallback, and never treats Unknown as ready. Re-running resolution after a #43 transition supplies progressive routing without embedding commercial model names. #45 adds a separate policy-only single-child ledger for bounded read-only evidence or mechanical workspace subtasks: opaque context/scope handles, explicit time/cost/output ceilings, no nesting, fail-closed high-risk/hazard checks, retained failures/protocol violations and advisory handoffs that require parent review. Production argv/runtime application, actual retry execution and child-process execution remain unimplemented pending evidence. For #46, a benchmark-only Rust replay adapter now exercises the actual #43/#44 policy over the same ten representative scenarios. The frozen adaptive measurement uses two repetitions, at most two attempts per job and one retry, so 20 adaptive jobs can start at most 40 Codex executions. The profile map is Economy → `gpt-6-luna`, Standard → `gpt-6-sol`, Strong → `gpt-6-astra`. The separately authorized 3-execution profile smoke completed with zero retries; all three profiles exported submissions and passed production grading. Execution evidence `908a97f1...` is accepted as the profile-mapping execution proof. The accepted representative baseline remains `ffd8fbbc...`.

The explicitly invoked local preparation runtime now provides a dedicated Linux
worker, independently pinned descriptor execution, bounded inspection-only protocol
and actual parent supervision. It is a process-isolated offline evidence adapter,
not a hostile-code sandbox or production Adaptive/model runtime. See the
[architecture boundary](../architecture.md#supervised-preparation-boundary-explicit-local-runtime)
for post-spawn timing limits and process-lifetime cleanup ownership. Production
admission, retries, validation command execution and benchmark acceptance stay closed.

#102 adds a pure inspection-evidence binding evaluator, without a product adapter.
It checks a candidate against an independently supplied reviewed record and current
capability/source/configuration/tool identities, verifier and receipt digests, and a
validity interval capped at 300 seconds. Missing, declared, mismatched or expired
records stay Unknown. AcceptedInspection describes only that reviewed observation;
health, semantic sufficiency and execution authority remain unknown/ungranted.
No NativeSurface projection, receipt collection, tool probe or CLI join is added.
[#114](https://github.com/AlexandrShapkin/codex-smart/issues/114) adds pure v1
canonical SHA-256 hashing and an opt-in `assess_canonical` helper; existing `assess`
behavior is unchanged. The exact domain is `codex-smart/native-inspection/receipt/v1`
followed by NUL, then a one-byte read-files/search/git tag (1/2/3), four fixed
32-byte source/configuration/tool/verifier digests, and unsigned big-endian 64-bit
observation/expiry seconds. The receipt digest itself is excluded.
A self-computed hash and copied ReviewRecord do not independently authenticate an
observation or justify IndependentlyReviewed. The independent collector/attestation
boundary, current identity collection and trusted clock inputs are still missing.
No NativeSurface.Verified, runtime readiness, health, model execution or validation
rights follow from hashing; Adaptive stage acceptance remains outstanding.

## Target state

A bounded typed controller contract plus verified runtime adapters for progressive reasoning/model escalation, retries, validation feedback, handoffs and completion.

## Scope

Explicit failure/ambiguity/risk/validation triggers; bounded retries and delegation; compressed evidence-preserving handoff; strong-model final review where required; measured lifecycle economics.

The benchmark-only [split-host operator workflow](../adaptive-operations.md) composes
the existing runner and qualified grader with pinned source/SSH receipts, explicit
stage authority, non-replaying recovery and immutable archives. It does not implement
production retries/delegation, change frozen budgets, authorize a live campaign or
advance measured acceptance.

## Invariants

Minimize expected total lifecycle cost subject to required quality, safety and verification. Never intentionally reduce required quality. Typed deterministic plans, bounded state machines and observable conditions; Codex remains the reasoning engine. Cheap-first is not universal: high-risk, architecture/security-sensitive or ambiguous work may start strong. Profile classes are separate from replaceable verified provider mapping and concrete benchmark pins. Failed cheap attempts remain evidence.

## Out of scope

Implementation in this roadmap PR, benchmark execution, invented results, hidden installation, authentication mutation, global configuration changes and a second general autonomous agent.

## Non-goals

No opaque LLM policy planner, production routing from fixture size/language, required source/prompt logging or automatic stage advancement.

## Implementation constraints

Use the thin Rust control plane and existing argument/configuration safety contracts. Unknown/unavailable/incompatible capabilities stay unready. Keep current and planned behavior distinct. Future work starts only after dependencies are accepted, in bounded reviewed slices with isolated fake environments. Changes to benchmark variants/pins need a separate reviewed campaign contract.

## Acceptance

Risk floors and budgets enforced; every transition explainable; no lower-quality price optimization; #43 completion requires independent validation and retains failed attempts. #44 policy resolution and #45 bounded narrow delegation preserve provider independence, authority/time/cost/context limits and parent validation boundaries. #46 has accepted profile-smoke evidence and a merged offline-tested benchmark runner, but comparative measurement acceptance remains outstanding. Any campaign requires separate execution authorization; any savings claim requires independently accepted quality-equivalent lifecycle evidence. A closed issue does not satisfy these missing gates.

## Validation

Fake model/controller tests for escalation, refusal, exhausted budgets, validation failures and interruption; genuine implemented variants measured only on a qualified approved host. Report quality,total lifecycle tokens,estimated cost,latency,escalation,failed-cheap,strong-model-avoided and handoff overhead. Run repository-native docs/check/nextest gates, inspect all diffs and record exact-head CI/review. No model execution or publication without separate explicit authorization.

## Documentation updates

Update architecture, semantic contracts, explain/configuration guidance and owned registries as implementation becomes real. Generate ROADMAP/index via `just docs-sync`; never claim target behavior is delivered merely because a plan exists. Preserve historical ADRs and benchmark evidence.

## Issue reconciliation

Stage issues: #43, #44, #45, #46. Keep one area, one severity, at most one stage and one work-kind. #14 owns benchmark acceptance; #15 telemetry remains separate; #16 retains release/migration history; #17 owns final readiness. GitHub owns live dependency and closeout state.

## Closeout

Reconcile each issue against concrete implementation and independent evidence. Record exact-head check/review from GitHub Actions app 15368 and Security. Update recorded progress only after acceptance; do not advance the active stage or publish a version implicitly.

## Follow-ups

Next dependent stage begins after explicit acceptance. Unresolved quality, security, compatibility or measurement gaps stay visible and fail closed.

### Bounded preparation increment

An explicit core adapter now acquires nominated local file evidence and reuses the
existing validation recipe. [Architecture](../architecture.md#bounded-native-preparation-adapter)
owns limits, fail-safe behavior and remaining runtime joins. Production passthrough,
measurement acceptance and stage status remain unchanged. The local worker adds
post-spawn supervision; semantic sufficiency and approved validation execution remain
follow-up work.

### Supervision runtime increment

The supervision policy now drives an actual pinned Linux preparation worker with
bounded transport and a parent deadline after successful spawn. The per-obligation
report still confers no semantic coverage authority. Production admission always
refuses; validation argv is deferred pending approved command contracts. The
[architecture boundary](../architecture.md#supervised-preparation-boundary-explicit-local-runtime)
owns implemented behavior and missing confinement/verification/spawn guarantees.
This does not advance stage acceptance, live issue state, production routing or
measurement evidence.

The supervised preparation parent now isolates inherited descriptors in its forked
child before descriptor-pinned exec, while direct worker launches retain strict
bootstrap refusal. [ADR-0009](../decisions/0009-child-descriptor-isolation.md)
records the narrow unsafe helper and Linux 5.11 close-on-exec requirement. This is
CI/runtime isolation hardening within the current slice, not stage advancement.

### Plan-only integration increment and residual owners

[#93](https://github.com/AlexandrShapkin/codex-smart/issues/93) adds the explicit
inspection plan preview: typed assessment, deterministic workflow, lexical context
nominations and declared validation readiness, with unknown capability/model evidence
and no runtime effects. The [configuration contract](../configuration.md#explicit-inspection-plan-preview)
owns public options and bounds. Production passthrough and active stage status remain
unchanged. Closed #43–#46 preserve historical policy/offline acceptance.
[#94](https://github.com/AlexandrShapkin/codex-smart/issues/94) owns residual runtime
integration acceptance; [#95](https://github.com/AlexandrShapkin/codex-smart/issues/95)
owns separately authorized comparative lifecycle measurement. Milestone issue counts
do not constitute stage acceptance. [#92](https://github.com/AlexandrShapkin/codex-smart/issues/92)
tracks the bounded positive-control reliability investigation without release ownership.

### Explicit preparation CLI increment (#100)

[#100](https://github.com/AlexandrShapkin/codex-smart/issues/100), the first bounded
child of #94, joins the typed inspection plan to one independently pinned local worker
through explicit `prepare`. It reuses accepted pin/protocol/supervision and renders
only acquisition counts and enum outcomes, preserving unknown semantic sufficiency,
cleanup uncertainty and closed production admission. Ordinary run remains passthrough
and plan remains declarative. [Configuration](../configuration.md#explicit-supervised-inspection-preparation)
owns CLI bounds and exit meanings. Isolated regressions cover success, pin/scope
refusal, timeout, protocol/private-output failure and uncertainty rendering; the
existing pure supervision suite covers unreapable-child cleanup uncertainty.
No model/retry/escalation/validation/delegation or measurement is activated. Independent
technical review remains required; Adaptive stays active and #94/#95 remain residual owners.
