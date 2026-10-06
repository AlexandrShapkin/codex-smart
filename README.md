# codex-smart

[![CI](https://github.com/AlexandrShapkin/codex-smart/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/AlexandrShapkin/codex-smart/actions/workflows/ci.yml)
[![Security](https://github.com/AlexandrShapkin/codex-smart/actions/workflows/security.yml/badge.svg?branch=main)](https://github.com/AlexandrShapkin/codex-smart/actions/workflows/security.yml)

Thin Rust policy and capability layer over Codex CLI with deterministic routing previews, safe diagnostics and verifiable execution. Codex remains the development agent: codex-smart is a launcher, not a second agent.

## Status

**Pre-1.0: 0.1.0, unreleased.** Foundation, workflow, tool pins and offline diagnostics have validated slices. Router v2 is planned; current routing is not yet benchmark-proven. No production support guarantee or published package is claimed. See the [roadmap](ROADMAP.md).

## Why codex-smart

Make launch decisions and capability evidence inspectable while minimizing cost subject to correctness, verification, security and requirement coverage. Keep implementation decisions with Codex and record the limits of the evidence available.

## Core principles

- Thin Rust core with explicit inputs and deterministic policy previews.
- Availability != compatibility != readiness; unknown health stays unknown.
- No hidden installations, downloads or implicit indexing.
- No silent mutation of Codex configuration, authentication, MCP or plugins.

## Quick start

Build from source with Rust 1.98. Prepare Codex CLI separately for actual execution; diagnostics do not require it. Cargo may fetch locked build dependencies during this explicit build.

```sh
cargo build --workspace --locked
cargo run -p codex-smart-cli -- --version
cargo run -p codex-smart-cli -- doctor
cargo run -p codex-smart-cli -- run --dry-run -- exec "describe this repository"
```

## Commands

After building, use `target/debug/codex-smart` or `cargo run -p codex-smart-cli --`:

| Command | Purpose |
| --- | --- |
| `doctor` | Offline capability and configuration diagnostics |
| `explain --task architecture` | Inspect a routing preview without execution |
| `config show` | Inspect separate codex-smart configuration |
| `run --dry-run -- [codex args...]` | Plan an explicit launch |
| `run -- [codex args...]` | Launch Codex with unchanged OS arguments |

Other non-reserved arguments pass through; `codex-smart -- doctor` forwards a reserved name to Codex. See [configuration](docs/configuration.md) for explicit dry-run/apply/rollback and [tool pins](docs/tool-compatibility.md) for optional `--tool-lock FILE`.

## Safety model

Diagnostics are offline/read-only by default and never execute discovered binaries, index a repository or change git metadata. Project configuration and PATH are untrusted. Explicit launches use OS argument arrays without a shell; the launched Codex process follows its own configuration and permissions. Separate marked codex-smart configuration transactions require explicit actions. See [doctor](docs/doctor.md), [tooling](docs/tooling.md) and [configuration](docs/configuration.md).

## Routing model

`explain` previews the reference Rust policy using explicit task hints and conservative capability evidence. `run` currently preserves exact Codex arguments and injects no profile or reasoning override. Router v2 composition, fallback and escalation remain planned; see [routing](docs/routing.md) and [architecture](docs/architecture.md).

## Development

Start with `just context [STAGE]` and `just issues`; validate with `just check`. See the [development guide](docs/development.md) for prerequisites and [workflow](docs/workflow.md) for documentation ownership. Security checks use `just security-fetch` for the explicit public advisory refresh, then `just security`.

## Documentation

Start at the [documentation index](docs/index.md), then the [roadmap](ROADMAP.md), [workflow](docs/workflow.md) and [architecture](docs/architecture.md). Consult [routing](docs/routing.md), [configuration](docs/configuration.md) and [tooling](docs/tooling.md) as needed.

## Roadmap

[ROADMAP.md](ROADMAP.md) records stage scope and implementation evidence; [GitHub Issues](https://github.com/AlexandrShapkin/codex-smart/issues) own live actionable state. Milestones group releases; stage labels describe current ownership. Release tags use `vMAJOR.MINOR.PATCH` only after logical release acceptance; see [release readiness](docs/releasing.md).

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) for focused branches, issue taxonomy, acceptance evidence and PR requirements.

## Security

Read [SECURITY.md](SECURITY.md) before reporting sensitive findings. Never post credentials or authentication material in public issues.

## License

No software license has been granted yet. License files and Cargo license metadata are absent pending an explicit owner decision; do not assume an open-source license.
