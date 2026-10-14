"""Require review for direct dependencies; validate registry provenance in the lock."""
import re
import tomllib
from pathlib import Path

approved = {
    "libc": ("=0.2.189", []),
    "sha2": ("=0.11.0", []),
    "toml_edit": ("=0.25.17", ["display", "parse"]),
    "rustix": ("=1.1.5", ["fs", "process", "thread"]),
    "codex-smart-process": ("=0.1.0", []),
    "codex-smart-core": ("=0.1.0", []),
}

def check_table(table):
    for name, spec in table.items():
        if not isinstance(spec, dict):
            raise SystemExit(f"Dependency requires reviewed exact version/features: {name}")
        selected = (spec.get("version"), sorted(spec.get("features", [])))
        if name not in approved or selected != approved[name]:
            raise SystemExit(f"Unreviewed direct dependency/version/features: {name}")
        if name in {"toml_edit", "sha2", "libc"} and spec.get("default-features") is not False:
            raise SystemExit("Dependency must keep only reviewed features")
        if name in {"codex-smart-core", "codex-smart-process"} and spec.get("path") != "../" + name:
            raise SystemExit("Unexpected local package path")
        allowed = {"version", "features", "default-features"}
        if name in {"codex-smart-core", "codex-smart-process"}:
            allowed.add("path")
        if set(spec) - allowed:
            raise SystemExit(f"Unreviewed dependency options/source: {name}")
        if name == "rustix" and spec.get("default-features", True) is not True:
            raise SystemExit("rustix default features changed without review")
        if "git" in spec or "registry" in spec:
            raise SystemExit(f"Unreviewed dependency source: {name}")

workspace = tomllib.loads(Path("Cargo.toml").read_text())
if workspace.get("patch") or workspace.get("replace"):
    raise SystemExit("Unreviewed workspace dependency source override")
check_table(workspace.get("workspace", {}).get("dependencies", {}))
for manifest in [Path("Cargo.toml"), *Path("crates").glob("*/Cargo.toml")]:
    config = tomllib.loads(manifest.read_text())
    for container in [config, *config.get("target", {}).values()]:
        for kind in ("dependencies", "dev-dependencies", "build-dependencies"):
            check_table(container.get(kind, {}))
packages = tomllib.loads(Path("Cargo.lock").read_text())["package"]
external = [p for p in packages if "source" in p]
internal_names = {"codex-smart-cli", "codex-smart-core", "codex-smart-process"}
for package in packages:
    if "source" not in package and (
        package["name"] not in internal_names
        or package["version"] != workspace["workspace"]["package"]["version"]
    ):
        raise SystemExit("Unreviewed local lockfile dependency")
for package in external:
    if package["source"] != "registry+https://github.com/rust-lang/crates.io-index":
        raise SystemExit("Unreviewed transitive source: " + package["name"])
    if not re.fullmatch(r"[0-9a-f]{64}", package.get("checksum", "")):
        raise SystemExit("Missing registry checksum: " + package["name"])
print(f"Dependency provenance: {len(external)} registry packages, checksums present; direct pins/features reviewed")
