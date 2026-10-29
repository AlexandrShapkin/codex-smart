# Reusable automation and prepared workflows

Status: planned 0.6 Reusable Automation; not implemented. Dependencies: adaptive.

## Goal

Make recurring development workflows cheaper and more deterministic without opaque learning or a background agent.

## Context

Read [workflow intelligence](../workflow-intelligence.md), [architecture](../architecture.md), [ADR 0008](../decisions/0008-deterministic-workflows.md) and [distribution](../distribution.md). Start with `just context automation`; live actionable state remains in GitHub Issues.

## Current state

Router v2 and the single native-first Codex launch are delivered. Workflow playbooks, adaptive execution, reusable automation and install/update tooling are not implemented. The representative 40-run campaign has executed on the accepted split-host boundary and produced the accepted measured baseline `ffd8fbbc...`; the historical 42-job campaign remains unexecuted. Submitted-code production grading and representative technical readiness are verified.

## Target state

Versioned explicit repository/workflow profiles, justified prepared capability/index/cache state, deterministic setup/validation fast paths, inspection and reset.

## Scope

Recurring dependency update, generated-client refresh, CI repair, regression tests, release preparation and issue-to-implementation-to-validation-to-PR; deterministic known routine steps with LLM reasoning only where needed.

## Invariants

Minimize expected total lifecycle cost subject to required quality, safety and verification. Never intentionally reduce required quality. Typed deterministic plans, bounded state machines and observable conditions; Codex remains the reasoning engine. User-defined profiles always possible. Automatic promotion must be local, explainable, versioned, reversible, privacy-reviewed and evidence-gated. No daemon, arbitrary source/prompt cache or hidden install.

## Out of scope

Implementation in this roadmap PR, benchmark execution, invented results, hidden installation, authentication mutation, global configuration changes and a second general autonomous agent.

## Non-goals

No opaque LLM policy planner, production routing from fixture size/language, required source/prompt logging or automatic stage advancement.

## Implementation constraints

Use the thin Rust control plane and existing argument/configuration safety contracts. Unknown/unavailable/incompatible capabilities stay unready. Keep current and planned behavior distinct. Future work starts only after dependencies are accepted, in bounded reviewed slices with isolated fake environments. Changes to benchmark variants/pins need a separate reviewed campaign contract.

## Acceptance

Prepared state records identity/version/scope/owner/validity/invalidation/privacy/cleanup; invalidation covers repository identity, relevant HEAD/config, tool/playbook/capability/schema changes and explicit reset; stale resources fail closed.

## Validation

Fake repeated-workflow runs and stale-state controls; ownership-safe cleanup/reset; offline capability tests; version migration and explicit profile override; lifecycle quality/cost evidence before any savings claim. Run repository-native docs/check/nextest gates, inspect all diffs and record exact-head CI/review. No model execution or publication without separate explicit authorization.

## Documentation updates

Update architecture, semantic contracts, explain/configuration guidance and owned registries as implementation becomes real. Generate ROADMAP/index via `just docs-sync`; never claim target behavior is delivered merely because a plan exists. Preserve historical ADRs and benchmark evidence.

## Issue reconciliation

Stage issues: #47, #48, #49. Keep one area, one severity, at most one stage and one work-kind. #14 owns benchmark acceptance; #15 telemetry remains separate; #16 retains release/migration history; #17 owns final readiness. GitHub owns live dependency and closeout state.

## Closeout

Reconcile each issue against concrete implementation and independent evidence. Record exact-head check/review from GitHub Actions app 15368 and Security. Update recorded progress only after acceptance; do not advance the active stage or publish a version implicitly.

## Follow-ups

Next dependent stage begins after explicit acceptance. Unresolved quality, security, compatibility or measurement gaps stay visible and fail closed.

Issue #163 / Draft PR #164 adds a source-only bounded supervisor experiment and
offline lifecycle proof. See the [pilot contract](../autodev-supervisor-pilot.md).
Runtime enrollment, activation and live integration remain unavailable; automation
stage acceptance is not established by the offline proof.
