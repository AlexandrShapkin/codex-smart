# Integration and infrastructure stabilization — 2026-10-14

This is a fresh engineering review and local integration rehearsal, not accepted
GitHub main, host deployment, human approval or performance acceptance. Canonical
GitHub main was verified as `5102c0ebefeb53c3dbd56021266b340524be7ad3`.
All new work is isolated on `chore/integration-stabilization`. Existing PR branches,
dirty checkouts, source installations, historical evidence, issues and milestones
were preserved. No model or real benchmark execution occurred.

## Final engineering verdicts

| PR / exact reviewed head | Verdict | Direct evidence and residual acceptance |
| --- | --- | --- |
| [#85](https://github.com/AlexandrShapkin/codex-smart/pull/85) — `93e31c24ab90acd4a2f9874128857ef7dae5f3df` | **ACCEPT WITH NON-BLOCKING FOLLOW-UPS** for offline implementation | 68 focused adaptive tests passed, including real bounded SIGKILL/concurrency fixtures; direct review of controller/ledger, stage/transport, grading and archive paths. Source/runtime selection, fresh host preflight and separately authorized live measurement remain operational gates. |
| [#86](https://github.com/AlexandrShapkin/codex-smart/pull/86) — `f59dfc507e42fc955a061176cee18fcace1ef874` | **ACCEPT** for offline preparation | Four Rust composition tests passed. Effective changes are one test fixture, design and owned/generated documentation. No CLI/core implementation change or benchmark-model dependency. |
| [#87](https://github.com/AlexandrShapkin/codex-smart/pull/87) — `6ec86076846ecfc4367f43bbbc650321aaee2501` | **ACCEPT WITH NON-BLOCKING FOLLOW-UPS** | 44 focused tests passed: 16 consistency regressions plus 28 normalized workflow tests. Diagnostics use read-only Git with optional index writes/hooks/fsmonitor disabled; snapshot checks never repair bytes/modes. Unknown deployment evidence correctly remains incomplete. |

Complete PR diffs, descriptions and all paginated reviews/inline comments/discussion
comments were inspected. Each PR had zero submitted reviews/comments at the initial
observation. All four push/PR CI/Security checks for each exact head were successful
from GitHub Actions app 15368. These engineering verdicts do not replace independent
owner acceptance or manufacture a GitHub approving review. No new reproducible PR
blocker was confirmed, so the original three implementations/heads were not rewritten.
Their ready-for-review state and final live checks are recorded in the closeout record.

### Seven PR #85 corrections independently checked

| Correction | Actual enforcement / reproduction coverage |
| --- | --- |
| Controller decision before execution | `run_initial` compares the entire current Rust decision with the reviewed job decision before `_execute_attempt`; controller-drift fixture asserts zero callbacks. Resume validates stored profile/reasoning/model identity and skips started ledgers. |
| Complete typed stage receipts | `Campaign.receipt` checks exact keys, result types, every prior receipt hash, matching start receipt, exact output inventory and stage-specific result/artifact equivalence. Dropped hashes/null result cases refuse. |
| Nested directory permissions | `tree`/`check_files` validate each directory, including paths containing already hashed files. Nested and remote-parent `0777` fixtures refuse without chmod repair. |
| SSH forwarding disabled | Pinned options explicitly set `ForwardAgent=no`, `ForwardX11=no`, strict ED25519 host verification and noninteractive transport. Existing forwarding regression passes. |
| Retry rows exactly match started attempts | `_authenticate` requires grading row IDs equal the actual ordinal's started attempts and `_match_grade` binds job/attempt/profile/submission/trace identities. Orphan retry row fixture refuses. |
| Source checked before archival | `_archive` verifies agent snapshot SHA/receipt/full bytes before constructing source/attempt/grade/stage/final archive. Altered source fixture refuses. Completed archives additionally require read-only modes. |
| Interrupted metadata validated | `status`/`stage` bind stage, plan digest and every prerequisite receipt. Corrupt interrupted start, missing/altered receipt and replay cases cannot grant execution. |

### State-machine map and authority

Every completed stage binds the reviewed plan digest, start receipt, all previous
completion hashes and exact local outputs; every mutation holds the persistent
campaign lock. Host operations use a distinct remote campaign lock. Diagnostics
read state without creating locks. Out-of-order stages and mismatched resumes refuse.

| Transition | Evidence / mutation / interruption / authority |
| --- | --- |
| Plan → preflight | Exact source receipt, adapter hash, frozen 20-job policy/budget, reviewed runtime and pinned remote identity. Offline preflight cannot produce a completed online receipt. No model authority. |
| Preflight → initial | Fresh preflight and current Rust decisions; explicit online + model authorization. Durable/fsynced `started.json` is written before the fake/real executor boundary. Started attempts remain spent even after SIGKILL or missing result. |
| Initial → transfer-1 | All 20 ledgers and checked results; exclusive sanitized JSON bundle, manifest/remote plan receipt. Partial transfer copies only missing identical files on explicit resume; no model retry. |
| Transfer → grade | Qualified independent runtime; separate grading authorization. Partial rows are checked and retained; summary completes last. Transport timeout is a visible refusal, not automatic replay. |
| Grade → authenticate | Pinned SSH summary digest, transferred exact manifest, grade completion receipt and exact started/result row binding. Missing/changed/duplicate evidence refuses. |
| Authenticate-1 → escalate | Reauthenticate grading again; Rust controller is sole retry authority. Unknown interrupted outcome cannot retry. Successful jobs skip; Strong/High terminal failures cannot escalate. Explicit model authorization remains required. |
| Escalate → transfer-2 → grade-2 → authenticate-2 | Same sanitized transport/independent grading/authentication checks for exact second-attempt set, retaining first attempts. At most one retry/two attempts per job; maximum 40 ledgers globally. |
| Authenticate-2 → finalize | Reauthenticate both rounds and validate all attempts; preserve every one of 20 jobs, failures/unknown counters and zero delegation. Exclusive output rows compare on resume. No winner/savings inference. |
| Finalize → archive | Source rehash, complete attempts/final/authenticated grading and dependencies; exclusive archive completion receipt and read-only modes. Interrupted archive resumes by comparison; conflicting evidence is preserved/refused. No execution authority. |

Private campaign/source parents must be operator controlled with no racing writer.
Read-only metadata/hash observations are not an adversarial filesystem sandbox.
Remote bootstrap verifies the pinned source receipt before importing its code. The
transport allowlist excludes raw trace/stderr, keys and credentials; fixed argv plus
restricted remote paths and reviewed SSH identity constrain remote execution.

## Local integration order and conflicts

The expected order remains **#85 → #86 → #87**. Native non-destructive merges were
performed only in the new rehearsal branch, preserving every original commit:

| Rehearsal commit | Result |
| --- | --- |
| `8ae54eea86ae5037c36081a6882b36b471c42c3d` | #85 merged cleanly into verified main. |
| `044e6a432ea50395348b0319297e05478e40065c` | #86 conflicted only in `docs/documents.json`; exact metadata equality was required for common entries, all new ownership records retained; index regenerated. |
| `49e9e39f61a4edc574028527d77cf0d3c7b19077` | #87 conflicted in ownership JSON/generated index; same union/equality procedure and native docs generation; semantic adaptive/benchmark changes merged without source conflict. |

The combined effective diff introduces no production CLI/core implementation,
frozen benchmark data, model budget, credential or installed snapshot changes.
Original PR heads remain independently mergeable against the observed current main.
After the owner merges #85, later PRs may need current main merged into their clean
isolated branches and the documented registry/index resolution, followed by new
exact-head checks. Do not blindly rebase, squash away original work or accept old
checks after updating a branch. The tested rehearsal is evidence for that resolution,
not permission to bypass GitHub integration/review. Main was not merged by this task.

## New infrastructure-only preparation

- `scripts/verify_host_snapshot.py`: read-only host-side source/runtime/qualification
  report for the operator when Codex's SSH configuration boundary refuses. It reuses
  normalized source verification and frozen runtime parsers/contracts, hashes the
  complete runtime topology and validates saved qualification/implementation pins.
  No subprocess, SSH, toolchain, grader or model is launched. Nine fake-only tests
  cover repeat/read-only behavior, actual CLI output, permission/link/hash drift,
  missing/partial identities and the distinction from fresh host qualification.
- `docs/source-register.json`: existing bounded consistency schema, recorded main/PR
  heads and intentionally unknown deployment paths/digests. Historical pins remain
  distinct. Runtime/qualification/measurement JSON already owns those immutable
  contracts; no duplicate database or background service was introduced.
- The authoritative [workflow](../workflow.md#operational-source-register-and-host-side-checkpoint)
  owns host commands, missing-evidence recovery and operator approval. ADR-0008's
  current-context sentence now accurately describes pure policy vs CLI passthrough.

The accepted production grading implementation is hashed by its frozen candidate.
Refactoring it for this diagnostic would invalidate accepted evidence; it was left
byte-for-byte unchanged. The helper reuses its parsers and adds a clearly scoped
read-only inventory walk instead of executing or weakening production preflight.

## Live issue and milestone reconciliation proposals

No issue/milestone mutation was performed. Every proposed state/body/label/description
change below requires owner approval. Acceptance belongs to actual evidence, not
zero open issues or policy-only completion.

| Proposed mutation | Existing → correct state; evidence | Dependencies / approval |
| --- | --- | --- |
| Issue #46 state | Closed `completed` → reopen for full comparative adaptive lifecycle acceptance, or owner-approved residual issue explicitly linked to the completed preparation. #80–#83 and fake evidence do not satisfy its genuine quality/token/cost/latency criteria. | Prefer reopening the original unsatisfied acceptance; #85 review/accepted source, verified host/runtime pins and separate measurement authorization. Production CLI activation is separate and is not silently added as a prerequisite to the frozen benchmark-only contract. Owner approval. |
| Issue #46 context/priority | Dated “active stage remains benchmark”, P3 → current adaptive acceptance context and proposed P1. Keep stage/area ownership; no budget change. | Scoped criteria, #14/#44/#45 accepted policy/baseline; no campaign executed. Owner approval. |
| Milestone #2 description | Closed 0.2 Router v2, no description → clarify accepted pure policy, tests and main merge; production routing inactive/unmeasured. | Keep state unless owner changes release scope; track integration separately. Owner approval for metadata. |
| Milestone #3 scope/state | Open 0.3 Development Benchmark, both issues closed → owner decide baseline checkpoint scope; accepted #72/#73 do not imply Router/Adaptive efficiency or routine release readiness. | Explicit remaining criteria/new tracking before any closure. Owner approval. |
| Milestone #6 description | Planned/awaiting implementation → pure Playbooks contracts #74–#76 accepted/merged; runtime preparation/validation executor and comparative measurement absent. | Decide policy checkpoint vs operational release scope; keep open pending that decision. Owner approval. |
| Milestone #7 description | Planned/awaiting implementation → accepted pure adaptive contracts #77–#79, profile smoke #82 and offline runner #83; #85 reviewed candidate, comparative measurement/production routing outstanding. | Restore #46 tracking; future operational/measurement acceptance remains separate. Owner approval. |
| #16/#17 dependencies; production integration tracking | Open release/readiness umbrellas → add explicit #50–#52 / #53–#55 dependencies and separately scoped production plan/evidence/one-attempt integration acceptance. | Existing #86 plan guides scope; no new adaptive implementation in this task. Owner approval. |
| Main review protection | Zero approving reviews despite documented owner review → owner decide independent approval/admin/last-push enforcement. | Account for maintainer availability; no security settings changed. Owner approval. |

### All nine milestones and counter investigation

All due dates remain absent. Repeated live REST queries were compared with **GraphQL
counts and member nodes**, plus filtered REST member lists, rather than a historical
export. #4/#9 have stale/inconsistent REST counter metadata; GraphQL totals match
actual membership. No issue move or state toggle is justified to repair a counter.

| Milestone | State | REST open/closed | GraphQL open/closed | Real progress / unfinished boundary |
| --- | --- | --- | --- | --- |
| #1 Foundation | Closed | 0/10 | 0/10 | Scoped launcher/diagnostics/config baseline designed, implemented, tested, accepted, merged and usable within its bounds. Not 1.0. |
| #2 Router v2 | Closed | 0/5 | 0/5 | Policy implemented/tested/accepted/merged; production activation and genuine efficiency comparison absent. |
| #3 Development Benchmark | Open | 0/2 | 0/2 | Qualified representative baseline and aggregate telemetry accepted/merged/measured; ordinary vs native-first instruction only. No full Router winner. |
| #4 Hardening | Open | **3/0** | **2/0** | Correct members #53/#54; comprehensive hardening/routine readiness unaccepted. Owner can request GitHub counter refresh/support, not move unrelated issues. |
| #5 Stable | Open | 2/0 | 2/0 | #17/#55 readiness/public upgrade contract freeze outstanding. |
| #6 Workflow Intelligence | Open | 0/3 | 0/3 | Pure Playbooks accepted/merged; production preparation/validation execution and measured benefit absent. |
| #7 Adaptive Execution | Open | 0/4 | 0/4 | Pure contracts/profile proof/offline runner merged; #85 is still unmerged main; real comparative measurement and production routing absent. |
| #8 Reusable Automation | Open | 3/0 | 3/0 | #47–#49 designed, not implemented or operationally accepted. |
| #9 Distribution | Open | **3/0** | **4/0** | Correct members #16/#50–#52; installer/updater/recovery not delivered. GraphQL/member lists agree; REST counter correction is metadata-only. |

## ThinkPad / srv0 comparison and immutable provenance

| Installation / role | Expected vs observed source / runtime | Integrity / drift / next action |
| --- | --- | --- |
| GitHub accepted main | `5102c0ebefeb53c3dbd56021266b340524be7ad3`, verified live | Accepted canonical source. Rehearsal/PR branches are not main. |
| Opened checkout | `5cd1b9500a06fe5e1ee595a3eb0a509277e1ba5f`, clean, 4 local-only/38 main-only | Preserve unique work; not a deployment/main substitute. |
| Historical ThinkPad primary | `4d059299389603f41fe724bbbbe9390b860f8a14`, 3 changed files, 0 local-only/33 main-only | Preserve `fix/benchmark-lib64-probe`; no sync/stash/clean. |
| Existing historical adaptive Git copy | `4edd184e1e7796e763ef327f16adb76872b4b618`, intentional older source; normalized receipt missing | Valid historical role, incomplete normalized integrity evidence; do not relabel/replace. |
| New **audit-only**, disposable accepted-main export | Expected/observed `5102c0e…`; independent receipt `19d75d8cfd166b0bc36791afe788a1dd5d39a322c0ad97ff62320e0287744d8a`, 220 files | Source verification PASS. Not installed/selected on either host; source-only host report exits 2 because runtime is unknown. |
| Adaptive adapter in synthetic rehearsal | Built from frozen Rust example and SHA-pinned in private synthetic report; single-link disposable copy | Pure policy only; no real model/SSH. Actual execution-host installed adapter identity remains unverified. |
| srv0 actual grading installation | Installed path/source receipt/current full file hashes not observable through Codex's rejected SSH config | **NOT VERIFIED / blocked by execution environment**. Independent ThinkPad access succeeds; run the reviewed host-side checkpoint through that authorized access. No server-outage claim or bypass. |
| Saved accepted qualification/runtime contract | Qualification `d2af64ce…`, production grading `199ec772…`, frozen inventory/source `dc2befe…` | Accepted historical provenance is distinct from freshly verifying the current installed bytes/isolation. |

The historical evidence-store `CURRENT_RUNTIME_BUNDLE.txt` and adjacent inventories
remain inconsistent: expected files `50c3b03c…` vs observed `944660e6…`; expected dirs
`663c3335…` vs observed `77ef85f4…`; symlink manifest matches `e6831ba6…`. SHA256 was
recomputed read-only. This does not identify the currently installed runtime. Preserve
all candidates/manifests/pointers/evidence; create a new independently reviewed
source/runtime deployment record after host-side verification, without replacement.

Two accessible Git repositories and every registered worktree were inventoried.
Three historical dirty worktrees and the missing adaptive-contract registration stay
preserved; prior merged/squash-content-equivalent branches need evidence/unique-work
review and explicit cleanup approval. No branch was deleted or stale entry pruned.
Full absolute-path inventories and prepared mutation records stay private outside Git.

## Fake-only full lifecycle and verification

A new disposable campaign ran the orchestrator and genuine Rust policy, with mocked
model execution and trusted transport and real separate filesystem host-request logic.
**Synthetic — not accepted performance evidence:** 20 finalized jobs, 24 fake callbacks /
started ledgers, four controller retries, one interrupted attempt, 13 fake quality passes,
zero real model executions and SSH connections, zero delegation; cost/winner remain
unknown/null. All stage receipts and immutable archive verified, including repeated
archive. These numbers cannot be compared with real baseline performance.

The first synthetic setup refused Cargo's hardlinked adapter artifact before execution;
its partial disposable directory was retained. A new single-link adapter copy and new
campaign destination completed. No uncertain attempt or historical evidence was replayed.

Observed focused exits: adaptive suite `0` (68 tests), readiness fixture `0` (4),
workflow suite `0` (44), new host verifier suite `0` (9), Rust adapter build `0`,
completed synthetic lifecycle `0`.

| Final check | Observed result |
| --- | --- |
| `just docs-check` | PASS / exit `0`; generated ownership/index and local links valid |
| `CARGO_NET_OFFLINE=true just check` | PASS / exit `0`; 295 Python tests in 294.213 seconds, 166 Rust tests; fmt/Clippy/build passed |
| `CARGO_NET_OFFLINE=true just nextest` | PASS / exit `0`; 166 passed, zero skipped |
| `just security` | BLOCKED BY ENVIRONMENT / exit `1`; dependency provenance passed for 30 packages, default advisory database lock refused on read-only path |
| Reviewed temporary public-cache refresh / frozen cargo-deny check | PASS / both exits `0`; advisories/bans/licenses/sources; only `advisories.db-path` differs from repository policy |
| Actual multi-repository/source-register audit | NOT VERIFIED / exit `2`; missing deployment references and unavailable Git objects retained as unknown |
| New accepted-main source export and normalized verification | PASS / exits `0`; 220 files; source-only host report intentionally exits `2` with runtime unknown |
| `git diff --check` | PASS / exit `0`; original CLI/core/frozen benchmark/grading implementation files unchanged |

The first combined `just check` exited `1` (294 tests, two failures/three errors): new
documentation data references were absent from isolated fixture scope. Owning workflow
source pointers and canonical documentation references were corrected; the eight
workflow-fixture regressions then passed and the full final gate above passed. This
was a corrected checkpoint implementation omission, not an environment excuse or an
original PR defect. Historical diagnostics were not rewritten.

Exact final rehearsal commit, remote checks and live PR state are recorded in the
private closeout JSON and branch/check links supplied to the owner. No check is
treated as passed without its exit; the cache procedure never weakens policy.

## Owner boundaries, checkpoint and next efficiency tasks

No GitHub merge authorization was supplied. Unblocked PRs can be marked ready and
recommended, but main integration requires owner acceptance. Issue #46 reopening,
milestone edits, protection settings, cleanup, deployment selection and any real
measurement also require their explicit decisions/authorization. Host verification
is incomplete until independently authorized access supplies exact installed paths,
source/qualification receipt digests, complete runtime JSON and fresh preflight evidence.
The workflow checkpoint describes the commands; unknown values must not be fabricated.

After stabilization/owner acceptance, the three prioritized efficiency tasks from
[production readiness](../production-routing-readiness.md) are:

1. Explicit plan/evidence adapter with bounded native context and approved validation
   preparation; measure retrieval bytes and preparation overhead while retaining quality.
2. Opt-in one-attempt profile/reasoning supervisor with verified compatibility and
   durable ledger; preserve ordinary interactive passthrough and Strong/High floors.
3. Validation-driven bounded escalation/context reuse and opt-in lifecycle telemetry;
   count all failures/unknowns and independently accept comparative quality before claims.

These are expected opportunities, not demonstrated savings. No production adaptive
routing implementation or activation was started during this stabilization.
