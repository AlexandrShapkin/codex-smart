# Adaptive orchestrator adversarial audit — 2026-10-14

This is a code-path and fake-only failure-injection audit of PR #85 at
`fe3da54be952703f2d6e2c0711b9466e55163ae9`, based on accepted main
`5102c0ebefeb53c3dbd56021266b340524be7ad3`. GitHub main, PR head and clean task
worktree were independently checked before edits. Original checkouts, local-only
commits, historical dirty worktrees, deployments and accepted evidence are preserved.
The [operator runbook](../adaptive-operations.md) remains authoritative for operations.
This report neither authorizes execution nor changes frozen measurement contracts.

## Confirmed findings, ranked by consequence

| Severity | Reproduction / observed behavior before correction | Root cause / correction |
| --- | --- | --- |
| High | `test_controller_drift_refused_before_first_model_callback`: a changed controller decision caused **20 fake callbacks** before a plan mismatch was reported. | Only post-execution artifacts were compared with the reviewed plan. Pass the complete reviewed decision matrix into the existing runner and compare before every launch; also bind resumed ledgers to their reviewed profiles. |
| High | `test_completed_receipt_cannot_drop_execution_hashes`: removing the entire initial output inventory was accepted; `test_completed_receipt_cannot_replace_result_with_null`: null preflight result was accepted. | Completion validation checked only envelope/dependency hashes and whatever output entries remained. Require start/completion binding, typed results, exact per-stage inventories and result/artifact consistency. No explicit model authorization flag was bypassed. |
| High | `test_nested_artifact_permission_drift_refused_read_only` and `test_remote_campaign_parent_permission_drift_refused`: changing attempt directories or remote campaign root to 0777 remained accepted. | File hashes did not verify parent permissions, and an existing remote campaign root was reused without checking ownership/mode. Recheck control directories and output ancestors, and remote base/root ownership and permissions on every request. Verification never repairs permission drift. |
| High, configuration-dependent | `test_forwarding_is_disabled_even_when_fake_config_enables_it`: real offline `ssh -G` kept agent forwarding enabled under a disposable fixture config despite ClearAllForwardings. | ClearAllForwardings disables tunnel forwarding, not agent/X11 forwarding. Add explicit per-command ForwardAgent=no and ForwardX11=no. No system configuration or authentication method is changed. |
| Medium | `test_orphan_retry_grading_row_refused`: an authenticated, schema-valid second-round row without any local attempt was accepted. | Authentication matched only existing local attempts and ignored extra grading rows. Require exact equality between returned jobs and started jobs for the round before matching identities. |
| Medium | `test_archive_rechecks_source_bytes`: modifying source after finalization did not prevent archive creation. | Archive read the old source manifest without verifying current snapshot bytes. Reuse the normalized full snapshot verifier immediately before archival. |
| Low | `test_status_rejects_corrupt_interrupted_stage`: arbitrary interrupted-stage JSON was described as running/interrupted. | Status checked file existence only. Validate interrupted receipt identity and dependencies read-only before reporting its state. |

The first six regressions failed on the original head (6 failures / 6 tests,
28.121 s). The separate controller regression failed with 20 callbacks (1.958 s).
The status regression failed independently (0.145 s). All failures used disposable
fixtures and no real model, SSH, credential or grading-host access.
The forwarding regression failed independently (0.134 s) using real `ssh -G` against
a fake config and loopback hostname, without opening a network connection. The tested
fixture's agent-forwarding value was yes; explicit command restrictions make it no.

Reproduce and verify from this branch:

```bash
PYTHONPATH=scripts python3 -B -m unittest test_benchmark_adaptive_audit
PYTHONPATH=scripts python3 -B -m unittest test_benchmark_adaptive_orchestrator test_benchmark_adaptive_campaign test_benchmark_adaptive_trusted_handoff
```

The named negative tests require refusal and inspect callback counts or retained
bytes/modes. On the original proposed implementation these assertions failed.
Tests are independent filesystem fixtures, not altered accepted benchmark artifacts.

## Actual transition map

