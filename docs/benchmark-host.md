# Benchmark qualified-host and representative runner contract

Status: one bounded qualified-host receipt (`d2af64ce...`), agent-execution
isolation evidence (`ae2840a9...`), the constrained grading backend (`af25f513...`) and
production submission-grading evidence (`199ec772...`) are accepted. The representative
runner is wired to require a fully rehashed reviewed grading runtime before its explicit
authorization gate, and the frozen technical readiness flag is now true. This does not
execute or authorize the campaign: both plans remain unexecuted, the offline plan reports
`model_execution_enabled=false`, and the real entry still requires explicit operator
authorization plus all runtime/identity gates. Active work remains #14 until measured
evidence exists; #15 remains separate.

## Qualification boundary

[host-contract-v1.json](../benchmarks/host-contract-v1.json) freezes the platform,
identity requirements, required components and accepted receipt policy.
[benchmark_host.py](../scripts/benchmark_host.py) evaluates typed component evidence
without executing tools, probing the machine or discovering paths. Required states
are `verified`, `blocked`, `unavailable` or `not-verified`. Missing, duplicate,
misordered, unknown or malformed components fail closed.

Every component must be independently verified and have a non-secret SHA-256
reference to its reviewed evidence. A receipt consists only of contract ID and
component/state/evidence-hash tuples; it contains no overall status override, host
identifier, private runtime path, prompt, source or arbitrary payload. Qualification
is a conjunction, not a score. **Self-asserted verified states and hashes are
insufficient**: the computed receipt reference must also be explicitly accepted by
the frozen reviewed host contract. The contract accepts one reviewed receipt,
`d2af64ce...`, tied to the exact normalized candidate evidence file
`qualified-host-candidate-v1.json` (`5b8c8846...`). Any future receipt still requires
independent review and an explicit contract update; hashes identify evidence, not
authenticate the truth of a declaration. The receipt reference hashes component
evidence only; it is not a self-referential file checksum.

| Component | Required independent evidence |
| --- | --- |
| Platform | Compatible Linux x86_64 execution and namespace/resource capabilities |
| Codex identity | Exact official `rust-v0.162.1` x86_64 musl release asset/archive and executable bytes, plus codex-cli 0.162.1 |
| Toolchains and Cargo | Exact frozen versions/arguments, including Cargo 1.98.0 |
| Isolation backend | Exact reviewed unprivileged backend identity plus the CVE-2026-87766 mount-topology guard and synthetic positive/negative controls |
| Aggregate memory | Observed bounded allocation rejection/termination within an aggregate limit |
| Aggregate tasks | Observed aggregate task/process rejection, not just command success |
| Descendants | Controls apply to children and grandchildren |
| Cleanup | Whole-tree cleanup after timeout, kill and interruption; no persistence |
| Network | TCP/UDP escape attempts blocked in the final boundary |
| Filesystem | External reads/writes and symlink escapes blocked; no HOME/CODEX_HOME, artifacts or checkout exposure |
| Environment | Allowlisted environment; synthetic secret absent; no inherited auth/proxy secrets |
| Agent execution isolation | Keyring-only auth, no readable auth file, core-only child environment, blocked child access to credential IPC, reviewed model-reachable command paths |
| Privilege | No sudo, privileged containers, capability escalation or unsafe host devices |
| Trusted grader immutability | Independent grader/oracles/configuration outside submitted writable files |
| Runtime inventory | Accepted immutable executable, sysroot, Cargo, library/linker/data closure with reviewed byte identities |
| Grader compatibility | All ten references pass and all wrong controls fail inside the same final boundary |

The representative contract intentionally does not reuse the historical Arch Linux
package executable identity. The historical smoke remains pinned to its inspected
`openai-codex 0.162.1-1` bytes (`89cc44e8...`) and is unchanged. The representative
qualified-host contract instead pins OpenAI's official `rust-v0.162.1`
`codex-x86_64-unknown-linux-musl.tar.gz` asset (`86f268d8...`) and the extracted
static-pie executable (`628e3548...`). This separates historical provenance from a
portable upstream artifact suitable for the disposable Ubuntu qualification host.

