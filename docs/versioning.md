# Versioning

Semantic Versioning: 0.1.x Foundation; 0.2.x Router v2; 0.3.x benchmarks/telemetry; 0.4.x+ hardening; 1.0.0 after independent stability and quality gates. Pre-1.0 breaking changes require changelog and migration guidance. Internal commits do not bump versions.

Workspace version is the sole binary version source. Lockfile is committed. Local stable is rustc 1.98.0; CI requests 1.98.0 explicitly. A named 1.98.0 local toolchain is not provisioned, so rust-toolchain.toml is deferred to avoid implicit rustup downloads. No automatic rustup install is performed by runtime diagnostics.


External runtime declarations are independent of the product version. [The tool lock](tool-compatibility.md)
accepts strict three-component release versions only; build/prerelease suffixes and raw
wrapper output are never reflected. Codex 0.160.0 and Serena 1.7.0 are pinned release-source
references, not claims about a discovered executable. Unknown versions stay unknown.
Repository dependencies are exact and checksum-locked; runtime diagnostics never install tools.
