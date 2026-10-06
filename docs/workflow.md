# Bounded development workflow

Use `just` as the stable developer and CI command surface. Start with `just context`
or `just context STAGE`; read its contract and only the referenced docs/source needed
for the change. Context is capped at 8192 UTF-8 bytes and never launches discovered
tools or reads live GitHub state. A clipped excerpt points to the complete contract;
the byte limit never excuses missing evidence or verification.

The loop is `just context`, `just issues`, implement one bounded stage slice,
`just docs-generate`, `just check`, inspect all diffs/new files, then record PR/CI
evidence. `just security-fetch` is the explicit public advisory refresh;
`just security` uses the cached database. CI runs the same `just check` gate.

## Sources of truth

The permanent [issue taxonomy and closeout rules](../CONTRIBUTING.md#issue-governance)
live in CONTRIBUTING.md. Every actionable issue has one primary area, one severity,
at most one current stage owner and one work-kind. Milestones group releases;
stage labels track mutable implementation ownership.

- `docs/stages.json` owns stable stage IDs, dependency order, issue links, context
  entry points and recorded implementation progress. Each stage has a contract
  defining scope, non-goals, acceptance, validation, context and follow-ups.
- `docs/documents.json` owns each Markdown document's maintainer, role and stages.
  [The generated index](index.md) is the entry point. Current docs describe delivered
  behavior; ADRs own durable decisions; dated diagnostics are historical evidence.
- GitHub Issues own live actionable state, dependencies and acceptance discussion.
  `just issues` explicitly fetches bounded metadata through authenticated gh. Local
  `docs/issues/*.md` are design references, not synchronized issue status or closure.
- Workspace Cargo version owns product SemVer. Recorded stage progress never bumps
  versions or implies a release, merged PR, closed issue or complete milestone.

## Offline correction gate

`just docs-check` validates schemas, unique IDs/ownership, dependency cycles, source
paths, required contract sections, local Markdown links/fragments and exact generated
views. It never calls git/gh, opens external URLs, executes registry commands, writes
files or consults clocks/auth/config. Python stdlib is sufficient; no reference
checkout or optional tools are required. Inputs are bounded to 32 stages, 128 owned
documents and 128 KiB per file. Document discovery is limited to root Markdown,
`docs/` and `.github/`; runtime and generated build trees are excluded.

`just docs-generate` is the separate explicit write: it rebuilds ROADMAP.md and
docs/index.md deterministically from the registries, without timestamps or live issue
states. Update registries/contracts first; inspect both generated diffs. Add ownership
for every new document. Never edit generated views directly.

Preserve validated stage evidence and contracts in later work. Reopen a validated
slice only for a reproducible finding, record the regression and use the smallest
repair. Baseline evidence is linked from its stage; later stages do not erase it.
Automatic stage advancement, runtime orchestration and issue-state copying are out
of scope. Workflow tooling remains outside the thin Rust launcher.

## Reference and dogfooding

The local rustcraft-b173 reference supplied the coherent-stage/acceptance pattern and
canonical `just` developer loop. This repository adds machine-readable registries and
offline governance for its own smaller scope; it has no runtime dependency on rustcraft.

After baseline commit eb18745 passed CI and Security, the workflow stage (#20) is
implemented before the tools stage (#7). Use `just context tools` to recover the
pending pin slice and update its contract, evidence and live issue as it is validated.
