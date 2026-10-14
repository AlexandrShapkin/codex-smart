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
filesystem operation: hard wall time requires a future supervised adapter. No
production launch should consume this adapter until that boundary is reviewed.

Acquisition never establishes semantic sufficiency. All context obligations remain
explicitly unresolved, including relevant-file coverage. Validation recipes expose
existing obligation/native-readiness checks, not approved executable commands or
validation passes. Remaining joins are reviewed intent/coverage evidence, trusted
bounded validation argv and a separately opt-in single-attempt runtime; Adaptive
routing, retries, command execution and comparative measurements remain pending.

### Supervised preparation boundary: policy-only slice

`preparation_supervision` models one worker with independently verified identity,
protocol, containment and termination facts. Unknown facts refuse admission; denied
facts take precedence. `runtime_admission` always returns `RuntimeUnavailable` even
when every fact is verified. There is no preparation worker binary, transport,
spawn, OS timer, kill or reap implementation in this slice. The existing acquisition
adapter still has only its cooperative deadline; no hard wall-time guarantee is
claimed and production consumption remains prohibited.

The pure policy accepts a monotonic elapsed-time observation and cumulative wire
output count. It limits modeled acquisition time to 250 ms, cleanup to a further
250 ms and wire output to 65536 bytes (source ceilings remain those above). Deadline
expiry, output overflow or regressing observations request termination and
nonblocking reap polling. Success requires both a verified response and successful
reap strictly before the deadline. Cancellation cannot become success. At the fixed
cleanup ceiling, unreaped workers remain `CleanupUnknown`; terminal observations
cannot reopen the attempt. There is one worker slot, no retry and constant ledger
space. Tests simulate observations; they do not test an OS supervisor.

A reviewed runtime needs a dedicated pinned worker executable and bounded/versioned
request-response protocol around the acquisition adapter, trusted OS argv, a
parent-owned monotonic timer, bounded nonblocking transport, worker containment and
bounded termination/reap handling. Reusing the passthrough Codex launcher or running
filesystem I/O in an uncancellable thread cannot provide that guarantee. Linux
uninterruptible kernel I/O may delay SIGKILL and reaping indefinitely: caller return
must remain bounded independently, cleanup uncertainty must be retained, and a
supervisor must prevent further workers while one remains unreaped. Other platforms
need independently reviewed containment/termination adapters and otherwise refuse.
Spawn and executable verification can themselves involve filesystem operations;
review must cover those before claiming an end-to-end wall-time bound.

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
