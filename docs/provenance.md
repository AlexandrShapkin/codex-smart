# Provenance gate

No codex-toolkit baseline archive is present in this repository or the checked project artifact filenames. No legacy code is imported.

The user reports that the studied archive directory and VERSION both identify **1.4.0**, whereas the supplied brief refers to **1.4.1**. The latter is unverified. Do not relabel 1.4.0 as 1.4.1. Source inspection and archive checksums remain pending until the actual artifacts are supplied. This does not block new Rust development.

Preserved input: `codex-smart-project-brief.md`, SHA-256 `eb73025973d0da73c2d2d29e3d89b1b0e84546dd9d2b13fbdfe5eeb29bbf1317`. Its historical claims and benchmark numbers are supplied claims, not independently verified measurements. The brief is retained unchanged.

Future archives go in an isolated provenance store, with checksum manifest, source version evidence and license review; never in new core modules. No known old defect is claimed reproduced without a baseline; tests instead cover the reported failure contracts (read-only explain, no hidden installs, no shell injection, capability honesty).

## Issue #104: accepted exact TOML dependency update (2026-10-15)

The reviewed `toml_edit =0.25.17` update was accepted through merged
[PR #108](https://github.com/AlexandrShapkin/codex-smart/pull/108) at
`c47c61880c2f791241134c0b5c5283553f757f15`.
[Issue #104](https://github.com/AlexandrShapkin/codex-smart/issues/104) is completed;
bot PR #97 was closed without merge. The following records the investigation and
validation preceding acceptance, not a pending dependency proposal.

The investigation base on accepted main was independently observed through native
GitHub API, native HTTPS
`git ls-remote`, and governed task-start:
`9f5a9a359c03e58fd1980cffefb2191ff34a2abc`. Investigation used the separate
`chore/issue-104-toml-review-20261015` worktree. Legacy Dependabot
[#97](https://github.com/AlexandrShapkin/codex-smart/pull/97), head
`1610127bc34a721006c970ddf0f3e82d1a70ef12`, supplied a proposal, not approval.

Official `https://index.crates.io/to/ml/<crate>` records and independently downloaded
`https://static.crates.io/crates/<crate>/<crate>-<version>.crate` archives agree with
these lock checksums (all versions include `+spec-1.1.0`, none is yanked):

| Crate | Version | Archive SHA-256 |
| --- | --- | --- |
| toml_edit | 0.25.17 | e3641d5bbb5349a79e1020a242d251efbc546ad8048d133958323ce9c40a9c9c |
| toml_datetime | 1.1.2 | 2b86d767906c6c42421dcba507eb9d203e779497710a47782a224bb871653053 |
| toml_parser | 1.1.5 | baa693a8032d7e1cada7d0041e96126df243179ff061456783ac7f12bda4744c |
| toml_writer | 1.1.3 | 06bdbd8cfc056b8d2e2e85f29b56a3bdbecb527cef81eb39e3e7b98af4652770 |

Every packaged `src/` file and both license texts match Git blob hashes from the
independent official upstream recursive trees: 39/6/17/8 files respectively.
Edit/parser publication commit is
[ceac6e4412420d5a5c19e4f7293ad005cf1a31b2](https://github.com/toml-rs/toml/tree/ceac6e4412420d5a5c19e4f7293ad005cf1a31b2);
datetime/writer publication commit is
[f72038c2508112dfaaedb227a511f91bf9b2015c](https://github.com/toml-rs/toml/tree/f72038c2508112dfaaedb227a511f91bf9b2015c).
Cargo packages dereference upstream license symlinks to the matching root license
texts. All four declare MIT OR Apache-2.0, Rust 1.85 and no build script. The project
uses Rust 1.98. No other lock package is changed by this candidate.

The [official release comparison](https://github.com/toml-rs/toml/compare/v0.25.15...v0.25.17)
changes parser token allocation estimation, bounding capacity by addressable size,
and removes unchecked comment/newline span access from the public event receiver.
Whitespace decoding was a no-op and is removed. No Rust source changes occur in
edit/datetime/writer. The key-encoding fix in that comparison concerns the separate
`toml` crate, not an added dependency here. This source review is not an exhaustive
security audit or a substitute for the required advisory gate.

The direct dependency remains exact, default-features=false, parse/display only.
Parse selects parser/winnow; display selects writer; datetime and indexmap remain
required. Parser/writer/datetime use their existing std/alloc defaults. Serde/debug,
unbounded parsing, parser unsafe and SIMD features are not requested. Optional
serde_core's presence in the lock is not evidence of activation. Strict approved
project-wide direct pins, source restrictions, option rejection and checksum checks
remain enforced; libc, rustix, sha2 and internal pins are unchanged.

Affected paths are bounded config DocumentMut parsing (64 KiB), explicit migration
with decorated key replacement and output revalidation, read-only doctor parsing,
tool-lock parsing, and reasoning argument Value parsing. Tests cover comment and
opaque-field preservation, idempotent migration, Unicode/quoted keys, datetime
roundtrip, malformed syntax/duplicate keys and generated key encoding. Existing
transaction tests remain the write/rollback safety gate. No benchmark scripts,
frozen manifests, source/evidence pins or deployed bytes are changed; historical
pins identify their original source, not this candidate. ADR-0005 records the
original accepted pin; PR #108 records acceptance of this reviewed update.

The initial offline cache blocker was resolved by the owner's explicit authorization
of `cargo fetch --locked` on resumption. Installed Rust/Cargo 1.98 performed that
fetch and downloaded only the four reviewed packages. Cached archive checksums
and all 70 source/license blobs were reverified against this record and official
upstream trees. The resolved feature tree confirms parse/display and the existing
std/alloc transitive closure, with no additional optional TOML features.

Four focused Rust tests and four isolated dependency-policy Python tests pass.
Standard `just security` passes advisories, licenses, bans and sources with the
explicitly refreshed advisory cache. `CARGO_NET_OFFLINE=true just check` passes
297 Python tests, formatting, workspace clippy/tests/build and documentation gates.
`CARGO_NET_OFFLINE=true just nextest` passes all 207 tests with none skipped.
`just docs-check` and `git diff --check` pass. Existing private Unix socket/process
tests ran through supported host approval without changing permissions or assertions.
At the end of that investigation, independent ChatGPT/owner acceptance and exact-head
CI/check and Security/review app 15368 were still required. Those were review gates
before acceptance, not current open conditions. The accepted owner update in #108
superseded #97's dependency proposal; #104 is completed and #97 closed without merge.