Representative toolchains follow the same rule instead of inheriting the historical
Arch host identity. Rust/Cargo 1.98.0 are pinned to the official minimal x86_64 GNU component
archives: rustc (`0e37cb33...`), Cargo (`2f512d17...`) and rust-std (`f5022e6c...`), Go to the official `go1.27.2.linux-amd64.tar.gz`
archive (`ecbadb99...`) whose version is `go1.27.2 linux/amd64`, and Python 3.14.8
to the official source archive (`c2215904...`) for a staged source build. The historical
Go `go1.27.2-X:nodwarf5` pin remains historical evidence only and is not a qualified-host
requirement. Runtime executable/library bytes still require a separate reviewed immutable
inventory; source/archive provenance alone does not qualify them.

The reviewed grading-backend candidate is deliberately narrower than accepting Ubuntu's
Bubblewrap package in general. `grading-isolation-backend-v1.json` pins `/usr/bin/bwrap`
`0.11.1-1ubuntu0.3`, executable SHA-256 `523da3e7...`, the loaded Ubuntu
`bwrap-userns-restrict` profile SHA-256 `d61facde...`, and
`kernel.apparmor_restrict_unprivileged_userns=1`. That upstream version is explicitly
known to be affected by CVE-2026-87766; the contract does not claim otherwise. The
compensating invariant is structural: attacker-controlled workspace content may only be
bound once at `/work`, never at `/`, and that bind must be the final filesystem operation
performed by Bubblewrap. No `--dir`, `--file`, nested bind, tmpfs, device/proc mount,
symlink or other destination-creating operation may follow it. A repository validator
constructs and checks this exact plan before process launch.

The candidate probe requires both sides of the threat model. On the exact pinned Ubuntu
binary, the upstream-vulnerable synthetic topology (`untrusted` bound at `/` followed by
a destination-creating operation beneath an attacker symlink to `/oldroot`) must actually
escape into a disposable host target; otherwise the probe is not exercising the known
issue. The constrained topology must then complete with the same malicious symlink while
creating nothing in that host target. The accepted normalized backend evidence reference
is `af25f513...`; it made zero model calls. This accepts only the constrained backend
contract, not a qualified host and not arbitrary Bubblewrap 0.11.1 invocations.

Pinned `0.162.1` source and synthetic VM probes also separate credential ownership
from model-reachable child execution. The pinned keyring backend has no file fallback
and removes `auth.json` after a successful keyring save. The default shell environment
policy is unsafe for this benchmark: a synthetic `OPENAI_API_KEY` reached `codex sandbox`
and a synthetic `auth.json` was readable. Under the exact representative override
`shell_environment_policy.inherit=core`, the synthetic API key was absent while PATH
and HOME remained available.  `/run/user/1001/bus` was visible to the child but a Unix
socket connect returned `EPERM`. A second probe used a parent-only Unix socket as a
private credential-bus surrogate: `DBUS_SESSION_BUS_ADDRESS` was absent from the
core-only child environment and the child could not connect even when given the exact
socket path. A separate synthetic keyring-backing file was readable under the default sandbox, then became unreadable under a reviewed `permissions.benchmark` filesystem deny for `~/.local/share/keyrings`. Exact-source review at commit `092d3acd...` is pinned
by `agent-execution-source-review-v1.json` (`bca3f3d3...`): `codex exec` hard-defaults
approvals to `Never`, approval requests are unsupported in exec mode, shell/unified-exec
and apply-patch route through sandbox orchestration, spawned agents inherit live runtime
policy, and Code Mode exposes controlled V8 globals/tools rather than ambient process
APIs. The representative campaign additionally disables multi-agent, Code Mode and
account/network-backed app/plugin/browser/computer/image/skill-search features. The
normalized credential-free candidate is frozen as
`agent-execution-isolation-candidate-v1.json`, reference `ae2840a9...`, and that exact
reference is now accepted by `agent-execution-isolation-v1.json`. Acceptance is still
conjunctive: the qualified-host receipt must carry the same component reference, and
the frozen campaign readiness gate remains false. No real credential or model call was
used for these probes.

