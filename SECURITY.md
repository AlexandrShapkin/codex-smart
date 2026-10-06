# Security

## Reporting

Never put secrets, credentials, authentication material, private prompts or private source code in public issues, diagnostics or telemetry. Sensitive reports include unintended execution, unsafe config writes, auth/private-data exposure and bypasses of the read-only or trust boundaries.

Prefer GitHub private vulnerability reporting through the repository's Security tab when available. It is currently disabled. Until a private channel is available, request a private reporting channel without disclosing exploit details or sensitive material in public. No personal contact address is published here.

Provide a minimal isolated reproduction where possible, expected versus observed behavior, affected version/commit and impact. Use fake tools/data rather than real credentials. Documented known limitations are not automatically vulnerabilities; a regression or bypass of an established contract warrants investigation.

## Support and boundaries

The project is pre-1.0; current builds have no production support guarantee. Report regressions against current `main`; no supported release series is established yet.

Project configuration and PATH are untrusted inputs. Diagnostics never execute tools; execution uses argument arrays without a shell. Migration must not touch Codex auth/MCP/plugins or bypass symlink and concurrent-edit checks. See the [roadmap](ROADMAP.md) for security work not yet delivered and [configuration](docs/configuration.md) for transaction boundaries.
