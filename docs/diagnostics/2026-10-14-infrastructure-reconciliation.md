# Infrastructure and governance reconciliation — 2026-10-14

This dated audit observes accepted GitHub main `5102c0ebefeb53c3dbd56021266b340524be7ad3`.
It is a historical inventory, not a deployment instruction or performance result.
The authoritative operational procedure is [workflow](../workflow.md).
All implementation was isolated on `chore/infrastructure-reconciliation`, initially
at that main commit. No existing checkout, PR implementation, deployment, benchmark
evidence, issue state, milestone, branch existence or protection setting was changed.
No model execution was launched. GitHub pushes and a draft PR for this audit are
reported separately with their exact commit and check results.

## Scope, provenance and limits

Live paginated GitHub API collection covered **9 milestones, 35 actual issues,
51 PRs, 9 remote branches and all 35 issue timelines**, including closed records,
labels, milestone assignments, state reasons and cross-referenced PRs. Milestones
were queried twice. GitHub comparisons succeeded for 52 public source heads.
Local inspection covered two Git repositories and all their registered worktrees;
no pruning or branch deletion occurred. These observations are point-in-time,
not transactional across API requests or hosts.

Full absolute paths, dirty filenames, Git observations, API records and JSON audit
results are kept in an operator-private directory outside Git. The public tables
use logical checkout aliases and public branch/source identities. Inventories do
not contain credentials, private host configuration, raw traces or stderr. Logical
host `ThinkPadA285` is visible; physical host identity is not independently attested
inside Codex's execution environment. Process-name-only inspection found the active
Codex process but namespace visibility cannot exclude other host sessions. Existing
PR #85 and #86 worktrees were clean and retained at their observed heads.

Independent ThinkPad-to-srv0 SSH access is known to succeed. The Codex environment
rejects system SSH configuration permissions during `ssh -G srv0`, **before making
any connection**. Thus installed srv0 source/runtime identity remains unknown here;
this is not evidence that srv0 is unavailable. No SSH configuration or security check
was altered. A guarded object-only Git fetch for the historical repository was
refused because its Git metadata is outside this execution environment's writable
roots; no permission bypass was attempted. Native read-only tree comparisons plus
explicit GitHub comparisons supplied the available public-source evidence.

## Infrastructure state and source/data classes

| Class / installation | Observed identity / integrity | Role and disposition |
| --- | --- | --- |
| Accepted GitHub source | Full main SHA above; canonical repository verified live | Only accepted source of new task bases |
| Opened checkout (`opened`) | `5cd1b9500a06fe5e1ee595a3eb0a509277e1ba5f`; clean; 4 local-only / 38 main-only commits | Preserve unique development work; not equivalent to main |
| Historical ThinkPad checkout (`historical`) | `4d059299389603f41fe724bbbbe9390b860f8a14`; 3 changed files; 0 local-only / 33 main-only | Preserve dirty `fix/benchmark-lib64-probe` branch; do not synchronize |
| PR #85 isolated source | `93e31c24ab90acd4a2f9874128857ef7dae5f3df`; clean; draft | Independent orchestrator hardening; leave untouched |
| PR #86 isolated source | `f59dfc507e42fc955a061176cee18fcace1ef874`; clean; draft | Offline routing preparation, not production activation; leave untouched |
| Historical adaptive live Git copy | `4edd184e1e7796e763ef327f16adb76872b4b618`; clean; no normalized source receipt | Intentional historical pin, not automatically a defect |
| Historical accepted-check Git copy | `76d6d9018be98a44a3f51a51d4ef1d24d2b20c87`; clean; no normalized receipt | Preserve source/evidence reference |
| Historical smoke-plan Git copy | `0a47c428ef68435548e3ed7515a61c81b7bd7e61`; clean; no normalized receipt | Historical source, not current deployment |
| Historical full-campaign Git copy | `08d255788562b03d0682ca92ee6141f26c5a1618`; clean; no normalized receipt | Historical source, not current deployment |
| Normalized deployment directory | Expected operator source-snapshot directory absent; no reviewed deployment register found in inspected locations | Record missing references; never infer an installation from a directory name |
| srv0 grading installation | Exact installed path, source SHA, normalized receipt SHA256 and current integrity unverified from Codex | Host-side read-only verification required; never replace installation |
| Runtime/toolchain dependencies | Qualified contracts in accepted source; historical runtime pointer ambiguity below | Source hashes alone do not qualify a runtime |
| Immutable benchmark evidence | Accessible evidence store retained; accepted provenance in PR #72/#82 and frozen contracts | Preserve historical bytes and accepted ledgers; no reruns |
| Temporary synthetic artifacts | Fake-only rehearsal/test source receipts may be internally valid but not accepted GitHub source | Not a deployment or accepted performance evidence |
| Caches / regenerable files | Kept outside immutable source snapshots | Cache identity does not establish source identity |
| Credentials / private host configuration | Not inventoried or copied | Outside audit content scope |

Historical Git copies lack `.codex-smart-source.json`; their receipt SHA256 is
**unknown**, not falsely verified. A metadata-only evidence search bounded to five
levels found no normalized source receipts in the inspected evidence store; it is
not an exhaustive claim about every host directory. Existing dated `NOT VERIFIED`
notes describe candidates at their observation date; subsequent accepted qualification
must be checked separately, rather than rewriting those notes or treating them as
current failures. The 20-job adaptive split-host rehearsal is synthetic, not accepted
performance evidence, and remained unchanged.

### Confirmed ambiguous runtime reference

The historical evidence store's `CURRENT_RUNTIME_BUNDLE.txt` describes an
accepted-review candidate at source `dc2befe8d143d670c7a0ac47c5c3141a964c0a7c`.
Its file-manifest reference and the accepted production contract differ from the
adjacent `runtime-files.tsv`; the adjacent directory manifest also differs from the
accepted contract. This is a **reference inconsistency**, not a proven deployed-runtime
integrity failure. Several historical candidates coexist; filenames cannot select one.

| Inventory | Accepted contract SHA256 | Adjacent evidence-store SHA256 |
| --- | --- | --- |
| Files | `50c3b03c2bf1ae30ecb6d910c8e6d5b422d8bf839597f1de6dce55b355ab82df` | `944660e6956f2c4d6fdfb28094f895cd975efc6a022d7c82ae3d0af56ca22a7c` |
| Directories | `663c3335fe7586f5372615c65d71b88f098b5673990a65a6659809eaef83c78d` | `77ef85f4bb5474d1f8b97e84b3da8e6c2b44bc9a879cb5b71cff27684957f65c` |
| Symlinks | `e6831ba698554b772a1b7627833ad518cf43fe6eba451ddbdb02419d8fd1102d` | Same |

