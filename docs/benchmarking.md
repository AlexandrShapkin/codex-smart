# Development benchmark protocol

This is the first harness slice of #14, not a measured campaign. Router remains
validated; benchmark progress is partial after the harness merge. No benefit or winner is claimed. #15 production telemetry is separate.

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

## Remaining acceptance campaign

Design and verify grading isolation, finalize realistic task coverage,
preserve the frozen toolchains and campaign model/settings, validate all graders within that boundary,
and run repeated seeded quality-first measurements with cache/overhead evidence.
Obtain exact legacy provenance or retain unavailable status. Implement and verify a
separate decision-applying adapter before any Router v2 measurement. #14 stays open
until those measured acceptance criteria are satisfied; #15 remains separate.

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

Recommended next #14 task: **Design and verify the grading isolation boundary, then
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
The next slice examines an already installed Linux backend without installing packages,
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

Implementation validation: 60 Python tests, docs-check, just check, nextest (85/85),
diff checks and bounded benchmark context pass with synthetic namespace probes
and fake/mocked benchmark runners.
Local deny is skipped because the advisory cache is mounted read-only; exact-head
green Security CI and check/review success from GitHub Actions app 15368 are required
before owner acceptance. No merge or further live invocation is authorized here.
