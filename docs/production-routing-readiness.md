# Production routing integration readiness

This is an offline preparation design and regression fixture, not activated routing.
It starts from verified accepted main
`5102c0ebefeb53c3dbd56021266b340524be7ad3` in the isolated
`chore/production-routing-readiness` worktree. The production CLI remains passthrough.
The [workflow intelligence contract](workflow-intelligence.md) owns policy semantics;
[ADR 0008](decisions/0008-deterministic-workflows.md) owns the accepted direction.
No roadmap acceptance or benchmark contract is changed.

## Why there is no demonstrated efficiency winner

The accepted [representative evidence](benchmarking.md) is Vanilla 19/20 versus Native
17/20 strict successes, with all 36 exported submissions passing independent production
grading. Native's two additional failures were provider-capacity failures. Matched
successful runs had about 19.44% fewer observed native tool calls, but observed calls
are a lower bound, not token, latency or cost evidence. Input-token counters were
incomplete and no reviewed price table establishes a lifecycle cost winner.

The Native variant appended a native-first instruction to the same model command.
It did not exercise the complete Router v2 → Playbooks → Adaptive execution path.
Therefore those results do not measure the prospective architecture. Conversely,
implementing pure policy contracts does not prove practical savings. Local models
are neither required nor supported by these findings as the missing prerequisite.

## Actual CLI call path and disconnected policy

`crates/codex-smart-cli/src/main.rs::main` → `execute` → the `run` arm → `launch` →
`LaunchPlan::prepare` → optional `require_pin` → `summary` (dry-run) or `execute`.
`process.rs::execute` rechecks executable metadata/checksum and uses OS argv; Unix
exec replaces the launcher and preserves terminal/signals/exit behavior. No router,
workflow, controller, context retriever or validation executor runs on this path.

`explain` separately resolves launcher config and read-only inventory, then calls the
older `routing::decide` diagnostic. It does not activate Router v2. Native inventory
discovery finds trusted executable candidates; a filename on PATH is not runtime
health/semantic capability verification. Read-only doctor/explain must retain that
distinction and never run discovered tools or prepare indexes.

| Component | Implemented policy | Missing production adapter / exact join |
| --- | --- | --- |
| Task classification | `routing::assessment::assess(RoutingFacts)`; semantic safety facts impose risk floors | Collect explicit user/config task intent and repository facts before `launch`; conflicting/unknown facts request evidence, never classify from fixture size or arbitrary prompt heuristics |
| Capability detection | `Inventory::discover`, tool-lock fingerprint checks; Router `CapabilitySurface` and `NativeSurface` distinguish Unknown/Verified | Separate explicit verification from read-only discovery; short-lived identity-bound receipts for approved native/tool/model capabilities |
| Playbook selection | `workflow::select_playbook`, `plan_workflow`, owned resource validity/invalidation | Resolve explicit archetype/intent, feed actual verified surfaces; expose plan and refusal before effects |
| Context | Playbook context obligations and `fallback::PlanEvidence::context_sufficient` | A bounded collector with file/byte/time limits, provenance and selected snippets; no repository-wide source stuffing or implicit external activation |
| Model/profile | `adaptive_routing::resolve_controller` with opaque descriptors, verified availability/reasoning; stronger compatible fallback | Reviewed provider/model string adapter plus exact executable/profile compatibility evidence. Benchmark model keys are not automatic production defaults |
| Reasoning | Pure reasoning policy and `routing::reasoning_args::plan_reasoning_args` preserve user overrides and defer ambiguous invocation | Compose with resolved target only after compatibility proof; reject conflicting profiles/targets or unsupported invocation grammar; never inject settings into passthrough |
| Execution | `AdaptiveController::from_workflow`, start/outcome/history/bounded budget | Durable session ledger, lock, subprocess supervisor for a separately explicit noninteractive mode; `Command::exec` cannot supervise retries after replacing the launcher |
| Validation | `WorkflowPlan::validation_recipe` readiness/obligations | Approved native command recipes executed independently, with trusted argv, identity, scope, time/output bounds; model completion alone never means success |
| Escalation | `observe_attempt`, `observe_validation`, NeedsEvidence/Blocked/Exhausted states; monotonic floors | Explicit bounded retry authority after known outcome + independent checks; re-resolve target and reuse verified bounded evidence, never replay uncertain execution |
| Telemetry | `scripts/benchmark_telemetry.py` optional aggregate-only benchmark accounting | Product-owned opt-in session aggregates with full attempts and unknown counters; separate preparation/retrieval/validation/transport/model durations, no prompts/source/auth logging |
| Ordinary fallback | Existing passthrough launcher and pure fallback obligations | Preserve default ordinary behavior. Before any attempt, fallback only where explicitly permitted without violating active floors. Active high-risk incompatibility blocks; a started uncertain attempt never triggers ordinary replay |

