# codex-smart

A thin Rust launcher and capability/policy layer for Codex CLI. Minimize cost subject to correctness, verification, security and requirement coverage. Codex remains the development agent.

Version: **0.1.0, unreleased**. See [ROADMAP](ROADMAP.md) for implemented and pending slices. No legacy code has been imported.

```sh
cargo build --workspace --locked
cargo run -p codex-smart-cli -- --version
cargo run -p codex-smart-cli -- doctor
cargo run -p codex-smart-cli -- explain --task architecture
cargo run -p codex-smart-cli -- config show
cargo run -p codex-smart-cli -- run --dry-run -- exec "describe this repository"
just check
```

Diagnostics are offline, read-only, and never invoke discovered binaries. Executable discovery is not a health, authentication or MCP handshake assertion. See [configuration](docs/configuration.md), [routing](docs/routing.md), [tooling](docs/tooling.md), [development](docs/development.md), and [provenance](docs/provenance.md).

No automatic installations, downloads, indexing or edits to Codex configuration, authentication, plugins or git metadata occur at runtime.

`codex-smart run -- [codex args...]` launches Codex with unchanged OS arguments. `run --dry-run` only plans; other non-reserved arguments pass through. Use `codex-smart -- doctor` to forward a reserved name to Codex. No profile or reasoning override is injected yet.

Separate marked codex-smart TOML configuration and explicit dry-run/apply/rollback are implemented. `explain` and `doctor` resolve/validate it without mutation; `run` continues exact Codex passthrough. See [configuration contract](docs/configuration.md). Security: `just security-fetch` then `just security`; these checks access the network only during the explicit public advisory refresh.
