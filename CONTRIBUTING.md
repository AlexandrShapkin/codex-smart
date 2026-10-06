# Contributing

## Workflow

Start on clean, synchronized `main` with `just context [STAGE]` and `just issues`. Read the owning stage contract, relevant ADRs and [workflow](docs/workflow.md) before editing. Keep changes within one acceptance slice and preserve the thin launcher and safety contracts.

Use `feat/<scope>`, `fix/<scope>`, `docs/<scope>` or `chore/<scope>` branches and small Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`). Inspect all diffs, including new files. Push, merge, release and publish only with authorization; never auto-merge by default.

## Issue governance

Every actionable issue has exactly one `area:*`, exactly one `severity:*`, at most one `stage:*` and exactly one meaningful work-kind: `bug`, `enhancement`, `type:investigation` or another explicitly defined `type:*`.

| Dimension | Meaning |
| --- | --- |
| `area:*` | Primary technical/product scope |
| `severity:*` | Priority / impact |
| `stage:*` | Current roadmap owner |
| Work-kind | Nature of the work |
| Milestone | Release grouping |

Choose one primary area rather than assigning multiple areas. Stage ownership is mutable: when residual acceptance transfers, replace the stage label instead of adding another. Milestones remain independent and are not replaced by stage labels. Keep severity out of issue titles; do not reuse bare `P0`–`P3` or flat area labels.

`severity:P0` blocks the foundation/dependent stage activation; `P1` is current-stage critical work; `P2` is important planned work with bounded deferral; `P3` is later hardening/release work, not a current-stage blocker. `type:investigation` means bounded evidence gathering before a change decision. Define any additional type explicitly before use.

Forms collect proposed area/severity/stage and pre-label only an unambiguous work-kind. Maintainers apply the actual labels during triage; form answers do not synchronize labels automatically. Issues need scope, non-goals, acceptance, validation, dependencies and known risks before implementation.

## Validation and documentation

Keep core logic pure where practical. Add focused regression tests for behavior changes and fixes; use fake executables and isolated directories for integrations, without requiring host MCP installations. For documentation-only work, validate links, ownership and templates instead of adding product tests.

Run `just check` before a commit; CI runs the same gate. Run `just nextest` when available and `just security-fetch` then `just deny` when dependency/security validation applies. The advisory refresh is an explicit network action. See [development](docs/development.md) for prerequisites.

Update documentation at its canonical owner in `docs/documents.json`; update stage contracts/registries when scope or recorded evidence changes. Run `just docs-generate` for generated views and `just docs-check` for ownership and links. Never hand-edit ROADMAP.md or docs/index.md. Update changelog/version at logical release boundaries, not for routine internal commits.

## PRs and closeout

Use the PR template to connect the problem, scope, approach and validation to the owning issue/stage. Report safety/compatibility effects, risks, known limits and follow-ups. CI `check` and Security `review` must pass on the exact final SHA before owner acceptance; do not present a local pass as remote evidence.

Close an issue only when its acceptance is satisfied and linked PR/commit/check evidence is recorded. Partial delivery needs explicit residual acceptance and an owning follow-up; stage transfers replace ownership labels. After authorized merge, return to clean `main` before the next slice.

## Security and privacy

Never expose credentials, auth material, private prompts or private source in issues, logs or diagnostics. Treat project config and PATH as untrusted; preserve offline/read-only diagnostics and OS argument launches. Introduce no hidden installs, network actions, indexing or Codex config/auth/MCP/plugin mutation. Keep any necessary setup or mutation explicit and reviewable. Follow [SECURITY.md](SECURITY.md) for sensitive reports.

## Contribution licensing

Unless explicitly stated otherwise, contributions intentionally submitted to
codex-smart are accepted under the [Apache License 2.0](LICENSE), the same license
as the project. Contributors retain copyright in their own contributions while
licensing them to the project and its users under Apache-2.0.