Common gates: external reviewed plan SHA matches canonical JSON; source/config identities
are explicit; local control directories are owned, non-symlink and not group/world writable;
exclusive creation never adopts conflicting evidence. Each online stage holds the
persistent campaign lock, requires every preceding completion receipt, and binds its
start and completion to the current dependency hashes. Host operations additionally
hold the independent host lock. No stage loop exists in the production CLI.

| Transition | Preconditions and required evidence | Trusted / untrusted boundary | Persistent changes and irreversible work | Failure / explicit resume | Authority and execution ceiling |
| --- | --- | --- | --- | --- | --- |
| Plan → initialize | Verified agent snapshot receipt, hash-pinned pure Rust adapter, frozen 20-job matrix; new reviewed state destination | Reviewed snapshot/adapter vs configuration and filesystem | New private state, plan and stages directory; no model | Partial/unbound plan refuses; no overwrite/adoption | Explicit initialize; 0 executions |
| Initialize → preflight | Exact agent source/runtime/executable/adapter; qualified remote source/runtime, pinned SSH host and usable new destination | Verified snapshots/qualification vs transport response and paths | Start/completion receipts; remote preflight reads only | Offline preflight reports grader unknown and writes no successful stage; failed online operation needs resume | Explicit online; 0 executions |
| Preflight → initial | All prior receipts; refreshed host readiness; each Rust decision equals reviewed plan before launch | Trusted controller/runtime vs model observation and workspace | Attempt directory; fsynced started ledger **before callback**, raw local logs/result/submission; summary and stage receipts | Every valid started ledger is spent, even without result; resume skips it. Partial missing/truncated ledger refuses instead of guessing | Separate literal execution authorization; ≤20 first attempts; total ≤40 |
| Initial → transfer-1 | Initial ledger, full output inventory, validated sanitized bundle | Local immutable records vs packet bytes and destination | Local bundle and plan-bound host bundle; metadata marker last | Matching complete files retained; only missing files copied. Truncated/different files preserved and refused | Explicit online; no model executions |
| Transfer-1 → grade-1 | Exact uploaded bundle, accepted independent qualification/runtime | Qualified production grader vs untrusted public submission | Host grading rows/summary and local remote-digest receipt | Completed valid rows retained; missing rows may be graded after explicit resume; active host lock prevents overlap | Separate grading authorization; no model executions |
| Grade-1 → authenticate-1 | Fresh pinned SSH digest equals grade receipt; all hashes, job membership and local started/result identities match | Pinned host and source verifier vs fetched grading packet | Local verified grades and authentication receipt | Partial transfer must match; missing, altered, duplicate or malformed evidence refuses | Explicit online; no model executions |
| Authenticate-1 → escalate | Fresh source/runtime/preflight and reauthentication; completed initial results plus eligible failed grading; genuine Rust strict escalation | Controller and independent validation vs failure events | At most attempt-2 ledgers/results and retry summary | Uncertain attempts cannot be retried; any started second attempt is skipped forever; exhausted/no-higher-profile jobs retain failure | Separate execution authorization; ≤1 retry/job, ≤2 attempts/job, ≤40 total |
| Escalate → transfer-2 | Completed retry decisions and all spent attempts | Same sanitized allowlist; raw stderr/traces never transmitted | New second bundle includes retained attempt identities | Same copy-only-missing behavior; transport cannot replay agent work | Explicit online; no model executions |
| Transfer-2 → grade-2 | Qualified runtime and exact second bundle | Independent grader vs attempt-2 submissions | Rows only for actually started attempt-2 jobs; empty round is valid | Same partial grading recovery; no substituted synthetic grader in production | Separate grading authorization; no model executions |
| Grade-2 → authenticate-2 | Fresh host digest; exact attempted-job membership; row/hash/model/submission identity | Same pinned evidence boundary | Verified local retry grades and receipt | Extra as well as missing rows now refuse; no silent repair | Explicit online; no model executions |
| Authenticate-2 → finalize | Both rounds freshly authenticated; all 20 jobs and retry ledger consistent | Accepted source/controller plus independent evidence vs accounting inputs | Twenty final rows and summary, preserving failed/unknown data | Compare existing outputs, write missing only; any mismatch refuses | Explicit online; no model executions |
| Finalize → archive | Checked full prior receipts, current agent source integrity, 20 finalized jobs and zero model delegation | Local operator-owned receipts vs filesystem drift | Exclusive source/execution/grading/final manifests and hashes; files 0400, root 0500 | Partial identical archive resumes; marker-before-permission-freeze interruption completes explicitly; changed files or modes refuse | Explicit archive; no model executions or performance acceptance |

