# ADR-0002: Thin launcher and conservative discovery

Status: accepted. Codex remains the sole implementation agent. Discovery reads executable metadata but never runs arbitrary PATH programs. This prevents diagnostics invoking installers or writing caches, at the cost of reporting version/health/auth unknown. Launch is explicit and uses OS argument arrays. Presence alone must never assert MCP readiness.
