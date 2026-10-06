# Configuration

Implemented resolution: built-in defaults < user config < project config < explicit CLI hints. Invalid files fail closed before an explanation is produced; explicit hints do not bypass validation. Origins are shown without dumping source values.

Locations: `$XDG_CONFIG_HOME/codex-smart/config.toml`, otherwise `$HOME/.config/codex-smart/config.toml`; project file is `.codex-smart.toml` in the current directory. No upward directory search or implicit config creation. Relative XDG/HOME roots, symlinks (including ancestors), hardlinks and group/world writable or foreign-owned files are rejected. Missing files use defaults. Reads are capped at 64 KiB. Linux with openat2 (kernel 5.6+) is the first supported platform; unsupported secure access fails closed.

```toml
kind = "codex-smart"
schema_version = 1
task = "local"
reasoning = "medium"
context_limit = 8192

[extensions.team]
workflow = "example" # preserved, inert
```

All three policy fields are optional. Task: local, architecture, refactor, external-api, github, migration, security. Reasoning: medium/high; absent means built-in task-based selection. Context limit: 1024..65536 bytes per retrieval response as a policy-preview parameter; it is not currently enforced by the passthrough launch. Never skip necessary evidence because of a context budget: escalate instead.

Unknown fields are inert and preserved. Project-local executable, shell, codex_path, MCP, plugins, auth, sandbox, approval and policy-script overrides are explicitly rejected. No config field can execute a program. `explain --task ... --reasoning ... --context-limit ...` has the highest precedence. `config show` and `doctor` validate/display only the recognized derived fields and origins. `run` remains exact Codex passthrough until Router v2 integrates these decisions; it does not silently apply preview policy or override user Codex arguments.

## Transactions

This migrates **codex-smart's marked schema 0 → 1**, not Codex config or an unverified codex-toolkit archive. Schema 0's `reasoning_effort` is renamed to `reasoning`; schema_version is updated. A conflicting old/new key is rejected. Unknown data and comments survive, including comments attached to the renamed key. TOML formatting may normalize (e.g. newline and dotted-key order); rollback restores exact original bytes. The actual toolkit migration adapter remains deferred until provenance evidence exists.

```sh
codex-smart config validate --file ./smart.toml
codex-smart config migrate --file ./smart.toml            # read-only diff/dry-run
codex-smart config migrate --file ./smart.toml --apply    # explicit mutation
codex-smart config rollback --file ./smart.toml          # read-only diff/dry-run
codex-smart config rollback --file ./smart.toml --apply
```

Migration requires an existing marked config, owner-only permissions, one hard link, and an owner-controlled non-group/world-writable parent. It creates no directories. Paths containing `..` are rejected; choose an explicit normalized path. The diff shows only schema/key changes and omits unrelated values; it is flushed before applying.

A directory descriptor anchors all operations. A persistent private `.codex-smart-migration.lock` serializes cooperating writers. Private exclusive-create artifacts beside the target: `<filename>.codex-smart-backup` (exact original), `.codex-smart-applied` (expected migrated bytes), `.codex-smart-stage` (atomic replacement). Created artifacts are mode 0600 even under restrictive umask. Existing artifacts are never overwritten. File/parent ownership and permission checks, content/identity rechecks, file fsync, directory fsync and relative atomic rename protect the transaction. Idempotent migration/rollback no-ops do not rewrite files.

Before commit, errors preserve the source and remove only artifacts created by that operation. After commit, errors retain recovery data and report `E_CONFIG_RECOVERY`. Rollback refuses intervening edits and validates that receipt equals the supported transformation of the backup. If the original is already intact after interruption, rollback offers read-only recovery cleanup, then removes only verified transaction artifacts with explicit --apply. Incomplete/corrupt/unrecognized recovery data is refused rather than guessed. The lock stays after apply to avoid competing lock inodes.

The advisory lock and optimistic identity checks cover cooperating migrations and edits observed before commit. They do not prove an atomic compare-and-swap against arbitrary noncooperating same-user writers in the last check/rename window. No claim of race-free execution or exhaustive power-failure testing is made. Symlink traversal cannot redirect writes outside the held directory.

Default resolution never reads Codex config/auth/MCP/plugins. Transactions reject targets inside CODEX_HOME or any .codex directory (including project/default stores) even if a file carries a codex-smart marker. Reserved transaction artifact filenames are also rejected as primary targets. Explicit validate can read a supplied file but refuses unmarked/non-schema-1 input without printing its contents. No actual user configuration was migrated during development; tests use isolated marked fixtures.


## Explicit executable lock

The separate [tool-lock contract](tool-compatibility.md) uses kind="codex-smart-tools"
and schema_version=1. It is not a policy layer and has no automatic project/global lookup.
Only the caller's explicit --tool-lock file can require the owned Codex artifact digest;
no lock record can select an executable, command, shell or install action. Policy preview
and user Codex config/auth/MCP/plugins remain separate. See the compatibility matrix for
why a declared version or matching digest never establishes runtime readiness.

## Doctor single-file analysis

`doctor --codex-config FILE` explicitly analyzes an allowlisted Codex TOML subset without
printing values or reading referenced auth/plugin stores. It reports permission-profile
and legacy sandbox conflicts and MCP declarations. It does not resolve effective Codex
configuration across layers/profiles/CLI. Default Doctor retains no Codex store discovery.
See [the Doctor contract](doctor.md) for schema, privacy and required-check semantics.
