#!/usr/bin/env python3
"""Pure operation planner, not a privilege issuer or an execution adapter.

Only results from the currently connected providers may populate Evidence.
Repository manifests, Issues, PRs and TOML are never admissible capability
evidence. The destination enforces its own authorization again before use.
"""
from dataclasses import dataclass, field

GITHUB = {
    "source.read": "pull", "source.edit": "push",
    "issues.read": "issues_read", "issues.write": "issues_write",
    "pr.review": "pr_review", "pr.write": "pr_write",
    "ci.inspect": "actions_read",
}
GH_ADMIN = {"labels.read", "labels.sync", "milestones.list",
            "milestones.create", "milestones.update"}
RELAY = {
    "workstation.status": "repo.status",
    "workstation.sources": "repo.list",
    "workstation.inventory": "projects.inventory",
    "workstation.disk": "projects.inventory",
    "workstation.build": "build.start",
    "task.inspect": "task.status",
    "recovery.inspect": "recovery.inspect",
}
RELAY_MUTATIONS = {"workstation.build"}
INTERACTIVE = {"gui.interactive", "terminal.interactive"}


@dataclass(frozen=True)
class Evidence:
    # Observations from active trusted integrations only, never a file or Issue.
    github_capabilities: frozenset[str] = field(default_factory=frozenset)
    gh_authorized: bool = False
    relay_operations: frozenset[str] = field(default_factory=frozenset)
    relay_development_grant: bool = False
    rdc_quota_available: bool = False


@dataclass(frozen=True)
class Decision:
    destination: str | None
    status: str
    explanation: str


def select(operation: str, evidence: Evidence, *, explicit_interactive=False) -> Decision:
    if operation in GITHUB:
        permission = GITHUB[operation]
        if permission in evidence.github_capabilities:
            return Decision("github", "candidate", "provider must authorize every request")
        return Decision(None, "blocked", f"GitHub {permission} unavailable")
    if operation in GH_ADMIN:
        if evidence.gh_authorized:
            return Decision("gh-api", "candidate", "use reviewed gh session; dry-run default")
        return Decision(None, "blocked", "GitHub admin API not authorized")
    if operation in RELAY:
        capability = RELAY[operation]
        if capability not in evidence.relay_operations:
            return Decision(None, "blocked", f"RelayForge {capability} unavailable")
        if operation in RELAY_MUTATIONS and not evidence.relay_development_grant:
            return Decision(None, "blocked", "RelayForge local grant missing")
        return Decision("relayforge", "candidate", "server must revalidate fixed scope and local grant")
    if operation in INTERACTIVE:
        if not explicit_interactive:
            return Decision(None, "operator-required", "RDC is never an automatic fallback")
        if not evidence.rdc_quota_available:
            return Decision(None, "blocked", "RDC quota exhausted; no attempt permitted")
        return Decision(None, "operator-required", "RDC requires a separate manual decision")
    return Decision(None, "blocked", "unknown operation; no fallback")