The new `tests/production_routing_readiness.rs` composes the genuine assessment,
Router/workflow, validation, controller and resolver types. It proves ready inspection,
unknown-evidence refusal, Strong/High safety floors and validation-driven escalation
with retained exhaustion history. Catalog/native evidence is synthetic; there is no
runtime launch, network, command selection, credential access or activation.

## Minimal reviewed integration sequence

1. **Explicit plan adapter and evidence boundary.** Add a separately opt-in plan-only
   command/API, leaving `run` untouched. Typed task/archetype/risk facts feed the
   existing policy; identity-bound verified capability/model receipts are independent
   of configuration hints. Unknown/ambiguous facts stay unready. Extend the composition
   fixture with public goldens for the supported task classes, override grammar,
   drift and refusal. Review before granting any execution authority.
2. **Bounded context + validation preparation.** Implement only native local collection
   first: target files/symbols, applicable AGENTS/constraints and nearest approved test
   recipe. Enforce a hard byte/file/time ceiling and scope/provenance; retrieve on
   demand and cache identity-bound facts, invalidating on source/config/tool changes.
   Do not install tools, index repositories, copy entire source or synthesize readiness.
   Validation commands stay declarative until explicitly approved execution. Measure
   collector overhead before proposing external augmentations.
3. **One-attempt operational adapter.** After review, support explicit noninteractive
   execution only, with pinned target/reasoning argv, private durable ledger, cancellation
   and independent validation. Preserve current interactive exec passthrough. Start
   with no model delegation and no automatic retry. Use fake process tests for all
   start/kill/resume boundaries; never accept cached metadata as new health proof.
4. **Bounded retry and measurement.** Add separately authorized controller escalation
   only after one-attempt behavior is accepted. Reuse sanitized prior work/evidence
   without duplicating context unnecessarily, preserve all failures and unknown metrics,
   and cap budgets/time/output for the complete lifecycle. A transport or provider
   uncertainty is not permission to retry. Enable comparative measurement only through
   a separate reviewed campaign using actually implemented, pinned variants.

Do not wire the benchmark orchestrator into production `run`; it is specialized
20-job measurement control. Reuse invariants and the existing pure Rust contracts,
not benchmark hardcoded profiles, SSH roles, synthetic inventories or grading pins.

## Highest-value next tasks and evidence criteria

1. **Bounded native context and approved validation recipe preparation.** Expected benefit:
   less repeated searching and model-side planning; evidence must show lower total
   retrieved/prompt bytes and preparation overhead with the same independent quality.
2. **Opt-in one-attempt profile/reasoning adapter with verified readiness.** Expected benefit:
   minimally sufficient profiles for suitable work while high-risk tasks stay strong.
   Evidence must compare entire completed-task tokens/latency, counting provider
   failures and preparation, against ordinary Codex on matched tasks.
3. **Durable validation-driven escalation with context reuse and lifecycle telemetry.**
   Expected benefit: controlled recovery without unnecessary strong calls or duplicated
   context. Evidence must retain failed cheap attempts, uncertainty, escalation and
   validation overhead; no savings claim until independently accepted equivalent quality.

These are expected practical opportunities, not promised improvements. Tasks 1/2 can
be prototyped offline behind the plan adapter; Task 3 depends on accepted single-attempt
execution. Benchmarks must distinguish capacity outages from code/quality failures
while retaining failures in denominators. Cold/warm caches, complete token counters,
provider identity and source/policy pins are needed before any cost or latency winner.

## Verification and remaining decisions

Run `CARGO_NET_OFFLINE=true cargo test --locked -p codex-smart-core --test production_routing_readiness`,
`just docs-check`, `CARGO_NET_OFFLINE=true just check`, offline nextest and Security.
Exact results and proposed SHA are recorded in the separate draft PR. The fixture does
not verify real provider compatibility or context economics. Product invocation/schema,
capability receipt freshness, budget defaults, approved validation command sources and
opt-in privacy/telemetry consent require independent design review before implementation.

## Delivered bounded acquisition slice

