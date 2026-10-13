# Production security and reliability hardening

Status: planned 0.8 Hardening; not implemented. Dependencies: adaptive, automation, distribution.

## Goal

Verify security, supply-chain and reliability of the functional pre-1.0 contracts without adding product features to satisfy hardening.

## Context

Read [workflow intelligence](../workflow-intelligence.md), [architecture](../architecture.md), [ADR 0008](../decisions/0008-deterministic-workflows.md) and [distribution](../distribution.md). Start with `just context hardening`; live actionable state remains in GitHub Issues.

## Current state

Router v2 and the single native-first Codex launch are delivered. Workflow playbooks, adaptive execution, reusable automation and install/update tooling are not implemented. The representative 40-run campaign has executed on the accepted split-host boundary and produced the accepted measured baseline `ffd8fbbc...`; the historical 42-job campaign remains unexecuted. Submitted-code production grading and representative technical readiness are verified.

## Target state

Reviewed threat model, compatibility matrix, privacy/supply-chain audit and failure recovery evidence for adaptive execution, automation and distribution.

## Scope

PATH ownership/ancestor trust and final executable-path races; installer/updater security, resource bounds, races, transaction recovery, performance, failure injection, upgrade/downgrade rehearsal and long-running reliability; optional telemetry/privacy review.

## Invariants

Minimize expected total lifecycle cost subject to required quality, safety and verification. Never intentionally reduce required quality. Typed deterministic plans, bounded state machines and observable conditions; Codex remains the reasoning engine. No new product feature merely for hardening. Unknown security evidence is not readiness; no private source/prompt/credential/payload logging requirement; qualified submitted-code grading remains mandatory.

## Out of scope

Implementation in this roadmap PR, benchmark execution, invented results, hidden installation, authentication mutation, global configuration changes and a second general autonomous agent.

## Non-goals

No opaque LLM policy planner, production routing from fixture size/language, required source/prompt logging or automatic stage advancement.

## Implementation constraints

Use the thin Rust control plane and existing argument/configuration safety contracts. Unknown/unavailable/incompatible capabilities stay unready. Keep current and planned behavior distinct. Future work starts only after dependencies are accepted, in bounded reviewed slices with isolated fake environments. Changes to benchmark variants/pins need a separate reviewed campaign contract.

## Acceptance

Independent security and supply-chain review; execution-race limits resolved or explicit; artifact/checksum validation and release reproducibility limits documented; supported compatibility matrix verified; recovery and race failures handled; resource/performance budgets measured; privacy findings reconciled with separate #15.

## Validation

Repository checks plus isolated threat/failure controls, transaction interruption, execution races, bounded resource and long-running tests, supported upgrade/downgrade and release rehearsal. Run repository-native docs/check/nextest gates, inspect all diffs and record exact-head CI/review. No model execution or publication without separate explicit authorization.

## Documentation updates

Update architecture, semantic contracts, explain/configuration guidance and owned registries as implementation becomes real. Generate ROADMAP/index via `just docs-sync`; never claim target behavior is delivered merely because a plan exists. Preserve historical ADRs and benchmark evidence.

## Issue reconciliation

Stage issues: #53, #54. Keep one area, one severity, at most one stage and one work-kind. #14 owns benchmark acceptance; #15 telemetry remains separate; #16 retains release/migration history; #17 owns final readiness. GitHub owns live dependency and closeout state.

## Closeout

Reconcile each issue against concrete implementation and independent evidence. Record exact-head check/review from GitHub Actions app 15368 and Security. Update recorded progress only after acceptance; do not advance the active stage or publish a version implicitly.

## Follow-ups

Next dependent stage begins after explicit acceptance. Unresolved quality, security, compatibility or measurement gaps stay visible and fail closed.
