# Repository engineering contract

Before edits, inspect repository/worktree state and verify GitHub main; start substantial tasks in a new pinned branch/worktree via [docs/workflow.md](docs/workflow.md). Preserve unrelated local work and deployments. Inside the task start with `just context [STAGE]`, then read ROADMAP.md and the relevant contract/ADRs before nontrivial edits. Use the generated [documentation index](docs/index.md); keep ownership and generated views checked with `just docs-check`. GitHub Issues own live actionable state (`just issues`). Keep codex-smart a thin launcher; Codex owns implementation decisions and verification. Core is Rust, with no plugin framework or Rhai before a demonstrated need.

Use native rg/git/targeted reads for local work; code-graph-smart only for useful architectural context after checking its wrapper does not install packages. Use semantic tools for symbols and Context7 for version-specific external APIs. Do not duplicate equivalent retrieval.

Read-only doctor/explain must never execute discovered tools, index, alter git metadata or touch Codex config/auth/MCP/plugins. Project config and PATH are untrusted. Execute explicit launches through OS arguments, never a shell. Unknown capability health must stay unknown.

Add behavior and regression tests using isolated fake environments. Run `just check`, inspect all diffs including new files, update docs/issues/roadmap. Use small Conventional Commits when git metadata is writable. Do not bypass read-only mounts. Follow [scoped engineering authority](docs/workflow.md#review-and-merge-authorization): effective standing authority covers ordinary bounded work without repeated personal approvals, while changed heads require fresh independent ACCEPT/checks. Bootstrap requires personal PR/full-head merge consent; exceptions require separate explicit owner authority. Veto/revocation and the PR #125 merge ban remain binding; release/distribution publication is outside standing scope. Never expose credentials or private prompts/source in diagnostics or logs.

## Mandatory cleanup after each task

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