Reproduction is read-only SHA256 of the three adjacent TSV files, compared with
`scripts/benchmark_submission_grading.py::expected_contract()['runtime_inventory']`
and the dated pointer. Preserve all historical files. Before any dependent operation,
the owner should record the actual installed runtime and source identity in a **new**
reviewed deployment record using independently verified host access.

## Milestone reconciliation

Design, implementation, offline testing, reviewed acceptance, main integration,
production activation, measured behavior and routine readiness are distinct states.
`docs/stages.json` describes recorded implementation evidence, not live closure or
activation. The active stage remains `adaptive`; this audit does not advance it.

| Number / milestone | State; due date; API open/closed | True scoped progress and accepted PRs | Remaining work / recommended owner correction |
| --- | --- | --- | --- |
| 1 — 0.1 Foundation | Closed; none; 0/10 | Designed, implemented, tested, accepted and merged: #19, #21, #22, #25, #26. Launcher/read-only diagnostics/config transactions operational within documented bounds. | Scoped foundation complete; not a 1.0 or benchmark claim. No state change needed. |
| 2 — 0.2 Router v2 | Closed; none; 0/5 | Pure policy designed, implemented, tested, accepted, merged: #27–#31. | **Not integrated into production `run`, not comparatively measured.** Retain closure only as policy milestone; clarify scope and track runtime activation separately. |
| 3 — 0.3 Development Benchmark | Open; none; 0/2 | Harness, qualified representative baseline and aggregate telemetry accepted/merged: #32, #64–#73. Measurements compare vanilla vs native-first instruction. | No Router/Playbooks/Adaptive efficiency winner. Owner decide whether release grouping can close as baseline or needs explicit remaining criteria. Zero open issues alone does not decide. |
| 4 — 0.8 Hardening | Open; none; 3/0 | Designed future work; focused security controls exist, no comprehensive readiness acceptance. | #53/#54 remain; API count 3 disagrees with 2 assigned actual issues and no assigned PRs. Reconcile count before scope decisions. |
| 5 — 1.0 Stable | Open; none; 2/0 | Designed release contracts; #17/#55 open. | Supported upgrades, public-contract freeze and hardening acceptance outstanding. Correctly open. |
| 6 — 0.4 Workflow Intelligence | Open; none; 0/3 | Pure archetype/planning/validation recipes implemented, tested, accepted, merged: #74–#76. | No production preparation/validation executor or efficiency measurement. Description saying implementation awaits prerequisites is stale; clarify pure-policy acceptance and remaining runtime work. Do not auto-close. |
| 7 — 0.5 Adaptive Execution | Open; none; 0/4 | Pure controller/profile/delegation contracts #77–#79, harness #80, accepted profile smoke #82 and offline-tested runner #83 merged. #85 remains draft. | Production adaptive routing inactive; full comparative campaign unexecuted; #46 acceptance unmet despite closure. Replace stale planned-only description and restore measurement tracking, owner approval required. |
| 8 — 0.6 Reusable Automation | Open; none; 3/0 | Designed only; #47–#49 open. | Depends on accepted operational adaptive execution; no cache/index/recurring executor. Correctly open. |
| 9 — 0.7 Distribution | Open; none; 3/0 | Designed only; #16/#50–#52 open. | Installer/updater/recovery not implemented. API count 3 disagrees with 4 assigned actual issues and no assigned PRs; clarify umbrella #16, retain open state. |

The two milestone count mismatches persisted across repeated paginated queries.
Treat counters as inconsistent API metadata, not proof that an issue is missing or
permission to move it. All nine due dates are absent. No milestone state was changed.

## Issue reconciliation

A = correctly closed within accepted scope; B = should reopen or explicitly split
unfinished acceptance; C = correctly open; D = implemented awaiting acceptance;
E = proven superseded/duplicate; F = requires scope clarification. Secondary scope
notes do not automatically undo accepted policy work. All 24 closed actual issues
have state reason `completed`; the 11 open issues have no close reason. Labels each
provide one area, one stage, one severity and a meaningful enhancement/investigation
kind. Linked PRs are cross-reference/acceptance evidence, not necessarily automatic
closing links; all issue timelines were read. No proven issue duplicate warrants E,
and no already completed open issue warrants D. Draft PR #85/#86 are awaiting review,
not a reason to mass-close unrelated issues.

