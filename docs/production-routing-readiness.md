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

The following records the initial local attempt. The resumed finalization below
supersedes its working-tree, network and current verification observations while
retaining that earlier evidence.

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

### Resumed finalization after quota repair (2026-10-14)

The owner repaired the host's temporary-filesystem quota outside this session.
Sandbox launches and file access now work. The existing branch and commits were
preserved at `5ef6b4c37050d70820761b6bae6ae149099bb0fe`; no competing writer was
visible in the session's process namespace. GitHub main was independently observed
at accepted base `b6b41c5814fd21549bae6fcc042d10b3a1c20fd2`.

The retained `/tmp/cs-worker-check-final.log` recorded eight direct disk-quota errors
and a downstream partial-transfer IndexError. All nine failed Python tests passed
when reproduced individually. Sequential offline verification then passed all
three focused preparation/protocol unit tests, 14 worker/acquisition/supervision
integration tests, formatting, Clippy with warnings denied, all 183 workspace Rust
tests, all 183 nextest tests with zero skips, and docs-check. The complete
`CARGO_NET_OFFLINE=true just check` passed (exit 0): 295 Python tests, including the
Unix-socket and trusted-reference controls, followed by formatting, Clippy, workspace
Rust tests and build. Fixture compilation uses one code-generation unit and one
linker thread; no post-spawn deadline or adversarial coverage was changed.

Dependency provenance passed for the same 30 checksum-backed registry packages.
`CARGO_NET_OFFLINE=true just security` exited 1 because cargo-deny could not take
the exclusive `/home/user/.cargo/advisory-dbs/db.lock` on its read-only path. No
advisory policy, cache, quota, permission or mount was changed or bypassed.

Existing Draft PR [#91](https://github.com/AlexandrShapkin/codex-smart/pull/91) and
the remote branch both resolve to `5ef6b4c37050d70820761b6bae6ae149099bb0fe`.
GitHub Actions app 15368 reports Security/review success and CI/check failure for
that exact head. Both CI logs show the first real worker returning bootstrap
refusal code 3 (expected Succeeded, observed Failed), before adversarial fixture
compilation. Which bootstrap prerequisite refused is not identified by that code;
this remains an unresolved CI acceptance failure, distinct from quota exhaustion
and fixture compilation load. Local passes do not establish remote acceptance.

The common Git metadata and worktree index remain read-only in the sandbox. The
final fixture/tooling adjustments and this verification update remain uncommitted;
no new commit or push was attempted. The existing PR stays Draft. Final acceptance
requires diagnosis of the Ubuntu CI bootstrap refusal, unchanged host security
verification, a commit/push from the existing writable owner session and successful
exact-head CI/Security. Main, historical evidence and unrelated worktrees remain unchanged.

### Bootstrap diagnosis increment (2026-10-14)

The pending finalization files above were preserved. Published CI evidence identifies
only legacy bootstrap refusal code 3 on Ubuntu 24.04.5 runner image 20261004.327.1;
it does not identify a syscall, resource limit or descriptor target. The local kernel
is 7.2.9-zen1-1-zen. The [pinned runner-image documentation](https://github.com/actions/runner-images/blob/ubuntu24/20261004.327/images/ubuntu/Ubuntu2404-Readme.md)
reports 6.17.0-1022-azure; this is image metadata, not a fresh capability probe.
No kernel capability, resource-limit or system-security configuration was changed.

Bootstrap now returns payload-free categories for environment, individual procfs
prerequisites, descriptor enumeration/inheritance, no-new-privileges and each
resource limit. The [architecture contract](architecture.md#supervised-preparation-boundary-explicit-local-runtime)
owns the exit-code map. Invalid-request tests require code 4, so an earlier bootstrap
refusal cannot masquerade as successful protocol rejection.

A separate controlled exec fixture demonstrated a descriptor-check defect: the old
worker accepted an inherited descriptor to its own procfs directory and reached
request handling (exit 4, empty stdout/stderr). The corrected worker rejects that
same fixture with code 17, empty stdout/stderr. The exemption now uses only the
iterator's exact owned fd; the procfs target-string comparison is removed. This
strengthens inheritance refusal and removes target-rendering assumptions while
preserving all other prerequisites and resource ceilings.

All five focused real/adversarial/bootstrap integration tests passed after the
change, including environment/argument categories, inherited-directory refusal and
absence of observable child leakage. The corrected descriptor check is a demonstrated
local defect; its causal connection to the existing Ubuntu CI failure remains
unproven until a new exact-head runner execution. No CI success or exact root-cause
attribution is claimed from the legacy code 3 logs.

Sequential verification of the updated implementation passed the three focused
protocol/acquisition unit tests, 12 acquisition/supervision integration tests,
formatting, Clippy with warnings denied and docs-check. Nextest passed all 186 tests,
zero skipped. The single full offline just check after the code change passed
(exit 0): 295 Python tests, formatting, Clippy, all 186 Rust tests and workspace build.
The adversarial exec fixture uses the correct variadic fcntl ABI; the complete gate
tested that final fixture source. No timeout or acceptance assertion was weakened.
Dependency provenance again passed for 30 registry packages. Local just security
again exited 1 solely at the read-only advisory database lock; no advisory-policy
or cache bypass occurred. Git metadata is still read-only, so no new commit or
exact-head CI execution is available for these changes until owner-side publication.

## Plan preview increment (#93)

The explicit `plan --intent inspection` CLI now composes the genuine typed assessment,
workflow and declarative validation requirements. It accepts bounded lexical file
nominations without acquisition and keeps capability/model evidence Unknown.
The [configuration contract](configuration.md#explicit-inspection-plan-preview) owns
its grammar and limits. This implements only the plan-only portion of step 1; verified
receipt ingestion, semantic preparation, validation execution and runtime joins remain
[#94](https://github.com/AlexandrShapkin/codex-smart/issues/94). Comparative acceptance
remains [#95](https://github.com/AlexandrShapkin/codex-smart/issues/95). Existing offline
fixtures and policy floors do not authorize execution or prove savings.
