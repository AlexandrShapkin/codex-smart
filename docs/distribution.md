# Distribution and release lifecycle target

Status: planned 0.7 Distribution. This is a target contract, not an installer,
updater or release implementation. Current readiness scaffolding remains described
in [releasing](releasing.md); #16 retains release/migration ownership. Initial
supported distribution may remain Linux x86_64. Other platforms require evidence
and an explicit supported-matrix decision. Roadmap milestone numbers do not bump
SemVer: the package remains 0.1.0 unreleased.

## Release verification

Use prebuilt versioned artifacts and checksums with a reviewed authenticity
mechanism. A checksum alone proves neither publisher identity nor trusted metadata.
Select the authenticity/trust-root mechanism before enabling installation; document
key rotation/revocation, metadata freshness and compromised-release recovery.
Do not claim present artifacts are signed or byte-reproducible. Release publication,
tags and channels require separate authorization and validated build provenance.

The lifecycle is release artifact → authenticity/integrity verification →
compatibility preflight → explicit target location → atomic install → validation.
An explicit version/channel selects the artifact. Stable/preview channels are
conditional on a reviewed contract, not an automatic promise.

## Install

Default to an explicit user-local target without sudo. Detect existing installations
and ownership before replacement. Verify artifact and compatibility before commit;
stage on the target filesystem, replace atomically, then validate with doctor.
Never silently mutate PATH. Any opted-in PATH/config change is reversible and
ownership-recorded. Reject incompatible, ambiguous or unverified inputs without
partial installation. Do not install unrelated dependencies or configure plugins.

## Update check

A future `codex-smart update --check` inspects verified release metadata under an
explicit policy/configuration contract. It does not perform an update. Network
checks are not silently enabled; offline mode reports unavailable/stale evidence
accurately. No background updater or daemon is planned.

## Update

Updating requires an explicit action; silent automatic updates are disabled by
default. Verify release metadata, artifact authenticity/integrity and Codex/platform
compatibility. Detect concurrent updates and existing state. Plan a migration dry-run,
backup and reversible transaction before atomic binary replacement. Validation and
failure recovery must cover the binary and owned configuration as one coherent
operation; never leave half-written binary/config state.

## Migration

Preserve the current safe configuration transaction contract. Show the dry-run,
validate the target schema, preserve a recovery backup and commit transactionally.
Migrate only codex-smart-owned state with explicit authority. Never copy or rewrite
Codex credentials, silently mutate authentication or plugins, or collect secrets
into backups. Profile/playbook schema compatibility belongs in the migration plan.

## Rollback and downgrade

Keep the last verified recoverable binary/config pair. Define supported downgrade
and rollback windows and incompatible-schema refusal before release. Rollback
verifies the retained artifact and restores an atomic compatible state; it cannot
silently skip authenticity checks or overwrite newer incompatible configuration.
Record non-secret provenance and make recovery commands inspectable.

## Interrupted-update recovery

Model staging, verification, backup, commit and validation as bounded transaction
states. Failure injection must exercise interruption at every boundary, concurrent
execution, disk/permission failures and validation failure. Recovery determines
which verified pair is authoritative, removes only owned temporary files and
restores a usable installation without erasing user data. Rehearse supported
pre-1.0 upgrade/downgrade paths before stable acceptance.

## Uninstall

Remove only the explicitly owned installation and opted-in PATH/config changes.
Allow retained user configuration/backups by explicit policy. Never delete Codex
configuration/authentication, credentials, external tools or unrelated user files.
Provide an inspectable removal plan and detect ambiguous ownership.

## Offline and local artifacts

Support explicit local-artifact installation/update without network dependency.
Apply the same integrity, authenticity, version and compatibility checks; absent
trusted metadata is a refusal, not an insecure fallback. Offline update checks can
report that current release knowledge is unavailable without changing state.

## Security boundaries and acceptance

The lifecycle plane remains separate from model/task routing. No sudo by default,
no hidden installation, silent auth/plugin changes, unrelated dependencies or
implicit global configuration. Authenticated user execution is not authorization
to inspect credential stores. Artifact verification, trust-root management,
transaction races, rollback attacks and malicious release metadata require security
review. Supported compatibility, installer/uninstaller, updater/check/rollback,
migration and interruption-recovery tests precede 0.8 hardening and 1.0 release
rehearsal. No implementation is added by this document.

## Local working preview archive (#141)

A local-only Linux x86_64 helper builds the current 0.1.0 unreleased preview:

```bash
python3 scripts/local_preview.py build /absolute/new/archive-directory
mkdir -p /absolute/user/bin
python3 scripts/local_preview.py install /absolute/new/archive-directory/codex-smart-0.1.0-preview-linux-x86_64.tar.gz /absolute/user/bin
python3 scripts/local_preview.py remove /absolute/new/archive-directory/codex-smart-0.1.0-preview-linux-x86_64.tar.gz /absolute/user/bin
```

Build requires cached Rust dependencies and uses locked offline Cargo. The archive contains the launcher plus a bounded `build-info.txt` manifest
recording version `0.1.0-preview` and the exact clean-source Git commit SHA;
the optional preparation worker is not included. Inspect the manifest with
`tar -xOzf ARCHIVE build-info.txt` before installation. Keep the adjacent
`.sha256` file for install/remove. Only use artifacts built from your trusted local
source: this checksum checks corruption, not publisher authenticity. Install refuses
replacement and symlink destinations; remove requires matching binary bytes. The bin
directory must already exist at an absolute path without symlinks. No PATH, config,
auth, tags, publication or updater is changed. Install writes a new file directly;
interruption can leave a partial file, which must be inspected and removed manually.
This is a single-operator local helper, not a concurrent or hostile-directory installer
and not completion of the distribution stage or its authenticity contract.