The accepted receipt refers to one composed boundary and inventory; any future
receipt must preserve the same review discipline. Review actual resource limits,
descendant scope and cleanup owner together. Version output,
controller existence, environment filtering, timeout alone or broad read-only `/usr`
mounts do not verify isolation. Rust sysroot/Cargo must be staged without normal HOME,
credential material or mutable package caches; runtime inventory must support offline
locked check/test. No vendor or distribution recommendation is made.

The current development host is not a candidate for further qualification work unless
its capabilities materially change. Retained #37/#38 evidence reports systemd/cgroup-v2
present, user manager and delegation unavailable, aggregate memory/tasks unverified.
`current_host()` returns non-qualified without repeating those inspections. Future
qualification happens on a separately provisioned host satisfying this contract.
No installation, sudo, global security changes or privileged fallback is permitted.

## One representative production entry

[benchmark_representative.py](../scripts/benchmark_representative.py) is the sole
production-facing representative `real_run` entry. It consumes a computed
`QualifiedHostContract`, not component declarations it reinterprets itself. CLI
`--qualification-evidence` imports the strict non-secret receipt; absence uses the
retained non-qualified current-host evidence. `--real` and explicit
`--authorize-execution` cannot override a failed security gate.

Gate order:

1. Frozen representative campaign, manifest, fixtures, graders, runner/harness and all
   qualification/isolation/production-grading pins.
2. Fully verified reviewed qualified-host result and frozen host-readiness state.
3. Verified agent-execution isolation state and accepted credential/child-execution evidence.
4. Verified grading-isolation state and accepted constrained backend evidence.
5. Verified accepted production submission-grading evidence.
6. Frozen `representative_campaign_ready=true` technical-readiness state.
7. Full topology/byte rehash of the staged grading runtime against the accepted inventory.
8. Explicit absolute Codex executable plus exact SHA/version and exact Rust/Cargo/Go/Python versions from that prepared runtime; host `PATH` toolchains are not accepted substitutes.
9. Runtime auth preflight: keyring-only contract, no parent `OPENAI_API_KEY`, no `auth.json`.
10. Explicit operator execution authorization.
11. Fresh private artifact target; existing identifiers and symlinks rejected.
12. Only then model execution and isolated grading.

Readiness is deliberately distinct from authorization. A technically ready campaign
still performs zero model calls unless step 10 is explicitly satisfied. The historical
campaign remains immutably blocked by its own frozen loader and cannot become an
alternate representative path. Legacy harness real mode stays disabled. Private
injection-only helpers have no direct process-launch behavior.

The adapter reuses staging, seeded ordering, trace parsing, frozen auth/argv and
quality-first aggregation. Ten tasks × vanilla/native × two repetitions = 40 primary
runs, seed 14, zero retries, 120 seconds. There are no automatic smokes or hidden extra
model calls. Native instruction is the only variant difference. Keyring routing,
normal CODEX_HOME, ephemeral/ignore-user-config/ignore-rules remain intact, without
credential copying or auth-file creation. Identity preflight occurs once per campaign,
not once per job.

## Submission grading boundary

Representative submissions go only through `grade_representative` in the isolation
abstraction. The accepted production implementation requires the reviewed host/backend
receipt, accepted production-grading evidence and a prepared runtime object produced by
a full inventory rehash. It never calls the direct trusted-control host grader and never
falls back to host execution.

