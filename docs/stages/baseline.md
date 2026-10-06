# Recover trustworthy repository baseline

## Scope

Inspect all recovered files and reconcile architecture, provenance, acceptance and versioning. Commit reviewed launcher/config/test/CI slices.

## Non-goals

No legacy import without artifacts; no release, automatic tool activation or unrelated feature work.

## Acceptance

All original untracked files inspected; source brief unchanged; local check/security gates and pushed-branch CI/Security pass. Orphan staging is refused without mutation.

## Validation

just check; just nextest; just security. Check original inventory hashes, PR #19 and recorded remote runs.

## Context

Read [docs/provenance.md](../../docs/provenance.md), [docs/architecture.md](../../docs/architecture.md), [docs/configuration.md](../../docs/configuration.md). Start with `just context baseline`; follow source entry points only as needed.

## Follow-ups

Legacy artifact uncertainty (#1), coverage unavailable, full doctor (#4), external pins (#7) and race-free execution (#17) remain explicit.
