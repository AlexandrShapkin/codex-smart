# Development

Prerequisites: Rust 1.98 with rustfmt/clippy; just is optional (run the commands from `justfile` directly). The first slice used std only; config now adds exactly pinned toml_edit/rustix. Run `cargo fetch --locked` explicitly to prepare a clean developer cache.

`just check` matches CI: fmt, clippy with warnings denied, workspace tests and build using the lockfile. Optional installed nextest/llvm-cov add runner isolation and coverage. `just security-fetch` explicitly refreshes the public advisory database; `just security` checks reviewed direct dependency pins, registry checksums and cargo-deny advisories/licenses/bans/sources. CI uses the same security commands and installs pinned cargo-deny 0.20.2 on its runner. No additional tool was installed locally. `just coverage` refuses missing LLVM prerequisites without installing components.

Git/GitHub access was revalidated on 2026-10-06: local metadata is writable, origin HEAD resolves and authenticated issue access succeeds. Use focused working branches and record pushed commit/CI evidence in PRs. Historical read-only blockers remain in dated diagnostics only. Required PR checks: CI `check` and Security `review`.

In this sandbox, one missing build crate (toml_writer 1.1.2) was checksum-verified into `/tmp/codex-smart-cargo`; local checks use `CARGO_HOME=/tmp/codex-smart-cargo just check` and the corresponding security/nextest commands. This is a session-specific workaround, not a repository config requirement or runtime cache. Global Cargo/auth stores were not copied or modified.
