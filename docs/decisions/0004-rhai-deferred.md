# ADR-0004: Defer Rhai until reference policy is validated

Status: deferred decision, not sandbox implementation. The current policy has seven typed task hints and no demonstrated need for scripts. Keep Rust first. Issue #13 will evaluate configurable rules after P0 and Router v2; integration requires bounded deterministic execution, typed inputs, no filesystem/network/shell and enforced safety fallback. No Rhai dependency or plugin framework is added now.