## Execution and budget conclusions

`started.json` consumes budget before the executor callback. Actual forked-process
SIGKILL tests pause immediately before and after that write. A kill before the write
leaves an ambiguous empty attempt directory: resume refuses non-destructively, with
zero callbacks. A kill after the fsynced write retains one spent ledger; resume starts
only the other 19 jobs. Concurrent operator-process tests confirm the OS lock refusal.
Deleting or corrupting completion metadata cannot replay an existing started ledger.

The campaign enforces two attempt directories per known job and rejects unknown jobs,
attempt numbers, ledger/controller identities and >40 started attempts. A retry exists
only after independently graded eligible failure and strict controller escalation.
The frozen policy has four Strong/High starting jobs; no cheaper or imaginary stronger
profile can be used to retry them. Therefore the existing all-failure synthetic case
starts 36 attempts, while the frozen authorization ceiling remains 40.

No new execution-authorizing config field exists. CLI booleans are separately required;
API execution authorization uses identity with literal True, refusing numeric/string
lookalikes. Duplicate keys and non-finite JSON are rejected before crossing the boundary.
Unknown token/cost data stay unknown; interrupted latency remains unknown. Model
delegation and its overhead remain zero. Operational recovery latency is unmeasured,
not fabricated as delegation overhead or savings.

## Synthetic lifecycle — not accepted performance evidence

Fresh evidence retained under
`/tmp/codex-smart-adaptive-audit-synthetic-20261014-c`; see `synthetic-report.json`
and `rust-state/archive/`. Real model calls and real SSH connections: **zero**.
The genuine Rust adapter was built offline and copied to a new independently hashed,
single-link executable. Its SHA-256 is
`07ec9d05af4d9bcec3500a7e26d2eedf0dbf71eec23d919df8e1d529df14f369`.
Both fixture snapshots use the real normalized exporter/verifier. Fake transport calls
the real Python host request logic against a distinct disposable grading snapshot;
runtime qualification, model execution and quality responses are deliberately fake.

Results: **20 jobs, 24 started attempts/fake callbacks, 4 controller-authorized retries,
13 synthetic quality passes, 7 terminal failures**. Two retries succeed and two exhaust;
four Strong/High jobs fail without retry, and one initial attempt remains uncertain.
All 20 jobs have unknown token accounting; one has unknown lifecycle latency.
Estimated cost, winner and savings are null. Handoff count/overhead are 0/0.
Missing SSH receipt and malformed grading summary are refused and safely resumed.
Every stage receipt and archive is checked; archival repeat is idempotent.
Archive receipt SHA-256:
`7693700ebfa61dca75eca7af2e8737b061b31224961a17b0fad86575c8afe67f`.

Two preliminary disposable fixtures remain preserved: the first correctly refused
Cargo's multi-link output as an adapter; the second exposed a fake preflight fixture
still pointing at its non-executable placeholder. An independently hashed single-link
copy and corrected fixture binding resolved these harness issues. No real snapshot
or evidence was repaired or replaced.

To repeat after explicitly building/copying the public Rust adapter, select a NEW path:

```bash
CARGO_NET_OFFLINE=true cargo build --locked -p codex-smart-core --example adaptive_benchmark_plan
PYTHONPATH=scripts python3 -B scripts/test_benchmark_adaptive_audit.py --synthetic /absolute/single-link/pinned-adapter /tmp/NEW-synthetic-audit
```

This harness lives only in the test module. Production CLI has no synthetic acceptance
mode and never accepts fake quality in place of its qualified grader.

## Residual limitations and operational decisions

