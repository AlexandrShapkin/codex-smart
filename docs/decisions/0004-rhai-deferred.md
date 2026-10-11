# ADR-0004: Rust-only Router v2 and evidence-gated Rhai deferral

Status: accepted — Rust-only for Router v2; Rhai deferred pending evidence.

## Context

Router v2 issues #9–#12 now provide typed task/risk assessment, deterministic
capability decisions, Medium/High reasoning policy, bounded OS-argv planning,
fallback/escalation modes, verification obligations and missing/degraded capability
explanations. Pure Rust decision functions and table-driven regression/stubbed
sessions validate deterministic rendered evidence and bounded context contracts.
Repository size does not drive policy. Policy execution has no hidden installs,
network, shell execution or runtime scripts.

No demonstrated requirement currently exists for user-authored rules, frequently
changing runtime policy, organization-specific scripting, or policy changes that
cannot reasonably be compiled in Rust.

## Decision

Router v2 0.2 remains Rust-only. Rust is the reference and production policy
representation; this decision does not activate Router policy in production launch.
Rhai is not integrated and no dependency or scripting framework is added.
Issue #13 is satisfied by evaluation and documented deferral, as its acceptance
allows. Rhai is deferred pending evidence, not permanently rejected.

## Rationale

Runtime scripting does not currently reduce demonstrated development or operating
cost. It would introduce sandbox enforcement, CPU/instruction/time and memory
limits, typed serialization, script schema/version compatibility, error/fallback
semantics, abuse testing, policy provenance and dependency/update maintenance.
Without a concrete benefit, this additional security and maintenance surface is
not justified by configurable policy alone.

## Consequences

The compiled Rust policy remains small, auditable and deterministic. Router v2
policy composition can be recorded as validated after #12 and this decision.
Production run remains passthrough: no automatic reasoning injection, backend
activation, production Verified capability producer or automatic evidence execution
is claimed. Independent end-to-end benchmark evidence is next; no Rhai benchmark
variant exists. Production activation/hardening must follow measured evidence.

## Reconsideration criteria

Reconsider only with concrete evidence that runtime scripting materially benefits
an explicit configurable-policy need, for example:

- Multiple real policy variants require changes without rebuilding.
- Benchmark or real usage shows Rust policy iteration is materially costly.
- Organization/user customization becomes an explicit product requirement.

A desire to make policy configurable alone is insufficient. Any reconsideration
must compare its demonstrated benefit against implementation and operating costs.

## Safety requirements if reconsidered

Integration would require a validated typed input/output boundary; no filesystem,
network, shell or process execution; bounded instruction/time and memory/data
budgets; deterministic behavior; and safe Rust fallback. Mandatory Rust safety
constraints remain authoritative and cannot be disabled by scripts.
Sandbox abuse, input validation and timeout/resource-limit tests must demonstrate
these guarantees before integration. Script provenance, schema/version and
error/fallback contracts must also be explicit.