| Issue | Current state / milestone | Category | Acceptance evidence / concrete recommendation |
| --- | --- | --- | --- |
| [#1](https://github.com/AlexandrShapkin/codex-smart/issues/1) — Establish repository provenance and baseline | closed / 1 | A | Accepted audited baseline PR #19; no legacy completeness claim. |
| [#2](https://github.com/AlexandrShapkin/codex-smart/issues/2) — Bootstrap Rust workspace and CLI | closed / 1 | A | Rust workspace/CLI accepted #19. |
| [#3](https://github.com/AlexandrShapkin/codex-smart/issues/3) — Implement read-only capability preflight | closed / 1 | A | Conservative offline preflight accepted #19/#21; discovered availability is not runtime health. |
| [#4](https://github.com/AlexandrShapkin/codex-smart/issues/4) — Implement codex-smart doctor | closed / 1 | A | Read-only Doctor accepted #22. |
| [#5](https://github.com/AlexandrShapkin/codex-smart/issues/5) — Guarantee explain is side-effect free | closed / 1 | A | Side-effect-free explain contract accepted #19; isolated regression coverage. |
| [#6](https://github.com/AlexandrShapkin/codex-smart/issues/6) — Design safe configuration and migration model | closed / 1 | A | Safe marked TOML transactions/migration accepted #19 and ADR-0005; installation upgrades excluded. |
| [#7](https://github.com/AlexandrShapkin/codex-smart/issues/7) — Pin and report external capability versions | closed / 1 | A | Owned executable pins/compatibility accepted #21; comment explicitly defers runtime auth/MCP integration. |
| [#8](https://github.com/AlexandrShapkin/codex-smart/issues/8) — Add CI quality gates | closed / 1 | A | Required local/CI gates accepted #19; review enforcement gap below is separate governance work. |
| [#9](https://github.com/AlexandrShapkin/codex-smart/issues/9) — Define task and risk model | closed / 2 | A | Pure task/risk assessment accepted #27. |
| [#10](https://github.com/AlexandrShapkin/codex-smart/issues/10) — Implement Router v2 decision engine | closed / 2 | A | Pure capability engine accepted #28; actual production caller still absent. |
| [#11](https://github.com/AlexandrShapkin/codex-smart/issues/11) — Add reasoning-effort selection | closed / 2 | A | Reasoning policy/argv planner #29; acceptance comment explicitly says no runtime activation. |
| [#12](https://github.com/AlexandrShapkin/codex-smart/issues/12) — Add routing fallback and escalation | closed / 2 | A | Finite fallback/escalation policy #30; acceptance comment excludes executing retries. |
| [#13](https://github.com/AlexandrShapkin/codex-smart/issues/13) — Evaluate and integrate sandboxed Rhai policies | closed / 2 | A | Rhai evaluated and deferred by ADR-0004/#31; title does not require an unnecessary plugin runtime. |
| [#14](https://github.com/AlexandrShapkin/codex-smart/issues/14) — Build end-to-end development benchmark | closed / 3 | A | Harness/qualified representative baseline #32/#72; 19/20 vanilla, 17/20 native; not full adaptive acceptance. |
| [#15](https://github.com/AlexandrShapkin/codex-smart/issues/15) — Add token/tool/latency telemetry | closed / 3 | A | Normalized aggregate telemetry #73; runtime telemetry collector excluded. Clarify title scope if revisited. |
| [#16](https://github.com/AlexandrShapkin/codex-smart/issues/16) — Implement release and migration workflow | open / 9 | C/F | Release/migration umbrella intentionally open. Add explicit parent/child links to #50–#52; retain limited schema migration acceptance separately. |
| [#17](https://github.com/AlexandrShapkin/codex-smart/issues/17) — Production hardening and 1.0 readiness | open / 5 | C/F | Readiness umbrella intentionally open. Link #53–#55 and production integration/evidence prerequisites explicitly. |
| [#18](https://github.com/AlexandrShapkin/codex-smart/issues/18) — Launch Codex safely with exact OS arguments | closed / 1 | A | Exact OS argv/safe launch #19; no shell or routing activation. |
| [#20](https://github.com/AlexandrShapkin/codex-smart/issues/20) — Add bounded stage context and documentation workflow | closed / 1 | A | Bounded context/document ownership #19; later normalized workflow #84 extends it. |
| [#40](https://github.com/AlexandrShapkin/codex-smart/issues/40) — Define task archetype and playbook contract | closed / 6 | A | Pure archetype contract #74; comment records scoped acceptance. |
| [#41](https://github.com/AlexandrShapkin/codex-smart/issues/41) — Implement deterministic playbook and resource planner | closed / 6 | A | Pure deterministic resource planner #75; no preparation executor. |
| [#42](https://github.com/AlexandrShapkin/codex-smart/issues/42) — Add validation recipes and explainable preparation | closed / 6 | A | Pure validation recipes/explain #76; executing validators deferred. |
| [#43](https://github.com/AlexandrShapkin/codex-smart/issues/43) — Define adaptive execution and escalation contract | closed / 7 | A | Pure bounded execution/controller contract #77; benchmark runner later #83. |
| [#44](https://github.com/AlexandrShapkin/codex-smart/issues/44) — Implement progressive model and reasoning routing | closed / 7 | A/F | Pure replaceable model/reasoning resolver #78 accepted. Clarify description that production argv/controller integration is still absent; #86 prepares tests only. |
| [#45](https://github.com/AlexandrShapkin/codex-smart/issues/45) — Implement bounded delegation and handoff contract | closed / 7 | A/F | Bounded delegation/handoff policy #79 accepted. Clarify no child-execution integration; frozen measurement delegation remains zero. |
| [#46](https://github.com/AlexandrShapkin/codex-smart/issues/46) — Benchmark adaptive lifecycle economics | closed / 7 | B | Full comparative lifecycle quality/token/latency/cost acceptance unmet; #80–#83 are preparation/smoke/runner, not measurement. Reopen or owner-approved split; consider P1 instead of P3 and depend on review of #85 plus production adapter readiness. |
| [#47](https://github.com/AlexandrShapkin/codex-smart/issues/47) — Add repository workflow profiles and invalidation | open / 8 | C | Repository profile/invalidation future work; depends on operational adaptive acceptance, not closed #46 alone. |
| [#48](https://github.com/AlexandrShapkin/codex-smart/issues/48) — Add prepared capability index and cache lifecycle | open / 8 | C | Prepared capability cache/index future work; retain unknown readiness until verified producer exists. |
| [#49](https://github.com/AlexandrShapkin/codex-smart/issues/49) — Add deterministic recurring workflow fast paths | open / 8 | C | Recurring deterministic fast paths future work; no current executor. |
| [#50](https://github.com/AlexandrShapkin/codex-smart/issues/50) — Implement explicit atomic installer and uninstaller | open / 9 | C | Atomic installer/uninstaller future work; link umbrella #16. |
| [#51](https://github.com/AlexandrShapkin/codex-smart/issues/51) — Implement secure update check update and rollback | open / 9 | C | Secure update/rollback future work; link #16/#50 and source/runtime identity requirements. |
| [#52](https://github.com/AlexandrShapkin/codex-smart/issues/52) — Rehearse migration and interrupted update recovery | open / 9 | C | Migration/interruption rehearsal future work; require #50/#51 acceptance, link #16. |
| [#53](https://github.com/AlexandrShapkin/codex-smart/issues/53) — Review security supply chain and privacy boundaries | open / 4 | C | Comprehensive security/supply-chain/privacy review still needed; current deny gate is not full acceptance. |
| [#54](https://github.com/AlexandrShapkin/codex-smart/issues/54) — Verify failure recovery resource bounds and reliability | open / 4 | C | Reliability/failure-recovery acceptance still needed; historical isolated tests do not establish routine readiness. |
| [#55](https://github.com/AlexandrShapkin/codex-smart/issues/55) — Freeze durable public contracts and supported upgrade path | open / 5 | C | Public contracts/support/upgrade freeze still needed; depend on #16/#50–#54. |

Owner-approved factual issue edits should annotate #40–#55's dated “active stage
remains benchmark” creation context, rather than leaving it as current state.
Current stage is adaptive. Add a separately scoped production-routing integration
issue with explicit validation, bounded escalation, telemetry, fallback and comparative
acceptance dependencies; do not imply #44/#45's pure APIs already execute these steps.
No label, milestone assignment, issue state or body was changed by this task.

## GitHub governance and open PRs

Main protection requires strict `check` and `review` contexts from GitHub Actions
app 15368; force push and deletion are disabled. Auto-merge is disabled. However,
required approving review count is **0**, administrators are not covered, code-owner
review and last-push approval are not required. The workflow's owner-review requirement
is therefore not fully enforced by settings. Recommend an owner decision on at least
one independent approval and administrator/last-push coverage, accounting for project
maintainer availability. No settings were changed.

GitHub allows merge commits, squash and rebase merges; branch deletion after merge
is enabled. Automatic deletion is not this task's action, but historical source pins
must use SHA/receipts rather than assume branch existence. Recommended retention:
retain active PR branches, unique/dirty work and evidence references; after acceptance,
inspect exact head/content and PR linkage, archive needed identities, then seek owner
approval for a bounded cleanup list. Never prune missing registrations automatically.

| Open PR | Head | Status / recommendation |
| --- | --- | --- |
| [#23](https://github.com/AlexandrShapkin/codex-smart/pull/23) | `e758503953a28a69f9ee45fbe06495c3342e2153` | Open; Dependency major update; independent compatibility/security review needed. |
| [#24](https://github.com/AlexandrShapkin/codex-smart/pull/24) | `1285b667dab76ea255fe9caae28ff3ce959acdfb` | Open; Dependency major update; independent compatibility/security review needed. |
| [#63](https://github.com/AlexandrShapkin/codex-smart/pull/63) | `558a0fd0c67f11fac6b20ed4c3846e0aa30894c4` | Open; Isolation acceptance purpose appears superseded by #64–#66; 9 changed files include stale no-host-qualified documentation. Inspect every hunk before any owner-approved closure; do not merge old claims. |
| [#85](https://github.com/AlexandrShapkin/codex-smart/pull/85) | `93e31c24ab90acd4a2f9874128857ef7dae5f3df` | Draft; independent orchestrator hardening; no modifications by this audit. |
| [#86](https://github.com/AlexandrShapkin/codex-smart/pull/86) | `f59dfc507e42fc955a061176cee18fcace1ef874` | Draft; offline production policy preparation, not activation; no modifications by this audit. |

## Branch and worktree reconciliation

Divergence is **local-only / main-only commits** against the exact selected main,
not cached branch names. `merged-content-equivalent` requires accepted PR identity
and equal source trees at its merge; this covers squash merges without declaring
all non-ancestor branches redundant. GitHub comparisons supplement missing local
objects in the historical clone; they are marked `GH`. Counts alone never authorize
cleanup. This task's working changes are intentional and excluded from unrelated
source preservation claims.

### Every live remote branch

| Branch | Full head | PR | Divergence | Classification / recommendation |
| --- | --- | --- | --- | --- |
| `benchmark/accept-agent-isolation` | `558a0fd0c67f11fac6b20ed4c3846e0aa30894c4` | [#63](https://github.com/AlexandrShapkin/codex-smart/pull/63) | 1/26 GH | Open PR; retain |
| `chore/production-routing-readiness` | `f59dfc507e42fc955a061176cee18fcace1ef874` | [#86](https://github.com/AlexandrShapkin/codex-smart/pull/86) | 1/0 GH | Open PR; retain |
| `chore/recover-baseline-context` | `cf1769a2c3fca3f7973060da281931df22268776` | [#19](https://github.com/AlexandrShapkin/codex-smart/pull/19) | 0/92 GH | Accepted PR source; cleanup candidate only after exact content/evidence review and approval |
| `dependabot/github_actions/actions/checkout-7.0.1` | `1285b667dab76ea255fe9caae28ff3ce959acdfb` | [#24](https://github.com/AlexandrShapkin/codex-smart/pull/24) | 1/91 GH | Open PR; retain |
| `dependabot/github_actions/actions/upload-artifact-7.0.1` | `e758503953a28a69f9ee45fbe06495c3342e2153` | [#23](https://github.com/AlexandrShapkin/codex-smart/pull/23) | 1/91 GH | Open PR; retain |
| `feat/adaptive-split-host-orchestrator` | `93e31c24ab90acd4a2f9874128857ef7dae5f3df` | [#85](https://github.com/AlexandrShapkin/codex-smart/pull/85) | 4/0 GH | Open PR; retain |
| `feat/doctor` | `53c1adbbf7496dcfa0b054a5bbe5c7cb337654fb` | [#22](https://github.com/AlexandrShapkin/codex-smart/pull/22) | 0/81 GH | Accepted PR source; cleanup candidate only after exact content/evidence review and approval |
| `feat/external-version-compatibility` | `94bdcb06ae1c0e830a08639345df5584e2b4f7a7` | [#21](https://github.com/AlexandrShapkin/codex-smart/pull/21) | 0/88 GH | Accepted PR source; cleanup candidate only after exact content/evidence review and approval |
| `main` | `5102c0ebefeb53c3dbd56021266b340524be7ad3` | none | 0/0 GH | Accepted main; retain |

### Every local branch — opened repository

| Branch | Full head | Worktree alias / dirty state | PR | Divergence | Classification / disposition |
| --- | --- | --- | --- | --- | --- |
| `benchmark/agent-execution-isolation-gate` | `5cd1b9500a06fe5e1ee595a3eb0a509277e1ba5f` | codex-smart (clean) | none at exact head | 4/38 | unique-or-squash-unresolved; preserve unique/unresolved work; inspect commits individually |
| `benchmark/grading-isolation` | `ffc7d336a1e66d1b1f5eb08bf23b15893ca8356d` | no attached worktree | [#37](https://github.com/AlexandrShapkin/codex-smart/pull/37) | 0/51 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/isolation-resource-contract` | `2a6e702e47013760a1371d725719334f9eeda86e` | no attached worktree | [#38](https://github.com/AlexandrShapkin/codex-smart/pull/38) | 0/49 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/live-contract-preflight` | `6dec19db52b69efcfbbf3bb275c97655c689456d` | no attached worktree | [#33](https://github.com/AlexandrShapkin/codex-smart/pull/33) | 0/62 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/live-smoke-unblock` | `076485ee363149af7235717b89c17989bf848c74` | no attached worktree | [#34](https://github.com/AlexandrShapkin/codex-smart/pull/34) | 0/60 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/representative-coverage` | `c6580d88ee60515a551757b8ea4124e63e549331` | no attached worktree | [#39](https://github.com/AlexandrShapkin/codex-smart/pull/39) | 0/45 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/representative-runner-contract` | `cd5e589f0b27d67126fbf430bfb3db47d3b4ea20` | no attached worktree | [#57](https://github.com/AlexandrShapkin/codex-smart/pull/57) | 0/41 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/upstream-codex-pin` | `2debd9b10389b3741e2ce604037fee30c309f07e` | no attached worktree | [#58](https://github.com/AlexandrShapkin/codex-smart/pull/58) | 0/39 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/upstream-toolchain-pin` | `c392f0298b26b50c7d757a37751047327d5d6b9c` | no attached worktree | none at exact head | 1/37 | unique-or-squash-unresolved; preserve unique/unresolved work; inspect commits individually |
| `benchmark/verify-live-contract` | `ffada221f30c02f58f66da5f621136541390951f` | no attached worktree | [#36](https://github.com/AlexandrShapkin/codex-smart/pull/36) | 0/54 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `chore/infrastructure-reconciliation` | `5102c0ebefeb53c3dbd56021266b340524be7ad3` | this isolated audit (intentional task changes) | none at exact head | 0/0 | accepted-main; active audit task; retain |
| `chore/legal-and-repository-finalization` | `8a12bc1baa39453943d69dbb965a5b9392029e2d` | no attached worktree | [#26](https://github.com/AlexandrShapkin/codex-smart/pull/26) | 0/76 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `chore/production-routing-readiness` | `f59dfc507e42fc955a061176cee18fcace1ef874` | codex-smart-production-readiness-20261014 (clean) | [#86](https://github.com/AlexandrShapkin/codex-smart/pull/86) | 1/0 | open-pr; retain for review |
| `chore/recover-baseline-context` | `cf1769a2c3fca3f7973060da281931df22268776` | no attached worktree | [#19](https://github.com/AlexandrShapkin/codex-smart/pull/19) | 0/92 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `chore/repository-polish` | `0cc71a76c0ff153756fe8bec6732ece3290066f6` | no attached worktree | [#25](https://github.com/AlexandrShapkin/codex-smart/pull/25) | 0/78 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `chore/workflow-normalization` | `d38b6dc198623614aeb3bf173c02f4f15bee130a` | codex-smart-workflow-20261014 (clean) | [#84](https://github.com/AlexandrShapkin/codex-smart/pull/84) | 4/1 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `docs/close-router-v2` | `458eb8bdfc82c0bde8183cc109d17afd2536418e` | no attached worktree | [#31](https://github.com/AlexandrShapkin/codex-smart/pull/31) | 0/66 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `feat/adaptive-split-host-orchestrator` | `93e31c24ab90acd4a2f9874128857ef7dae5f3df` | codex-smart-adaptive-orchestrator-20261014 (clean) | [#85](https://github.com/AlexandrShapkin/codex-smart/pull/85) | 4/0 | open-pr; retain for review |
| `feat/doctor` | `53c1adbbf7496dcfa0b054a5bbe5c7cb337654fb` | no attached worktree | [#22](https://github.com/AlexandrShapkin/codex-smart/pull/22) | 0/81 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `feat/e2e-benchmark-harness` | `1d43f556e33ec40f5dbde7281339ff801940c04e` | no attached worktree | [#32](https://github.com/AlexandrShapkin/codex-smart/pull/32) | 0/64 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `feat/external-version-compatibility` | `94bdcb06ae1c0e830a08639345df5584e2b4f7a7` | no attached worktree | [#21](https://github.com/AlexandrShapkin/codex-smart/pull/21) | 0/88 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `feat/reasoning-effort-selection` | `7df7a85f308f6ff1f2e61a091cfd2ac84fabdecd` | no attached worktree | [#29](https://github.com/AlexandrShapkin/codex-smart/pull/29) | 0/70 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `feat/router-v2-decision-engine` | `02b26f408a012fad7e89737a0b7a38c2e140d7d6` | no attached worktree | [#28](https://github.com/AlexandrShapkin/codex-smart/pull/28) | 0/72 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `feat/routing-fallback-escalation` | `b6d700c669db7cbcdcf84b271d5ef0655f63e3f6` | no attached worktree | [#30](https://github.com/AlexandrShapkin/codex-smart/pull/30) | 0/68 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `feat/task-risk-model` | `712f541f2050109379540ce5fe87afe8f2db977a` | no attached worktree | [#27](https://github.com/AlexandrShapkin/codex-smart/pull/27) | 0/74 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `fix/benchmark-auth-parser-contract` | `5d8ed08a31ccd92f380c63eed68fac4e86663211` | no attached worktree | [#35](https://github.com/AlexandrShapkin/codex-smart/pull/35) | 0/58 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `main` | `5846f5cf0be5c3a90056b9182affa66cff53b38f` | no attached worktree | none at exact head | 0/38 | accepted-history; historical source; preserve pins/dirty work |
| `roadmap/workflow-intelligence` | `e40e8881d5141c4e0d15ee084f706e09b8a59d10` | no attached worktree | [#56](https://github.com/AlexandrShapkin/codex-smart/pull/56) | 0/43 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `tmp/keyring-review-accidental` | `5119881ab6452b5ce629106f75a18d3980cfecd1` | no attached worktree | none at exact head | 3/38 | unique-or-squash-unresolved; preserve unique/unresolved work; inspect commits individually |

### Every local branch — historical repository

| Branch | Full head | Worktree alias / dirty state | PR | Divergence | Classification / disposition |
| --- | --- | --- | --- | --- | --- |
| `adaptive/bounded-delegation` | `7145dd6595003313b8fcccc16d5c46fe9c76c9b8` | codex-smart-adaptive-delegation (clean) | [#79](https://github.com/AlexandrShapkin/codex-smart/pull/79) | 1/6 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `adaptive/execution-contract` | `d8fabc7eb5bc5ece36495d11bf04454d4ac2c3dc` | no attached worktree | [#77](https://github.com/AlexandrShapkin/codex-smart/pull/77) | 1/8 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `adaptive/lifecycle-economics-harness` | `96796a7ff8aa7205f2bc79f32ef613b17626386e` | codex-smart-adaptive-economics (clean) | [#80](https://github.com/AlexandrShapkin/codex-smart/pull/80) | 1/5 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `adaptive/progressive-routing` | `158ed23e69300843360d6d32945ce7f970c24d9b` | codex-smart-adaptive-routing (clean) | [#78](https://github.com/AlexandrShapkin/codex-smart/pull/78) | 1/7 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/accept-adaptive-profile-smoke` | `e3b9589ecea79f25ef754b397df73512c7073487` | codex-smart-adaptive-profile-accept (clean) | [#82](https://github.com/AlexandrShapkin/codex-smart/pull/82) | 1/3 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/accept-agent-isolation` | `558a0fd0c67f11fac6b20ed4c3846e0aa30894c4` | codex-smart-backend-review (clean) | [#63](https://github.com/AlexandrShapkin/codex-smart/pull/63) | 1/26 GH | open-pr; retain for review |
| `benchmark/accept-production-grading-readiness` | `8426eb54e836e13be7bd032d3d1af548c2c10f69` | codex-smart-readiness (clean) | [#66](https://github.com/AlexandrShapkin/codex-smart/pull/66) | 3/19 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/accept-representative-baseline` | `b3b8fd6134d8c479a1efdc925f5710382b4f9e77` | codex-smart-measurement-accept (clean) | [#72](https://github.com/AlexandrShapkin/codex-smart/pull/72) | 1/13 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/accept-split-host-campaign` | `9e26be5fa5f80d46c5fa949943ee21f6a3c35e8d` | codex-smart-split-accept (clean) | [#70](https://github.com/AlexandrShapkin/codex-smart/pull/70) | 1/15 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/adaptive-live-runner` | `7eb9a26140e0bb604bc93017c05567db21fb7b12` | codex-smart-adaptive-live-runner (clean) | [#83](https://github.com/AlexandrShapkin/codex-smart/pull/83) | 2/2 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/fix-python-billing-rounding-spec` | `4b713cc736a28e80832fb41e2be5f95048d9f5ac` | codex-smart-rounding-fix (clean) | [#68](https://github.com/AlexandrShapkin/codex-smart/pull/68) | 1/17 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/isolated-submission-grader` | `b583904f5fba1e8d7a564bb679c5b15e05a18842` | codex-smart-submission-review (dirty) | none at exact head | 0/24 | accepted-history; historical source; preserve pins/dirty work |
| `benchmark/privacy-aggregate-telemetry` | `61905469ca83710b0d19b7275025fdbb6eb5d878` | codex-smart-telemetry (clean) | [#73](https://github.com/AlexandrShapkin/codex-smart/pull/73) | 1/12 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/production-isolated-grader` | `90cc38c4cd16552edfa0e168aaa60556a6b9ca01` | codex-smart-prod-grader (clean) | [#65](https://github.com/AlexandrShapkin/codex-smart/pull/65) | 0/20 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/production-isolated-grading` | `b583904f5fba1e8d7a564bb679c5b15e05a18842` | codex-smart-grading (dirty) | none at exact head | 0/24 | accepted-history; historical source; preserve pins/dirty work |
| `benchmark/record-adaptive-profile-smoke` | `de202644a1cca56acf4953c42c773d8dfd2b3591` | codex-smart-adaptive-profile-record (clean) | [#81](https://github.com/AlexandrShapkin/codex-smart/pull/81) | 1/4 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/record-representative-baseline` | `fe4ae08f7e3d0a07277d5112ff16f5c4fbfff40e` | codex-smart-measured-baseline (clean) | [#71](https://github.com/AlexandrShapkin/codex-smart/pull/71) | 1/14 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/representative-live-smoke` | `8b0d99ef21437c40215783c0eb0915d7e4f5a247` | codex-smart-live-smoke (clean) | [#67](https://github.com/AlexandrShapkin/codex-smart/pull/67) | 1/18 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/review-ubuntu-bwrap-backend` | `166ba0465ddeeaa60057db4ac4972b46c4d0c9ae` | no attached worktree | [#62](https://github.com/AlexandrShapkin/codex-smart/pull/62) | 0/27 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/split-host-representative-campaign` | `5c0bbd12243f0481fdb91ca8624b4ce94b0d702c` | codex-smart-split-campaign (clean) | [#69](https://github.com/AlexandrShapkin/codex-smart/pull/69) | 1/16 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `benchmark/upstream-toolchain-pin` | `4d059299389603f41fe724bbbbe9390b860f8a14` | no attached worktree | [#60](https://github.com/AlexandrShapkin/codex-smart/pull/60) | 0/33 | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `fix/benchmark-lib64-probe` | `4d059299389603f41fe724bbbbe9390b860f8a14` | codex-smart (dirty) | none at exact head | 0/33 | accepted-history; historical source; preserve pins/dirty work |
| `main` | `69cdff7f56656347cdd1e7a58a2ea2e0f2850049` | no attached worktree | none at exact head | 0/34 | accepted-history; historical source; preserve pins/dirty work |
| `playbooks/deterministic-resource-planner` | `3f51dbb64f52bedec9e3c4e5139f3a0d22e9a743` | codex-smart-playbooks-planner (clean) | [#75](https://github.com/AlexandrShapkin/codex-smart/pull/75) | 1/10 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `playbooks/task-archetype-contract` | `5c9132243466c94536d334e833543846657c79ba` | codex-smart-playbooks-contract (clean) | [#74](https://github.com/AlexandrShapkin/codex-smart/pull/74) | 1/11 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |
| `playbooks/validation-explain` | `78ef2fbb7b417363bd4a4cfb0901360f9723e551` | codex-smart-playbooks-validation (clean) | [#76](https://github.com/AlexandrShapkin/codex-smart/pull/76) | 1/9 GH | merged-content-equivalent; content accepted; preserve until evidence/dirty review and cleanup approval |

### Every registered worktree

There are 5 registrations in the opened repository and 29 in the historical
repository. Three **unrelated** historical worktrees are dirty (3, 15 and 8 status
records); all were preserved. The missing adaptive-contract path remains registered.
No new evidence was attached to an old source copy.

| Repository / worktree alias | Branch or detached head | Full registered/observed head | State / disposition |
| --- | --- | --- | --- |
| opened / codex-smart | `benchmark/agent-execution-isolation-gate` | `5cd1b9500a06fe5e1ee595a3eb0a509277e1ba5f` | clean; preserve |
| opened / codex-smart-adaptive-orchestrator-20261014 | `feat/adaptive-split-host-orchestrator` | `93e31c24ab90acd4a2f9874128857ef7dae5f3df` | clean; preserve |
| opened / codex-smart-infrastructure-audit-20261014 | `chore/infrastructure-reconciliation` | `5102c0ebefeb53c3dbd56021266b340524be7ad3` | intentional audit changes; preserve |
| opened / codex-smart-production-readiness-20261014 | `chore/production-routing-readiness` | `f59dfc507e42fc955a061176cee18fcace1ef874` | clean; preserve |
| opened / codex-smart-workflow-20261014 | `chore/workflow-normalization` | `d38b6dc198623614aeb3bf173c02f4f15bee130a` | clean; preserve |
| historical / codex-smart | `fix/benchmark-lib64-probe` | `4d059299389603f41fe724bbbbe9390b860f8a14` | dirty; preserve |
| historical / codex-smart-adaptive-contract | `(detached or missing)` | `d8fabc7eb5bc5ece36495d11bf04454d4ac2c3dc` | stale-registration; missing/stale; inspect, no prune |
| historical / codex-smart-adaptive-delegation | `adaptive/bounded-delegation` | `7145dd6595003313b8fcccc16d5c46fe9c76c9b8` | clean; preserve |
| historical / codex-smart-adaptive-economics | `adaptive/lifecycle-economics-harness` | `96796a7ff8aa7205f2bc79f32ef613b17626386e` | clean; preserve |
| historical / codex-smart-adaptive-live-runner | `benchmark/adaptive-live-runner` | `7eb9a26140e0bb604bc93017c05567db21fb7b12` | clean; preserve |
| historical / codex-smart-adaptive-profile-accept | `benchmark/accept-adaptive-profile-smoke` | `e3b9589ecea79f25ef754b397df73512c7073487` | clean; preserve |
| historical / codex-smart-adaptive-profile-record | `benchmark/record-adaptive-profile-smoke` | `de202644a1cca56acf4953c42c773d8dfd2b3591` | clean; preserve |
| historical / codex-smart-adaptive-routing | `adaptive/progressive-routing` | `158ed23e69300843360d6d32945ce7f970c24d9b` | clean; preserve |
| historical / codex-smart-backend-review | `benchmark/accept-agent-isolation` | `558a0fd0c67f11fac6b20ed4c3846e0aa30894c4` | clean; preserve |
| historical / codex-smart-grading | `benchmark/production-isolated-grading` | `b583904f5fba1e8d7a564bb679c5b15e05a18842` | dirty; preserve |
| historical / codex-smart-live-smoke | `benchmark/representative-live-smoke` | `8b0d99ef21437c40215783c0eb0915d7e4f5a247` | clean; preserve |
| historical / codex-smart-measured-baseline | `benchmark/record-representative-baseline` | `fe4ae08f7e3d0a07277d5112ff16f5c4fbfff40e` | clean; preserve |
| historical / codex-smart-measurement-accept | `benchmark/accept-representative-baseline` | `b3b8fd6134d8c479a1efdc925f5710382b4f9e77` | clean; preserve |
| historical / codex-smart-playbooks-contract | `playbooks/task-archetype-contract` | `5c9132243466c94536d334e833543846657c79ba` | clean; preserve |
| historical / codex-smart-playbooks-planner | `playbooks/deterministic-resource-planner` | `3f51dbb64f52bedec9e3c4e5139f3a0d22e9a743` | clean; preserve |
| historical / codex-smart-playbooks-validation | `playbooks/validation-explain` | `78ef2fbb7b417363bd4a4cfb0901360f9723e551` | clean; preserve |
| historical / codex-smart-prod-grader | `benchmark/production-isolated-grader` | `90cc38c4cd16552edfa0e168aaa60556a6b9ca01` | clean; preserve |
| historical / codex-smart-readiness | `benchmark/accept-production-grading-readiness` | `8426eb54e836e13be7bd032d3d1af548c2c10f69` | clean; preserve |
| historical / codex-smart-rounding-fix | `benchmark/fix-python-billing-rounding-spec` | `4b713cc736a28e80832fb41e2be5f95048d9f5ac` | clean; preserve |
| historical / codex-smart-split-accept | `benchmark/accept-split-host-campaign` | `9e26be5fa5f80d46c5fa949943ee21f6a3c35e8d` | clean; preserve |
| historical / codex-smart-split-campaign | `benchmark/split-host-representative-campaign` | `5c0bbd12243f0481fdb91ca8624b4ce94b0d702c` | clean; preserve |
| historical / codex-smart-submission-review | `benchmark/isolated-submission-grader` | `b583904f5fba1e8d7a564bb679c5b15e05a18842` | dirty; preserve |
| historical / codex-smart-telemetry | `benchmark/privacy-aggregate-telemetry` | `61905469ca83710b0d19b7275025fdbb6eb5d878` | clean; preserve |
| historical / codex-smart-adaptive-accepted-check | `(detached or missing)` | `76d6d9018be98a44a3f51a51d4ef1d24d2b20c87` | clean; preserve |
| historical / codex-smart-adaptive-live-4edd184 | `(detached or missing)` | `4edd184e1e7796e763ef327f16adb76872b4b618` | clean; preserve |
| historical / codex-smart-adaptive-smoke-main | `(detached or missing)` | `0c846addbb313524910ec9891482f0eddbfd2f3e` | clean; preserve |
| historical / codex-smart-full-campaign-main | `(detached or missing)` | `08d255788562b03d0682ca92ee6141f26c5a1618` | clean; preserve |
| historical / codex-smart-main-smoke-plan | `(detached or missing)` | `0a47c428ef68435548e3ed7515a61c81b7bd7e61` | clean; preserve |
| historical / codex-smart-main-smoke-v4 | `(detached or missing)` | `c047af5e59b0ef29e3d64dc75a09f2b0a60098f7` | clean; preserve |

Physical paths and detailed status records are in the private JSON inventory. The
opened checkout is `/home/user/Documents/Projects/codex-smart`; historical root is
`/home/user/src/codex-smart`; this task is
`/tmp/codex-smart-infrastructure-audit-20261014`. Temporary task aliases in these
tables refer to registered absolute paths, not permission to delete their directories.
The historical primary's three known changes are the representative campaign
contract, isolation script and isolation regression tests. Dirty grading worktrees
and locally advanced `benchmark/agent-execution-isolation-gate`,
`benchmark/upstream-toolchain-pin`, `tmp/keyring-review-accidental` require manual
unique-change review even where earlier PRs of similar names were merged.

## Documentation consistency and focused corrections

Reviewed README, AGENTS, CONTRIBUTING, generated ROADMAP/index, workflow, architecture,
routing, benchmarking/host, workflow-intelligence, stage registries/contracts and
applicable ADRs against current code and public acceptance. The production CLI's
`launch` still prepares a `LaunchPlan` and forwards original OS arguments; it does
not invoke Router v2, playbooks or the adaptive controller. Pure policy and separate
benchmark runners are implemented and tested; that is not production activation.

| Finding | Correction / disposition |
| --- | --- |
| README still broadly called Router v2 future work despite accepted pure policy | Clarify implemented/tested policy and deferred production integration; passthrough unchanged. |
| Architecture/workflow-intelligence/adaptive contract still treated accepted profile mapping as the next blocker | Record accepted #82 and offline-tested #83; full adaptive campaign unexecuted, separately authorized. |
| Adaptive current-state text implied production native-first/adaptive execution | Explicitly distinguish CLI passthrough from benchmark instruction variants/pure policy. |
| Playbooks stage implied all adaptive policy was future | Clarify accepted pure adaptive contract and outstanding production activation. |
| Benchmark/host sections contradicted their own accepted baseline with “both plans unexecuted”, “readiness false”, “#14 open” and “#15 begins later” | Correct current readiness, accepted #72 baseline/#73 aggregates and separate historical blocked entry; preserve historical diagnostics and execution gates. |
| No repeatable cross-checkout/declared snapshot audit | Extend existing workflow commands with read-only bounded inventory and recovery instructions. |
| Milestone descriptions and issue creation context stale | Record owner-approved proposed changes above; no remote metadata mutation. |
| Dated candidate evidence and diagnostics differ from current acceptance | Preserve as history; do not rewrite or discard. |
| Active stage / roadmap / stage ownership | Adaptive remains active; no artificial progress upgrade. |

The existing offline documentation checker checks owned documents, local links,
contracts and generated views. No new external link checker/network was added;
external URLs beyond queried GitHub records were not exhaustively crawled. A passing
structural checker cannot prove semantic consistency or remote link availability.

## Source divergence prevention and small refactoring

`scripts/repository_consistency.py`, reached through existing `scripts/workflow.py`
and `just consistency-audit`, inventories declared repositories/worktrees and verifies
source receipts through PR #84's exact-permission/hash verifier. Optional explicit
GitHub main observations use `ls-remote` only. Offline output keeps remote freshness
unknown; PR/branch catalogs remain caller-supplied. Missing identities, unsafe paths,
unknown Git objects, failed observations and concurrent changes report incomplete
scope rather than silently passing. Historical pins and current references differ.
No implicit SSH, fetching, mutation, repair, synchronization or cleanup is performed.
JSON is suitable for private machine-readable inventories; the concise report omits
private changed-file content. Empty declared snapshot scope proves no deployment.

Small refactor: share `repository_workflow.checkout_state` between existing status
and the new audit, preserving existing JSON fields and Git security options. It
eliminates duplicate branch/HEAD/dirty inspection without introducing a deployment
framework, database, service or production behavior change. Two observations include
changed-file lstat metadata, addressing the reproduced case where editing an already
dirty file left the same porcelain status but invalidated the inventory. Metadata
checks remain observational, not an atomic lock against a racing writer.

Recovery: retain all conflicting source/evidence, stop dependent operations, verify
GitHub and host-side receipts independently, record missing facts, then start a new
task or approved new snapshot at a new path. An interrupted audit can be rerun
read-only; incomplete redirected JSON is not verification evidence. Never rerun a
started model execution, rewrite old manifests or repair unknown source in place.

## Verification and residual limitations

Focused regression coverage uses fake Git repositories and real disposable filesystem
operations: dirty/diverged worktrees, accepted squash-tree proof, stale-clone proof
without fetch, missing main/remote objects, inconsistent receipts, expected historical
pins, outdated current references, source acceptance mismatch, unsafe paths/symlinks,
duplicate/non-finite JSON, missing SSH verification, missing registrations, partial
and interrupted observations, repeated dirty edits, GitHub changes/unavailability,
and repeated read-only runs preserving file bytes/modes/mtime and Git metadata.
All source checks are offline; none invoke a model, real SSH or live campaign.

| Command | Observed exit / result |
| --- | --- |
| `python3 -B -m unittest discover -s scripts -p 'test_repository_*.py'` | `0`; 44 passed (16 new consistency tests, 28 existing workflow tests) |
| `just docs-check` | `0`; ownership, contracts, local links and generated views passed |
| `CARGO_NET_OFFLINE=true just check` | `0`; 250 Python tests in 107.138 seconds, 162 Rust tests; fmt, Clippy with warnings denied and build passed |
| `CARGO_NET_OFFLINE=true just nextest` | `0`; 162 passed, 0 skipped |
| `just security` | `1`; dependency provenance passed (30 registry packages), advisory cache lock refused on a read-only path |
| `cargo deny --locked --config /tmp/codex-smart-workflow-security-20261014/deny.toml fetch db` | `0`; explicit public advisory refresh into writable temporary cache |
| `cargo deny --frozen --config /tmp/codex-smart-workflow-security-20261014/deny.toml check -D warnings` | `0`; advisories, bans, licenses and sources passed; config differs from repository policy **only** by advisory `db-path` |
| `git diff --check` | `0`; inspected tracked diffs and new files |
| Read-only declared real infrastructure JSON audit | `2`; missing source references and Git objects retained as unknown |

Exact proposed commit and GitHub CI/Security results are recorded in the draft PR's
verification block. The real multi-repository audit exits `2`
(incomplete), correctly retaining unknown source receipts, srv0 identity and missing
historical-clone objects rather than asserting consistent deployments. This is an
infrastructure observation, not a unit-test failure. Worktree reads are not atomic;
process namespace and filesystem permissions limit visibility. Host-side installation
and runtime checks remain outstanding, as do independent review and owner decisions.

## Prioritized remediation backlog

**Critical before dependent execution:** obtain a new reviewed ThinkPad/srv0
deployment register with installed paths, accepted source SHAs, independent receipt
SHA256, runtime/adapter inventory and qualification; reconcile ambiguous historical
runtime pointers without modifying them. Restore tracking of #46's unperformed
comparative acceptance. Complete independent PR #85 hardening before operations.

**Important:** owner decide/enforce independent review protection; clarify milestone
#2/#6/#7 policy scope and mismatched #4/#9 counters; scope benchmark milestone #3;
add explicit production integration/dependency issue and umbrella #16/#17 links;
review possibly superseded PR #63 and dependency PR #23/#24. Preserve unique/dirty
branches until their owners review the exact changes.

**Optional after acceptance:** use the private inventory for periodic explicit audits;
review a small cleanup list backed by exact PR/content/evidence checks and owner
approval. Retain source SHA/receipts independent of branch lifetime. No background
synchronization, issue mass-edit or branch pruning is needed to start the next task.
