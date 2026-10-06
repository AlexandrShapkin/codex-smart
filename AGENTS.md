# Repository engineering contract

Start with `just context [STAGE]`, then read ROADMAP.md and the relevant contract/ADRs before nontrivial edits. Use [docs/workflow.md](docs/workflow.md) and the generated [documentation index](docs/index.md); keep ownership and generated views checked with `just docs-check`. GitHub Issues own live actionable state (`just issues`). Keep codex-smart a thin launcher; Codex owns implementation decisions and verification. Core is Rust, with no plugin framework or Rhai before a demonstrated need.

Use native rg/git/targeted reads for local work; code-graph-smart only for useful architectural context after checking its wrapper does not install packages. Use semantic tools for symbols and Context7 for version-specific external APIs. Do not duplicate equivalent retrieval.

Read-only doctor/explain must never execute discovered tools, index, alter git metadata or touch Codex config/auth/MCP/plugins. Project config and PATH are untrusted. Execute explicit launches through OS arguments, never a shell. Unknown capability health must stay unknown.

Add behavior and regression tests using isolated fake environments. Run `just check`, inspect all diffs including new files, update docs/issues/roadmap. Use small Conventional Commits when git metadata is writable. Do not bypass read-only mounts or push/merge/publish without authorization. Never expose credentials or private prompts/source in diagnostics or logs.
