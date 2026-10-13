# Development benchmark protocol

The representative 40-run campaign has now completed and its frozen measured baseline
evidence `ffd8fbbc...` is accepted for #14. The historical 42-job campaign remains unexecuted. No
overall winner or savings claim is accepted from this sample; #15 production telemetry
remains separate.

## Representative measured baseline — 2026-10-13

The frozen `representative-development-v1` campaign completed all **40/40** primary
jobs on the accepted split-host topology: ThinkPad agent execution and independent
production grading on `srv0`, with zero retries. Each variant has 20 runs. Strict
quality keeps every terminal execution failure in the denominator: `vanilla` passed
19/20 (**95%**) and `native` passed 17/20 (**85%**). Median measured duration was
60.13 s vs 61.53 s respectively. Median observed input tokens were 129,602 vs
130,725.

Those strict rates must not be interpreted as a demonstrated content-quality regression.
Exactly 36 jobs exported submissions, and **all 36/36 passed** the independent
production grader. The four non-submission executions were one timeout per variant and
two `native` agent failures whose private traces report the provider response
`Selected model is at capacity`. Provider-capacity failures remain failures in the
strict result; the diagnostic classification only prevents misattributing them to the
submitted solution or grader.

Cost comparisons are restricted to the 16 matched scenario/repetition pairs where both
variants passed quality and exposed the relevant counters. On those pairs, native had
a median **-19.44% observed tool-call lower bound** and used fewer observed tool calls
in 12 pairs, more in 2 and tied in 2. Median input-token delta was -1.32%; median
duration delta was +3.71%. Output-token delta was -0.64%, while cached-input and
reasoning medians increased by 4.29% and 11.86%. These are descriptive measurements,
not a general savings claim. There is no accepted winner.

The measured `native` variant still differs from `vanilla` only by the public
native-first instruction. It is **not** the future `router-v2` production adapter and
therefore cannot establish Router, Playbooks or Adaptive Execution benefits. The
versioned candidate measurement is `representative-development-measurement-v1`; raw
traces/stderr remain private and only normalized hashes/aggregates are eligible for
repository evidence.

## Quality before cost

Correctness, requirement coverage, regressions and security qualify a result before
cost is compared. `benchmarks/graders.py` runs fixed independent oracles outside the
agent workspace. The named gates currently share one conservative composite verdict:
all pass only when every scenario assertion passes. They are not separate measurements.
Failed, unavailable and retried runs remain in denominators. Cost summaries use matched
scenario/repetition/seed/snapshot/model/settings/cold-warm strata where every runnable
variant passes; a cheaper incorrect result never wins. Report median, range and sample
count, without winner logic. Token totals include every retry only when all attempts
expose that counter; otherwise the metric is unknown.

## Variants and provenance

- `vanilla`: direct non-interactive Codex with controlled settings.
- `native`: the same command with an explicit native-first instruction appended to
  the public task prompt; it is a policy instruction, not verified tool enforcement.
- `legacy`: unavailable. No exact source/version/checksum archive exists; historical
  numbers in the project brief are not new measurements.
- `router-v2`: unavailable. No verified experimental adapter applies the actual
  decision. Production `codex-smart run` remains passthrough. A future adapter must
  preserve decision/application evidence before this variant can be runnable.

Both runnable variants ignore user config/rules, use an ephemeral workspace-write
session, and require explicit model and executable. No MCP setup, indexing, network
probe or installation is performed by the harness. Real model execution itself uses
the existing authenticated Codex service. Toolchain absence records not-runnable.

## Pinned scenarios and setup

`benchmarks/manifest.json` version 1 pins seven purpose-built public fixtures: Rust
clamp bugfix, Go sum feature, Python mutation-sensitive tests, Python multi-file
rename, Python API/caller migration, IaC deployment security/config repair and Python
repository exploration. This is compact harness coverage, not representative campaign
coverage of every language/task pairing or large repositories. IaC uses a JSON
configuration contract; it does not measure Terraform/provider behavior.

Each fixture pins the SHA-256 of a canonical JSON file map (sorted keys, compact JSON,
UTF-8). This content-addressed snapshot replaces a repository commit for purpose-built
fixtures. Setup requires an empty disposable directory, materializes only baseline
files and verifies the resulting hash. Dirty state, changed snapshot, missing fixture
and setup errors reject execution. Every retry also starts fresh; retries are independent
attempts, not session resumes. Graders and solution/wrong controls are never copied into
the agent workspace. Real grading should run in a disposable container with no secrets
or network: submitted source executes during grading. The harness timeout terminates
process groups but is not a security isolation boundary.

The grader self-test requires positive controls to pass and deliberately wrong controls
to fail: happy-path-only clamp, hardcoded sum, vacuous tests, stale callers, privileged
configuration and incomplete call chain. Python test grading additionally mutates the
implementation to prove submitted assertions detect faults. Missing Rust/Go toolchains
skip those self-tests explicitly; full campaign acceptance requires all toolchains.

## Runner and trace contract

Run local fake validation with `python3 -B scripts/benchmark.py`; artifacts are created
under `benchmarks/.artifacts`. Remove that local directory explicitly before repeating
the same run identifiers (the runner refuses to overwrite evidence). Configure
`--repetitions`, `--seed`, `--retries`, `--timeout` and `--cold-warm`. Seed plus manifest
produces stable shuffled scenario/variant/repetition order, including unavailable rows.
CI uses fake runs and needs no OpenAI credentials. The initial read-only preflight
failed at startup; the first writable-host smoke subsequently reached a real turn.

`scripts/benchmark.py` is a low-level harness/library and synthetic validation CLI.
Its legacy `--real` path is disabled; `--codex` and `--model` live options are removed.
The only production-facing real entry is `scripts/benchmark_campaign.py`, which is
currently blocked by the unverified grading isolation contract. CLI inspection and
executable identity validation are benchmark setup, never product runtime behavior.

