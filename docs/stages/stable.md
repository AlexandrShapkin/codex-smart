# 1.0 readiness and durable public contracts

Status: planned 1.0 Stable; not implemented. Dependencies: hardening.

## Goal

Accept durable public contracts and a safe supported release lifecycle, not a quantity of features.

## Context

Read [workflow intelligence](../workflow-intelligence.md), [architecture](../architecture.md), [ADR 0008](../decisions/0008-deterministic-workflows.md) and [distribution](../distribution.md). Start with `just context stable`; live actionable state remains in GitHub Issues.

## Current state

Router v2 and the single native-first Codex launch are delivered. Workflow playbooks, adaptive execution, reusable automation and install/update tooling are not implemented. The representative 40-run campaign has executed on the accepted split-host boundary and produced the accepted measured baseline `ffd8fbbc...`; the historical 42-job campaign remains unexecuted. Submitted-code production grading and representative technical readiness are verified.

## Target state

Stable CLI/configuration/migration/playbook schema and supported Codex/platform compatibility; safe install/update/rollback and supported pre-1.0 upgrade path.

## Scope

Final contract review, quality evidence, adaptive-policy evidence for any savings claim, privacy/security review, supported matrix and release rehearsal.

## Invariants

Minimize expected total lifecycle cost subject to required quality, safety and verification. Never intentionally reduce required quality. Typed deterministic plans, bounded state machines and observable conditions; Codex remains the reasoning engine. CodeGraph, Serena, Rhai, multiple models and subagents are not mandatory absent demonstrated benefit. Roadmap milestones do not bump SemVer or authorize publication.

## Out of scope

Implementation in this roadmap PR, benchmark execution, invented results, hidden installation, authentication mutation, global configuration changes and a second general autonomous agent.

## Non-goals

No opaque LLM policy planner, production routing from fixture size/language, required source/prompt logging or automatic stage advancement.

## Implementation constraints

Use the thin Rust control plane and existing argument/configuration safety contracts. Unknown/unavailable/incompatible capabilities stay unready. Keep current and planned behavior distinct. Future work starts only after dependencies are accepted, in bounded reviewed slices with isolated fake environments. Changes to benchmark variants/pins need a separate reviewed campaign contract.

## Acceptance

All P0 and prerequisite acceptance evidence reconciled; explicit owner authorization at release boundaries; stable CLI/config/migration/workflow schemas documented; quality benchmark evidence; any adaptive savings backed by lifecycle measurements; privacy/security sign-off and successful release/upgrade rehearsal.

## Validation

Full supported acceptance matrix, clean-install/update/rollback/uninstall and upgrade rehearsal; exact-head check/review/Security; independent quality controls and measured evidence on a qualified host. Run repository-native docs/check/nextest gates, inspect all diffs and record exact-head CI/review. No model execution or publication without separate explicit authorization.

## Documentation updates

Update architecture, semantic contracts, explain/configuration guidance and owned registries as implementation becomes real. Generate ROADMAP/index via `just docs-sync`; never claim target behavior is delivered merely because a plan exists. Preserve historical ADRs and benchmark evidence.

## Issue reconciliation

Stage issues: #17, #55. Keep one area, one severity, at most one stage and one work-kind. #14 owns benchmark acceptance; #15 telemetry remains separate; #16 retains release/migration history; #17 owns final readiness. GitHub owns live dependency and closeout state.

## Closeout

Reconcile each issue against concrete implementation and independent evidence. Record exact-head check/review from GitHub Actions app 15368 and Security. Update recorded progress only after acceptance; do not advance the active stage or publish a version implicitly.

## Follow-ups

Version stays 0.1.0 unreleased until a separately authorized release. No stability claim or date before independent evidence. Unresolved quality, security, compatibility or measurement gaps stay visible and fail closed.
