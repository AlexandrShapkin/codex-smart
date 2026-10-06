# Offline Doctor contract

`codex-smart doctor` is an independent, bounded, offline diagnostic command. It adds
local evidence to the external [compatibility model](tool-compatibility.md), never
`ready` from executable presence. No subprocess, network, installer, auth/keyring read,
MCP startup, indexing, Git operation or configuration write is part of Doctor.

```sh
codex-smart doctor
codex-smart doctor --json
codex-smart doctor --tool-lock ./tools.toml --codex-config ./codex.toml
```

## Evidence and exit status

The core `DoctorReport` holds typed checks and per-capability evidence. Human and JSON
renderers use that same model. Facts, assessments and fixed explanations are separate;
external names, URLs, paths, commands, arguments and environment values are never echoed.

PASS means the named local check passed, not runtime readiness. WARN means an optional
condition needs attention. FAIL means the named contract is violated. UNKNOWN lacks
sufficient evidence; NOT_CHECKED means the offline mode deliberately omitted a probe.
Required checks are Codex discovery, launcher configuration, and explicitly requested
artifact/configuration checks. Exit 1 indicates a required FAIL; optional unknown/warn
conditions do not fail Doctor. Exit 0 never certifies auth/MCP/index readiness. Invalid
arguments or tool-lock inputs retain exit 2 and fixed stderr errors, including with
--json; completed reports are emitted on stdout.

JSON schema version 1 has mode, product version, checks, capabilities, exit_code,
mutations and network_used. Each check has id, required, state, fact and explanation.
Each capability has id, nullable discovered, nullable declared_version, nullable
runtime_version, artifact, compatibility, execution_contract and readiness. No raw
configuration/tool output enters the encoder. Fields use deterministic inventory/check
order. Runtime version is null until an attestation source exists.

## Offline checks and limits

- Trusted bounded PATH discovery; explicit Codex locks use the reviewed bounded SHA-256
  verifier. A match validates the entrypoint bytes, not version/auth/interpreter dependencies.
- Launcher configuration uses existing marked schema/security validation.
- Workspace readability/writability and .git writability are separate Linux effective-access
  and mode hints through held, symlink-free directory descriptors. Mount/sandbox/ACL state
  and later races can still deny operations. No write test is attempted.
- A direct .git directory is a metadata hint. Gitdir files, symlinked metadata, parent
  repositories and linked worktree indirection are not followed. Origin/transport is a
  bounded local config syntax hint; includes, multiple URLs, rewrites and global precedence
  leave uncertainty. URL values/credentials never appear in output.
- Conventional .serena/project.yml and .code-graph/index markers are inspected through
  symlink-free O_PATH descriptors, without reading their contents. Absent/present is a
  marker fact; format, actual backend location, freshness and index readiness stay unknown.
- Network, GitHub API/auth, remote Git connectivity, Codex auth and MCP handshake are
  distinct NOT_CHECKED checks. Offline absence of an optional capability is normal.

## Explicit Codex configuration analysis

Default Doctor never discovers Codex config/auth/plugin stores. --codex-config explicitly
accepts only a .toml path; other file kinds (including auth.json) are rejected before
opening. It reads that caller-supplied TOML file using the existing secure reader: 64 KiB, current
ownership, one hard link, no symlinks/ancestor symlinks or group/world write permissions.
It does not read referenced files, environment values, credentials or servers.

It validates an allowlisted subset: permission selector/sandbox/approval types, expected
sections, up to 32 MCP definitions and selected command/url/args/enabled/required types.
Unknown fields are ignored, never displayed; this is not a full upstream schema validator.
It detects profile-selector versus legacy sandbox coexistence, reports exact-cwd project
trust declarations, name-based Serena/CodeGraph/Context7 configured/enabled state, duplicate
capability aliases, declared stdio/HTTP transport and obvious installer/shell commands.
Every process probe remains refused: absence of a known installer name does not prove safety.
Profiles, managed layers, project precedence and CLI overrides are not resolved; effective
configuration remains UNKNOWN. A missing profile definition may live in another layer.

The [official permissions contract](https://learn.chatgpt.com/docs/permissions) says to
choose permission profiles or legacy sandbox settings; legacy loaded settings can override
the selector. See also the [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
The supplied-file conflict check reports ambiguity; it never silently repairs config.

## Security and verification

No active/online flags are shipped: there is no demonstrated mutation-free probe contract
for the discovered wrappers/MCP clients. The legacy CodeGraph npx fallback stays unsupported.
Future deeper checks require a separate explicit, reviewed contract; they are not startup work.

Golden human/JSON fixtures and isolated filesystem tests cover absence, pins, unknown
versions, hostile config, permission conflicts, read-only metadata, symlinks, oversized
inputs, unsafe wrappers, secrets, option boundaries and marker/remote uncertainty. Snapshots
compare bytes, paths, modification times and modes before/after commands, including .git,
config, locks and index fixtures. Kernel access-time effects of reads are not an explicit
write and are not covered by this snapshot claim. TOCTOU and ancestor trust limits from
[artifact security](tool-compatibility.md) remain; no atomic execution guarantee is added.
