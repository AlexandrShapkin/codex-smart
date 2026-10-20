<!-- shared-agent:start -->
# Agent engineering contract

## 1. Purpose and authority

Follow [.github/DEVELOPMENT_INTERFACE.md](.github/DEVELOPMENT_INTERFACE.md), the
single shared workflow interface. These instructions do not grant runtime,
merge, deployment, device, credential or destructive-operation authority.
Preserve stricter product rules in section 10; stop dependent work on a conflict
and continue independent authorized work. Never use RDC for development.

## 2. Repository start (START)

Discover the actual root, full HEAD, branch and Git status. Compare the intended
base SHA with current GitHub evidence; record divergence rather than assuming
freshness. Inventory worktrees, unfinished changes and active PRs, including
intersecting files and dependencies, before creating commits. Do not silently
switch checkout, overwrite unknown work or rewrite existing branch history.

## 3. GitHub task (TASK)

Search open and closed Issues; reuse the owning task and avoid duplicates.
Record goal, scope/non-goals, acceptance, dependencies and risks. Link Issues
and PRs for cross-repository work to the coordinating Issue. Roadmaps and stage
registries provide navigation, not execution authority or a second live queue.

## 4. Necessary context (CONTEXT)

Read AGENTS.md, the shared interface and the product context entrypoint first.
Read only task-relevant contracts, architecture and source; never load the
whole repository by default. Prefer native git/rg and targeted reads for known
locations; use CodeGraph for useful structural context, semantic tools for
symbol questions and Context7 for version-sensitive external APIs when available.
Do not repeat equivalent retrieval or install tools automatically. An absent
tool is a reported limitation, not permission to download or execute it.

## 5. Planning and implementation (IMPLEMENT)

Work on one bounded task/branch from a verified base or explicitly documented
PR dependency. Preserve product architecture and security invariants. Make
minimal coherent changes; add regression and negative tests for behavior.
Create extra clones/worktrees only for a concrete justified need and within
product authorization. Preserve unrelated files, user data and unique evidence.

## 6. Verification and quality (VERIFY)

Run targeted checks first, then the full mandatory product gates in section 10.
A smoke test cannot replace native validation. Report PASS, FAIL, BLOCKED and
UNVERIFIED distinctly; never disable a failing check to obtain green results.
Keep secrets/private data out of source, diagnostics and public reports. CI is
source evidence, not proof of deployment correctness or runtime authority.

## 7. PR, CI, review and acceptance (PR / REVIEW)

Inspect the complete diff, including new files, before committing. Create or
update a scoped PR linked to its Issue; record base and full HEAD SHA, actual
commands/results, exact-head CI, risks and limits. Repeat affected verification
and refresh CI/review evidence after HEAD changes. Keep author verification,
independent technical ACCEPT, formal GitHub APPROVE and merge authority separate.
Never present your own checks as independent review. Keep PRs Draft pending
required independent acceptance. Do not merge, deploy or change GitHub settings
without explicit task authorization and all applicable product gates.

## 8. Temporary resources (CLEANUP)

At completion, abandonment or supersession, inventory obsolete worktrees,
branches and reproducible artifacts; inventory disk usage before expensive work
when space is low. Delete only exact, verified recoverable and unused items
within authority, after checking tasks/PRs, dirty/untracked files and processes.
Never delete active/protected branches, open or Draft PR work, unknown data,
unique results or user files. No blanket git clean, forced worktree removal or
age-based deletion. Preserve uncertain candidates; record what was removed,
what was retained, why, and measured freed space only when actually measured.

## 9. Final evidence (REPORT)

Report: what changed; repository, PR and full SHA; actual tests and CI; remaining
UNVERIFIED evidence; blockers; owner actions; and temporary resources removed
or preserved. Separate source preparation from installation and live-host proof.

## 10. Product-specific rules
<!-- shared-agent:end -->

<!-- agent-project: codex-smart -->

Context entrypoint: `just context [STAGE]`; workflow: `docs/workflow.md`.
Mandatory native gates: `just docs-check`, `just check`, applicable cached
`just security`, and exact-head CI and Security. Preserve stages, documentation
registry and security gates. PR #125 is prohibited from merge; PR #164 remains
experimental and must not be activated. This PR depends on #170, not #172.

### Repository engineering contract

Before edits, inspect repository/worktree state and verify GitHub main; start substantial tasks in a new pinned branch/worktree via [docs/workflow.md](docs/workflow.md). Preserve unrelated local work and deployments. Inside the task start with `just context [STAGE]`, then read ROADMAP.md and the relevant contract/ADRs before nontrivial edits. Use the generated [documentation index](docs/index.md); keep ownership and generated views checked with `just docs-check`. GitHub Issues own live actionable state (`just issues`). Keep codex-smart a thin launcher; Codex owns implementation decisions and verification. Core is Rust, with no plugin framework or Rhai before a demonstrated need.

Use native rg/git/targeted reads for local work; code-graph-smart only for useful architectural context after checking its wrapper does not install packages. Use semantic tools for symbols and Context7 for version-specific external APIs. Do not duplicate equivalent retrieval.

Read-only doctor/explain must never execute discovered tools, index, alter git metadata or touch Codex config/auth/MCP/plugins. Project config and PATH are untrusted. Execute explicit launches through OS arguments, never a shell. Unknown capability health must stay unknown.

Add behavior and regression tests using isolated fake environments. Run `just check`, inspect all diffs including new files, update docs/issues/roadmap. Use small Conventional Commits when git metadata is writable. Do not bypass read-only mounts. Follow [scoped engineering authority](docs/workflow.md#review-and-merge-authorization): effective standing authority covers ordinary bounded work without repeated personal approvals, while changed heads require fresh independent ACCEPT/checks. Bootstrap requires personal PR/full-head merge consent; exceptions require separate explicit owner authority. Veto/revocation and the PR #125 merge ban remain binding; release/distribution publication is outside standing scope. Never expose credentials or private prompts/source in diagnostics or logs.

#### Mandatory cleanup after each task

Prevent disk exhaustion: on task closeout, abandonment or replacement, promptly
audit and remove **verified obsolete** local worktrees, task branches, generated
build/test outputs and caches. Check disk space and inventory candidate paths
before another expensive task when storage is low. For worktrees and branches,
verify actual Git state, active tasks/PRs, dirty or untracked files, running
processes and recoverability of commits before removing anything. Only delete
known project-owned artifacts that are reproducible and not needed as evidence.
Never delete active/default/protected branches, open or Draft PR branches,
unknown work, checkpoints, user data, reference material or unique test data.
Do not use blanket `git clean -fdx`, forceful worktree removal, guessed
recursive paths or automatic age-based cleanup. Remote branch deletion,
device cleanup and uncertain/destructive operations require separate authority.
Record exact candidates, actions and measured reclaimed space; if any
precondition is unknown, preserve the item and report it for review.

