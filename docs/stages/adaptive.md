# Adaptive model routing and runtime escalation

Status: active 0.5 Adaptive Execution. #43 bounded execution state, #44 pure replaceable model/profile resolution and #45 bounded delegation/handoff policy are implemented. Profile-smoke evidence is accepted (#82), and an offline-tested benchmark runner is merged (#83). The comparative adaptive campaign has not run; production execution remains passthrough.

## Goal

Begin with the least expensive reasonably capable profile and escalate only on evidence, subject to required quality and risk floors.

## Context

Read [workflow intelligence](../workflow-intelligence.md), [architecture](../architecture.md), [ADR 0008](../decisions/0008-deterministic-workflows.md) and [distribution](../distribution.md). Start with `just context adaptive`; live actionable state remains in GitHub Issues.

## Current state

Pure Router v2 policy, the passthrough Codex launcher and Playbooks 0.4 contracts are delivered; native-first instruction results belong to the separate accepted benchmark. #43 now adds a pure bounded adaptive controller contract on top of a ready workflow plus ready validation recipe. It preserves workflow profile/reasoning floors, starts high-risk/security work at `Strong/High`, records every attempt outcome, requires independent validation before completion, and exposes explicit `Ready`/`Running`/`AwaitingValidation`/`NeedsEvidence`/`Completed`/`Blocked`/`Exhausted` states. #44 now adds a pure replaceable compatibility resolver: product policy keeps opaque `Economy`/`Standard`/`Strong` classes separate from provider/model identity; caller-supplied model descriptors must independently verify availability and Medium/High reasoning support. Resolution chooses the minimally sufficient verified class, may use a verified stronger class as a quality-safe fallback, and never treats Unknown as ready. Re-running resolution after a #43 transition supplies progressive routing without embedding commercial model names. #45 adds a separate policy-only single-child ledger for bounded read-only evidence or mechanical workspace subtasks: opaque context/scope handles, explicit time/cost/output ceilings, no nesting, fail-closed high-risk/hazard checks, retained failures/protocol violations and advisory handoffs that require parent review. Production argv/runtime application, actual retry execution and child-process execution remain unimplemented pending evidence. For #46, a benchmark-only Rust replay adapter now exercises the actual #43/#44 policy over the same ten representative scenarios. The frozen adaptive measurement uses two repetitions, at most two attempts per job and one retry, so 20 adaptive jobs can start at most 40 Codex executions. The profile map is Economy → `gpt-6-luna`, Standard → `gpt-6-sol`, Strong → `gpt-6-astra`. The separately authorized 3-execution profile smoke completed with zero retries; all three profiles exported submissions and passed production grading. Execution evidence `908a97f1...` is accepted as the profile-mapping execution proof. The accepted representative baseline remains `ffd8fbbc...`.

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
