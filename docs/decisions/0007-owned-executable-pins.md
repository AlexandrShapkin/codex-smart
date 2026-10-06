# ADR-0007: Explicit Codex artifact pins and honest offline evidence

Status: accepted for Foundation; deeper readiness remains #4.

Keep pins restricted to the one external executable the launcher owns: Codex. Use an
explicit marked schema-1 TOML file with strict release version and SHA-256 declaration;
never infer pins from discovered names or silently impose versions on user-managed MCP.
Separate discovery, declarations, reference contracts, artifact verification and readiness.
No offline declaration/digest match authenticates a runtime version or MCP handshake.

Hash through a held Linux openat2 descriptor with bounded reads and before/after metadata.
Use exactly pinned sha2 0.11.0 with default features disabled instead of handwritten
cryptography or a subprocess. The reviewed lock records 30 registry packages/checksums;
source/feature/advisory/license gates apply. Root patches and unreviewed local lock packages
must fail provenance review, as must direct path/package/source overrides.

Capabilities/explain defer hashing; doctor hashes only on explicit --tool-lock. Explicit
run checks the selected artifact without altering OS argv or user Codex configuration.
The final pathname execution race remains a documented hardening limit, not a solved
property. This is a data contract, not a plugin framework or automatic installer.
