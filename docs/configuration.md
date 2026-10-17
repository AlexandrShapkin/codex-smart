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
or `codex-smart run -- plan`; explicit run/legacy escaped passthrough retains exact operator
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

## Working preview invocation

`codex-smart` opens interactive Codex; `codex-smart "task"` starts one exec.
The [preview runtime contract](production-routing-readiness.md#working-preview-0x-141)
owns typed inspection guidance, explicit reasoning and Strong/High refusals.
Preview facts come only from explicit options, not the diagnostic configuration
fields above. Unknown compatibility never enables automatic model/reasoning changes.
The existing reasoning argv adapter caps preview arguments at 256 entries/16,384 bytes;
exceeding bounds refuses before launch without printing their contents.

## Supervised inspection accounting (#145)

`codex-smart inspect --supervised-json [--timeout-seconds 1..120]
[--answer-file PATH] [existing typed inspect options] [--] "task"` explicitly
supervises one noninteractive Codex CLI **0.162.1** `exec -s read-only --json
--ephemeral` attempt on Linux. Existing inspect policy, bundled catalog and
LaunchPlan executable identity checks apply. Default inspect and `run --` retain
their existing behavior. No launcher retry, replay, escalation or second model
attempt is made. Supervised catalog/version probes use the same group cleanup
with five-second deadlines and 128-byte/2,000,000-byte output caps. They make no
model call; provider availability remains unknown. Ephemeral mode asks Codex not to persist session files.

The post-spawn deadline defaults to 120 seconds and can only be reduced. Captured
stdout is capped at 1 MiB; stdin is null and child stderr is discarded. The parent
handles SIGINT/SIGTERM, kills the original process group before reaping its leader
(including after normal exit), and allows at most one additional second for
cleanup. Leader identity stays reserved until group termination. An unreaped child
remains owned by the process and blocks another supervised launch. These limits
do not bound OS spawn, executable identity/filesystem checks or answer-file I/O.
Process groups are supervision, not hostile-process confinement: a descendant
that changes its group or session can escape group termination. A pipe still open at
the cleanup deadline yields Unknown; escaped processes that close their inherited
pipes cannot be detected. SIGKILL of the parent cannot be handled.

After supervision, stdout is one JSON object containing only `status`, `usage`
(`input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`,
`output_tokens`, `reasoning_output_tokens`) and the `answer_file`
status. No event bodies, paths, model answer, prompt, source, identifiers or child
errors are printed. Counters come only from `turn.completed.usage`, with absent,
invalid or unavailable counters represented as JSON **null**, never invented zero.
Explicit reported zero remains zero. Complete JSONL framing, start events and one
terminal event are required; malformed, truncated, unknown or oversized streams
fail closed. No usage is inferred from other events or stderr.

| Status | Meaning | Exit |
| --- | --- | --- |
| CompletedSuccess | Complete successful turn and successful child exit/cleanup | 0 |
| CompletedFailure | Complete terminal protocol with failed turn or nonzero child exit | 1 |
| Timeout | Post-spawn deadline reached and cleanup confirmed | 124 |
| Interrupted | Parent interrupt or signaled child, with cleanup confirmed | 130 |
| Unknown | Spawn/identity failure, incomplete protocol, output bound or uncertain cleanup | 2 |

Policy, catalog, arguments, unsupported platforms and answer-file creation can
refuse before supervision: stdout remains empty and stderr contains only a fixed
privacy-safe diagnostic. A completion status describes transport/provider outcome,
not independent validation of the answer or Adaptive stage acceptance.

`--answer-file PATH` requires `--supervised-json`. Before the attempt the launcher
exclusively creates the file with mode 0600; an existing file or final-component
symlink refuses without launching. It retains that descriptor and never passes the
path to Codex. Only the last completed `agent_message` from a complete terminal
stream and confirmed child outcome is written. Its status is `Written`,
`Unavailable`, `WriteFailed` or `NotRequested`; write failure makes the overall
outcome Unknown. An unavailable answer leaves the newly created file empty; an I/O
failure may leave a partial private file. No automatic deletion/reopening occurs.
The operator chooses a trusted private parent directory and manages the private
answer file separately from the aggregate report. Launcher diagnostics never log
private transport contents; native Codex remains responsible for its own runtime,
provider behavior and authentication.

Validation uses isolated fake Codex executables without credentials or live model
calls. Native 0.162.1 `exec --help` and local binary event metadata establish the
JSONL field names used by the parser; broader version compatibility is unknown.
