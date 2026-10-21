# Repository workflow normalization audit — 2026-10-14

## Observed source and isolation

Canonical repository: https://github.com/AlexandrShapkin/codex-smart.
Explicit HTTPS fetch and independent ls-remote agreed on GitHub main
`4edd184e1e7796e763ef327f16adb76872b4b618`; authenticated GitHub API agreed as well. This happens to
match the historical reference; it was not assumed.

The opened repository `/home/user/Documents/Projects/codex-smart` was on
`benchmark/agent-execution-isolation-gate`, HEAD
`5cd1b9500a06fe5e1ee595a3eb0a509277e1ba5f`, with canonical HTTPS origin,
no staged/unstaged/untracked changes and one registered worktree before isolation.
It has **4 local-only / 37 main-only commits**. Neither its branch nor files changed.
Fetch updated origin/main from `eb5438b` to the verified commit; Git's normal fetch
metadata and the new worktree/branch registrations are the only intended shared
metadata changes.

Implementation is exclusively in `/tmp/codex-smart-workflow-20261014`, branch
`chore/workflow-normalization`, created from the verified full SHA with native
`git worktree add -b`. No stash, reset, clean, forced checkout, rebase, pruning,
benchmark execution, deployment replacement or automatic integration occurred.

## Current-state inventory before normalization

- `justfile` already owns context, issues, docs generation/checking, Python regressions,
  Rust fmt/clippy/tests/build, nextest and explicit cached/network security checks.
  `scripts/workflow.py` has bounded stdlib-only offline registries/context; retain it.
- CI runs `just check`; Security checks dependency provenance and pinned cargo-deny
  with explicit advisory fetch. Push checks apply to the branch SHA; PR checks also
  apply to the synthetic merge commit. Existing owner policy requires exact-commit
  CI `check` and Security `review`, from Actions app 15368. No settings were modified.
- CONTRIBUTING assumed a synchronized main checkout and returning to clean main.
  That conflicts with preserving older/dirty worktrees. The workflow document also
  had obsolete next-stage instructions for the already completed tools stage.
- Status omitted remotes/worktrees/divergence, and no shared guard pinned new task
  creation to observed GitHub main. Native Git remains the underlying implementation.
- Benchmark procedures already distinguish ThinkPad model execution from srv0
  grading, pin runtime/runner hashes, spend started attempts before launch and
  authenticate grading handoffs. Preserve these contracts and accepted evidence.
- Deployment directories are not necessarily Git repositories. Existing benchmark
  pins do not provide a general complete-source receipt or config drift check.
  Distribution remains planned; source export is not an installer/updater.
- Documentation ownership, stage contracts and generated ROADMAP/index are enforced
  by docs-check. Extend the authoritative workflow document and dated evidence,
  without creating a second workflow framework or advancing Adaptive Lifecycle.

## Historical ThinkPad checkout and existing worktrees

`/home/user/src/codex-smart` exists locally, on `fix/benchmark-lib64-probe`, HEAD
`4d059299389603f41fe724bbbbe9390b860f8a14`, with canonical SSH origin. It has
**0 local-only / 32 main-only commits** and the three known modified files below.
All registered existing worktrees were inspected offline with hooks/fsmonitor and
optional Git index writes disabled. Counts compare to the verified GitHub SHA;
local-only commits can represent squash-merged equivalents, not necessarily new
unaccepted behavior. Full heads are recorded rather than inferred from branch names.
A missing worktree registration and additional dirty historical worktrees were
reported and preserved. Ignored benchmark evidence was not read or modified.

