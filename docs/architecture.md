# Architecture

Two crates: `codex-smart-core` holds typed capability inventory, policy, config, migration and process planning; `codex-smart-cli` holds argument parsing and output. No second agent, custom MCP, vector database or local model.

Level A prepares capabilities, risk, reasoning and auditable fallback. Level B is one Codex session deciding implementation and verification. Explicit task hints precede costly discovery. Pure decisions accept an inventory; host adapters never leak into unit tests.

Read-only commands inspect PATH metadata and bounded own configuration files only. Presence is distinguished from readiness. MCP, index health and auth are unknown until a future explicitly controlled compatibility probe can validate them without mutation. Runtime version strings are not obtained by launching arbitrary wrappers.

The process layer resolves an absolute executable path, records file metadata, rechecks it before execution and uses `Command` without a shell. Unix replaces the launcher with Codex so terminal/signals/exit code are preserved. Argument bytes, including non-UTF8, are passed unchanged. Read-only dry-run omits argument values. This is passthrough execution: preview policy is not enforced against unverified MCP integrations.

PATH lookup is bounded to 64 absolute directories and 16 KiB of PATH. Relative/repository paths and group/world-writable entries are rejected. Ownership, ancestor-directory trust and race-free descriptor execution are not yet guaranteed; the metadata recheck narrows but does not eliminate TOCTOU. Linux is the initial supported execution platform; non-Unix discovery fails closed pending platform adapters.

Own configuration resolution is deterministic and read-only; transactional changes are a separate explicit config command. See ADR-0005 and configuration.md for crash recovery, filesystem invariants and concurrency limits. Preview policy still does not activate MCP or inject launch settings.