The sandbox-side controller opens only reviewed expected submission paths with
descriptor-relative `O_NOFOLLOW`, rejects hardlinks/special nodes and copies bounded
UTF-8 bytes into private tmpfs before the independent grader runs. Verdict transport is
a private Unix socket established before untrusted code executes; the service is kept
anchored until its cgroup is empty. For `explore-notification`, original task files are
immutable and only `answer.json` is permitted. These controls passed the accepted
positive/wrong and security-control suite on the qualified host.

## Normalized evidence and failure accounting

Per completed attempt, schema version 1 records campaign/scenario/variant/repetition/
seed, frozen references, host qualification, agent-execution isolation, grading-isolation,
production-grading and grading-runtime-inventory references, terminal status, process exit, parser validity and bounded error categories, independent quality,
failure category, duration, observed tokens and completed-tool lower bound. Include
execution kind, attempt count and zero retry count. Internal model-request count is not
reliably exposed by the current trace contract and remains null for executed jobs;
preflight refusal/plan can report zero because no model execution occurred.

Observed token keys are input, cached input, output and reasoning. Fresh input, total
and full tool-call count remain null; never subtract or derive them. Parser-invalid
usage stays null. Normalization whitelists fields; arbitrary event payloads, prompts,
source, stderr and private paths cannot enter normalized records. Raw traces/stderr
remain local under private gitignored artifact directories. No measured records are
committed by this slice.

Distinguish qualification/preflight refusal (zero attempts and model calls), launch/
process/timeout failure, agent terminal failure, invalid trace, grading refusal and
quality failure. Completed normalized records are written exclusively per job and
survive later interruption where feasible. Failures remain in pass/failure denominators;
only quality-equivalent matched scenario/repetition/seed/reference strata enter cost
comparison. No retries, discarded failures or winner logic. Synthetic adapter tests
report 40 synthetic attempts and zero model calls, not comparative measurements.

## Readiness and next action

Matrix, host receipt, agent isolation, constrained grading backend and production
submission-grading evidence `199ec772...` are accepted. The runner now passes a fully
verified `PreparedRuntime` into every isolated grade and records both the production-
grading evidence and runtime-inventory references. Host `PATH` is no longer used for
representative toolchain identity: the runner verifies and injects the exact staged
Rust/Cargo/Go/Python binaries and linker/library paths through the frozen Codex shell
environment policy. Credential-free readiness probe `ea86c70f...` on srv0 verified the
full runtime rehash, exact Codex/toolchains, Codex environment-config parsing, Rust/Go/
Python compile/run and the final pre-authorization refusal with zero model calls, zero
attempts and no artifact creation. Frozen technical readiness is true.

No campaign execution occurred in this promotion. Repository-owned production controls
remain 10/10 references, 20/20 wrong controls and 9/9 security controls with zero model
calls and no real credentials. The offline plan remains non-executing; the real entry
still refuses before artifacts/model execution unless exact Codex/toolchains, agent auth
runtime, full grading-runtime rehash and explicit authorization all pass. Historical 42
jobs and representative 40 primary executions remain unexecuted; successful IaC smoke
and historical failed evidence remain unchanged. Before spending the 40-execution
representative budget, `representative-smoke-v1.json` freezes a separate one-execution
`python-billing`/`vanilla` smoke. The smoke reuses the complete production preflight, is
excluded from comparative metrics, has retries zero and requires its own explicit
`--authorize-smoke-execution` flag. #14 stays open until measured evidence exists; #15
separate.

A split-host representative topology is also staged for the measured campaign because
`srv0` cannot reach the model endpoint from its current egress. This is not a proxy or
VPN topology: the agent process runs directly on the agent host, while `srv0` remains
the accepted trusted grading host. Credentials never cross between hosts. Only a bounded
submission JSON envelope is transported, and the grading host independently validates
and grades it. The topology has a 40-entry pre-launch ledger with no retry of any started
job, preserving the frozen maximum of 40 Codex processes. Its candidate evidence `1a9e7a...` is accepted; explicit campaign authorization is
still required before any Codex execution.
