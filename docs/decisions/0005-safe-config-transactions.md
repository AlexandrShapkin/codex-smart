# ADR-0005: Marked TOML and descriptor-based config transactions

Status: accepted for Linux Foundation.

Typed config uses a separate codex-smart namespace and explicit kind/schema markers. Use pinned toml_edit 0.25.15 with only parse/display features instead of a handwritten TOML parser, preserving opaque fields/comments. Use pinned rustix 1.1.5 fs/process APIs to hold directory descriptors, reject symlinks through openat2, verify ownership and use safe relative filesystem operations while workspace unsafe code remains forbidden. These are two focused dependencies, not a plugin framework.

Dry-run is the default; mutations require --apply. Transaction artifacts are private and exclusively created. Backups and receipts are durable before atomic rename; rollback compares source, backup and receipt, and can clean up recognized interrupted states. No global Codex patching or auth migration. Locking is advisory; noncooperating same-user edit races are an explicit limit. Exact byte rollback is preferable to reparsing a backup.

An actual codex-toolkit migration cannot be specified from an absent archive. This schema-0 reference transition establishes tested safety primitives without pretending to import legacy code. Direct dependencies and registry checksums are reviewed; cargo-deny adds advisory/license/source/bans gates. Dependency downloads occur only as explicit developer build preparation, never in runtime diagnostics or launch.
