# Adaptive model routing and runtime escalation

Status: active 0.5 Adaptive Execution; not implemented. Playbooks 0.4 dependency is accepted.

## Goal

Begin with the least expensive reasonably capable profile and escalate only on evidence, subject to required quality and risk floors.

## Context

Read [workflow intelligence](../workflow-intelligence.md), [architecture](../architecture.md), [ADR 0008](../decisions/0008-deterministic-workflows.md) and [distribution](../distribution.md). Start with `just context adaptive`; live actionable state remains in GitHub Issues.

## Current state

Router v2 and the single native-first Codex launch are delivered. Workflow playbooks, adaptive execution, reusable automation and install/update tooling are not implemented. The representative 40-run campaign has executed on the accepted split-host boundary and produced the accepted measured baseline `ffd8fbbc...`; the historical 42-job campaign remains unexecuted. Submitted-code production grading and representative technical readiness are verified.

## Target state

A bounded typed controller for initial profile selection, progressive reasoning/model escalation, retries, validation feedback, handoffs and completion.

## Scope

Explicit failure/ambiguity/risk/validation triggers; bounded retries and delegation; compressed evidence-preserving handoff; strong-model final review where required; measured lifecycle economics.

## Invariants

Minimize expected total lifecycle cost subject to required quality, safety and verification. Never intentionally reduce required quality. Typed deterministic plans, bounded state machines and observable conditions; Codex remains the reasoning engine. Cheap-first is not universal: high-risk, architecture/security-sensitive or ambiguous work may start strong. Profile classes are separate from replaceable verified provider mapping and concrete benchmark pins. Failed cheap attempts remain evidence.

## Out of scope

Implementation in this roadmap PR, benchmark execution, invented results, hidden installation, authentication mutation, global configuration changes and a second general autonomous agent.

## Non-goals

No opaque LLM policy planner, production routing from fixture size/language, required source/prompt logging or automatic stage advancement.

## Implementation constraints

Use the thin Rust control plane and existing argument/configuration safety contracts. Unknown/unavailable/incompatible capabilities stay unready. Keep current and planned behavior distinct. Future work starts only after dependencies are accepted, in bounded reviewed slices with isolated fake environments. Changes to benchmark variants/pins need a separate reviewed campaign contract.

## Acceptance

Risk floors and budgets enforced; every transition explainable; no lower-quality price optimization; bounded narrow delegation with authority/time/cost/context limits and independent validation.

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
