# External capability pins and compatibility

## Scope

Recover the pending tool-lock/version slice. Add explicit owned-Codex artifact pins, offline version declaration reporting and a supported/reference command/transport matrix. Validate entrypoint checksums without arbitrary wrapper execution.

## Non-goals

No automatic version probes, network installs, MCP activation, profile injection or false readiness. A digest cannot authenticate the declared runtime version or script/shim dependencies.

## Acceptance

Rust/CLI versions documented; strict marked version/digest records; incompatible and unknown tools never called ready; explicit launch pin failures prevent execution. Diagnostics preserve files and secrets.

## Validation

just context tools; just docs-sync; just docs-check; just check; just nextest; just deny. Stub valid/invalid/unknown versions, checksum mismatch, unsafe/oversized artifacts, exact argv/status and offline snapshots.

## Context

Read [docs/tooling.md](../../docs/tooling.md), [docs/architecture.md](../../docs/architecture.md), [docs/decisions/0002-thin-launcher.md](../../docs/decisions/0002-thin-launcher.md), [docs/issues/07.md](../../docs/issues/07.md). Start with `just context tools`; follow source entry points only as needed.

## Follow-ups

See [implementation validation](../diagnostics/2026-10-06-tools.md); it is separate from live issue closure. All MCP/auth/index handshakes remain unknown. CodeGraph wrapper can download packages, so no supported wrapper execution is claimed. Complete doctor in the next stage.
