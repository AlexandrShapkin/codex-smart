# codex-smart governance context

Native architecture, security, CI and product rules remain consumer-owned; see
[AGENTS.local.md](../AGENTS.local.md), [local workflow](PROJECT_WORKFLOW.md), the existing roadmap and documentation index.
Template alone owns the active shared lifecycle. Kit snapshots and optional skills
are inert technical references; no skill is installed or activated.

## Source adoption

Owning Issue: [#169](https://github.com/AlexandrShapkin/codex-smart/issues/169);
coordinator: [Kit #8](https://github.com/AlexandrShapkin/codex-engineering-kit/issues/8).
See [provenance and update/rollback](UPGRADING.md) and independent channel records
[Kit](../.engineering-kit/source.json) / [Template](../.project-template/source.json).
This is a reviewed source migration, **not an accepted Kit sync installation**.
There are no format-1/2 bundles or fabricated sync locks in this adoption.
Public source licenses do not approve a generated format-3 artifact digest.
MIT attribution is retained in [GOVERNANCE-NOTICE.txt](../GOVERNANCE-NOTICE.txt).

## Native stage map

Use [stage registry](stages.json) and generated [roadmap](../ROADMAP.md); workflow adoption is #169. Existing stage and milestone decisions remain unchanged.
GitHub Issues own live status; this is navigation, not another backlog.
No new milestone is warranted: this task is not a confirmed product release.

## Product release applicability

Applicable: CLI distributions; preserve existing local-only working-preview and release-readiness restrictions. GitHub Release asset publication remains separately qualified under the existing release Issue #16.
The shared release requirements resolve through the canonical interface; product
version history remains independent of Kit and Template. No tag, Release,
release asset or publication automation is introduced by this migration.

## Dependencies and acceptance

Existing lifecycle Drafts overlap these entrypoints. They remain untouched and
must be reconciled explicitly during independent review; do not merge either
policy activation blindly. This branch starts from main, not an unreviewed stack.
Author checks, exact-head native CI, independent acceptance and merge authority
remain separate. No consumer is ACCEPTED by opening this Draft.

## Bounded release matrix qualification

| Product | Targets / format | Qualification |
| --- | --- | --- |
| CLI | Linux x86_64 working preview; additional targets require their own evidence | Existing `docs/releasing.md` and `docs/distribution.md` remain authoritative; no installer or portable package support is inferred from a Cargo build. |

The first significant distributable release must select usable CLI packages from
that qualified target set, with SHA-256, source/build provenance and narrative
notes. Unqualified targets are omitted, never filled by placeholder artifacts.

Contract v1 adoption remains inert. Its canonical schema and passive validator
are Codex Smart #166/#167; independently pinned adapter mappings and Git evidence
must be accepted before claiming authenticated readiness. GitHub Issues remain
the live queue. No runtime or optional Hub integration is enabled.
