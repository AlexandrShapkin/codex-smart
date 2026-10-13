# Architecture

Two crates: `codex-smart-core` holds typed capability inventory, policy, config, migration and process planning; `codex-smart-cli` holds argument parsing and output. No second agent, custom MCP, vector database or local model.

Level A prepares capabilities, risk, reasoning and auditable fallback. Level B is one Codex session deciding implementation and verification. Explicit task hints precede costly discovery. Pure decisions accept an inventory; host adapters never leak into unit tests.

Router v2's separate task/risk foundation accepts structured explicit hints and cheap
already collected semantic facts, then returns typed task, risk, ambiguity and stable
reasons. Its pure boundary excludes repository size, capability selection and reasoning
effort. The separate pure decision engine consumes this assessment, explicit capability needs
and one normalized evidence snapshot. Native tools remain the baseline; only caller-verified
augmentations may be selected. Offline evidence never fabricates verified readiness.
Pure reasoning selection uses the same authoritative assessment, a resolved explicit
override and independent CLI/model support evidence. A separate bounded OS-argv planner
models compatible injection and user override preservation without launching Codex.
A finite fallback/evidence plan consumes these decisions and preserves typed verification
obligations under degraded capabilities, ambiguity and incompatible reasoning. It directs
required evidence, while the Codex session owns file, command and implementation choices.
The legacy preview and passthrough launch stay unchanged until controlled integration. See [routing](routing.md).

Read-only commands inspect bounded PATH and local filesystem evidence. Doctor additionally reads bounded local Git config and explicitly supplied Codex TOML without executing tools or following referenced stores; see [the Doctor contract](doctor.md). Presence is distinguished from readiness. MCP, index health and auth are unknown until a future explicitly controlled compatibility probe can validate them without mutation. Runtime version strings are not obtained by launching arbitrary wrappers.

The process layer resolves an absolute executable path, records file metadata, rechecks it before execution and uses `Command` without a shell. Unix replaces the launcher with Codex so terminal/signals/exit code are preserved. Argument bytes, including non-UTF8, are passed unchanged. Read-only dry-run omits argument values. This is passthrough execution: preview policy is not enforced against unverified MCP integrations.

PATH lookup is bounded to 64 absolute directories and 16 KiB of PATH. Relative/repository paths and group/world-writable entries are rejected. Ownership, ancestor-directory trust and race-free descriptor execution are not yet guaranteed; the metadata recheck narrows but does not eliminate TOCTOU. Linux is the initial supported execution platform; non-Unix discovery fails closed pending platform adapters.

Own configuration resolution is deterministic and read-only; transactional changes are a separate explicit config command. See ADR-0005 and configuration.md for crash recovery, filesystem invariants and concurrency limits. Preview policy still does not activate MCP or inject launch settings.


External evidence is typed independently: Availability, declared/runtime version,
reference execution contract, Compatibility and Readiness. Artifact pins are restricted
to explicitly requested Codex launches; see [ADR-0007](decisions/0007-owned-executable-pins.md)
and [the command/transport matrix](tool-compatibility.md). No handshake or installer is
part of normal startup. Hash verification narrows execution races without eliminating them.

## Future target: two deterministic planes

The implemented architecture above remains the current behavior. The roadmap target
adds workflow intelligence without a second general autonomous agent:

```text
Execution plane
Task Assessment → Playbook Selector → Resource Planner → Execution Controller
                                                        ↓
                                                      Codex
                                                        ↓
                                                     Validator
                                                        ↓
                                              Escalation / completion

Lifecycle plane
Installer · Updater · Migration · Rollback · Release metadata
Compatibility verification · Doctor
```

Router assessment feeds the implemented pure workflow planner. The v1 playbook semantic
contract in `codex-smart-core::playbook` defines eleven bounded archetypes. The planner
in `codex-smart-core::workflow` selects only from typed Router evidence plus optional
explicit archetype intent: generic edits remain `NeedsEvidence`, while inspection,
refactor and explicit security-safety cases have deterministic mappings. Risk floors
can only raise profile/reasoning requirements.

Resource planning is also pure and lazy. Required native capability state must be
verified before a plan is ready. External capabilities are optional augmentations and
unknown/unavailable/blocked state can never become prepared state by assumption. A
planned external resource carries typed identity, exact version, scope, owner, validity,
invalidation, privacy and cleanup metadata. The only mutation-like plan dispositions
are `PrepareOwned` and `RefreshOwned`, both restricted to Codex-Smart-owned resources;
user/provider-owned absent or stale resources fall back to native. No planner function
installs, authenticates, changes configuration or invokes a tool/model.

The adaptive controller remains future work and will respond to independent validation
evidence with bounded escalation. Lifecycle operations never become model-routing
decisions. Minimize expected total lifecycle cost subject to required quality, safety
and verification, rather than single-call token count. Validation application,
explainability, telemetry boundaries and replaceable profile/model mapping are in
[workflow intelligence](workflow-intelligence.md),
[distribution](distribution.md) and [ADR 0008](decisions/0008-deterministic-workflows.md).
Production launch behavior is unchanged; #42 remains the validation/explain slice.
