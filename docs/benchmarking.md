# Development benchmark protocol

This is the first harness slice of #14, not a measured campaign. Router remains
validated; benchmark progress is partial after the harness merge. No benefit or winner is claimed. #15 production telemetry is separate.

## Quality before cost

Correctness, requirement coverage, regressions and security qualify a result before
cost is compared. `benchmarks/graders.py` runs fixed independent oracles outside the
agent workspace. The named gates currently share one conservative composite verdict:
all pass only when every scenario assertion passes. They are not separate measurements.
Failed, unavailable and retried runs remain in denominators. Cost summaries use matched
scenario/repetition/seed/snapshot/model/settings/cold-warm strata where every runnable
variant passes; a cheaper incorrect result never wins. Report median, range and sample
count, without winner logic. Token totals include every retry only when all attempts
expose that counter; otherwise the metric is unknown.

## Variants and provenance

- `vanilla`: direct non-interactive Codex with controlled settings.
- `native`: the same command with an explicit native-first instruction appended to
  the public task prompt; it is a policy instruction, not verified tool enforcement.
- `legacy`: unavailable. No exact source/version/checksum archive exists; historical
  numbers in the project brief are not new measurements.
- `router-v2`: unavailable. No verified experimental adapter applies the actual
  decision. Production `codex-smart run` remains passthrough. A future adapter must
  preserve decision/application evidence before this variant can be runnable.

Both runnable variants ignore user config/rules, use an ephemeral workspace-write
session, and require explicit model and executable. No MCP setup, indexing, network
probe or installation is performed by the harness. Real model execution itself uses
the existing authenticated Codex service. Toolchain absence records not-runnable.

## Pinned scenarios and setup

`benchmarks/manifest.json` version 1 pins seven purpose-built public fixtures: Rust
clamp bugfix, Go sum feature, Python mutation-sensitive tests, Python multi-file
rename, Python API/caller migration, IaC deployment security/config repair and Python
repository exploration. This is compact harness coverage, not representative campaign
coverage of every language/task pairing or large repositories. IaC uses a JSON
configuration contract; it does not measure Terraform/provider behavior.

Each fixture pins the SHA-256 of a canonical JSON file map (sorted keys, compact JSON,
UTF-8). This content-addressed snapshot replaces a repository commit for purpose-built
fixtures. Setup requires an empty disposable directory, materializes only baseline
files and verifies the resulting hash. Dirty state, changed snapshot, missing fixture
and setup errors reject execution. Every retry also starts fresh; retries are independent
attempts, not session resumes. Graders and solution/wrong controls are never copied into
the agent workspace. Real grading should run in a disposable container with no secrets
or network: submitted source executes during grading. The harness timeout terminates
process groups but is not a security isolation boundary.

The grader self-test requires positive controls to pass and deliberately wrong controls
to fail: happy-path-only clamp, hardcoded sum, vacuous tests, stale callers, privileged
configuration and incomplete call chain. Python test grading additionally mutates the
implementation to prove submitted assertions detect faults. Missing Rust/Go toolchains
skip those self-tests explicitly; full campaign acceptance requires all toolchains.

## Runner and trace contract

Run local fake validation with `python3 -B scripts/benchmark.py`; artifacts are created
under `benchmarks/.artifacts`. Remove that local directory explicitly before repeating
the same run identifiers (the runner refuses to overwrite evidence). Configure
`--repetitions`, `--seed`, `--retries`, `--timeout` and `--cold-warm`. Seed plus manifest
produces stable shuffled scenario/variant/repetition order, including unavailable rows.
CI uses fake runs and needs no OpenAI credentials. The one live preflight invocation
failed during local app-server initialization; no live model trace was emitted.

A bounded real campaign invocation requires `--real --codex /absolute/executable
--model MODEL`. The harness only accepts the inspected `codex-cli 0.162.1`; it records
executable checksum, requested model and controlled settings reference, plus manifest,
grader and harness checksums. Existing auth
is reused, never read/copied by this harness. Model reference is requested, not a claim
of provider-confirmed identity. CLI inspection is explicit benchmark setup, never
product runtime behavior.

The [official non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode)
defines `codex exec --json` and the sample `turn.completed.usage` fields. Local 0.162.1
`exec --help` confirms the flags. `benchmarks/fixtures/official-example.jsonl` is a
sanitized captured documentation example, not a live model trace or measurement.
Parser tests validate that example. A live trace contract smoke remains required before
claiming measured results for this pinned binary; the preflight below did not pass.

Only input, cached input, output and reasoning-output counters are read. Total and
fresh input stay unknown; neither is derived or estimated. Observed command/MCP/search
completed-item count is a lower bound; full tool-call count stays unknown. Unknown
event types/fields are ignored without projecting their contents. Malformed JSON,
invalid counters, duplicate terminal/item events, late events and truncated streams
fail closed and invalidate parsed counters. Nonzero exit, timeout, agent failure and
grader failure remain distinct. Every attempt and initial failure are retained.

