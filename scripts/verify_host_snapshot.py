"""Read-only source/runtime identity report. No processes, SSH, repairs or grading."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

import benchmark_host as host
import benchmark_submission_grading as grading
import repository_workflow as repository


def file(path):
    path = repository.safe_path(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o022:
        raise ValueError("unsafe identity file")
    return path


def runtime_identity(root, inventory):
    """Check frozen bytes only; deliberately does not call prepare_runtime/probes.

    The grading implementation is evidence-pinned and must not be refactored merely
    to remove its executable host probes. Reuse its reviewed manifest parsers and
    contract while inspecting the same inventory without executing any binary.
    """
    root, inventory = repository.safe_path(root), repository.safe_path(inventory)
    repository.snapshot_directory(root)
    repository.snapshot_directory(inventory)
    if root.parent != Path("/tmp") or not root.name.startswith("benchmark-runtime-"):
        raise ValueError("unexpected runtime staging root")
    if {p.name for p in root.iterdir()} != {"python", "rust", "go", "libraries", "linker", "grader"}:
        raise ValueError("runtime role mismatch")
    contract = grading.load_contract()
    expected = contract["runtime_inventory"]
    hashes = {}
    paths = {}
    for kind in ("files", "symlinks", "dirs"):
        paths[kind] = file(inventory / f"runtime-{kind}.tsv")
        if paths[kind].stat().st_size > 32 * 1024 * 1024:
            raise ValueError("oversized runtime manifest")
        hashes[kind] = grading._sha256(paths[kind])
        if hashes[kind] != expected[f"{kind}_manifest_sha256"]:
            raise ValueError("runtime manifest identity mismatch")
    files = grading._parse_file_manifest(paths["files"])
    links = grading._parse_symlink_manifest(paths["symlinks"])
    dirs = grading._parse_dir_manifest(paths["dirs"])
    if (len(files), len(links), len(dirs)) != (
            expected["regular_file_count"], expected["symlink_count"], expected["directory_count"]):
        raise ValueError("runtime inventory count mismatch")
    seen = {"files": set(), "symlinks": set(), "dirs": set()}
    for current, directories, names in os.walk(root, followlinks=False):
        current = Path(current)
        if current != root:
            repository.safe_path(current)
            seen["dirs"].add(current.relative_to(root).as_posix())
        for name in list(directories) + names:
            path = current / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                seen["symlinks"].add(relative)
                if name in directories:
                    directories.remove(name)
            elif name in names:
                if not stat.S_ISREG(path.lstat().st_mode):
                    raise ValueError("runtime special node")
                seen["files"].add(relative)
    if seen != {"files": set(files), "symlinks": set(links), "dirs": set(dirs)}:
        raise ValueError("runtime topology mismatch")
    for relative, (digest, size, mode) in files.items():
        path = file(root / relative)
        info = path.stat()
        if info.st_size != size or stat.S_IMODE(info.st_mode) != mode or grading._sha256(path) != digest:
            raise ValueError("runtime file drift")
    for relative, (mode, target) in links.items():
        path = root / relative
        if stat.S_IMODE(path.lstat().st_mode) != mode or os.readlink(path) != target:
            raise ValueError("runtime link drift")
    for relative, mode in dirs.items():
        if stat.S_IMODE((root / relative).stat().st_mode) != mode:
            raise ValueError("runtime directory drift")
    if file(root / "grader/repository-head.txt").read_text().strip() != contract["runtime_repository_head"]:
        raise ValueError("runtime source mismatch")
    # Validates the frozen grading implementation, controller and supervisor pins.
    candidate = grading.load_candidate_evidence()
    reference = hashlib.sha256(json.dumps({**hashes, "head": contract["runtime_repository_head"]},
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"status": "PASS", "inventory_reference": reference,
            "repository_head": contract["runtime_repository_head"], "manifest_sha256": hashes,
            "production_grading_reference": candidate["evidence_reference"],
            "implementation_sha256": candidate["candidate"]["implementation_sha256"]}


def inspect(snapshot, source_sha, receipt_sha256, *, runtime_root=None,
            inventory_dir=None, qualification=None, qualification_sha256=None):
    result = {"schema": 1, "scope": "source bytes, runtime bytes and saved qualification receipt",
              "expected_source": None, "observed_source": None,
              "source": "NOT VERIFIED", "runtime": "NOT VERIFIED",
              "qualification": "NOT VERIFIED", "physical_host_attested": False,
              "fresh_host_qualification": "NOT VERIFIED", "operation_authorized": False}
    phase = "source"
    try:
        result["expected_source"] = repository.full_sha(source_sha)
        if not repository.safe_path(snapshot, exists=False).exists():
            raise FileNotFoundError("source snapshot missing")
        result["source"] = repository.verify_snapshot(snapshot, source_sha, receipt_sha256)
        result["observed_source"] = result["source"]["source_sha"]
        supplied = (runtime_root, inventory_dir, qualification, qualification_sha256)
        if not any(value is not None for value in supplied):
            result.update(status="NOT VERIFIED", exit_code=2)
            return result
        if not all(value is not None for value in supplied):
            raise ValueError("all runtime and qualification identities are required")
        phase = "qualification"
        if not re.fullmatch(r"[0-9a-f]{64}", qualification_sha256):
            raise ValueError("independent qualification digest required")
        evidence = file(qualification)
        if grading._sha256(evidence) != qualification_sha256:
            raise ValueError("qualification receipt mismatch")
        qualified = host.load_evidence(evidence)
        if not grading.contract_verified(qualified):
            raise ValueError("qualification is not accepted by the frozen production contract")
        result["qualification"] = {"status": "PASS", "reference": qualified.reference,
                                    "receipt_sha256": qualification_sha256}
        phase = "runtime"
        result["runtime"] = runtime_identity(runtime_root, inventory_dir)
        result.update(status="PASS", exit_code=0)
    except (FileNotFoundError, PermissionError) as error:
        result.update(status="BLOCKED BY ENVIRONMENT" if isinstance(error, PermissionError) else "NOT VERIFIED",
                      failed_phase=phase, exit_code=2)
    except (ValueError, TypeError, KeyError, OSError):
        result.update(status="FAIL", failed_phase=phase, exit_code=1)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--receipt-sha256", required=True)
    for name in ("runtime-root", "inventory-dir", "qualification", "qualification-sha256"):
        parser.add_argument(f"--{name}")
    result = inspect(**vars(parser.parse_args()))
    print(json.dumps(result, sort_keys=True, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
