# Architecture

Three workspace crates: `codex-smart-core` holds typed capability inventory, policy, config, migration and process planning; `codex-smart-cli` holds argument parsing, output and the `codex-smart` and `codex-smart-preparation-worker` binaries; `codex-smart-process` is the narrow Linux helper for the audited child-only descriptor-isolation hook. Core and CLI forbid unsafe code; the helper permits it only in that hook. No second agent, custom MCP, vector database or local model.

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

## Cross-repository Autonomous Development Contract v1 (proposal)

The proposed `automation/project.toml` is an optional **data contract**, not
a new orchestrator or an execution policy. This design is tracked in
[Issue #165](https://github.com/AlexandrShapkin/codex-smart/issues/165).
An initial disabled candidate exists in
[RelayForge PR #72](https://github.com/AlexandrShapkin/relayforge/pull/72).
No accepted Codex Smart parser, workflow adapter or autonomous integration is
claimed. In particular, experimental PR #164's operator-owned JSON manifest,
offline test recipes and private checkpoint ledger remain independent and
unchanged. The `run` command remains passthrough.

### Minimum manifest

TOML fields in this proposal have these semantics:

| Key | Meaning |
| --- | --- |
| `schema_version = 1` | Exact supported major contract version; unknown versions fail closed. |
| `project_id`, `project_type`, `repository` | Stable identity, e.g. `rust-workspace` or `python-stdlib`, and canonical `owner/name`. Bind against independently verified origin and accepted-main SHA. |
| `context.entrypoint`, `architecture`, `workflow`, `current_plan`, `security` | Bounded pointers to tracked regular files, not instructions to execute or read everything. |
| `context.task_source = "github-issues"` | Issues contain live actionable tasks; registry/roadmap only define stage ordering and dependencies. |
| `verification.profiles` | Named identifiers for project-owned **trusted adapter** verification, not shell scripts or free-form command strings. |
| `verification.ci_workflows` | Required workflow path hints; cannot lower the currently enforced GitHub branch, check, reviewer or security gates. |
| `verification.live_device_proof` | Additional environment evidence remains separately required where applicable. |
| `execution.enabled`, `max_stage_seconds`, `max_changed_files`, `max_changed_lines` | Source-declared opt-in candidate and stage ceilings; runner limits and operator policy can only tighten them. |
| `execution.checkpoint_mode`, `auto_merge`, `auto_deploy` | Private external state and explicit lifecycle prohibitions. V1 requires `auto_merge = false` and `auto_deploy = false`. |
| `change_policy.candidate_paths`, `blocked_unattended_paths` | Informational source areas and risk exclusions, not permission to write those paths. |

The candidate RelayForge file starts with `execution.enabled = false`.
Setting it to `true` in Git, a PR, or an Issue **never** grants execution
authority: absent an independently authorized operator grant and a validated
source snapshot, the executor must refuse. The exact accepted schema, optional
extensions and any later activation mechanism require a separately reviewed
implementation and compatibility negotiation.

### Deterministic interpretation and authority

A future reader must use a known parser and strict schema, bound to an
explicitly verified project identity, canonical root and full 40-character
accepted GitHub commit SHA. It must reject unknown executable profile IDs,
unexpected keys or versions, duplicated/ambiguous paths, path traversal,
symlinks, dirty or mismatched checkouts, and unsupported platforms. An unknown
value is not an implied default or permission. Git-controlled metadata is
untrusted, including when offered through a pull request. A task's actionable
scope is the intersection of separately authorized operator policy, an
independently pinned accepted project contract, and the specific task's
allowed files. Never grant rights from broader candidate paths in a repository.

No arbitrary command text, `sh -c`, copied scripts, environment expansion,
or repository-specified executable lookup may cross the runner boundary.
Adapter implementations must map supported profile IDs to audited fixed OS
argv, timeouts, sanitized environments and product-specific checks. Profile
names in this proposal do not constitute an implemented or universal recipe.
For RustCraft, `just check` is only a Cargo type check; full validation is
`just ci` plus any separately required Windows, GPU or measurement proof.
For RelayForge, GitHub CI cannot establish actual device recovery. For
Assistant Hub, Python, public-tree and UI checks stay distinct. Codex Smart's
own `just check`, cached `just security` and independent review gates remain
required where applicable.

The operator must supply a separate private allowed task manifest and
permission scope. The worker creates or verifies an isolated worktree, pins
Codex CLI and test executables, and uses the stricter of all time/file/line
limits. A missing dependency, source cache, test recipe, safe sandbox,
current Issue, matching SHA or trustworthy evidence causes a **refusal or
unverified result**, never an automatic network fallback or policy downgrade.
Resume requires a private, durable, restricted checkpoint matching the
actual committed SHA; an ambiguous interruption is not silently replayed.

### Evidence and rollout boundary

An accepted local check, exact-head GitHub CI, independent technical/security
review, merge eligibility, installed artifact and verified live system are
different evidence levels. Neither a commit nor green CI authorizes merge,
release, live benchmarking, secret access or production deployment. Explicit
owner vetoes, including the PR #125 merge prohibition, remain binding.

Adoption sequence: (1) approve a small schema and offline validator;
(2) add disabled metadata through independent PRs without rewriting existing
`just` or CI behavior; (3) implement a pure Codex Smart adapter and
negative-path Python/Rust tests; (4) verify four independent repositories
without RDC or Assistant Hub; (5) only then create a generic template
repository. This does not activate RustCraft stage DX2, merge experimental
PR #164, or create a parallel task queue.

## Linux target and libc ABI qualification

This is the canonical qualification matrix for [Issue #116](https://github.com/AlexandrShapkin/codex-smart/issues/116).
The existing execution-platform claim above remains **Linux**. Qualification
evidence is narrower than that claim; Unknown below means missing evidence, not
unsupported or withdrawn support. The [distribution contract](distribution.md)
separately describes a planned initial Linux x86_64 distribution, not a released
target matrix. Neither README nor the Cargo target predicates establish ABI proof.

| Target / candidate concern | Existing evidence and qualification limit |
| --- | --- |
| `x86_64-unknown-linux-gnu` | Tested host/CI environment for the existing pin; [tooling](tooling.md) records the x86_64 Linux host and `.github/workflows/ci.yml` uses Ubuntu 24.04 with Rust 1.98.0 and no cross-target matrix. This does not qualify libc 0.2.190. |
| `x86_64-unknown-linux-musl` | Unknown; GNU results do not establish musl ABI compatibility, including static/dynamic linking differences. |
| `aarch64-unknown-linux-gnu`, `aarch64-unknown-linux-musl` | Unknown; architecture and libc environment need separate evidence. |
| 32-bit Linux GNU/musl targets (for example `i686-unknown-linux-gnu`, `i686-unknown-linux-musl`, `armv7-unknown-linux-gnueabihf`) | Unknown; word size, calling convention, layout and time64 cfg selection are candidate review concerns, not asserted support or observed failures. |
| Other Linux triples/configurations | Unknown; no inference from the tested x86_64 GNU environment. |

The accepted direct pin remains `libc =0.2.189`, default features disabled, in
the [process-helper manifest](../crates/codex-smart-process/Cargo.toml).
[ADR-0009](decisions/0009-child-descriptor-isolation.md) owns the child-only hook
contract. The [helper](../crates/codex-smart-process/src/lib.rs) uses
`SYS_close_range`, `CLOSE_RANGE_CLOEXEC`, `c_ulong` casts and variadic `syscall`;
its errno/spawn-error handling is part of the review boundary. Linux-wide Cargo
cfg predicates select code; they do not prove it works on every Linux ABI.

The owner-reported [#105 investigation](https://github.com/AlexandrShapkin/codex-smart/issues/105)
matched libc 0.2.190's upstream checksum and 445 source files, but stopped before
target ABI qualification. A source/provenance checksum match establishes matching
bytes relative to the reference, **not ABI compatibility**. The old Dependabot
[#96](https://github.com/AlexandrShapkin/codex-smart/pull/96) was closed without
merge; neither that closure nor source matching authorizes adoption.

Before proposing libc 0.2.190, collect the following evidence for each relevant
target/configuration and obtain independent PR/security review:

1. Record the exact source revisions/checksums, Rust version, target triple,
   target features/cfgs, libc implementation/version, linking mode and runtime
   kernel. Compare 0.2.189 with 0.2.190 under those cfgs: macros/constants, extern
   signatures and symbol selection, syscall numbers/argument widths, and affected
   type sizes, alignments and field offsets. Trace GNU/musl, architecture and
   32-bit/time64 changes to reachable use; explicitly justify any inapplicable
   change rather than assuming the host cfg covers it.
2. Build the actual helper/worker and run isolated runtime regressions on that
   target (native hardware or an explicitly identified representative runtime).
   Rust cross-compilation alone is **not runtime ABI validation**. Use the existing
   [worker regressions](../crates/codex-smart-cli/tests/preparation_worker.rs):
   deliberate inheritable low/high descriptors must be removed only in the
   supervised child while parent flags remain unchanged; unsanitized direct
   launches must still refuse with exit 17, including proc-directory descriptors.
   Retain helper syscall-refusal and failed-exec transport negatives, plus worker
   identity, malformed-protocol, deadline and cleanup regressions. Do not sanitize
   away the descriptors in negative inheritance tests.
3. Attach per-target static findings and actual runtime results/limitations to
   the adoption review. Independent review must assess the unsafe hook and any
   ABI/layout/time64 changes; retain Unknown where evidence is missing. An x86_64
   GNU pass cannot establish that all Linux is validated. Resolve uncovered scope
   explicitly before adoption without silently narrowing the public Linux claim.

This matrix records documentation debt and required evidence only. It adds no
qualification results, dependency update, release/deployment or model execution.

## Delivered policies and future runtime: two deterministic planes

The pure Router v2, Playbooks and Adaptive policies below are implemented. Public
`plan` previews inspection intent and explicit `prepare` performs one supervised
local acquisition attempt. Production `run` remains passthrough; the complete execution
and lifecycle planes remain a roadmap target without a second general autonomous agent:

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

Validation recipe planning and explainable preparation are pure core contracts. Each validation obligation has bounded native readiness (`Ready`, `NeedsEvidence` or `Blocked`); optional external state cannot substitute for those checks. The rendered workflow explanation covers workflow/profile/reasoning/context/tools/preparation/validation/escalation/cleanup/fallback and contains no source/prompt/credential/runtime-path payload.

The #43 adaptive state machine in `codex-smart-core::adaptive` is likewise pure and grants no execution authority. It can be constructed only from a ready workflow plus ready validation recipe; preserves profile/reasoning floors; records every started attempt and validation result; escalates monotonically within explicit attempt/retry ceilings; keeps unresolved evidence in `NeedsEvidence`; and exposes terminal `Completed`, `Blocked` or `Exhausted` outcomes. Completion requires an independent validation pass. Its lifecycle budget also carries the single bounded delegation slot consumed only by the separate #45 policy contract.

#45's `codex-smart-core::adaptive_delegation` adds a policy-only narrow delegation boundary, not a general multi-agent runtime. It allows only parent-originated read-only evidence or mechanical workspace subtasks with opaque bounded context/scope handles, explicit time/cost/output ceilings and mandatory parent revalidation. High-risk parents and explicit security, concurrency, destructive-migration, ambiguous-API or conflicting-evidence hazards are refused. Nested delegation is refused. Handoffs retain bounded evidence digests, child failures and protocol violations, but a successful child result remains advisory and can never complete the parent controller. No child process, network, authentication, source transfer or model call is launched by this layer.

#44's `codex-smart-core::adaptive_routing` keeps provider/model identity outside policy. A caller-supplied compatibility catalog uses opaque provider/model handles plus independently verified availability and reasoning-support states. The pure resolver maps the controller's current profile/reasoning requirement to the minimally sufficient verified candidate; stronger verified fallback is allowed, lower capability and unknown compatibility are not. Catalog order cannot change the result and conflicting duplicate descriptors block. Production Codex argv application, actual retries and validation command execution remain future/evidence-gated work. #46 therefore uses a benchmark-only replay adapter built from the same core state machine/resolver; it does not change production `run`. The adapter has no authority to execute a model. Profile-smoke evidence is accepted in #82, and an offline-tested benchmark runner is merged in #83. The comparative campaign remains unexecuted and requires separate explicit authorization and reviewed operational readiness. Lifecycle operations never become model-routing decisions. Minimize expected total lifecycle cost subject to required quality, safety and verification, rather than single-call token count. See [workflow intelligence](workflow-intelligence.md), [distribution](distribution.md) and [ADR 0008](decisions/0008-deterministic-workflows.md). Production launch behavior remains unchanged.

## Bounded native preparation adapter

`codex-smart-core::preparation::prepare` is an explicit repository I/O boundary
around an existing `WorkflowPlan` and its native validation recipe. It accepts
caller-nominated relative file paths tagged with a playbook context obligation;
it does not infer task intent, crawl directories, read manifests for commands or
execute tools. Router assessment, playbook selection and validation planning remain
in their existing modules. CLI `run`, `explain` and `doctor` remain unchanged.

Hard ceilings are 16 requests, 8192 bytes per file, 32768 acquired bytes,
1024 bytes per path, 16 relative path components and a 250 ms cooperative deadline.
Callers can lower these limits. Requests are sorted; duplicate paths, traversal,
absolute paths, irrelevant obligations and invalid limits are refused. Acquisition
errors discard all snippets and preserve unresolved obligations and the independent
validation recipe. Empty requests supply no evidence. Blocked plans refuse acquisition.
Snippets carry relative provenance and SHA-256 of the exact UTF-8 bytes; source text
has no Debug implementation and is never automatically logged or persisted.

The Linux adapter uses descriptor-relative openat2 with no symlinks or magic links,
pins each file with O_PATH before opening its verified regular-file descriptor through
/proc/self/fd, and rejects hard links, special files, binary text and observed concurrent
modification. Unsupported kernels/platforms and unavailable procfs fail safely.
These checks are not a consistent repository snapshot or a sandbox against concurrent
writers. The caller must nominate public repository files appropriate to the task;
there is no credential discovery or automatic source upload. The root and filesystem
must be operator-controlled. The deadline checks cannot interrupt a stalled kernel
filesystem operation: post-spawn enforcement requires the explicit local supervisor
below. No production launch should consume this adapter until that boundary is reviewed.

Acquisition never establishes semantic sufficiency. All context obligations remain
explicitly unresolved, including relevant-file coverage. Validation recipes expose
existing obligation/native-readiness checks, not approved executable commands or
validation passes. Remaining joins are reviewed intent/coverage evidence, trusted
bounded validation argv and production runtime integration; Adaptive
routing, retries, command execution and comparative measurements remain pending.

### Supervised preparation boundary: explicit local runtime

The dedicated `codex-smart-preparation-worker` binary and explicit core API
`preparation_worker::run_local_preparation` implement one Linux child process around
`preparation::prepare`. Ordinary CLI run/explain/doctor and declarative plan never invoke this API.
The separately explicit `prepare` command joins the shared typed inspection plan
to this API once; [configuration](configuration.md#explicit-supervised-inspection-preparation)
owns its grammar and payload-free outcome contract. The
initial accepted intent is Inspection and the only accepted nomination obligation
is RelevantFiles. The existing Router assessment, workflow planner, default unknown
native surface and validation recipe are reused. All obligations remain unresolved;
no validation command, model, tool, SSH or network operation is implemented.

This is a smaller functioning process-isolation slice, **not a hostile-code sandbox**.
The independently trusted worker artifact is the authority boundary. Worker startup
requires an empty environment, refuses inherited descriptors beyond stdio (other than
its temporary procfs listing descriptor), sets no-new-privileges and caps core dumps
at zero, CPU at one second, address space at 128 MiB, descriptors at 32 and NPROC at
zero. NPROC does not prevent root from forking and these limits do not deny exec,
network or arbitrary filesystem syscalls. There is no seccomp, namespace, cgroup or
Landlock confinement. The dedicated reviewed worker contains no command-launch,
model or networking path; replacing it with an arbitrary pinned binary grants that
binary the caller's OS authority. Dynamic loader and system libraries are also trusted.
These missing guarantees prohibit production admission. The pure #90
`runtime_admission` still returns RuntimeUnavailable even for all-Verified facts.

The supervised parent installs a final child-only pre-exec hook through the narrow
`codex-smart-process` Linux helper. It calls `close_range(3, UINT_MAX,
CLOSE_RANGE_CLOEXEC)` after stdio setup. Rust's hook forces fork with a private
child descriptor table; unrelated parent descriptors and concurrent threads are
untouched. Marking rather than immediately closing preserves the descriptor-pinned
procfs executable lookup and Rust's spawn-error pipe until exec. Successful exec
closes every descriptor above stderr. Linux 5.11 or later is required for this flag;
unsupported kernels, flags or syscall denial fail spawn without a fallback. The
post-spawn deadline still excludes verification and spawn, including this hook.
The hook performs only a syscall and allocation-free errno read, with no locks,
logging, filesystem enumeration or captured destructors. Core and CLI retain the
workspace unsafe-code prohibition; the helper permits unsafe only in this audited
hook, using pinned libc 0.2.189 (already present transitively). See
[ADR-0009](decisions/0009-child-descriptor-isolation.md) for the review boundary.
Direct worker launches continue to refuse genuinely inherited descriptors with 17.
Malformed-protocol tests separately sanitize ambient harness inheritance in their
child so protocol handling remains observable; descriptor-refusal tests do not.

The descriptor exemption uses the exact fd owned by rustix's directory iterator,
not a procfs symlink target spelling. Every other fd above stdio is refused,
including an inherited descriptor to the worker's own procfs directory retained
across exec. Enumeration failures also refuse. No descriptor targets are read or
logged by this check; it does not depend on kernel-specific target rendering.

Integration-test failure messages also retain a pre-spawn parent descriptor count
and numeric fd/kernel-flag pairs read from procfs fdinfo. Only numeric fields are
reported; descriptor targets, paths, environment values and raw procfs contents
are excluded. The listing is dropped before reading flags. These test diagnostics
do not change worker output or security decisions. Linux's close-on-exec flag is
`0o2000000` in fdinfo; a parent descriptor without that bit can survive Rust
`Command` startup even when the child environment is empty. Parent snapshots are
observations, not proof of which descriptors the child actually received.

The dedicated executable reports failures only through stable exit codes, with
empty stdout/stderr before request handling. Legacy code 3 meant undifferentiated
bootstrap refusal; the current `BootstrapRefusal` replaces it with these categories:

| Code | Refusal |
| --- | --- |
| 2 | Unexpected arguments |
| 4 | Invalid request or request handling failure |
| 10 | Unsupported platform |
| 11 | Nonempty environment |
| 12 | Procfs prerequisite root open |
| 13 | openat2 procfs descriptor-directory prerequisite |
| 14 | Procfs executable open |
| 15 | Procfs executable metadata/type |
| 16 | Descriptor-directory open/iteration/entry parsing |
| 17 | Inherited descriptor |
| 18 | no-new-privileges setup |
| 19 | Core-dump limit |
| 20 | CPU limit |
| 21 | Address-space limit |
| 22 | Process-count limit |
| 23 | Descriptor-count limit |

These enum-only categories carry no environment values, source, paths, targets or
OS error text. They do not bypass a prerequisite or imply an unsupported host is
supported. Parent admission continues to map unavailable host prerequisites to
Unsupported; `Outcome.worker_exit_code` retains a reaped worker's numeric category.

The separate private `admit_pinned_local_worker` gate requires Linux openat2 and
procfs, plus a caller-specified trusted absolute executable, independently recorded
32-byte SHA-256 and protocol version 1. It never discovers PATH, reads project config,
or creates a pin from a candidate. It uses O_PATH/no-symlink descriptor traversal,
refuses special files, hardlinks, foreign ownership (only root or effective UID),
group/world write and special mode bits, then opens the pinned regular descriptor
through procfs. Only ELF files up to 64 MiB are accepted. Bounded streaming hashing
and metadata rechecks precede invocation of that same descriptor with OS arguments,
empty environment, cwd `/` and three pipes. Holding the descriptor removes pathname
replacement races; the operator must still exclude concurrent inode writers and
control the root/filesystem. Ancestor-directory permission ownership is not certified.
No candidate content or protocol source is logged or given a Debug implementation.
Sensitive-name nominations are refused in the shared acquisition boundary, including
.env variants, .git/.ssh/.aws/.codex/.gnupg directories, auth/credential files and
private-key names/extensions. This is not semantic secret detection: public task-file
nomination remains the caller's responsibility.

The parent drives #90's SupervisionPolicy using its own Instant clock, actual cumulative
output and actual try_wait results. Runtime and cleanup are each caller-lowered
nonzero budgets of at most 250 ms, with one nonblocking read per output pipe and one nonblocking write
per iteration, separated by at most a 1 ms requested sleep. Stdout retention is capped
at 65536 bytes; any stderr, malformed response or exhaustion cancels the attempt.
Success requires the complete exact response, EOF on both pipes, successful reap and
elapsed time strictly below the deadline. Late responses cannot restore success.
The parent sends SIGKILL directly, polls reaping without wait/wait_with_output and
returns at the fixed deadline-plus-cleanup ceiling even if the child remains in
uninterruptible kernel I/O. CleanupUnknown remains an honest terminal uncertainty.
This is a post-successful-spawn bound subject to OS scheduling and finite processing
per tick, not a real-time or end-to-end wall-clock guarantee: executable verification,
procfs/filesystem operations and spawn itself may block before that clock starts.

One process-wide mutex slot serializes these explicit calls. Busy callers refuse;
there is no retry or second simultaneous worker. An unreaped Child remains owned in
the process-lifetime slot even after return or unwinding. Later calls may kill and
try_wait that child but cannot launch until reaping is proven. At most one verified executable descriptor is also retained until the next
pre-spawn admission, keeping filesystem close/release operations out of the timed
loop and caller return path. No background reaper is started; a dropped/inactive caller does not erase uncertainty. Parent process exit
is the end of this ownership contract; cross-process exclusion and crash recovery
are not implemented. The trusted worker does not fork; descendant containment for an
arbitrary replacement artifact is not claimed. Policy tests model unreapable children;
integration tests exercise real success, cancellation, noncooperation, late output,
protocol errors, floods, descriptor refusal and absence of observable child leakage.

#### Wire protocol version 1

All integers are unsigned big-endian u32. A frame is an 8-byte magic (`CSPREQ`, NUL,
version byte 1 for requests; `CSPRES`, NUL, 1 for responses), payload length and exactly
that payload, followed by EOF. Total request length is at most 18432 bytes; total
response length is at most 65536 bytes. Strings are u32 length plus strict UTF-8
without NUL. Decoders check ceilings before allocations and reject unknown versions,
trailing/partial messages, oversized counts, invalid intent/obligation and encoding.
The worker consumes at most request-limit-plus-one bytes, not unbounded stdin.

Request payload: intent byte 1 (Inspection); root string (absolute, at most 1024
bytes/32 components); u32 files/file_bytes/total_bytes/elapsed_ms limits; u32 nomination
count; then for each nomination obligation byte 1 (RelevantFiles) and relative path
string (at most 1024 bytes/16 components). Existing hard acquisition ceilings apply:
16 files, 8192 bytes/file, 32768 total bytes and 250 ms cooperative acquisition time.
Only integer millisecond acquisition budgets are accepted. There are no command,
executable, URL or native-readiness fields. The root must be an operator-controlled
public repository; filesystem confinement and sensitive-file policy remain in prepare.

Response payload: SHA-256 of the entire request frame (32 raw bytes); failure byte;
u32 snippet count; then lexically sorted nominated path string, text string and
SHA-256 of exact text (32 raw bytes) for each snippet. Failure 0 means acquisition
success; codes 1–10 map to InvalidLimits, MissingIntent, BlockedPlan, InvalidRequest,
UnsafeOrMissingFile, FileLimit, ByteLimit, Deadline, InvalidText, UnsupportedPlatform.
Failures require zero snippets; success requires exactly every nomination in order.
The parent independently checks binding, counts, names, digests, text and request
byte ceilings, and reconstructs the same unresolved obligations/validation recipe
from the deterministic workflow. A successful process can report an acquisition
refusal; that does not become acquired evidence. Source snippets reach only the
explicit caller. No transcript or diagnostic source retention is automatic.

`Preparation::context_evidence(plan)` supplies a deterministic enum-only row for
every selected playbook obligation, including blocked acquisition. Each row records
no acquisition, acquired-but-unreviewed file count, or the acquisition refusal.
`covered` is always `None` (unknown); this view cannot accept semantic review receipts
or grant readiness. The supplied plan must be the acquisition plan; identity-bound
review receipts and protection against changed plans remain future work. Paths,
source and digests are absent from the report; exact snippets remain available to an
explicit independent reviewer under the existing privacy boundary.

Validation argv planning is deferred entirely. Existing validation recipes approve
obligations/native readiness, not executable identities or command argument lists.
Reading a repository recipe is insufficient command authority. No validation
commands are selected or executed by preparation; developer verification remains the
repository's existing offline gates. Production routing, CLI passthrough, model
retry/grading and benchmark evidence remain unchanged.

## Explicit plan-only CLI composition

The opt-in `plan` command calls `routing::assessment::assess` and
`workflow::plan_workflow` with explicit Inspection intent and independently unknown
native/external/resource surfaces. The CLI adapter reuses the pure preparation
nomination predicate and ceiling without calling acquisition, supervision or the
worker. It renders the existing enum-only workflow and validation recipe alongside
unknown evidence and declarative counts. Operator task/risk/safety declarations do
not verify capabilities or model identity; contradictions remain unready. See the
[public grammar and limits](configuration.md#explicit-inspection-plan-preview).
Ordinary `run` and implicit launch still use the existing passthrough path. This
increment grants no runtime authority or stage/measurement acceptance.