| Worktree | HEAD | Local-only / main-only | Observed state |
| --- | --- | --- | --- |
| `/home/user/src/codex-smart` | `4d059299389603f41fe724bbbbe9390b860f8a14` | 0 / 32 | 3 changed/untracked entries |
| `/home/user/src/codex-smart-adaptive-contract` | `d8fabc7eb5bc5ece36495d11bf04454d4ac2c3dc` | unknown | missing; stale registration retained |
| `/home/user/src/codex-smart-adaptive-delegation` | `7145dd6595003313b8fcccc16d5c46fe9c76c9b8` | 1 / 5 | clean |
| `/home/user/src/codex-smart-adaptive-economics` | `96796a7ff8aa7205f2bc79f32ef613b17626386e` | 1 / 4 | clean |
| `/home/user/src/codex-smart-adaptive-live-runner` | `7eb9a26140e0bb604bc93017c05567db21fb7b12` | 2 / 1 | clean |
| `/home/user/src/codex-smart-adaptive-profile-accept` | `e3b9589ecea79f25ef754b397df73512c7073487` | 1 / 2 | clean |
| `/home/user/src/codex-smart-adaptive-profile-record` | `de202644a1cca56acf4953c42c773d8dfd2b3591` | 1 / 3 | clean |
| `/home/user/src/codex-smart-adaptive-routing` | `158ed23e69300843360d6d32945ce7f970c24d9b` | 1 / 6 | clean |
| `/home/user/src/codex-smart-backend-review` | `558a0fd0c67f11fac6b20ed4c3846e0aa30894c4` | 1 / 25 | clean |
| `/home/user/src/codex-smart-grading` | `b583904f5fba1e8d7a564bb679c5b15e05a18842` | 0 / 23 | 15 changed/untracked entries |
| `/home/user/src/codex-smart-live-smoke` | `8b0d99ef21437c40215783c0eb0915d7e4f5a247` | 1 / 17 | clean |
| `/home/user/src/codex-smart-measured-baseline` | `fe4ae08f7e3d0a07277d5112ff16f5c4fbfff40e` | 1 / 13 | clean |
| `/home/user/src/codex-smart-measurement-accept` | `b3b8fd6134d8c479a1efdc925f5710382b4f9e77` | 1 / 12 | clean |
| `/home/user/src/codex-smart-playbooks-contract` | `5c9132243466c94536d334e833543846657c79ba` | 1 / 10 | clean |
| `/home/user/src/codex-smart-playbooks-planner` | `3f51dbb64f52bedec9e3c4e5139f3a0d22e9a743` | 1 / 9 | clean |
| `/home/user/src/codex-smart-playbooks-validation` | `78ef2fbb7b417363bd4a4cfb0901360f9723e551` | 1 / 8 | clean |
| `/home/user/src/codex-smart-prod-grader` | `90cc38c4cd16552edfa0e168aaa60556a6b9ca01` | 0 / 19 | clean |
| `/home/user/src/codex-smart-readiness` | `8426eb54e836e13be7bd032d3d1af548c2c10f69` | 3 / 18 | clean |
| `/home/user/src/codex-smart-rounding-fix` | `4b713cc736a28e80832fb41e2be5f95048d9f5ac` | 1 / 16 | clean |
| `/home/user/src/codex-smart-split-accept` | `9e26be5fa5f80d46c5fa949943ee21f6a3c35e8d` | 1 / 14 | clean |
| `/home/user/src/codex-smart-split-campaign` | `5c0bbd12243f0481fdb91ca8624b4ce94b0d702c` | 1 / 15 | clean |
| `/home/user/src/codex-smart-submission-review` | `b583904f5fba1e8d7a564bb679c5b15e05a18842` | 0 / 23 | 8 changed/untracked entries |
| `/home/user/src/codex-smart-telemetry` | `61905469ca83710b0d19b7275025fdbb6eb5d878` | 1 / 11 | clean |
| `/tmp/codex-smart-adaptive-accepted-check` | `76d6d9018be98a44a3f51a51d4ef1d24d2b20c87` | 0 / 1 | clean |
| `/tmp/codex-smart-adaptive-live-4edd184` | `4edd184e1e7796e763ef327f16adb76872b4b618` | 0 / 0 | clean |
| `/tmp/codex-smart-adaptive-smoke-main` | `0c846addbb313524910ec9891482f0eddbfd2f3e` | 0 / 3 | clean |
| `/tmp/codex-smart-full-campaign-main` | `08d255788562b03d0682ca92ee6141f26c5a1618` | 0 / 13 | clean |
| `/tmp/codex-smart-main-smoke-plan` | `0a47c428ef68435548e3ed7515a61c81b7bd7e61` | 0 / 16 | clean |
| `/tmp/codex-smart-main-smoke-v4` | `c047af5e59b0ef29e3d64dc75a09f2b0a60098f7` | 0 / 15 | clean |

### codex-smart

```text
 M benchmarks/representative-campaign-v1.json
 M scripts/benchmark_isolation.py
 M scripts/test_benchmark_isolation.py
```

### codex-smart-grading