The filesystem checks narrow pathname races; they do not provide descriptor-relative
transactions against a malicious same-UID operator, root or a compromised trusted host.
Permissions/hashes are integrity checks, not signed proof of malicious-owner resistance.
Stage receipts are operator-owned and depend on an independently retained plan digest;
do not restore stale evidence into a spent campaign or use a new run ID to hide attempts.

Partial/truncated ledgers, transferred files and plan writes intentionally refuse; safe
recovery may require operator inspection. Directory/file fsync protects the started-write
boundary but is not a qualified power-loss/filesystem durability claim for all ancestor
creation or all downstream artifacts. Fake fork interruption proves process-crash behavior.

Direct ThinkPad→srv0 SSH remains independently verified. The Codex environment's SSH
configuration permission rejection is a separate environment limitation. This audit
does not connect, change SSH configuration, copy credentials or weaken the ED25519 pin.
Full production host preflight, fresh accepted snapshots/adapter selection and separate
campaign authorization remain manual gates after review. Neither PR is merged here.

## Verification and integration record

Observed local results: expanded focused suite **39 passed in 57.148 s**; subsequent
SSH forwarding/handoff suite **10 passed in 0.052 s**; tightened post-preflight controller
regression **1 passed in 0.265 s**. `CARGO_NET_OFFLINE=true just check` passed with
**269 Python tests in 354.588 s and 162 Rust tests**, formatting, warnings-denied Clippy
and build (exit 0). The SSH regression was added during that gate; its focused suite
passed afterward, and exact-head CI must recheck the full final 270-test source.
Offline nextest: **162 passed, zero skipped**. Documentation and diff checks passed.

Default local Security passed provenance of 30 registry packages, then refused a
read-only `/home/user/.cargo/advisory-dbs/db.lock` (exit 1). An explicit public advisory
refresh plus frozen cargo-deny passed advisories/bans/licenses/sources using a temporary
config that changes only db-path (exit 0); no repository policy or security setting changed.
Exact GitHub results, correction commit SHAs and separate readiness PR are recorded in
the draft PR descriptions. All model and grading responses in tests are fake.
Code corrections: `f3404a837fde605183a05dc6c3339b1fa6fcafea` on PR #85's existing
branch. Separate [production readiness PR #86](https://github.com/AlexandrShapkin/codex-smart/pull/86)
at `f59dfc507e42fc955a061176cee18fcace1ef874` contains a concrete integration plan and
four genuine Rust policy-composition fixtures, with no production CLI changes.
Its local gate passed 234 Python tests (124.146 s), 166 Rust tests and 166 nextest tests;
its exact-head CI and Security also passed. Both PRs remain drafts for independent review.

| Required investigation | Deterministic coverage |
| --- | --- |
| Before/after started write | Actual fork/SIGKILL boundary test, retained ledger / refusal |
| Individual-file transfer interruption | Existing real partial local/remote unpack and copy-only-missing tests |
| Partial grading | Existing second-callback interruption, completed rows retained |
| Changed grade before retry | Fresh remote digest change after authentication; zero new callbacks |
| Corrupted receipts | Dropped inventory, null result, mismatched start and malformed interrupted metadata |
| Symlink/hardlink substitution | Actual artifact replacement and normalized snapshot/adapter checks |
| Nested directory permissions | Actual chmod drift on attempts, stages, remote root and completed archive |
| Concurrent operations | Separate forked operator blocked by persistent fcntl lock |
| Completed-stage replay | Initial/archive repetition verifies receipts and preserves callback count |
| Partial archive | Before-marker interruption and marker-before-permission-freeze recovery |
| Controller inconsistency | Runner-side decision drift after orchestration preflight, pre-launch refusal |
| JSON and types | Duplicate keys, non-finite values, malformed stage result and authorization lookalikes |
| Source/runtime substitution | Real source-byte verifier and wrong remote runtime identity |
| Failed/delayed SSH | Bounded timeout/OSError fake subprocess responses; explicit refusal |
| Retry/global ceilings | Existing cap-40 refusal, unknown ledger job rejection, all-failure 36-attempt exhaustion |

This audit is independent failure reproduction by the implementation agent, not a
second human/agent approval. Further independent review remains required. No roadmap
acceptance, benchmark winner, source deployment or live execution is inferred.
