# Benchmark qualified-host and representative runner contract

Status: prepared adapter and reviewed qualification semantics; no qualified host or
accepted grading backend. Active work remains #14. The representative matrix was
accepted in #39; #56 planned future stages separately. No 0.4+ runtime feature,
benchmark model execution, campaign execution or telemetry is added here.

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
the frozen reviewed host contract. That acceptance list is currently empty. A future
review must inspect independent evidence before admitting a receipt; hashes identify
evidence, not authenticate the truth of a declaration. The receipt reference hashes
component evidence only; it is not a self-referential file checksum.

| Component | Required independent evidence |
| --- | --- |
| Platform | Compatible Linux x86_64 execution and namespace/resource capabilities |
| Codex identity | Exact reviewed executable bytes and codex-cli 0.162.1 |
| Toolchains and Cargo | Exact frozen versions/arguments, including Cargo 1.98.0 |
| Isolation backend | Reviewed unprivileged backend identity/version; candidate Bubblewrap 0.13.0 alone is not acceptance |
| Aggregate memory | Observed bounded allocation rejection/termination within an aggregate limit |
| Aggregate tasks | Observed aggregate task/process rejection, not just command success |
| Descendants | Controls apply to children and grandchildren |
| Cleanup | Whole-tree cleanup after timeout, kill and interruption; no persistence |
| Network | TCP/UDP escape attempts blocked in the final boundary |
| Filesystem | External reads/writes and symlink escapes blocked; no HOME/CODEX_HOME, artifacts or checkout exposure |
| Environment | Allowlisted environment; synthetic secret absent; no inherited auth/proxy secrets |
| Privilege | No sudo, privileged containers, capability escalation or unsafe host devices |
| Trusted grader immutability | Independent grader/oracles/configuration outside submitted writable files |
| Runtime inventory | Accepted immutable executable, sysroot, Cargo, library/linker/data closure with reviewed byte identities |
| Grader compatibility | All ten references pass and all wrong controls fail inside the same final boundary |

Future receipts must refer to the same composed boundary and inventory. Review its
actual resource limits, descendant scope and cleanup owner together. Version output,
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

1. Frozen representative campaign, manifest, fixtures, graders, runner/harness,
   qualification/isolation/resource code and host-contract pins.
2. Fully verified, reviewed qualified-host result and frozen host-readiness state.
3. Verified grading-isolation state and an accepted backend contract.
4. Explicit absolute Codex executable, exact SHA/version and all exact toolchains.
5. Explicit operator execution authorization.
6. Fresh private artifact target; existing identifiers and symlinks rejected.
7. Only then model execution and isolated grading.

Current frozen host/isolation fields are `required-not-verified` and the isolation
abstraction accepts no runtime backend. Consequently public execution is unreachable,
even with synthetic all-verified claims or authorization. Future acceptance needs
separately reviewed evidence, backend implementation and explicit frozen-contract
updates. The historical campaign remains immutably blocked by its own frozen loader;
it cannot become an alternate representative path. Legacy harness real mode stays
disabled. Private injection-only helpers have no direct process-launch behavior.

The adapter reuses staging, seeded ordering, trace parsing, frozen auth/argv and
quality-first aggregation. Ten tasks × vanilla/native × two repetitions = 40 primary
runs, seed 14, zero retries, 120 seconds. There are no automatic smokes or hidden extra
model calls. Native instruction is the only variant difference. Keyring routing,
normal CODEX_HOME, ephemeral/ignore-user-config/ignore-rules remain intact, without
credential copying or auth-file creation. Identity preflight occurs once per campaign,
not once per job.

## Submission grading boundary

Representative submissions go only through `grade_representative` in the isolation
abstraction. That boundary currently refuses without reading/executing submitted files
or probing this host. It never calls the direct trusted-control host grader. Its future
accepted backend must use immutable pinned independent graders and return a typed
quality result; failure/refusal does not silently fall back to host execution.

For `explore-notification`, a typed submission policy requires original task files
immutable and permits only `answer.json` as the answer artifact. The isolated grader
must enforce preservation and reject other task changes; the policy conveys no oracle
contents or relevant-file hints. This enforcement is **not yet security-verified**.
Repository-authored reference/wrong controls may still use the explicitly named
trusted-control path to verify correctness; those results do not qualify model grading.

## Normalized evidence and failure accounting

Per completed attempt, schema version 1 records campaign/scenario/variant/repetition/
seed, frozen references, host qualification and grading isolation references, terminal
status, process exit, parser validity and bounded error categories, independent quality,
failure category, duration, observed tokens and completed-tool lower bound. Include
execution kind, attempt count, model-call count and zero retry count.

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

Matrix accepted; representative runner contract **prepared** means pinned adapter
implementation tested with fakes, not host/runtime verification. Qualified host and
grading isolation remain required-not-verified, representative readiness false,
comparative evidence absent. Historical 42 jobs and representative 40 calls remain
unexecuted; successful IaC smoke and historical failed evidence remain unchanged.
Next qualify a separate host, verify the backend/runtime/grader boundary and review
receipt/contract acceptance before any separately authorized spending. #14 stays
open; #15 stays separate. Future playbooks/adaptive/automation/distribution #40–#55
are not implemented here.