```text
 M benchmarks/representative-campaign-v1.json
 M docs/benchmark-host.md
 M docs/benchmarking.md
 M scripts/benchmark_coverage.py
 M scripts/benchmark_grading_backend.py
 M scripts/benchmark_isolation.py
 M scripts/benchmark_representative.py
 M scripts/test_benchmark_grading_backend.py
 M scripts/test_benchmark_isolation.py
 M scripts/test_benchmark_representative.py
?? --
?? scripts/benchmark_grading_supervisor.py
?? scripts/benchmark_submission_grader.py
?? scripts/benchmark_submission_grading_probe.py
?? scripts/test_benchmark_submission_grader.py
```

### codex-smart-submission-review

```text
 M scripts/benchmark_coverage.py
 M scripts/benchmark_grading_backend.py
 M scripts/benchmark_isolation.py
 M scripts/benchmark_representative.py
 M scripts/test_benchmark_grading_backend.py
?? benchmarks/grading-runtime-v1.json
?? scripts/benchmark_grading_runtime.py
?? scripts/test_benchmark_grading_runtime.py
```

## Opened checkout commit divergence

`<` means local-only; `>` means GitHub-main-only. This is the complete observed list.

```text
> 4edd184e1e7796e763ef327f16adb76872b4b618 benchmark: add authenticated adaptive lifecycle runner (#83)
> 76d6d9018be98a44a3f51a51d4ef1d24d2b20c87 benchmark: accept adaptive profile smoke evidence (#82)
> 895c11c06574237b851b9e4dd19224d72fc97bcd benchmark: record adaptive profile smoke evidence (#81)
> 0c846addbb313524910ec9891482f0eddbfd2f3e benchmark: prepare adaptive lifecycle measurement (#80)
> 333990542296b04df94beb31317a11a91d11f5ce adaptive: add bounded delegation contract (#79)
> 420d5eb52a0a312d8a635be1426dc3de9673bddf adaptive: add replaceable model routing (#78)
> e6a255270afb1a9d4176bc7f950a1e111115fd7c adaptive: define bounded execution contract (#77)
> c61492e51aefa3af691214350fb429baec6ac991 playbooks: add validation recipes and explain surface (#76)
> c83721c347ff3eaccd1fd69e309c4375f582311d playbooks: add deterministic resource planner (#75)
> 688db4549d18902354191591a5632ac0baadb96d playbooks: define task archetype contract (#74)
> e22307f7164e0cd3c1d3c4d3b72c5293c6050b67 benchmark: add privacy-preserving aggregate telemetry (#73)
> ad9903fe8edeb8dedfc7a535a1646c36f1693c36 benchmark: accept representative measured baseline (#72)
> 609ef098f668a6fb02c5ce9bde7f7a197617d5e4 benchmark: record representative measured baseline (#71)
> 08d255788562b03d0682ca92ee6141f26c5a1618 benchmark: accept split-host campaign evidence (#70)
> 1c82f9cc0c95cc85a79c04efad62895341c62545 benchmark: add split-host representative campaign path (#69)
> c047af5e59b0ef29e3d64dc75a09f2b0a60098f7 benchmark: align billing prompt with oracle (#68)
> 0a47c428ef68435548e3ed7515a61c81b7bd7e61 benchmark: add one-execution representative live smoke (#67)
> d833b16fbfd3508983a5edaac33d129ecf6b333c benchmark: accept representative technical readiness (#66)
> 927f788209201919bff8cee3a477882ddf72a717 Merge pull request #65 from AlexandrShapkin/benchmark/production-isolated-grader
> 90cc38c4cd16552edfa0e168aaa60556a6b9ca01 benchmark: make grading evidence acceptance stable
> 1725dd393112f35e9ffffb812281687ce92935db test: make runtime replacement identity deterministic
> 364c630fcc5df809b63e27feac7be783e8f336c8 benchmark: harden production grading boundary
> 33a2b622ae79764af4b8831b16a7d2990c868ff5 benchmark: add isolated production submission grader
> b583904f5fba1e8d7a564bb679c5b15e05a18842 Merge pull request #64 from AlexandrShapkin/benchmark/review-qualified-host-receipt
> 359506fbe380e6d629f28dc7970d1e47c18196e4 benchmark: accept reviewed qualified host receipt
> dc2befe8d143d670c7a0ac47c5c3141a964c0a7c Merge pull request #62 from AlexandrShapkin/benchmark/review-ubuntu-bwrap-backend
> 166ba0465ddeeaa60057db4ac4972b46c4d0c9ae fix: review constrained Ubuntu grading backend
> 47f15c7d3fbc896fd48613cc1629a8313a2e2363 Merge pull request #61 from AlexandrShapkin/fix/benchmark-lib64-probe
> 8b5598d5a6c76ba586b2ce85c486c9a7434172dd chore: refresh representative isolation pin
> 30b94a3de2c36c7abce114739015f6500c26cfb2 test: cover lib64 probe layout
> 4afb4585ae6c9bfd5d9dbed38f9a04bbff845a44 fix: use correct lib64 target in isolation probe
> 6b41c43b18bf99d2f08ef25cf4df0ceaf36fcf18 Merge pull request #60 from AlexandrShapkin/benchmark/upstream-toolchain-pin
> 4d059299389603f41fe724bbbbe9390b860f8a14 fix: pin representative upstream toolchains
> 69cdff7f56656347cdd1e7a58a2ea2e0f2850049 Merge pull request #59 from AlexandrShapkin/benchmark/agent-execution-isolation-gate
> 4d7fe6c3f4060c4bad06319837e0b4d4ba89a22c fix: isolate private credential paths
< 5cd1b9500a06fe5e1ee595a3eb0a509277e1ba5f fix: hide keyring backing store from child
< 48c795bd3b54ba6a7aabf8ae6cbb1b51493b9d25 test: isolate private credential IPC
> b2a8c8af14cf6873065ef4729a8bb36eb390eec3 docs: pin keyring dependency behavior
< c55c7f9fdeb3c667605246fb5615d1730b64f095 docs: pin keyring dependency behavior
> 84b1374ddf1fec3cd66b9099b3042bb31cb4231a feat: gate representative agent execution isolation
< 0ec3c21bc78361f8d6fe180f5cd4900a1ca09f0d feat: gate representative agent execution isolation
```

