# Development

Prerequisites: Rust 1.98 with rustfmt/clippy, Python 3.11+ and just 1.58.0. just is the stable command surface; run `just context` before a batch and `just check` after it. See [workflow](workflow.md) and the [index](index.md). The first slice used std only; config adds exactly pinned toml_edit/rustix and executable pins add sha2. Run `cargo fetch --locked` explicitly to prepare a clean developer cache.

`just check` matches CI: offline docs-check, Python regressions, fmt, clippy with warnings denied, workspace tests and build using the lockfile. Optional installed nextest/llvm-cov add runner isolation and coverage. `just security-fetch` explicitly refreshes the public advisory database; `just security` checks reviewed direct dependency pins, registry checksums and cargo-deny advisories/licenses/bans/sources. CI uses the same security commands and installs pinned cargo-deny 0.20.2 on its runner. No additional tool was installed locally. `just coverage` refuses missing LLVM prerequisites without installing components.

Git/GitHub access was revalidated on 2026-10-06: local metadata is writable, origin HEAD resolves and authenticated issue access succeeds. Use focused working branches and record pushed commit/CI evidence in PRs. Historical read-only blockers remain in dated diagnostics only. Required PR checks: CI `check` and Security `review`.

In this sandbox, one missing build crate (toml_writer 1.1.2) was checksum-verified into `/tmp/codex-smart-cargo`; local checks use `CARGO_HOME=/tmp/codex-smart-cargo just check` and the corresponding security/nextest commands. This is a session-specific workaround, not a repository config requirement or runtime cache. Global Cargo/auth stores were not copied or modified.


Requested command aliases: `just docs-sync` runs the existing deterministic docs-generate;
`just deny` runs the existing security gate. `just status` explicitly reads local git
state. They add no new workflow or automatic online action. The offline check/context
implementation from PR #19 is preserved.

## Main protection policy

Normal changes should reach `main` through reviewed/validated PRs. The owner has
authorized the following conservative policy. Repository settings own live
enforcement state; verify it with `gh api repos/AlexandrShapkin/codex-smart/branches/main/protection`.
CI `check` and Security `review` are existing GitHub Actions checks.

| Setting | Policy |
| --- | --- |
| Branch | Exactly `main` |
| Require PR | Enabled |
| Required approving reviews | 0; owner reviews acceptance, without requiring an unavailable second maintainer |
| Dismiss stale approvals | Enabled |
| Code-owner / last-push approval requirements | Disabled |
| Required status checks | `check`, `review`, from GitHub Actions (app ID 15368) |
| Require branch up to date | Enabled |
| Allow force pushes / deletion | Disabled / disabled |
| Enforce on administrators | Disabled; explicit owner emergency recovery remains possible |
| Linear history, signed commits, merge queue, branch lock | Not required |
| Push restrictions | None beyond the PR/check requirements |

Keep all currently accepted merge methods and leave auto-merge disabled. Owner
emergency bypasses should be followed by documented validation and a review of
the deviation. This public
repository is eligible under [GitHub's documented branch protection plan support](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
