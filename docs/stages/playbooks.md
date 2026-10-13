# Workflow playbooks and resource planning

Status: active 0.4 Workflow Intelligence. Benchmark dependencies are accepted; the task-archetype semantic contract is the first implementation slice.

## Goal

Convert Router v2 assessment into a deterministic reusable development workflow plan.

## Context

Read [workflow intelligence](../workflow-intelligence.md), [architecture](../architecture.md), [ADR 0008](../decisions/0008-deterministic-workflows.md) and [distribution](../distribution.md). Start with `just context playbooks`; live actionable state remains in GitHub Issues.

## Current state

Router v2, accepted representative baseline `ffd8fbbc...`, privacy-preserving aggregate telemetry and #40 typed archetype semantics are delivered. #41 adds a pure deterministic selector/resource planner: generic edits do not get guessed into an archetype; required native unknown/unavailable state fails closed; optional external state can only become a typed reusable/preparable resource from complete verified evidence. The planner performs no preparation or production activation. #42 validation/explain remains; adaptive execution, automation and distribution are future stages.

## Target state

Typed playbook semantics, bounded archetypes and deterministic selection; explicit context/resource preparation and validation recipes with inspectable decisions.

## Scope

Inspection, bug fix, failing-test repair, feature/API/refactor/security/CI/dependency/docs/release archetypes; applicability, context obligations, required/optional capabilities, preparation, profile, validation, escalation, cleanup and fallback.

## Invariants

Minimize expected total lifecycle cost subject to required quality, safety and verification. Never intentionally reduce required quality. Typed deterministic plans, bounded state machines and observable conditions; Codex remains the reasoning engine. Native-first verified capabilities; lazy preparation; no hidden install/auth/global changes; no LOC/language/size routing heuristics. Exact Rust APIs remain an implementation decision.

## Out of scope

Implementation in this roadmap PR, benchmark execution, invented results, hidden installation, authentication mutation, global configuration changes and a second general autonomous agent.

## Non-goals

No opaque LLM policy planner, production routing from fixture size/language, required source/prompt logging or automatic stage advancement.

## Implementation constraints

Use the thin Rust control plane and existing argument/configuration safety contracts. Unknown/unavailable/incompatible capabilities stay unready. Keep current and planned behavior distinct. Future work starts only after dependencies are accepted, in bounded reviewed slices with isolated fake environments. Changes to benchmark variants/pins need a separate reviewed campaign contract.

## Acceptance

The stage has three separately reviewable slices: #40 typed archetype semantics is accepted; #41 implements the deterministic selector/resource planner; #42 remains validation recipes and explainable preparation. #41 acceptance requires typed-only selection, conservative ambiguity handling, monotonic risk floors, required-native fail-closed behavior, optional-external native fallback, and complete resource identity/version/scope/owner/validity/invalidation/privacy/cleanup. Full stage acceptance additionally requires validation recipes and explain output for workflow/profile/reasoning/context/tools/validation/escalation/fallback.

## Validation

Isolated fake capability environments and deterministic selection snapshots; bounded explain/context; validation recipe controls; quality benchmark evidence before claiming savings. Run repository-native docs/check/nextest gates, inspect all diffs and record exact-head CI/review. No model execution or publication without separate explicit authorization.

## Documentation updates

Update architecture, semantic contracts, explain/configuration guidance and owned registries as implementation becomes real. Generate ROADMAP/index via `just docs-sync`; never claim target behavior is delivered merely because a plan exists. Preserve historical ADRs and benchmark evidence.

## Issue reconciliation

Stage issues: #40, #41, #42. Keep one area, one severity, at most one stage and one work-kind. #14 owns benchmark acceptance; #15 telemetry remains separate; #16 retains release/migration history; #17 owns final readiness. GitHub owns live dependency and closeout state.

## Closeout

Reconcile each issue against concrete implementation and independent evidence. Record exact-head check/review from GitHub Actions app 15368 and Security. Update recorded progress only after acceptance; do not advance the active stage or publish a version implicitly.

## Follow-ups

Next dependent stage begins after explicit acceptance. Unresolved quality, security, compatibility or measurement gaps stay visible and fail closed.