## Host limitations and manual decisions

An ordinary noninteractive `ssh` connection to srv0 was attempted **from the Codex
execution environment**. Its SSH client refused
before connecting: `Bad owner or permissions on /etc/ssh/ssh_config.d/20-systemd-ssh-proxy.conf`.
No system/SSH security settings were changed or bypassed. This is an
execution-environment-specific failure, not evidence that srv0 is generally
unreachable. The [independent PR review](https://github.com/AlexandrShapkin/codex-smart/pull/84#issuecomment-6152378136)
reports that ordinary pinned SSH directly from the authorized ThinkPad succeeds
and the existing srv0 runner SHA-256 matches the previously accepted snapshot.
That observation does not establish a complete deployed source receipt, runtime
qualification or production campaign readiness. Those remain unverified by this
Codex environment; no filesystem equivalence with GitHub is assumed.

Keep all old worktrees, dirty files and evidence. Owners must decide whether to
resume/reconcile local-only branches and the stale registration; this task does not
merge or repair them. Host operators can use the independently working ThinkPad
access to inspect/verify the existing srv0 snapshot; any Codex-environment access
problem requires separate diagnosis without bypassing SSH security checks.
Only a separately approved new source
snapshot may be selected for future execution/grading. Runtime qualification,
compiled adapter hashes and campaign authorizations remain independent gates.

## Normalized workflow and verification

The authoritative [workflow](../PROJECT_WORKFLOW.md) now defines verified-main task isolation,
offline gates, reviewed PR integration, complete-source receipts and non-destructive
interruption recovery. Read-only diagnostics never refresh remote knowledge;
worktree creation is the explicit network/mutation step. Source export writes only
a new directory, and verification requires an externally recorded receipt digest.
No model execution or campaign limit change is included.

Validation results are recorded below after the task checks, and exact proposed-head
CI/Security evidence belongs in the draft PR. Local passes do not establish remote
acceptance. Active roadmap stages and historical acceptance remain unchanged.

## Validation record

- Focused offline Python regressions: `python3 -B -m unittest discover -s scripts -p
  test_repository_workflow.py` — **22 passed**, including an actual local bare-Git
  fetch/ls-remote fixture, without GitHub/model/SSH/deployment access.
- `just docs-check` — **passed**. Ownership/index generation remains deterministic;
  ROADMAP was regenerated and has no content changes or stage advancement.
- The first `CARGO_NET_OFFLINE=true just check` — **passed** with 223 Python tests
  (before five added safety cases), fmt/clippy, 162 Rust tests and workspace build.
- A subsequent full run passed all **228 Python tests**, fmt and clippy, but exposed
  an existing Rust fixture's implicit umask assumption: the public-permission
  migration case created a private file under umask 077 and correctly accepted it.
  The test now explicitly sets its intended 0644 permissions; the targeted case
  **passes under both 022 and 077**. No production migration behavior changed.
- Final `CARGO_NET_OFFLINE=true just nextest` — **162 passed, 0 skipped**.
- Final `CARGO_NET_OFFLINE=true just check` — **passed**: **228 Python tests**,
  documentation checks, Rust formatting, clippy with warnings denied, **162 Rust
  tests** and locked workspace build. Full Python suite duration: **179.723 seconds**.
- `just security` initially could not acquire the advisory database lock in the
  read-only `/home/user/.cargo/advisory-dbs`. Dependency provenance passed for all
  **30 registry packages**. Only the public advisory database was copied to
  `/tmp/codex-smart-workflow-security-20261014`; no Cargo/auth/credential store was
  copied. A temporary deny config changes only `advisories.db-path`, keeping every
  security policy intact. Explicit public refresh followed by
  `cargo deny --frozen --config /tmp/codex-smart-workflow-security-20261014/deny.toml
  check -D warnings` — **advisories, bans, licenses and sources all passed**.
- Actual local source export from verified main created a new temporary snapshot
  with **217 files**. Two read-only verifications passed without `.git`. Source SHA:
  `4edd184e1e7796e763ef327f16adb76872b4b618`; independent receipt SHA-256:
  `0bba38044291ff3019ab781570e6d7bd1cc130650f29628c55dce788d1516c06`.
  This was a local smoke check, not a host deployment or benchmark execution.
- Follow-up reads confirmed both original checkout branches/HEADs and dirty-path
  lists unchanged; GitHub main still matched the initial verified SHA.
- Read-only `source-verify` on the existing
  `/tmp/codex-smart-adaptive-live-4edd184` worktree — **clean HEAD at verified main**.
  This proves that local Git source state, not physical host identity, runtime
  qualification or a selected deployment snapshot.

No real Codex/model call, adaptive campaign, authorization-limit change, historical
evidence mutation, host snapshot replacement or system security change was made.

## Independent permission review correction

The [review at head 439781b](https://github.com/AlexandrShapkin/codex-smart/pull/84#issuecomment-6152378136)
reproduced false verification of `0666` data files, `0777` executables and a `0777`
snapshot root. Fake-only regressions reproduced the defect before correction.
Verification now requires exact `0644`/`0755` tracked-file modes, receipt mode `0644`,
and no group/world write bits on roots or subdirectories. Special file permission
bits are rejected. Safe directory mode differences remain accepted. The verifier
performs no repairs or writes; symlink, hardlink, identity, receipt and inventory
checks remain in place.

Export explicitly sets permissions only on its exclusively created snapshot:
directories `0700`, tracked files `0644`/`0755`, receipt `0644`. Offline regressions
cover umasks `000`, `022`, `077` and `777`, unchanged contents/modes/mtime/ctime on
verification or refusal, and interruption before receipt permission normalization.
Partial destinations remain preserved and cannot be overwritten by rerunning export.

Correction validation and exact-head CI/Security results are recorded in PR #84;
the PR remains draft for independent review. The original and unrelated worktrees
were not accessed or changed during this correction.

- Focused offline permission/workflow tests: **28 passed**.
- `just docs-check` and `git diff --check`: **passed**.
- `CARGO_NET_OFFLINE=true just check`: **passed**, **234 Python tests** in
  **182.159 seconds**, formatting, clippy with warnings denied, **162 Rust tests**
  and locked workspace build.
- `CARGO_NET_OFFLINE=true just nextest`: **162 passed, 0 skipped**.
- Default `just security`: **exit 1**, because the Codex environment cannot acquire
  an exclusive advisory-cache lock on the read-only path. Dependency provenance:
  **30 registry packages passed**. Explicit advisory refresh and cargo-deny with the
  existing isolated public database/config (only `db-path` changed): **advisories,
  bans, licenses and sources passed**. No security policy or SSH setting changed.
