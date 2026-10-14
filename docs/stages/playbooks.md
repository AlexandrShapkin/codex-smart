# Workflow playbooks and resource planning

Status: validated 0.4 Workflow Intelligence. Benchmark dependencies and all three Playbooks slices (#40–#42) are accepted; Adaptive Execution is the next active stage.

## Goal

Convert Router v2 assessment into a deterministic reusable development workflow plan.

## Context

Read [workflow intelligence](../workflow-intelligence.md), [architecture](../architecture.md), [ADR 0008](../decisions/0008-deterministic-workflows.md) and [distribution](../distribution.md). Start with `just context playbooks`; live actionable state remains in GitHub Issues.

## Current state

Router v2, accepted representative baseline `ffd8fbbc...`, privacy-preserving aggregate telemetry and all 0.4 Playbooks slices are delivered. #40 defines the typed archetype semantics; #41 adds the pure deterministic selector/resource planner; #42 adds bounded native validation recipes plus the complete enum-only explain surface. Generic edits are not guessed into an archetype, required native state fails closed, optional external state cannot substitute for native validation, and preparation remains declarative. No playbook code executes tools, prepares resources, changes production launch behavior or authorizes model calls. Adaptive policy is now implemented in the active adaptive stage; production adaptive execution, automation and distribution remain future work.

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

The stage has three separately reviewable accepted slices: #40 typed archetype semantics, #41 deterministic selector/resource planning and #42 validation recipes/explainable preparation. Selection is typed-only with conservative ambiguity handling and monotonic risk floors. Required native capability state fails closed; optional external resources use native fallback and preserve complete identity/version/scope/owner/validity/invalidation/privacy/cleanup metadata. Validation is a separate native-only readiness recipe and can remain `NeedsEvidence` or `Blocked` even when preparation planning is ready. Explain output covers workflow/profile/reasoning/context/tools/preparation/validation/escalation/cleanup/fallback without source, prompt, credentials, runtime paths or execution authority.

## Validation

Isolated fake capability environments and deterministic selection snapshots; bounded explain/context; validation recipe controls; quality benchmark evidence before claiming savings. Run repository-native docs/check/nextest gates, inspect all diffs and record exact-head CI/review. No model execution or publication without separate explicit authorization.

## Documentation updates

Update architecture, semantic contracts, explain/configuration guidance and owned registries as implementation becomes real. Generate ROADMAP/index via `just docs-sync`; never claim target behavior is delivered merely because a plan exists. Preserve historical ADRs and benchmark evidence.

## Issue reconciliation

Stage issues: #40, #41, #42. Keep one area, one severity, at most one stage and one work-kind. #14 owns benchmark acceptance; #15 telemetry remains separate; #16 retains release/migration history; #17 owns final readiness. GitHub owns live dependency and closeout state.

## Closeout

Reconcile each issue against concrete implementation and independent evidence. Record exact-head check/review from GitHub Actions app 15368 and Security. Update recorded progress only after acceptance; do not advance the active stage or publish a version implicitly.

## Follow-ups

Playbooks 0.4 is accepted. Adaptive Execution 0.5 begins with #43; unresolved quality, security, compatibility or measurement gaps stay visible and fail closed.
