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

Router v2's separate pure reasoning API consumes a resolved explicit override rather
than repeating these layer rules. User/Project/Cli reasoning origins pass the selected
Medium/High; BuiltIn passes None. Its fake argv adapter does not read Codex profiles
or apply synthetic overrides to production run. See
[the reasoning contract](routing.md#router-v2-reasoning-effort-selection-11).

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

## Explicit inspection plan preview

`codex-smart plan --intent inspection` composes typed Router assessment and the
Inspection Playbook into a deterministic plan-only summary. `plan --help` lists the
bounded grammar. Optional `--task inspect|edit|refactor|unknown` supplies a separate
task declaration; edits/refactors conflict with inspection and unknown task evidence
remains ambiguous. Optional `--risk low|medium|high` and
`--safety none|security|migration|concurrency` are declarations, not verified facts.
Missing risk/safety declarations are explicitly Unknown; the displayed effective
risk is a policy floor, not proof that risk is known. Safety-sensitive declarations
retain Strong/High floors even with a low risk hint.

Repeated `--file RELATIVE_PATH` nominates at most 16 public relevant files using the
existing lexical nomination policy (1024 bytes/path, 16 components, no traversal,
absolute paths, sensitive names or duplicate normalized paths). Input is capped at
40 option/value arguments and 18432 bytes. Singleton options cannot repeat; unknown
options and non-UTF-8 values fail with bounded errors that omit input values.

The preview reads no configuration, PATH inventory or nominated file contents and
performs no acquisition, worker spawn, model call, validation execution, retry,
delegation, indexing or network action. Native/external capability evidence and model
identity stay Unknown. It displays context obligations, declarative nomination counts,
validation readiness and enum-only blockers; nomination grants no semantic coverage.
A successful exit means the preview was rendered, not that execution is ready.

`plan` is a reserved launcher command. Forward it to Codex with `codex-smart -- plan`
or `codex-smart run -- plan`; ordinary run/implicit passthrough retains exact operator
argv and configuration priority. The plan ignores configuration rather than adding a
new configuration layer. Explicit worker-backed preparation is documented below; residual runtime joins belong to
[#94](https://github.com/AlexandrShapkin/codex-smart/issues/94); measurement acceptance
belongs to [#95](https://github.com/AlexandrShapkin/codex-smart/issues/95). Neither is
activated by the preview.

## Explicit supervised inspection preparation

`codex-smart prepare --intent inspection --worker /absolute/reviewed/worker
--worker-sha256 INDEPENDENT_SHA256 --worker-protocol 1 [--file RELATIVE_PATH ...]`
explicitly invokes the accepted local preparation worker once. Supply one independently
reviewed executable path, its 64 hexadecimal SHA-256 characters and protocol 1;
the command never discovers or hashes a candidate to create its own trust pin.
Digest matching establishes artifact integrity against that declaration, not publisher
authenticity. The operator independently trusts the executable and nominates public files.
`prepare --help` renders the complete grammar without worker access.

The command shares the declarative inspection parser, nomination bounds and typed plan
with `plan`. Optional risk/safety declarations preserve policy floors; only a compatible
inspection task selection admits acquisition (`--task edit|refactor|unknown` refuses).
Native/model evidence remains Unknown. Protocol v1 carries inspection/file acquisition,
not task-risk declarations: the parent retains the declared plan and uses the returned
report only as acquisition evidence. It never admits model or validation execution.

Optional `--deadline-ms` and `--cleanup-ms` independently lower the existing nonzero
250 ms ceilings; defaults are 250 ms each. The acquisition cooperative budget is also
lowered to the selected runtime deadline. File/count/byte ceilings remain the accepted
16 files, 8192 bytes/file and 32768 total bytes. Preparation input is capped at 50
option/value arguments and 20480 bytes, worker path at 1024 bytes; singleton runtime
options cannot repeat. Invalid/unsafe input returns a bounded error without input values.
The current absolute directory is the acquisition root; existing descriptor traversal,
root and nomination rules apply. Configuration and PATH are never consulted.

Only enums and counts are rendered: worker state/exit category, acquisition failure,
unresolved obligations and declarative validation readiness. Source, paths, digests,
wire bytes and stderr payloads are omitted. Exit 0 means supervised acquisition
succeeded, including an empty nomination set; it never establishes semantic context
sufficiency. Refusal, acquisition failure, timeout, protocol failure and CleanupUnknown
exit 2. Semantic sufficiency stays Unknown and production admission closed. CleanupUnknown
retains the existing process-lifetime ownership contract; CLI exit does not prove reaping
and there is no durable cross-process recovery or automatic replay.

Worker verification and spawn are outside the post-spawn deadline; this is neither an
end-to-end real-time guarantee nor a hostile-code sandbox. The trusted artifact retains
the caller's OS authority. All isolation, pin/protocol and cleanup limitations in
[architecture](architecture.md#supervised-preparation-boundary-explicit-local-runtime)
remain applicable. No retry, escalation, model, validation command, delegation,
network, indexing or config/auth mutation is added. `plan` remains declarative.
`prepare` is reserved; `codex-smart -- prepare` and `codex-smart run -- prepare`
forward it through the ordinary unchanged Codex launch path.

This bounded CLI join belongs to [#100](https://github.com/AlexandrShapkin/codex-smart/issues/100),
the first child of #94. Independent technical acceptance and residual runtime gates
remain open; it does not activate production routing or measurement.