The core `preparation` adapter now collects explicitly nominated task files under
hard file/byte/path ceilings and a cooperative deadline, and attaches the existing
workflow validation recipe without command execution. See the
[architecture contract](architecture.md#bounded-native-preparation-adapter) for
refusal behavior and filesystem/time limitations. This closes the missing bounded
file-acquisition primitive, not semantic coverage, CLI integration or hard supervised
timeouts. Context sufficiency remains unknown; no measured savings are claimed.

The next increment adds a working Linux process-isolated preparation worker and
explicit local supervisor, based on accepted main `b6b41c5814fd21549bae6fcc042d10b3a1c20fd2`
(#90). Production runtime admission remains closed. Independently pinned descriptor
execution, bounded versioned transport and parent-owned post-spawn deadlines are
implemented for inspection-only requests, without validation/model/SSH operations.
[Architecture](architecture.md#supervised-preparation-boundary-explicit-local-runtime)
owns protocol, session ownership and limits. This smaller working boundary does not
implement hostile-code syscall confinement, cross-process lifetime ownership or
bounded verification/spawn, and therefore cannot activate production routing.
Semantic review authority and validation argv remain deferred. Real offline worker
and fake-worker tests establish local behavior, not efficiency or model-quality evidence.
Live issue reconciliation/CI acceptance remains external; no issue, benchmark or
production acceptance is advanced by this local slice.

Historical verification of #90's policy-only slice follows (not this runtime's results).

Local verification of this policy slice used base
`4c54b9bacd62e924f378ec745ef6d32415ad6079` in the existing isolated task
worktree. The offline focused preparation/supervision suites passed 10 tests
(exit 0); workspace nextest passed 177 tests (exit 0). Offline workspace Cargo
test/build, formatter, clippy with warnings denied, docs-sync/docs-check and
diff whitespace checks passed (exit 0). Generated roadmap/index content did not
change; the Adaptive source registry now includes the supervision module.

`CARGO_NET_OFFLINE=true just check` exited 1: 295 Python tests ran, with 294
passing and the existing private Unix-socket grader test failing at `listener.bind`
with `PermissionError: Operation not permitted`. The remaining Rust gate commands
were run independently after that stop; the combined gate remains unresolved.
`CARGO_NET_OFFLINE=true just security` exited 1: dependency provenance passed,
but cargo-deny could not acquire its advisory database lock on the read-only mount.
No gate was weakened or cache/mount bypassed. GitHub main observation exited 128
because github.com could not resolve; remote freshness and live issue state remain
unverified. Git metadata is read-only, so the result is an uncommitted review diff;
these local results do not establish exact-head CI/Security acceptance.

## Local preparation runtime verification

The worker/runtime diff starts from accepted main
`b6b41c5814fd21549bae6fcc042d10b3a1c20fd2` on
`feat/supervised-preparation-worker` in the existing isolated checkout. Base freshness
was independently supplied by the parent session; no network observation was attempted.
Local workspace Cargo tests and nextest each passed 183 tests (exit 0, no skips).
Focused protocol/acquisition tests and real/fake worker integration checks passed;
post-spawn bounds are asserted with a 100 ms scheduler allowance, including a worker
that never reads a request larger than the pipe capacity. Success, failed exits,
late responses, floods, unsolicited/partial/mismatched messages, inherited descriptors,
unsafe nominations, pin mismatch and concurrent admission are covered. Generated
fake-worker fixtures use the Rust 1.98 Linux default LLD-compatible linker with a
one-thread cap; alternative linker configurations were not verified. No actual
uninterruptible kernel-I/O worker was induced; policy tests cover CleanupUnknown.
Formatter, clippy with warnings denied, locked offline workspace build,
docs-generate/docs-check and diff whitespace checks passed (exit 0). Generated roadmap
and index content remained unchanged; Adaptive source pointers were extended.

`CARGO_NET_OFFLINE=true just check` exited 1 after 295 Python tests: 294 passed and
the existing `test_main_sends_verdict_only_over_private_unix_socket` failed at
`listener.bind` with `PermissionError: [Errno 1] Operation not permitted`. All Rust
gates were therefore run independently. `CARGO_NET_OFFLINE=true just security`
exited 1: dependency provenance passed (same 30 registry packages), but cargo-deny
could not acquire `/home/user/.cargo/advisory-dbs/db.lock` on the read-only path.
No policy/test/cache bypass or advisory refresh occurred.

Git reports effective write access false for both this worktree's index and metadata
directory. Changes are intentionally unstaged and uncommitted; no publication or
live issue update occurred. These local results are not exact-head CI/Security
acceptance. Next action: independent review of this local-only boundary and its
missing confinement guarantees, followed by the unchanged check/security gates in
a writable, socket-capable CI environment before considering integration.
