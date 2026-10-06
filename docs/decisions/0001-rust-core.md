# ADR-0001: Rust core and CLI

Status: accepted. Use a two-crate Rust workspace with no third-party dependency for the initial read-only slice. Typed pure policy and safe subprocess APIs reduce injection risk. Split further only at stable responsibility boundaries. Rhai is deferred until reference policy and actual configurable-rule needs exist.
