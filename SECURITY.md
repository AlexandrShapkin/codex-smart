# Security

Do not put credentials, private prompts or source code in issues, diagnostics or telemetry. Report sensitive vulnerabilities privately through GitHub private vulnerability reporting if enabled, otherwise request a private contact before disclosure.

Project configuration and PATH are untrusted inputs. Diagnostics never execute tools; execution uses argument arrays without a shell. Current pre-1.0 builds have no production support guarantee. Migration must not touch Codex auth/MCP/plugins or bypass symlink and concurrent-edit checks. See the roadmap for security work not yet delivered.
