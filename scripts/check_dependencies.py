"""Require review for direct dependencies; validate registry provenance in the lock."""
import re
import tomllib
from pathlib import Path

approved = {
    "toml_edit": ("=0.25.15", ["display", "parse"]),
    "rustix": ("=1.1.5", ["fs", "process"]),
    "codex-smart-core": ("=0.1.0", []),
}

def check_table(table):
    for name, spec in table.items():
        if not isinstance(spec, dict):
            raise SystemExit(f"Dependency requires reviewed exact version/features: {name}")
        selected = (spec.get("version"), sorted(spec.get("features", [])))
        if name not in approved or selected != approved[name]:
            raise SystemExit(f"Unreviewed direct dependency/version/features: {name}")
        if name == "toml_edit" and spec.get("default-features") is not False:
            raise SystemExit("toml_edit must keep only reviewed parse/display features")
        if name == "codex-smart-core" and spec.get("path") != "../codex-smart-core":
            raise SystemExit("Unexpected local core path")
        allowed = {"version", "features", "default-features"}
        if name == "codex-smart-core":
            allowed.add("path")
        if set(spec) - allowed:
            raise SystemExit(f"Unreviewed dependency options/source: {name}")
        if name == "rustix" and spec.get("default-features", True) is not True:
            raise SystemExit("rustix default features changed without review")
        if "git" in spec or "registry" in spec:
            raise SystemExit(f"Unreviewed dependency source: {name}")

for manifest in Path("crates").glob("*/Cargo.toml"):
    config = tomllib.loads(manifest.read_text())
    for container in [config, *config.get("target", {}).values()]:
        for kind in ("dependencies", "dev-dependencies", "build-dependencies"):
            check_table(container.get(kind, {}))
packages = tomllib.loads(Path("Cargo.lock").read_text())["package"]
external = [p for p in packages if "source" in p]
for package in external:
    if package["source"] != "registry+https://github.com/rust-lang/crates.io-index":
        raise SystemExit("Unreviewed transitive source: " + package["name"])
    if not re.fullmatch(r"[0-9a-f]{64}", package.get("checksum", "")):
        raise SystemExit("Missing registry checksum: " + package["name"])
print(f"Dependency provenance: {len(external)} registry packages, checksums present; direct pins/features reviewed")