The [official non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
defines `codex exec --json` and the sample `turn.completed.usage` fields. Local 0.162.1
`exec --help` confirms the flags. `benchmarks/fixtures/official-example.jsonl` is a
sanitized captured documentation example, not a live model trace or measurement.
Parser tests validate that example and synthetic event structures from verified live
evidence. The corrected bounded host smoke now verifies the live execution contract.

Only input, cached input, output and reasoning-output counters are read. Total and
fresh input stay unknown; neither is derived or estimated. Observed command/MCP/search
completed-item count is a lower bound; full tool-call count stays unknown. Unknown
event types/fields are ignored without projecting their contents. Malformed JSON,
invalid counters, duplicate terminal/item events, late events and truncated streams
fail closed and invalidate parsed counters. Exactly one terminal turn event is required: `turn.completed` or `turn.failed`.
`error` is non-terminal and may precede either. A valid failed terminal has no
structural parser errors, has null usage, skips grading and records agent-failure
even with a nonzero exit. Arbitrary error messages never enter normalized records.
Nonzero exit without a valid failed terminal, timeout, agent failure and
grader failure remain distinct. Every attempt and initial failure are retained.

## Records, overhead and privacy

`benchmarks/schema/record.schema.json` describes version 1 normalized records;
`schema/manifest.schema.json` describes manifests. Runtime validation checks manifests;
record serialization is tested against the fixed field contract without a framework.
Records contain scenario/variant/repetition/seed/snapshot, safe tool/model/settings
references, attempt start/end/duration/exit, composite quality gates, failure codes,
retry count, final status and nullable counters. No raw event payload enters records.

`cold` and `warm` are explicit operator classifications, not automatically inferred
cache state. Fresh fixture setup time is measured separately from development execution.
Bootstrap and index overhead are null until measured; no index is forced. Future
campaigns must document cache preparation and distinguish not-applicable from unobserved
index overhead. Missing metric is null, never zero.

Raw stdout JSONL and stderr can include prompts/source/tool details. They and local
records live only in the gitignored `benchmarks/.artifacts` directory with private
run directories. Never commit arbitrary output, auth, credentials, environment values,
private source or prompts. Checked-in fixtures use only public purpose-built data.
Export normalized records only after reviewing their metadata references; there is no
automatic commit/upload/export. This is benchmark-local instrumentation, not product
prompt/source logging or telemetry.

## Remaining acceptance work

The representative execution, independent grading, private evidence preservation and
normalized baseline acceptance are complete. #14 acceptance criteria are satisfied. Legacy remains unavailable
because exact provenance is absent, and the historical 42-job campaign remains
unexecuted by design. A separate decision-applying adapter is still required before any
Router v2 measurement. #15 remains separate and begins only after #14 acceptance.

## Historical initial campaign preflight

PR #32 merged the harness at `d6b74d4`. Exactly one vanilla Codex invocation used
`iac-security`, `gpt-6-sol`, explicit low reasoning, workspace-write, ephemeral mode,
ignored user config/rules, unknown cache state, timeout 120 seconds and zero retries.
Codex 0.162.1 exited 1 before emitting any JSONL because its in-process app-server
client could not initialize on the read-only filesystem. No second live invocation
was attempted. No terminal or usage fields were verified, and independent grading
was correctly skipped. The failed normalized attempt and empty raw trace remain local.
All documented input/cached-input/output/reasoning metrics are **not observed**;
fresh/total counters are unsupported by the documented parser contract and remain
null. Full tool-call count remains unknown. No comparative performance claim follows.

Privacy review found no auth-field categories in raw output, no arbitrary event payload
or absolute path in the normalized record, and private gitignored artifact directories.
Raw stderr is retained locally and is not committed; the reviewed failure contained
no auth-field categories or absolute paths. No live raw JSONL or
sanitized live fixture is committed: the empty stream supplies no useful regression
fixture. Existing parser tests cover the failed/truncated stream and nonzero exit.

`benchmarks/campaign-v1.json` originally froze the **plan**, with live preflight blocked. It pins
Codex version/artifact checksum, requested model, low reasoning, sandbox/config/rules
auth equivalence, scenario/grader/harness/campaign-runner checksums, seed `[14]`, three
repetitions, zero retries, timeout 120 seconds and unknown cache protocol. Planned work
is 7 scenarios × 3 repetitions × 2 variants = **42 primary runs**, vanilla and native.
Legacy and Router v2 remain unavailable. Native differs only by the public instruction
already documented; command settings, auth, fixtures and graders are identical.

Toolchain pins are Rust 1.98.0 (`88d9e12ae`), Go `go1.27.2-X:nodwarf5 linux/amd64`, and
Python 3.14.8. They are installed locally; the campaign planner checks exact version
strings. Missing/mismatched tools make affected scenarios not runnable; none are
installed automatically. IaC checks JSON configuration semantics, not Terraform.
Fresh fixture setup is guaranteed; inherited host caches are not controlled, so no
cold/warm claim is made and bootstrap/index timing stays unknown/not applicable.

`python3 -B scripts/benchmark_campaign.py` prints a no-execution plan.
`python3 -B scripts/benchmark_campaign.py --dry-run` uses the exact frozen config for
42 local fake-agent jobs with real independent graders. It never invokes Codex, and
labels all counters synthetic. Records include pinned references and stay under
`benchmarks/.artifacts/campaign-v1-dryrun`. Existing evidence is never overwritten.
At that stage the campaign entry point deliberately had no model-execution mode while live preflight
was blocked. It must not be treated as ready for the measured campaign. A writable,
approved benchmark environment with existing authentication must first pass a bounded
live smoke; do not modify permissions or copy credentials to bypass this environment.
Review and update preflight evidence before enabling any measured execution.

## Historical pinned startup diagnosis after PR #33

PR #33 merged at `1f1de4d`. No model call or live retry was made in this diagnosis.
The installed executable still matches the frozen 0.162.1 checksum. Public upstream
source was inspected at release tag `rust-v0.162.1`, commit
`092d3acd6bec3e3a14bdc7e7a2810ab628ab759d`; relevant source checksums are recorded in
`campaign-v1.json`. The installed package identifies `0.162.1+arch.1`; binary strings
match the bootstrap error/function/source-path contract. This identifies the inspected
upstream contract without claiming an independently reproduced package build.

The [in-process bootstrap](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/app-server/src/in_process.rs#L445)
unconditionally calls `resolve_installation_id` before returning the initialized
client. [Installation identity resolution](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/core/src/installation_id.rs#L19)
opens `$CODEX_HOME/installation_id` read/write/create and locks it, even if a valid
ID already exists. It can chmod that file to 0644 or rewrite an absent/invalid UUID.
The [exec entry point](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/exec/src/lib.rs#L1022)
starts this client before starting the ephemeral thread. Ephemeral mode does not
exempt installation identity from these startup writes.

Metadata checks found the normal Codex home and installation-ID file present but
read-only. Opening the existing installation-ID file read/write returned **EROFS (30)**;
no contents were read or written. The retained smoke stderr reports the matching
read-only in-process initialization error. SQLite/log redirects cannot affect this
installation-ID open. The pinned implementation accepts only the Codex-home root for
this path, with no separate installation-ID environment/config control.

Changing `CODEX_HOME` is not an auth-preserving state-only redirect:
[file auth](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/login/src/auth/storage.rs#L162)
uses that root, and [keyring identity](https://github.com/openai/codex/blob/092d3acd6bec3e3a14bdc7e7a2810ab628ab759d/codex-rs/login/src/auth/storage.rs#L246)
hashes its canonical path. No existing supported environment credential was available
to preserve auth independently (presence checks only; no credential-store contents
read). Consequently **no safe writable-state solution was established**, and the
conditional retry was not executed. No speculative SQLite/log override, fresh Codex
home, credential copy, chmod, normal-config mutation or filesystem-permission bypass
was attempted. Frozen model, reasoning, sandbox and artifact settings are unchanged.

At that historical diagnosis the live contract remained blocked, counters remained null and measured execution stayed
disabled. To proceed, the owner must supply a writable benchmark environment with its
normal existing authentication intact; an executable change would require separate
approval and a newly verified contract. This task does not authorize silently changing
the executable/settings or creating an alternate auth store. The planned campaign
remains 42 jobs; no native or measured campaign ran. No new live trace was produced.

## First writable-host smoke and corrected contract

The first writable-host smoke used Codex 0.162.1, iac-security, vanilla, one
repetition, zero retries, gpt-6-sol, low reasoning, workspace-write, ephemeral,
ignored user config/rules and timeout 120 seconds. Writable startup is verified.
It reached thread.started and turn.started, followed by repeated error events,
item.completed and turn.failed; process exit was 1. No successful turn or usage
counters were observed, and the independent grader did not run.

The failed request lacked authentication because ignore-user-config dropped the
normal cli_auth_credentials_store = "keyring" setting. Auth still used normal
CODEX_HOME but defaulted to file storage, where auth.json was absent. Normal login
status succeeded with existing ChatGPT auth. No credential was invalidated or copied.

The campaign now freezes typed auth evidence: existing normal CODEX_HOME, keyring,
credentials_copied false and user_config_loaded false. Both command variants pass
`-c cli_auth_credentials_store="keyring"`, the TOML string override accepted by
pinned Codex 0.162.1. Normal home and its existing keyring namespace remain unchanged.
No other user-config field is imported; model, reasoning, sandbox, task prompt,
user config and user/project rules remain isolated. Changing this pin requires
explicit review and repinning. No auth file is created and no normal config changes.

Parser semantics now reflect the verified event-type structure, using sanitized
synthetic regression inputs only. No raw live fixture, remote error message,
request identifiers, private paths or auth material is committed. Earlier startup
diagnosis above is historical evidence for the read-only host.

At the corrected-command repair checkpoint, the second host smoke was still pending,
live readiness was blocked and all 42 jobs were unexecuted. That repair made zero
model invocations and passed 45 Python tests, docs-check, check and nextest (85/85).
The subsequent successful smoke supplied by the owner supersedes that readiness gate.

## Verified corrected live contract and campaign readiness

The second writable-host smoke succeeded using the merged corrected auth routing.
One bounded smoke verifies execution machinery, independently of harness correctness
and representative performance evidence. It used iac-security / vanilla, repetition 0,
seed 14, retries 0, unknown cold/warm, Codex 0.162.1, gpt-6-sol, low reasoning,
workspace-write, ephemeral true, ignore_user_config true, ignore_rules true,
keyring through normal CODEX_HOME, and timeout 120 seconds.

Quality passed and the independent grader passed. Process exit status was 0,
terminal status completed, normalized final_status null, parser_errors []. Observed
input_tokens **58885**, cached_input_tokens **55040**, output_tokens **427**, and
reasoning_output_tokens **36** are smoke observations, not comparative benchmark
results. Observed_tool_calls **3** is only the documented completed command/MCP/search
lower bound. Fresh_input, total and full_tool_calls remain null/unknown, never derived.
Earlier read-only startup and writable-host auth failures remain historical evidence.
No raw trace, stderr, prompt, source, private absolute artifact path, credential
material, request identifiers or arbitrary event payload is committed.

The frozen state is live_contract verified, real_runner_contract prepared,
grading_isolation_contract required-not-verified, representative_campaign_ready false: representative task coverage has not yet been
accepted. Benchmark remains partial; #14 stays open and #15 stays separate. The seven
scenarios and 42 planned jobs remain a preliminary compact campaign. No winner,
savings or representative end-to-end performance claim follows from this smoke.
All 42 jobs remain unexecuted.

Codex live execution/JSONL/auth contract is verified; grader correctness is tested
using independent positive and deliberately wrong controls. Grader security isolation
is **not verified**, and representative coverage is **not accepted**. The IaC smoke
remains valid: that grader compares JSON semantics and executes no submitted program.
Other graders execute submitted Python, Rust or Go code in host subprocesses; environment
filtering, temporary directories and process timeouts do not provide filesystem/network
security isolation. Running submitted code on the normal authenticated host is not an
approved campaign configuration.

The campaign runner prints the frozen plan by default. Both `--real` and
`--allow-preliminary-campaign` remain necessary, but they cannot bypass grading isolation.
The public `real_run()` reloads the frozen configuration and refuses with
`grading isolation contract is not verified` before artifact creation or any executable,
version, toolchain or model execution. Real campaign execution is currently disabled.
No risk acknowledgement can override this gate; verifying isolation requires a separately
reviewed contract change. The private prepared execution helper is exercised with mocks only.

Semantic validation freezes exact executable SHA/version, toolchain versions and version
arguments, the entire cold/warm protocol, typed live evidence, smoke counters/readiness
and retained failed evidence. Future approved execution must run identity preflight once
before executing jobs. Seed 14, three repetitions, zero retries, timeout 120, model and
reasoning remain frozen. Vanilla/native commands are identical; only the native public
instruction differs. Normal CODEX_HOME and keyring routing are preserved, with ignored
user config/rules, no credential copies or auth files. No product telemetry or Router
runtime changes are involved.

Private gitignored run directories reject existing identifiers and symlinks. Each
completed normalized job is saved immediately; Ctrl-C kills the active process group
and leaves earlier records intact. Failures stay in denominators, missing counters
stay null and cost comparison still requires quality-equivalent matched runs.
The dry-run remains credential-free and synthetic. Real mode was not executed during
this implementation or its tests; all runner tests use fakes/mocks.

Recommendation at #36 (superseded by the representative-design slice below): **Design and verify the grading isolation boundary, then
finalize representative coverage.** Define a boundary that prevents submitted code from
accessing the authenticated host's files, credentials and network, and test attempted
escapes before accepting it. No container/orchestration system is implemented here.
Then accept or expand a bounded language/task matrix and independent grader criteria
before spending on 42 runs. Five of seven fixtures are Python or JSON-based IaC; Rust
and Go each cover one small task, CI lifecycle and large repositories are absent, and
legacy/Router variants remain unavailable. Repetitions cannot fill those coverage gaps.
The current 42 jobs may be separately approved later as preliminary harness evidence;
no coverage expansion or campaign execution occurs here.

## Grading isolation investigation after #36

Owner-accepted #36 merged at `bff575dce5498159939ddea4814a53e4da478f55`.
The #37 slice examined an already installed Linux backend without installing packages,
using sudo, changing security configuration or invoking models. No backend is accepted
for submitted-code grading. `scripts/benchmark_isolation.py` offers small typed
availability/grade results and an explicit `--probe` command for fixed synthetic code.
Its grade entry refuses without reading/executing submitted files; the prepared real
runner uses this entry instead of the host grader, with no fallback. The probe command
exits nonzero even when component probes pass, because
component success does not establish an accepted isolation contract.

| Mechanism | Local evidence | Privilege / decision |
| --- | --- | --- |
| Bubblewrap | 0.13.0 available; non-setuid/non-setgid executable | Unprivileged user/mount/PID/network namespaces work; candidate only |
| Rootless Podman | Not installed | Unavailable; no installation attempted |
| Docker | 29.9.0 available; daemon reports seccomp/cgroupns, not rootless mode | No approved rootless boundary; no container run or daemon changes |
| unshare | util-linux 2.42.4; user/network/PID namespace control succeeded | Namespace primitives, not a complete grading backend |
| Resource delegation | cgroup hierarchy mounted read-only | Aggregate memory/process budgets cannot be provisioned here without separate host setup |

Bubblewrap uses an empty root, read-only synthetic probe/runtime mounts, a single
writable disposable directory, bounded temporary tmpfs, a new procfs/PID namespace,
minimal Bubblewrap runtime devices, all capabilities dropped, a non-root namespace UID,
nested user namespaces disabled, a new session and die-with-parent. HOME/CODEX_HOME
are empty synthetic directories. It neither mounts normal home, repository checkout,
benchmark artifacts nor credentials. The launcher constructs an environment with PATH
only; the sandbox clears it and sets PATH/HOME/CODEX_HOME (Bubblewrap/Python add PWD and
LC_CTYPE). Probe source/configuration stays read-only outside the writable directory.

Local synthetic probes pass for an external sentinel read/write, symlink escape,
HOME/CODEX_HOME visibility, synthetic secret environment inheritance, local TCP listener
and remote TEST-NET TCP reachability, local UDP listener and remote TEST-NET UDP routing,
and immutable probe source. The host UDP listener receives no packet; successful local
socket creation within a namespace is not host connectivity. A forked child calls setsid
and attempts a delayed marker write; killing the controller on timeout prevents that
write. Interruption cleanup is also tested with mocked processes. No real credentials
or private source are probed; outputs contain only safe status/reason/check fields.

These are **partial namespace controls**, not full escape acceptance. Bubblewrap itself
does not enforce aggregate memory/process quotas; timeouts and a namespace alone cannot
prevent resource exhaustion. No delegated writable cgroup is available, and no controller
limits are configured by this slice. The synthetic probe's broad read-only system-runtime
mount is not an accepted minimal toolchain inventory. Rust uses a Rustup-managed sysroot
under normal home, which is deliberately not exposed; exact Rust/Go/Python grader
compatibility inside an approved boundary remains **not verified**. Positive/wrong
controls continue to test trusted public fixtures locally, not submitted-code isolation.
No submitted-code grader is launched through this blocked candidate.

The candidate reports `blocked / aggregate-resource-controls-not-verified` when the
reviewed version and namespace probes work. Missing backend reports unavailable;
unreviewed versions, privileged installations or failed probes stay blocked. No result
promotes the campaign gate: live_contract verified, real_runner_contract prepared,
grading_isolation_contract required-not-verified, representative_campaign_ready false.
All 42 jobs remain unexecuted. Linux namespace policy and installed version vary by host;
there is no portable abstraction or silent fallback. Next: provide and verify delegated
resource containment plus a minimal immutable toolchain inventory, run the full escape
suite and all positive/wrong graders inside that boundary, then finalize coverage.
This requires a separate approved host capability/contract, not a permission bypass.

## User-scoped resource contract after #37

Owner-accepted #37 merged at `12f25ad25da61a1860a7512b655909f73355c067`.
Read-only investigation explicitly checks the user systemd manager rather than inferring
its capabilities from direct cgroup writability. `systemd --version` was not on PATH;
the installed systemd binary and systemd-run report **262 (262-1-arch)**. systemd-run
supports user units, properties, wait and collection in its help. User-manager status,
show and user-slice queries fail with no usable local transport. An explicit normal
local user-bus address also fails, although the user's bus/socket metadata is present.
The system manager can show user-slice properties: MemoryMax/MemoryHigh exist but are
unlimited, TasksMax exists, and Delegate is no. None proves a constrained grading unit.

Cgroup v2 has memory and pids controllers, including subtree availability; the current
process belongs to a user session scope. The mount is read-only and the current scope
is not writable. No usable rootless delegation was established. Existing prlimit limits
individual processes/shared UIDs, not an accepted per-job aggregate memory/task boundary;
CGroups helper tools are absent. Privileged Docker is not a fallback. No systemd unit,
persistent service, allocation stress test or process-count probe was started, and no
host configuration, permissions or packages changed.

**Result: grading isolation blocked: host lacks verified unprivileged aggregate resource
containment.** This is a failure to demonstrate an available controller path, not proof
that systemd or the kernel never supports such limits. Memory enforcement, process-count
enforcement, descendant coverage and resource-scope cleanup are all not-verified. The
previous Bubblewrap timeout/namespace probes remain partial evidence, not resource proof.
`python3 -B scripts/benchmark_isolation.py --resources` emits bounded typed resource and
isolation states and exits nonzero. It issues only fixed local version/show queries with
an allowlisted environment; it exports no bus addresses, cgroup paths, unit IDs, raw
command output or secrets. Missing properties/controllers are reported unsupported;
property/controller presence alone cannot report enforcement verified.

### Intended composition and acceptance

If an approved user manager/delegation becomes available, the intended order is a
transient user resource service containing Bubblewrap, then the trusted immutable grader
controller and all submitted descendants. No such composition runs in this slice.

| Layer | Responsibility |
| --- | --- |
| User cgroup-v2 service | Aggregate MemoryMax, no swap escape, TasksMax/pids; bounded service lifetime; entire cgroup killed/reaped on timeout/interruption/OOM |
| Bubblewrap | Filesystem/PID/network namespaces, environment allowlist, capability drop, no nested user namespaces; namespace reaper cannot escape the outer resource service |
| Trusted grader | Fixed immutable oracles and normalized verdict; no resource accounting delegated to submitted code |
| Operator/controller | Observe rejection/events and service inactivity plus empty descendant cgroup before accepting cleanup; remove only the transient probe unit |

Future synthetic acceptance should use small bounds (e.g. eight tasks and 32 MiB memory,
with a capped 40 MiB allocation attempt) and finite lifetime. Observe fork rejection and
pids-limit events, plus memory-limit/OOM termination and memory events, in descendants
inside the exact service cgroup. Unit command success is insufficient. Timeout and
interruption require no remaining descendants; failed/unsupported/unknown evidence must
remain distinguishable. The pure complete-contract predicate requires every component,
including descendant scope and cleanup, verified; it is not a launch authorization.

### Minimal runtime candidate, not an accepted inventory

Known fixed host tool versions still match the campaign. Static ELF metadata was read
only from trusted executables/libraries; no submitted program was run. Candidate staging
roles mount read-only at `/runtime/python`, `/runtime/rust`, `/runtime/go`,
`/runtime/libraries`, `/runtime/linker`, and `/trusted`. The staging root must be a dedicated
disposable runtime directory, with no direct normal-home/sysroot mount. Plan drift,
symlinked roots, a Rust root outside staging, broad home/root/system mounts and missing
roles are rejected. Structural validation returns not-verified: bytes and recursive
library/data closure have not been accepted or staged.

| Class | Minimum identified executable/data requirements |
| --- | --- |
| Python | Python 3.14.8 executable (`python3.14`), libpython3.14.so.1.0, standard library/encodings/unittest/json and needed lib-dynload modules; exclude site-packages, user customization and caches |
| Rust | Pinned 1.98.0 sysroot discovered from rustc, staged separately: bin/rustc, librustc_driver-28a98848f7a7c026.so, libLLVM.so.22.1-rust-1.98.0-stable, x86_64 target rustlib including libtest/std; explicit staged sysroot, linker/CRT/libgcc closure |
| Go | Static pinned go executable (no ELF NEEDED entries); staged bin/go, src, pkg/tool/linux_amd64 and pkg/include; work-only build cache, local toolchain, no module download or package-manager cache |
| IaC / JSON | Trusted Python/JSON runtime and immutable grader, with submitted deployment.json treated only as data; no submitted program execution |

The inspected Python/Rust ELF closure names include ld-linux-x86-64.so.2, libc.so.6,
libdl.so.2, librt.so.1, libpthread.so.0, libm.so.6, libgcc_s.so.1 and libz.so.1,
plus the libpython/driver/LLVM files above. Python extension-module dependencies and
compiler/linker data still need a reviewed complete file digest inventory; this list
is not accepted runtime closure. No normal HOME/CODEX_HOME, checkout, artifacts,
credentials or unrelated home contents are copied or mounted. Broad `/usr` binding
remains synthetic namespace investigation only, never the final runtime plan.

Since both prerequisites are unverified, Python/Rust/Go/IaC compatibility and the full
escape suite inside the final composed boundary are **not run/not-verified**. Existing
trusted control tests retain their scope; the JSON-only IaC smoke remains intact.
The campaign gate remains disabled, grading_isolation_contract required-not-verified,
representative_campaign_ready false and all 42 jobs unexecuted. Next obtain an approved
usable unprivileged resource path, prove tiny descendant limits/cleanup, accept the
immutable runtime byte inventory, then run composed grader/escape acceptance. #14 stays
open and partial; #15 is separate. Zero live model calls.

Implementation validation: 69 Python tests, docs-check, just check, nextest (85/85),
diff checks and bounded benchmark context pass with synthetic namespace probes
and fake/mocked benchmark runners.
Local deny is skipped because the advisory cache is mounted read-only; exact-head
green Security CI and check/review success from GitHub Actions app 15368 are required
before owner acceptance. No merge or further live invocation is authorized here.

## Representative development design (separate frozen plan)

The primary question is whether a thin deterministic policy/capability layer can
preserve or improve **completed development-task quality** while reducing unnecessary
context/tool/token cost versus an equivalent native Codex workflow. Retrieval alone
is not the quality unit. The present vanilla/native comparison tests an instruction
policy only; it cannot establish the benefit of a decision-applying Router adapter.
That variant remains unavailable until a genuine adapter exists.

Representative execution also has its own Codex artifact identity. Historical
`initial-development-v1` evidence remains pinned to the inspected Arch Linux
`openai-codex 0.162.1-1` executable (`89cc44e8...`). The representative plan pins
the official OpenAI `rust-v0.162.1` x86_64 musl release archive (`86f268d8...`) and
its extracted executable (`628e3548...`) instead. Both report `codex-cli 0.162.1`;
the differing checksums are expected because they are different packaging channels.
No historical campaign byte or smoke result is rewritten by this representative pin.

Representative toolchain provenance is also separate from the historical Arch host.
Rust/Cargo 1.98.0 use the official minimal x86_64 GNU component archives: rustc (`0e37cb33...`), Cargo (`2f512d17...`) and rust-std (`f5022e6c...`).
Go uses the official `go1.27.2.linux-amd64.tar.gz` archive (`ecbadb99...`) and therefore
expects `go version go1.27.2 linux/amd64`; the historical Arch `X:nodwarf5` build remains
unchanged only in `initial-development-v1`. Python 3.14.8 uses the official source
archive (`c2215904...`) and must be built into the staged runtime. These artifact pins
establish provenance, not runtime qualification; executable, sysroot, linker, library and
standard-library byte inventories remain a separate host evidence requirement.

Whole-agent credential isolation is now an explicit independent gate. Exact pinned
`0.162.1` source shows keyring mode has no file fallback and removes `auth.json` after
successful keyring storage, while the default child shell environment inherits all
parent variables. Synthetic probes on the disposable Ubuntu VM confirmed the risk:
default `codex sandbox` could read a synthetic auth file and inherited a synthetic
`OPENAI_API_KEY`. With `shell_environment_policy.inherit=core`, the API key was absent
while PATH/HOME remained available. The user D-Bus socket was visible but a child
connect returned `EPERM`. A synthetic keyring-backing file was also readable by default; the representative permission profile now extends `:workspace` and denies read access to `~/.local/share/keyrings`, which made that backing file unreadable in the pinned Linux sandbox. Exact-source review is frozen separately in
`agent-execution-source-review-v1.json` (`bca3f3d3...`): headless exec uses approval
policy `Never`, model-visible execution routes through sandbox orchestration, subagents
inherit the effective runtime policy, and Code Mode lacks ambient process/env/fs globals.
The representative campaign also disables multi-agent and account/network-backed
app/plugin/browser/computer/image/skill-search surfaces for both variants. No real
credential or model call was used. These observations motivate the pinned
`agent-execution-isolation-v1` contract; they do not verify or accept runtime evidence.
The reproducible credential-free probe produced candidate reference `ae2840a9...`,
frozen in `agent-execution-isolation-candidate-v1.json`; the accepted-evidence list
remains empty, so this candidate cannot enable execution.

Seven kinds of evidence must remain separate:

1. **Harness validation:** the original seven scenarios are harness/component coverage.
2. **Codex live-contract smoke:** one successful bounded JSON-only IaC smoke verifies
   startup/auth/JSONL execution; its counters remain smoke observations, not comparisons.
3. **Historical preliminary plan:** `initial-development-v1` remains unchanged at
   seven scenarios × two variants × three repetitions = 42 unexecuted calls.
4. **Representative design:** `representative-development-v1` proposes ten tasks with
   independent graders and trusted controls; this PR seeks acceptance of that matrix.
5. **Agent execution isolation:** required-not-verified; credentials must remain parent-only and all model-reachable command paths require review.
6. **Grading isolation:** required-not-verified; correctness checks do not establish it.
7. **Measured evidence:** none. No comparative result, savings or winner exists.

The separate [representative manifest](../benchmarks/representative-manifest.json)
uses measurement-only metadata. It is never Router input; qualitative tiers describe
fixture structure, not LOC, language-based routing, or repository-size heuristics.
Purpose-built fixtures remain bounded local systems, not evidence for all repositories,
frameworks or workloads. The matrix is selected for distinct quality risks, not likely
savings. Python occupies three of ten tasks rather than dominating the suite.

| Scenario | Domain | Task/risk | Tier | Lifecycle |
| --- | --- | --- | --- | --- |
| rust-ledger | Rust | Signed refund bug; posted/pending callers | multi-file | inspect, edit, tests, build, impact |
| rust-duration | Rust | Named API refactor; formatting/scheduling callers | cross-cutting | inspect, edit, tests, build, impact |
| go-pagination | Go | Feature/API; offsets, exhaustion, response adapter | multi-file | inspect, edit, tests, build, impact |
| go-reservations | Go | Expiry bug/refactor; availability/report agreement | multi-file | inspect, edit, tests, build, impact |
| python-config-tests | Python | Test work; parser/consumer mutation detection | focused | inspect, edit, tests |
| python-billing | Python | Behavioral feature; monetary rounding/receipts | multi-file | inspect, edit, tests, impact |
| python-result-api | Python | Tagged-result API migration; absence vs falsy | cross-cutting | inspect, edit, tests, impact |
| infra-service-policy | Infrastructure | Least privilege and ingress across configs | multi-file | inspect, edit, declarative tests, impact |
| repo-ci-gates | Repository/CI | Build/test dependency graph and publish trust | cross-cutting | inspect, edit, declarative tests, impact |
| explore-notification | Exploration | Read-only conditional call flow and side effect | focused | inspect, impact |

Inspection and exploration correctness are independently checked. Edit scenarios
require several lifecycle steps and six or more multi-file/cross-cutting tasks; all
compiled-language tasks require build/check validation. Independent compilation/tests
verify the functional contract; lifecycle metadata states requested work, not observed
proof that an agent actually performed each step. Future trace review must distinguish
those. Declarative tasks do not deploy infrastructure or contact a CI service.

### Independent controls and leakage

[Representative graders](../benchmarks/representative_graders.py) use trusted oracles
outside the staged workspace. Only baseline files and developer-intent prompts are
staged. Reference patches, two plausible wrong controls per task, and oracle assertions
remain in benchmark-owned fixture JSON and are not staged. Agent sessions must be
restricted to their fixture, with no access to this repository's controls/oracles.
Snapshot pins cover initial file maps; campaign pins cover complete fixtures and the
grader, so hidden-control changes also require review/repinning.

Correct references must pass; both wrong controls must fail. Behavioral oracles check
refund signs and pending entries, caller units/invalid durations, pagination boundaries,
exact expiry, integer rounding, and absent/falsy distinctions. The `python-billing`
contract explicitly discounts each unit with integer-floor rounding **before** applying
quantity; its prompt, staged README, reference and oracle are pinned to that same order.
This wording is regression-tested because an authorized smoke exposed an earlier prompt
that incorrectly said to round each line after multiplication. The test task must pass
on the real parser and fail three independent mutants (truthiness, invalid acceptance,
and case coercion); production parser/consumer files must remain unchanged. CI/security
oracles validate the complete JSON contract and preserve unrelated policy. Exploration
checks both conditional paths and preserves all source. Submitted tests are never the
sole quality oracle. Prompts describe intent, not hidden values or patch structure.
Filename/phrase/reference-substring leakage checks are deterministic guards, supplemented
by manual prompt review; they do not prove absence of all semantic leakage.

Run `python3 -B scripts/benchmark_coverage.py` for a credential-free, read-only design
validation; it executes no tools/models and creates no artifacts. The explicit
`--trusted-controls` option executes **only repository-authored** references/wrong
controls locally. That host subprocess path verifies grader correctness, not grader
security isolation; it must never be used for model submissions. The coverage validator
has no real mode. The prepared representative entry is
described in [the host/runner contract](benchmark-host.md); it remains blocked.
The historical entry accepts only its immutably blocked preliminary contract.

### Call budget and provenance

The [new campaign](../benchmarks/representative-campaign-v1.json) has ten scenarios ×
vanilla/native × **two repetitions** = **40 maximum primary Codex executions**, seed 14, zero retries,
120-second timeout. Two repetitions are the minimum initial paired design to expose
run variability; they do not justify significance or broad claims. More repetitions
require a new reviewed budget. Failures remain evidence and in denominators; only
quality-equivalent matched runs enter cost comparisons. Unknown counters remain null;
there is no winner logic or derived fresh-input counter.

Vanilla/native use equivalent frozen executable/model/reasoning/auth settings and the
same core-only child environment policy; only the native instruction differs. Legacy
lacks provenance; Router-v2 lacks an
adapter. Neither is fabricated. The representative adapter, qualified-host receipt, agent-execution isolation, constrained
grading backend and production submission grader are now accepted and technically ready.
The separately frozen `representative-live-smoke-v1` uses `python-billing` / `vanilla`,
seed 14, repetition 0, retries zero and at most one `codex exec`. It is not included in
the 40 primary executions and cannot be counted as comparative evidence. Its offline path
is non-executing; its real path first requires the complete 40-run entry to reach only
the explicit authorization gate and then requires a distinct
`--authorize-smoke-execution` flag. One `codex exec` can make multiple internal model
requests while completing an agent turn, so neither the smoke nor campaign claims an
internal model-request ceiling. Internal model-request count is unsupported by the
normalized trace and remains null for executed jobs.

The reviewed split-host campaign path keeps the same frozen 40 primary jobs while
separating roles: Codex agent execution occurs on the eligible agent host and only a
bounded UTF-8 submission envelope crosses to the already accepted grading host. The
transport contains no credentials and exports only fixture/reference paths using
descriptor-relative no-follow reads; hardlinks and special nodes are rejected.
Exploration additionally rejects unexpected artifacts before export. Each job writes an
immutable `started` ledger immediately before Codex may launch. A started job is never
retried, including after interruption, so resume cannot exceed the 40-process budget.
The grading host independently reparses raw traces, verifies transfer hashes/envelopes,
reconstructs a private submission workspace and uses the accepted production grader.
The split-host candidate evidence `1a9e7a...` is accepted; execution still remains
fail-closed without explicit 40-run authorization.

### Qualified host dependency and stopping current-host investigation

#38 merged as `0f220d0caadfb08b15a640f3581bb01ff2b7f759`. Its current-host result is
final: systemd/cgroup-v2 present, user resource manager unavailable, direct delegation
unavailable, aggregate memory/tasks and grading isolation unverified. No further
current-host workarounds, service/login/cgroup changes, installations, sudo, or
privileged/rootful container fallback are planned. This machine cannot qualify for
submitted-code grading. Running submissions on the normal authenticated host is not
an approved campaign configuration.

A separately qualified host must demonstrate all of:

- unprivileged aggregate memory and task/process limits with observed enforcement;
- descendant containment and whole-tree cleanup on timeout/interruption;
- accepted immutable runtime/toolchain/grader inventory with exact pins;
- Bubblewrap-equivalent filesystem, network, environment and privilege isolation;
- verified agent-execution credential boundary: keyring-only auth, absent auth file, core-only child environment, blocked child credential IPC and reviewed model-reachable command paths;
- complete escape probes and positive/wrong grader compatibility inside that same boundary.

The reviewed execution contract now has a qualified separate host, accepted agent-
execution isolation, accepted constrained grading-backend evidence and accepted
production submission-grading evidence. No campaign flag can override those contracts.
The representative runner additionally requires a full rehash of the reviewed staged
runtime before checking exact Codex and staged Rust/Cargo/Go/Python identities; host
`PATH` toolchains are not accepted. It injects those staged paths through the frozen
Codex shell-environment policy. Credential-free readiness evidence `ea86c70f...` verifies
config parsing, Rust/Go/Python compile/run both directly and inside the exact Codex `:workspace` sandbox and the final no-authorization refusal with
zero model calls. Technical readiness is true; execution authorization is still separate. Coverage remains reviewable independently, both
campaigns remain unexecuted, and benchmark status stays partial until measured evidence
exists. #14 stays open; #15 separate.

### Structural workload realism amendment

Language/task diversity is an accepted candidate. This amendment strengthens workload
realism without changing any of the ten identities, variant bounds or 40-execution budget.
The suite is **purpose-built representative synthetic coverage**; it does not claim
large real-world repository coverage. Structural counts are acceptance metadata,
never production Router signals or proxies for token savings.

| Scenario | Tier | Initial files | Changed reference files | Unchanged support files |
| --- | --- | ---: | ---: | ---: |
| rust-ledger | multi-file | 11 | 3 | 4 |
| rust-duration | cross-cutting | 11 | 4 | 3 |
| go-pagination | multi-file | 8 | 4 | 3 |
| go-reservations | multi-file | 9 | 3 | 4 |
| python-config-tests | focused | 3 | 1 | 1 |
| python-billing | multi-file | 9 | 3 | 5 |
| python-result-api | cross-cutting | 8 | 4 | 3 |
| infra-service-policy | multi-file | 6 | 2 | 3 |
| repo-ci-gates | cross-cutting | 6 | 3 | 2 |
| explore-notification | focused | 11 | 1 | 4 |

Changed-reference counts include added regression tests. Tier acceptance is stricter:
**multi-file** requires four initial files and two changed existing behavior/configuration
files participating in the dependency graph; **cross-cutting** requires five initial
files, three such changes and a dependency path with at least two edges. Added tests,
README changes or Cargo metadata alone cannot meet those change thresholds. **Focused**
means a narrow reviewed measurement purpose (mutation-sensitive tests or conditional
analysis), not a size classification; exploration spans more files while remaining
read-only. Unchanged support must participate in the graph, with at least one supporting
file not named as the direct prompt target. At least one wrong control for each complex
task restores a stale initial caller/configuration while keeping the rest of the
reference patch; all wrong controls must fail the independent grader.

The supporting context is functional: exports and formatters, billing and command
callers, local request adapters, booking/audit readers, quote/summary layers, service
and archive entry points, deployment/policy links and multi-file CI configuration.
Existing tests and contracts help distinguish preserved behavior from requested changes.
These surfaces create decisions about what to inspect and which consumers to validate,
without adding random text or optimizing for LOC. They do not prove an agent will avoid
reading the entire fixture; eventual measured traces must establish context-selection
behavior. No measured comparative evidence exists.

Exploration has both live dispatch branches: notification performs profile resolution,
eligibility/preferences, destination selection and gateway delivery; archive records
an audit event. The independent answer checks invocation order for delivered/suppressed
notification paths and the external boundary, preserving every source file. Adjacent
archive/audit code is genuine functionality rather than dead filler.

Hidden fixture `structure` fields pin initial/changed counts, unchanged support and
reviewed dependency edges. Edge witnesses must occur in the original caller and their
referenced symbols in the callee; both files must exist. These deterministic checks
verify the reviewed textual relationship and reject drift, not arbitrary semantic
claims about a graph. Human review establishes relationship meaning. Hidden structural
evidence, reference changes, controls and oracles remain outside staged task files.
Prompts state developer intent and public behavior; they do not enumerate relevant
supporting files. Human and deterministic leakage review was repeated after expansion.

`python3 -B scripts/benchmark_coverage.py` now emits a deterministic safe review report:
scenario, domain, task classes, tier, initial count, changed-reference count, support
count and lifecycle requirements. It reveals no changed filenames, dependency witnesses,
reference source or grader assertions, and never executes tools/models. This report
is for design review, not the model-visible task or Router input.

Both Rust fixtures are normal dependency-free Cargo libraries with `Cargo.toml`, a
pinned local lockfile, `src/` modules and integration tests. Trusted-control validation
uses `cargo check --locked --offline` and `cargo test --locked --offline`, including the
fixed independent integration oracle. Already-installed Cargo was inspected as
**cargo 1.98.0 (797e8a9bc 2026-08-05)** and is frozen with `--version` in the representative
campaign only. JSON version/argument drift rejects loading; an actual version mismatch
refuses trusted controls. Trusted controls use `rustup run` without `--install`: the already-installed
1.98.0 alias when the CI selector is exactly 1.98.0, otherwise the installed stable
alias. Unknown selector values are ignored; either alias must produce the exact
frozen Cargo identity before controls proceed. This corrects CI default selection
without changing the pin or installing a toolchain. It is a trusted-control launcher,
not the future staged-runtime launcher. No toolchain was installed or updated. Offline/private
Cargo cache settings prevent registry setup; trusted host validation remains correctness
only, with no security-isolation claim.

The future accepted immutable Rust inventory must include the exact Cargo binary
alongside the pinned real rustc/sysroot, target libraries, compiler shared-library
closure, linker and CRT. Cargo must use disposable private home/target directories,
offline locked builds and no registry dependencies. A qualified host must demonstrate
that precise Cargo workflow within the final isolation boundary. This documentation
adds an inventory requirement, not a verified runtime or a host fallback.

Campaign execution history is unchanged: both campaigns remain unexecuted. Technical representative readiness is now true after accepting production submission-
grading evidence `199ec772...`, wiring mandatory staged-runtime verification into the
runner and pinning credential-free readiness evidence `ea86c70f...`.
Readiness is not authorization: the plan path remains non-executing and the real path
still requires explicit authorization after all identity/auth/runtime gates. The
historical seven-component manifest/preliminary 42-job plan and smoke evidence remain
byte-identical. #14 stays open until measured evidence exists; #15 separate.

### Representative runner contract preparation

#56 merged as `707c5f080af279cd99f54bfab564c3fe92798709`; active stage stays benchmark.
The matrix and representative runner contract are accepted. A separate-host receipt,
agent isolation, constrained grading backend and production submission grader are all
reviewed and accepted; the runner requires a prepared fully rehashed grading runtime.
Technical readiness is true, while measured comparative evidence remains absent because
no campaign execution has been authorized or performed. See [the typed qualification
and execution contract](benchmark-host.md). The historical development host remains
non-qualified.

`python3 -B scripts/benchmark_representative.py` prints an offline credential-free
40-job plan with zero model calls and no artifacts or tool execution. One guarded
public real entry consumes reviewed qualification evidence and frozen security gates;
operator authorization cannot bypass them. Submission grading has only an isolation
interface, with no direct-host fallback. Read-only exploration requires immutable task
files and permits its answer artifact only. Normalized evidence contains safe counters,
fixed failure categories and opaque host/isolation references; unsupported counters
remain null. Synthetic attempts never claim real model calls or comparative results.

Historical preliminary campaign bytes, 42-job budget, smoke and failed evidence remain
unchanged. The representative budget remains 40, two repetitions, vanilla/native, seed
14, retries zero, timeout 120 seconds. A separate one-execution representative smoke is
now frozen outside that budget; it cannot execute without distinct operator authorization.
Technical readiness is verified, but neither the representative smoke nor either campaign
has been executed. #14 remains open and partial until measured evidence exists; #15
remains separate.
