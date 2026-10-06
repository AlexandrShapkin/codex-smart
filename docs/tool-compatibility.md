# External version and execution compatibility

`available != compatible != ready`. Discovery proves an executable was found through
bounded PATH metadata. It does not identify its runtime version, supported commands,
transport, authentication or index health. No command, handshake or package installer
runs during capability/version diagnostics.

## Evidence model

Availability is discovered, not found, or session integration unknown. Version evidence
separates a strict numeric release declaration from an attested runtime version. The
runtime version remains unknown in this offline slice. A recognized declaration selects
only a reference execution contract; it is not validated runtime compatibility.
Readiness is unknown, unavailable, or blocked by rejected artifacts/unsupported execution.
There is deliberately no offline evidence path to assert ready.

Unknown version numbers have an unknown reference contract. A matching entrypoint digest
still does not identify an interpreter, shim-selected binary or dependencies. The legacy
CodeGraph wrapper is an unsupported execution contract, even when discovered: its known
fallback can invoke unpinned `npx -y`. Presence and hash equality cannot make it ready.

## Supported and reference command/transport matrix

| Capability | Version evidence/reference | Command / transport | Launcher ownership and readiness |
| --- | --- | --- | --- |
| Codex | Observed 0.160.0; exact release source reference | OS argv for interactive CLI or `exec`; inherited terminal/stdin/stdout | Only owned external launch. Optional explicit artifact pin; runtime/auth readiness unverified. No profile or reasoning injection. |
| Rust / Cargo | Local and CI 1.98.0, workspace minimum 1.98 | Developer build/test CLI through just | Build tooling only; runtime discovery never executes it or asserts compatibility. |
| Git / rg / gh | Engineering observations in tooling.md; runtime versions unknown | Developer native CLI; `just issues` explicitly calls gh online | No runtime execution/pins managed by codex-smart. Discovery is metadata only. |
| Serena | Observed 1.7.0; exact release CLI source reference | Reference `start-mcp-server`; stdio default, SSE and streamable HTTP options | No launcher invocation or runtime pin. MCP/auth/project readiness unknown. |
| Direct CodeGraph | Runtime/reference version unknown | CLI/MCP commands and transport not validated | No launcher invocation/pin; do not guess supported commands or enable MCP. |
| Legacy code-graph-smart | Version unknown; inspected shell wrapper | Unpinned npm fallback may download dependencies | Unsupported; never invoked by diagnostics or the launcher. |
| Context7 | Authoring-session integration; launched-session version unknown | Plugin/session transport not probed | No local executable artifact pin, duplicate manual MCP setup or readiness claim. |

Reference evidence: Codex CLI tag rust-v0.160.0 resolves to commit
[a956835d020762cb2b570053af06f643a11c0ecc](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/cli/src/main.rs).
Serena v1.7.0 resolves to
[949a27ef1e5fda1a6e7b561e777bcece345c6ffd](https://github.com/oraios/serena/blob/949a27ef1e5fda1a6e7b561e777bcece345c6ffd/src/serena/cli.py),
whose start-mcp-server definition explicitly lists those transports. These are source
contracts, not evidence that the user's discovered executable matches either release.
The [official Codex command reference](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
documents exec and repeatable configuration overrides; forwarded options remain the
user's responsibility and are never synthesized by this launcher.

## Explicit owned-executable lock

Only a Codex record is accepted because Codex is the only external executable the
launcher invokes. Pins for Serena, CodeGraph, Context7 or native developer tools are
rejected rather than imposing versions on externally managed capabilities.

The user supplies the marked file explicitly; no project/global lock is discovered or
created automatically. Obtain the digest from the reviewed canonical executable artifact
without running it. Example format (replace the digest placeholder before use):

```toml
kind = "codex-smart-tools"
schema_version = 1

[tools.codex]
version = "0.160.0" # declaration, not a runtime attestation
sha256 = "REPLACE_WITH_64_HEX_ARTIFACT_DIGEST"
```

```sh
codex-smart capabilities --tool-lock ./tools.toml
codex-smart explain --tool-lock ./tools.toml --task architecture
codex-smart doctor --tool-lock ./tools.toml
codex-smart run --tool-lock ./tools.toml --dry-run -- exec "task"
codex-smart run --tool-lock ./tools.toml -- exec "task"
```

Capabilities/explain parse the lock and defer hashing to keep preflight cheap. Doctor
with an explicit lock streams the canonical artifact and returns 1 on missing/rejected
artifacts or digest mismatch. Invalid locks return 2 without reflecting their contents.
Doctor's success indicates only that requested checks passed, not runtime readiness.
Default diagnostics do no hashing. This CLI has no JSON output/schema contract yet.

Explicit run verifies a required digest against the exact planned Codex path, including
in dry-run, then rechecks metadata/digest immediately before actual execution. Pin failure
returns E_CODEX_PIN without execution or exposing paths/arguments. Wrapper options are
consumed only before Codex arguments/`--`; after that boundary every OS argument byte,
including non-UTF8 and shell metacharacters, is preserved. Unpinned passthrough remains
available for the original launch contract; it makes no reproducibility claim. Unknown
runtime compatibility does not prohibit a user's explicit passthrough launch.

## Security and bounds

The TOML lock rejects unknown/duplicate fields, unowned tools, unsupported schemas,
non-string or non-release versions, malformed digests and command/path overrides.
Versions are three decimal u32 components without prefixes, leading zeros or suffixes;
SHA-256 is exactly 64 ASCII hex digits. Lock reads use the existing secure config reader:
64 KiB cap, one hard link, current ownership, no symlinks/ancestor symlinks or writable-by-other files.

Artifact hashing uses Linux openat2 without symlink/magic-link traversal, a held descriptor,
nonblocking opens and a regular executable owned by root/current user. Directories,
FIFOs, non-executables and group/world-writable artifacts fail closed. It streams at most
256 MiB per pass using a 16 KiB buffer; oversized artifacts are rejected before reading.
Before/after identity, size, mode and timestamps detect concurrent changes. Discovery
canonicalizes ordinary system symlinks; hashing operates on the resulting path. Executable
hard links are not forbidden: unlike private config, the reviewed digest binds their bytes.

Metadata and digest rechecks narrow TOCTOU; they do not eliminate the last pathname
check/exec race or prove ancestor-directory trust. Descriptor execution and PATH ownership/
ancestor hardening remain #17. No tools are run to obtain versions, no authentication/config/
plugin stores are read by this lock path, and no install/network/cache write occurs at runtime.
