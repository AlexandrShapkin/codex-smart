# Release readiness

No release is published yet. The manual workflow runs quality gates and builds a Linux x86_64 archive with SHA-256 checksum as a CI artifact. It cannot create a tag or GitHub Release (read-only repository permissions). This is readiness scaffolding, not completed release automation.

Issue #16 tracks an authorized release boundary: finalize changelog/version, reproducible build assessment, tag, GitHub Release, artifact/checksum validation and migration instructions. Never publish to crates.io without a separate public-API decision.

cargo-dist was evaluated conceptually: one binary/one target currently needs only Cargo and tar; introducing another release framework/tool install has no demonstrated payoff yet. Reconsider when supported target matrix/signing needs grow. Current archives are not byte-reproducible: tar timestamps and environment are not normalized. Do not claim reproducible binaries until repeated isolated builds compare successfully.