## Records, overhead and privacy

`benchmarks/schema/record.schema.json` describes version 1 normalized records;
`schema/manifest.schema.json` describes manifests. Runtime validation checks manifests;
record serialization is tested against the fixed field contract without a framework.
Records contain scenario/variant/repetition/seed/snapshot, safe tool/model/settings
references, attempt start/end/duration/exit, composite quality gates, failure codes,
retry count, final status and nullable counters. No raw event payload enters records.

`cold` and `warm` are explicit operator classifications, not automatically inferred
cache state. Fresh fixture setup time is measured separately from development execution.
Bootstrap and index overhead are null until measured; no index is forced. Future
campaigns must document cache preparation and distinguish not-applicable from unobserved
index overhead. Missing metric is null, never zero.

Raw stdout JSONL and stderr can include prompts/source/tool details. They and local
records live only in the gitignored `benchmarks/.artifacts` directory with private
run directories. Never commit arbitrary output, auth, credentials, environment values,
private source or prompts. Checked-in fixtures use only public purpose-built data.
Export normalized records only after reviewing their metadata references; there is no
automatic commit/upload/export. This is benchmark-local instrumentation, not product
prompt/source logging or telemetry.

## Remaining acceptance campaign

Independently verify the live pinned trace, expand realistic task coverage,
pin toolchains and campaign model/settings, validate all graders in isolated environments,
and run repeated seeded quality-first measurements with cache/overhead evidence.
Obtain exact legacy provenance or retain unavailable status. Implement and verify a
separate decision-applying adapter before any Router v2 measurement. #14 stays open
until those measured acceptance criteria are satisfied; #15 remains separate.

## Initial campaign preflight

PR #32 merged the harness at `d6b74d4`. Exactly one vanilla Codex invocation used
`iac-security`, `gpt-6-sol`, explicit low reasoning, workspace-write, ephemeral mode,
ignored user config/rules, unknown cache state, timeout 120 seconds and zero retries.
Codex 0.162.1 exited 1 before emitting any JSONL because its in-process app-server
client could not initialize on the read-only filesystem. No second live invocation
was attempted. No terminal or usage fields were verified, and independent grading
was correctly skipped. The failed normalized attempt and empty raw trace remain local.
All documented input/cached-input/output/reasoning metrics are **not observed**;
fresh/total counters are unsupported by the documented parser contract and remain
null. Full tool-call count remains unknown. No comparative performance claim follows.

Privacy review found no auth-field categories in raw output, no arbitrary event payload
or absolute path in the normalized record, and private gitignored artifact directories.
Raw stderr is retained locally and is not committed; the reviewed failure contained
no auth-field categories or absolute paths. No live raw JSONL or
sanitized live fixture is committed: the empty stream supplies no useful regression
fixture. Existing parser tests cover the failed/truncated stream and nonzero exit.

`benchmarks/campaign-v1.json` freezes the **plan**, with live preflight blocked. It pins
Codex version/artifact checksum, requested model, low reasoning, sandbox/config/rules
auth equivalence, scenario/grader/harness/campaign-runner checksums, seed `[14]`, three
repetitions, zero retries, timeout 120 seconds and unknown cache protocol. Planned work
is 7 scenarios × 3 repetitions × 2 variants = **42 primary runs**, vanilla and native.
Legacy and Router v2 remain unavailable. Native differs only by the public instruction
already documented; command settings, auth, fixtures and graders are identical.

Toolchain pins are Rust 1.98.0 (`88d9e12ae`), Go `go1.27.2-X:nodwarf5 linux/amd64`, and
Python 3.14.8. They are installed locally; the campaign planner checks exact version
strings. Missing/mismatched tools make affected scenarios not runnable; none are
installed automatically. IaC checks JSON configuration semantics, not Terraform.
Fresh fixture setup is guaranteed; inherited host caches are not controlled, so no
cold/warm claim is made and bootstrap/index timing stays unknown/not applicable.

`python3 -B scripts/benchmark_campaign.py` prints a no-execution plan.
`python3 -B scripts/benchmark_campaign.py --dry-run` uses the exact frozen config for
42 local fake-agent jobs with real independent graders. It never invokes Codex, and
labels all counters synthetic. Records include pinned references and stay under
`benchmarks/.artifacts/campaign-v1-dryrun`. Existing evidence is never overwritten.
The campaign entry point deliberately has no model-execution mode while live preflight
is blocked. It must not be treated as ready for the measured campaign. A writable,
approved benchmark environment with existing authentication must first pass a bounded
live smoke; do not modify permissions or copy credentials to bypass this environment.
Review and update preflight evidence before enabling any measured execution.
