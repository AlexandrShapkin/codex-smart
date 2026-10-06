# Development

Prerequisites: Rust 1.98 with rustfmt/clippy, Python 3.11+ and just 1.58.0. just is the stable command surface; run `just context` before a batch and `just check` after it. See [workflow](workflow.md) and the [index](index.md). The first slice used std only; config adds exactly pinned toml_edit/rustix and executable pins add sha2. Run `cargo fetch --locked` explicitly to prepare a clean developer cache.

`just check` matches CI: offline docs-check, Python regressions, fmt, clippy with warnings denied, workspace tests and build using the lockfile. Optional installed nextest/llvm-cov add runner isolation and coverage. `just security-fetch` explicitly refreshes the public advisory database; `just security` checks reviewed direct dependency pins, registry checksums and cargo-deny advisories/licenses/bans/sources. CI uses the same security commands and installs pinned cargo-deny 0.20.2 on its runner. No additional tool was installed locally. `just coverage` refuses missing LLVM prerequisites without installing components.

Git/GitHub access was revalidated on 2026-10-06: local metadata is writable, origin HEAD resolves and authenticated issue access succeeds. Use focused working branches and record pushed commit/CI evidence in PRs. Historical read-only blockers remain in dated diagnostics only. Required PR checks: CI `check` and Security `review`.

In this sandbox, one missing build crate (toml_writer 1.1.2) was checksum-verified into `/tmp/codex-smart-cargo`; local checks use `CARGO_HOME=/tmp/codex-smart-cargo just check` and the corresponding security/nextest commands. This is a session-specific workaround, not a repository config requirement or runtime cache. Global Cargo/auth stores were not copied or modified.


Requested command aliases: `just docs-sync` runs the existing deterministic docs-generate;
`just deny` runs the existing security gate. `just status` explicitly reads local git
state. They add no new workflow or automatic online action. The offline check/context
implementation from PR #19 is preserved.
