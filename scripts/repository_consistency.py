"""Bounded, read-only declared-source audit; no sync, fetch, SSH or cleanup."""
import json
import os
from pathlib import Path
import re
import stat

import repository_workflow as repo


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate inventory key")
        value[key] = item
    return value


def load(path):
    path = repo.safe_path(path)
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid()
            or info.st_mode & 0o022 or info.st_size > 131072):
        raise ValueError("Unsafe or oversized inventory")
    return json.loads(path.read_bytes(), object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite inventory value")))


def validate(value, root):
    allowed = {"schema", "repositories", "pull_requests", "remote_branches", "snapshots"}
    if (type(value) is not dict or not set(value) <= allowed or value.get("schema") != 1
            or type(value.get("schema")) is not int):
        raise ValueError("Unsupported inventory schema")
    limits = {"repositories": 16, "pull_requests": 200, "remote_branches": 512, "snapshots": 64}
    for key, limit in limits.items():
        if key in value and (type(value[key]) is not list or len(value[key]) > limit):
            raise ValueError("Inventory list budget or type mismatch")
    roots = value.get("repositories", [str(root)])
    if not roots or len(set(roots)) != len(roots):
        raise ValueError("Nonempty unique repository roots required")
    for path in roots:
        repo.safe_path(path, exists=False)
    seen = set()
    for pr in value.get("pull_requests", []):
        if (type(pr) is not dict or set(pr) != {"number", "branch", "head", "state", "merge"}
                or type(pr["number"]) is not int or pr["number"] <= 0 or pr["number"] in seen
                or type(pr["branch"]) is not str or pr["state"] not in {"open", "merged", "closed"}):
            raise ValueError("Malformed or duplicate PR observation")
        seen.add(pr["number"])
        repo.full_sha(pr["head"])
        if pr["state"] == "merged":
            repo.full_sha(pr["merge"])
        elif pr["merge"] is not None:
            raise ValueError("Unmerged PR cannot declare an accepted merge")
    names = set()
    for branch in value.get("remote_branches", []):
        if (type(branch) is not dict or set(branch) != {"branch", "head"}
                or type(branch["branch"]) is not str or branch["branch"] in names):
            raise ValueError("Malformed or duplicate remote branch observation")
        names.add(branch["branch"])
        repo.full_sha(branch["head"])
    names = set()
    for snapshot in value.get("snapshots", []):
        if (type(snapshot) is not dict
                or set(snapshot) != {"name", "host", "path", "sha", "receipt_sha256", "pin", "role"}
                or type(snapshot["name"]) is not str
                or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", snapshot["name"])
                or snapshot["name"] in names or snapshot["host"] not in {"local", "srv0"}
                or snapshot["pin"] not in {"current", "historical", "unknown"}
                or snapshot["role"] not in {"agent", "grader", "development-source"}):
            raise ValueError("Malformed or duplicate snapshot declaration")
        names.add(snapshot["name"])
        if snapshot["path"] is not None:
            repo.safe_path(snapshot["path"], exists=False)
        if snapshot["sha"] is not None:
            repo.full_sha(snapshot["sha"])
        if snapshot["receipt_sha256"] is not None and (not isinstance(snapshot["receipt_sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", snapshot["receipt_sha256"])):
            raise ValueError("Independent source receipt digest required")
    return roots


def compare(root, head, main, proof_root=None):
    if main is None:
        return None
    for candidate in dict.fromkeys([root, proof_root] if proof_root else [root]):
        try:
            return [int(n) for n in repo.git(candidate, "rev-list", "--left-right", "--count", f"{head}...{main}").split()]
        except ValueError:
            pass
    return None  # Missing objects are not evidence of equivalence or divergence.


def classify(root, branch, head, main, prs, proof_root=None):
    matches = [pr for pr in prs if pr["branch"] == branch and pr["head"] == head]
    if any(pr["state"] == "open" for pr in matches):
        return "open-pr", [pr["number"] for pr in matches]
    for pr in matches:
        if pr["state"] == "merged" and main:
            try:
                accepted_root = proof_root or root
                accepted = repo.git(accepted_root, "merge-base", pr["merge"], main) == pr["merge"]
                equal = repo.git(root, "rev-parse", f"{head}^{{tree}}") == repo.git(accepted_root, "rev-parse", f"{pr['merge']}^{{tree}}")
                if accepted and equal:
                    return "merged-content-equivalent", [pr["number"]]
            except ValueError:
                pass
    counts = compare(root, head, main, proof_root)
    if counts is None:
        return "unknown-main-object", [pr["number"] for pr in matches]
    if counts == [0, 0]:
        return "accepted-main", [pr["number"] for pr in matches]
    if counts[0] == 0:
        return "accepted-history", [pr["number"] for pr in matches]
    return "unique-or-squash-unresolved", [pr["number"] for pr in matches]


def changed_metadata(root, records):
    """Detect repeated edits without reading uncommitted/untracked file contents."""
    if len(records) > 4096:
        raise ValueError("Changed-path observation budget exceeded")
    result, rename_source = {}, False
    for record in records:
        if rename_source:
            name, rename_source = record, False
        else:
            if len(record) < 4 or record[2] != " ":
                raise ValueError("Malformed Git status record")
            name = record[3:]
            rename_source = "R" in record[:2] or "C" in record[:2]
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe Git status path")
        path = Path(root) / relative
        repo.safe_path(path.parent, exists=False)
        try:
            info = path.lstat()  # Never follow symlinks or read private working bytes.
            result[name] = {"size": info.st_size, "mtime_ns": info.st_mtime_ns,
                            "ctime_ns": info.st_ctime_ns, "mode": info.st_mode}
        except FileNotFoundError:
            result[name] = {"state": "missing"}
    return result


def _observe(root, main, prs, proof_root=None):
    root = repo.repository(root)
    repo.validate_origin(root)
    registry = repo.worktrees(root)
    refs = repo.git(root, "for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads").splitlines()
    if len(registry) > 128 or len(refs) > 512:
        raise ValueError("Repository inventory budget exceeded")
    trees = []
    for entry in registry:
        path = Path(entry["worktree"])
        row = {"path": str(path), "registered_head": entry.get("HEAD"), "state": "unknown"}
        if not path.exists() and not path.is_symlink():
            row["state"] = "stale-registration"
        else:
            try:
                repo.repository(path)
                repo.validate_origin(path)
                row.update(repo.checkout_state(path))
                row["changed_metadata"] = changed_metadata(path, row["changes"])
                row["state"] = "dirty" if row["changes"] else "clean"
            except (ValueError, OSError):
                row["state"] = "unsafe-or-unavailable"
        trees.append(row)
    branches = []
    for line in refs:
        branch, head = line.rsplit(" ", 1)
        state, links = classify(root, branch, head, main, prs, proof_root)
        associated = [t["path"] for t in trees if t.get("branch") == branch]
        branches.append({"branch": branch, "head": head, "classification": state,
                         "pull_requests": links, "local_only_main_only": compare(root, head, main, proof_root),
                         "worktrees": associated, "cleanup_authorized": False})
    try:
        cached = repo.git(root, "rev-parse", "--verify", "refs/remotes/origin/main^{commit}")
    except ValueError:
        cached = None
    return {"root": str(root), "cached_main": cached,
            "worktrees": trees, "branches": branches}


def audit(root, value=None, *, expected_main=None, github=False):
    root = repo.repository(root)
    repo.validate_origin(root)
    value = {"schema": 1} if value is None else value
    roots = validate(value, root)
    main = repo.full_sha(expected_main) if expected_main is not None else None
    problems, observations = [], []
    freshness = "unknown (offline)"
    if github:
        try:
            observed = repo.remote_main(root)  # Explicit ls-remote only; never fetch/update refs.
            if main is not None and main != observed:
                problems.append("github-main-changed")
            main, freshness = observed, "observed now"
        except (ValueError, OSError):
            freshness = "unavailable; no host/source equivalence inferred"
            problems.append("github-observation-unavailable")
    if main is None:
        problems.append("selected-main-unknown")
    if "snapshots" not in value:
        problems.append("snapshot-scope-undeclared")
    for path in roots:
        try:
            first = _observe(path, main, value.get("pull_requests", []), root)
            second = _observe(path, main, value.get("pull_requests", []), root)
            first["stable_observation"] = first == second
            if not first["stable_observation"]:
                problems.append("concurrent-repository-change")
            if any(t["state"] == "unsafe-or-unavailable" for t in first["worktrees"]):
                problems.append("partial-worktree-inventory")
            if any(b["local_only_main_only"] is None for b in first["branches"]):
                problems.append("main-object-unavailable")
            observations.append(first)
        except (ValueError, OSError):
            observations.append({"root": path, "state": "unavailable"})
            problems.append("repository-inventory-unavailable")
    snapshots = []
    for source in value.get("snapshots", []):
        row = dict(source)
        if source["pin"] == "unknown" or any(source[key] is None for key in ("path", "sha", "receipt_sha256")):
            row["state"] = "missing-deployment-reference"
            problems.append("snapshot-reference-incomplete")
            snapshots.append(row)
            continue
        try:
            accepted = main is not None and repo.git(root, "merge-base", source["sha"], main) == source["sha"]
        except ValueError:
            accepted = False
        if not accepted:
            row["state"] = "unaccepted-or-unavailable-source"
            problems.append("snapshot-source-acceptance-unverified")
        elif source["host"] != "local":
            row["state"] = "unknown-host-side-verification-required"
            problems.append("remote-snapshot-unverified")
        else:
            try:
                row["verification"] = repo.verify_snapshot(source["path"], source["sha"], source["receipt_sha256"])
                row["state"] = ("outdated-current-reference" if source["pin"] == "current" and source["sha"] != main
                                else "verified-historical-pin" if source["pin"] == "historical" else "verified-current-pin")
            except (ValueError, OSError):
                row["state"] = "missing-or-integrity-drift"
        snapshots.append(row)
    # An explicit network observation is checked again to catch changes during the audit.
    if github and freshness == "observed now":
        try:
            if repo.remote_main(root) != main:
                problems.append("github-main-changed-during-audit")
        except (ValueError, OSError):
            problems.append("github-final-observation-unavailable")
    attention = any(s["state"] in {"outdated-current-reference", "missing-or-integrity-drift"} for s in snapshots)
    attention |= any(t["state"] in {"dirty", "stale-registration"} for r in observations for t in r.get("worktrees", []))
    attention |= any(b["classification"] == "unique-or-squash-unresolved" for r in observations for b in r.get("branches", []))
    remote_branches = []
    for branch in value.get("remote_branches", []):
        state, links = classify(root, branch["branch"], branch["head"], main, value.get("pull_requests", []))
        counts = compare(root, branch["head"], main)
        if counts is None:
            problems.append("remote-branch-object-unavailable")
        remote_branches.append({**branch, "classification": state, "pull_requests": links,
                               "local_only_main_only": counts,
                               "cleanup_authorized": False})
    attention |= any(b["classification"] == "unique-or-squash-unresolved" for b in remote_branches)
    complete = not problems
    return {"schema": 1, "canonical": repo.CANONICAL, "selected_main": main,
            "github_freshness": freshness, "complete": complete, "attention_required": attention,
            "problems": sorted(set(problems)), "repositories": observations, "snapshots": snapshots,
            "remote_branches": remote_branches,
            "remote_catalog_freshness": "caller-supplied observation; not refreshed" if "remote_branches" in value else "unknown (undeclared)",
            "exit_code": 2 if not complete else 1 if attention else 0}


def render(report):
    lines = [f"Canonical: {report['canonical']}", f"Selected main: {report['selected_main'] or 'unknown'}",
             f"GitHub freshness: {report['github_freshness']}",
             f"Complete: {report['complete']}; attention required: {report['attention_required']}"]
    for row in report["repositories"]:
        lines.append(f"Repository: {row['root']}")
        branches = {b["branch"]: b for b in row.get("branches", [])}
        for tree in row.get("worktrees", []):
            branch = tree.get("branch", "(unknown/detached)")
            counts = branches.get(branch, {}).get("local_only_main_only")
            divergence = "/".join(map(str, counts)) if counts is not None else "unknown"
            lines.append(f"  {branch}: {tree['state']} {tree.get('head', tree.get('registered_head', 'unknown'))}; local/main-only {divergence}")
        for branch in branches.values():
            if not branch["worktrees"] and branch["classification"] in {"unique-or-squash-unresolved", "unknown-main-object"}:
                lines.append(f"  Unattached branch {branch['branch']}: {branch['classification']}; local/main-only {branch['local_only_main_only']}")
    for row in report["remote_branches"]:
        if row["classification"] in {"unique-or-squash-unresolved", "unknown-main-object"}:
            lines.append(f"Remote observation {row['branch']}: {row['classification']}; local/main-only {row['local_only_main_only']}")
    for row in report["snapshots"]:
        lines.append(f"Snapshot {row['name']} ({row['host']}, {row['pin']}): {row['state']}")
    lines.extend(f"Unresolved: {problem}" for problem in report["problems"])
    return "\n".join(lines) + "\n"
