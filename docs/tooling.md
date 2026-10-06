# Tooling and capability trust

Native first for exact files, git, tests, build/lint/format. CodeGraph for architectural relationships; Serena for semantic symbols; Context7 for version-specific external docs; GitHub for remote state. Do not repeat equivalent retrieval without missing evidence.

2026-10-06: rustc/cargo 1.98.0, rustfmt 1.9.0, clippy 0.1.98; stable x86_64 Linux. Installed rust-src, rust-docs, rust-analyzer, Linux and Windows GNU standard libraries. cargo-nextest 0.9.146, cargo-deny 0.20.2, cargo-audit 0.22.2, cargo-llvm-cov 0.9.1, cargo-semver-checks 0.50.0; cargo add/remove available (no independent cargo-edit version verified). just 1.58.0, gh 2.102.0, git 2.56.0, Codex CLI 0.160.0, Serena 1.7.0, uv 0.12.22. mise/task absent. Other cargo commands: bloat, flamegraph, machete, miri, mutants; versions/operability not yet verified.

GitHub account/repository access checked without retaining auth output. Context7 tools are exposed in the authoring session; that does not prove installation/readiness in a launched Codex session.

`code-graph-smart` is a shell wrapper with `npx -y -p @sdsrs/code-graph` fallback; direct `code-graph-mcp` absent. Initial help invocation attempted network/cache writes and failed on read-only npm cache. This is recorded as a legacy wrapper risk, not a supported offline capability. Runtime doctor/explain do not invoke it. No packages were installed.

Versions above are an engineering observation, not runtime pins or compatibility guarantees. Pinning and handshake matrix are tracked separately. Official Codex contract sources: https://developers.openai.com/codex/cli/reference/ and https://developers.openai.com/codex/config-reference/ . Installed CLI help confirms argument-array `--config` overrides. Avoid legacy profile assumptions: installed 0.160.0 describes layered profile files.

Config slice: toml_edit =0.25.15 (parse/display only), rustix =1.1.5 (fs/process; Linux). Cargo.lock pins transitive crates with registry checksums. One missing crate, toml_writer 1.1.2+spec-1.1.0, was fetched from static.crates.io and SHA-256 matched to Cargo.lock in an isolated /tmp Cargo cache. No tool/global config/auth installation occurred. yq 4.54.1 is installed and validates workflow/template/Dependabot YAML syntax locally. Public RustSec advisories were explicitly refreshed for cargo-deny; duplicate cargo-audit scanning is unnecessary for this gate.


## Current runtime evidence and pins

Issue #7 adds [the explicit compatibility/evidence contract](tool-compatibility.md).
Availability, declared version, reference compatibility and readiness are separate typed
states. All discovered runtime versions remain unknown without attestation; no arbitrary
wrapper is executed to turn a declaration into a health claim. The only owned executable
pin is Codex, supplied explicitly with --tool-lock. No Serena/CodeGraph/Context7 runtime
version is imposed. The CodeGraph wrapper is unsupported and never run by diagnostics.

The SHA dependency is now exactly pinned sha2 =0.11.0, default features disabled, alongside
toml_edit/rustix. Cargo.lock contains 30 checksum-backed registry packages. The provenance
check rejects root patches and unreviewed local lockfile packages as well as direct
path/package/source overrides. No developer tool or LLVM component was installed locally.

Doctor now separates local checks from unprobed runtime readiness; use `doctor --json`
for the schema-1 evidence report. No active probes or installers are invoked. See
[the Doctor contract](doctor.md) for permissions, remote hints and index limits.
