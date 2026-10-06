# Roadmap

Status: 2026-10-06. Recovered source implementation and local checks exist; Git/GitHub infrastructure is operational. Baseline correction evidence is in [the audit](docs/diagnostics/2026-10-06-baseline.md). See [GitHub issues](docs/issues/index.md). Checkmarks mean locally implemented slices, not completed milestones or released features.

## 0.1 Foundation

- [x] Environment inspection and recorded tool versions.
- [x] Provenance gate documented; supplied brief SHA-256 retained (#1).
- [ ] Verify/import legacy artifact when available; 1.4.1 remains unverified (#1).
- [x] Minimal Rust core/CLI workspace and workspace version; first slice std-only, config adds two reviewed pinned dependencies (#2).
- [x] Offline metadata-only capability preflight (#3).
- [x] Initial read-only doctor and explicit unknown health/config/index states (#4).
- [x] Read-only explain with typed reference routing, confidence/fallback/overhead (#5).
- [x] Filesystem mutation, hidden execution, PATH hijacking and golden regression tests (#3/#5).
- [x] Shell-free process launch, dry-run, unchanged argv and exit status (#18).
- [x] Marked TOML config, typed schema/precedence and explicit transactional schema migration/rollback with crash recovery (#6).
- [ ] Actual codex-toolkit migration adapter: deferred until verified artifacts (#1/#6).
- [x] Cargo-deny advisory/license/source/bans gates and direct dependency provenance checks (#8).
- [ ] Validated external pins, versions and compatibility matrix (#7).
- [ ] Complete doctor config/index/permissions/compatibility checks (#4).
- [x] Local fmt/clippy/tests/build and nextest checks (#8).
- [x] GitHub labels, five milestones, 18 scoped issues with linked dependencies.
- [x] Issue templates, PR template, CI/security/release-readiness scaffolding.
- [ ] Branch/commits/PR/remote CI: awaiting baseline push and CI evidence (#8).

## 0.2 Router v2

- [ ] Task/risk composition and cheap repository facts (#9).
- [ ] Deterministic decisions with validated tool-surface application (#10).
- [ ] Supported reasoning selection and highest-priority explicit overrides (#11).
- [ ] Evidence-based fallback/escalation and bounded context (#12).
- [ ] Evaluate sandboxed Rhai; defer without demonstrated benefit (#13).
- [ ] Expand explanation and golden compatibility matrix.

Prerequisite: all P0 safety gates, not just a working preview.

## 0.3 Development Benchmark

- [ ] Full-lifecycle bugfix/feature/test/multi-module/refactor/API/CI/exploration tasks (#14).
- [ ] Rust, Go, Python and IaC independent correctness gates (#14).
- [ ] Four variants with verified old baseline where possible (#14).
- [ ] Local aggregate token/tool/retry/latency telemetry and privacy tests (#15).
- [ ] Bootstrap/index overhead, repeats, failures and quality-first comparison.

## 0.4 Hardening

- [ ] Packaging and complete authorized release process (#16).
- [ ] Migration rehearsals, compatibility matrix and full doctor (#4/#6/#7/#16).
- [ ] PATH ownership/ancestor trust, execution races, performance/security review (#17).
- [ ] Release reproducibility assessment and supported Linux x86_64 binaries.

## 1.0 Stable

- [ ] Independent benchmark quality gates and production hardening (#17).
- [ ] Stable CLI/config contracts, documented upgrade/rollback and supported matrix.
- [ ] Reviewed release and security readiness. No 1.0 date before evidence.

## Current engineering status

Completed: three local slices: read-only capability→routing→explain, exact process launch, and marked TOML/config transactions. Validation includes CLI golden output, isolated metadata/content snapshots, migration failure/crash states, symlink/hardlink/permission/size rejection, concurrent-edit/lock checks and private artifacts under restrictive umask. Local CI-equivalent and dependency security checks are recorded in diagnostics. Issues updated, not closed without commit/CI evidence. New limits: optimistic commit does not eliminate noncooperating same-user edit races; preview config is not applied to passthrough launch. Next slice: #7 external version pin/report contract and compatibility, then complete doctor #4. Baseline must pass pushed-branch CI before #7 resumes.
