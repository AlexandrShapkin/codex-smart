# ADR-0006: Repository-owned bounded stage context

Status: accepted for the developer workflow.

Keep the Rust launcher thin. Use Python stdlib tooling behind stable `just` recipes
for offline stages/docs, with explicit JSON registries and Markdown stage contracts.
Separate read-only check/context from deterministic generation and explicit gh reads.
Do not execute commands supplied in registries or synchronize live issue closure into
generated views. Owners update durable contracts; historical evidence stays historical.

Generated ROADMAP.md and docs/index.md must compare byte-for-byte in local/CI checks.
An 8192-byte context response gives contract text and targeted paths, then requires
deeper reads when evidence exceeds the budget. This is developer tooling, not an
agent framework or runtime context engine. No dependencies, network or installs are
needed for these three offline actions.
