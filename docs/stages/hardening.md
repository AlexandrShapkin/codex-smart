# Packaging, migration and security hardening

## Scope

Assess PATH ownership/ancestor trust, execution races, migration rehearsal and Linux packaging/release reproducibility.

## Non-goals

No remote publication without explicit authorization; no crates.io publication or claimed byte reproducibility without evidence.

## Acceptance

Full acceptance/security audit, compatibility matrix and rollback/release rehearsal; artifacts/checksums validated; execution-race limitations resolved or explicit.

## Validation

just context hardening; just check; just security. Separate authorized release rehearsal and isolated repeated build comparisons.

## Context

Read [docs/releasing.md](../../docs/releasing.md), [docs/configuration.md](../../docs/configuration.md), [SECURITY.md](../../SECURITY.md). Start with `just context hardening`; follow source entry points only as needed.

## Follow-ups

The current release workflow creates CI artifacts only. Tar timestamps/environment are not normalized.
