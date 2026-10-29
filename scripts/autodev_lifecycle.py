"""Bounded supervisor lifecycle; host observations never manufacture authority.

The host is an independently authorized caller, not a repository-selected tool.
No production authority/reviewer enrollment or GitHub adapter is provisioned here.
"""
import re


class LifecycleRefused(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise LifecycleRefused(reason)


def sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


PHASES = {"awaiting-review", "findings", "revising", "awaiting-ci",
          "merge-pending", "merged", "verified", "cancelled"}


def validate(record):
    require(isinstance(record, dict) and set(record) == {
        "schema", "phase", "head", "base", "pr", "attempts", "review",
        "findings", "merge_sha"}, "invalid lifecycle receipt")
    require(type(record["schema"]) is int and record["schema"] == 1
            and isinstance(record["phase"], str) and record["phase"] in PHASES,
            "unknown lifecycle version or phase")
    require(sha(record["head"]) and sha(record["base"]), "invalid lifecycle SHA")
    require(type(record["pr"]) is int and record["pr"] > 0, "invalid PR")
    require(type(record["attempts"]) is int and 0 <= record["attempts"] <= 2,
            "invalid retry count")
    require(record["merge_sha"] is None or sha(record["merge_sha"]), "invalid merge SHA")
    review = record["review"]
    require(review is None or (isinstance(review, dict) and set(review) == {
        "reviewer", "head", "base"} and sha(review["head"]) and sha(review["base"])
        and isinstance(review["reviewer"], str) and 0 < len(review["reviewer"]) <= 80),
        "invalid review binding")
    findings = record["findings"]
    require(isinstance(findings, list) and len(findings) <= 4, "invalid findings")
    for item in findings:
        require(isinstance(item, dict) and set(item) == {"id", "path", "instruction"}
                and all(isinstance(item[k], str) and 0 < len(item[k]) <= limit
                        for k, limit in (("id", 80), ("path", 180), ("instruction", 1200))),
                "invalid actionable finding")
    require(len({item["id"] for item in findings}) == len(findings), "duplicate findings")
    return record


class Lifecycle:
    """One observed PR, two revisions at most; persist before uncertain effects.

    Host contract: observe() returns fresh authenticated facts and complete live
    protection/review/thread/check evaluation, including synthetic integration
    checks. None/Unknown must be False, never guessed. review() obtains an
    independently authenticated review, not a candidate-authored JSON claim.
    authorized() checks current owner provenance, scope, veto and revocation.
    merge() MUST enforce both expected head and base atomically, or refuse.
    postmerge() verifies ancestry/content and exact merge-SHA CI/Security.
    These are trust requirements on the operator host, not supplied credentials.
    """
    def __init__(self, state, save, host, *, revise=None, cancelled=None):
        self.state = state
        self.save = save
        self.host = host
        self.revise = revise or host.revise
        self.cancelled = cancelled or (lambda: None)
        if "lifecycle" in state:
            validate(state["lifecycle"])

    @property
    def record(self):
        require("lifecycle" in self.state, "lifecycle not attached")
        return self.state["lifecycle"]

    def persist(self):
        validate(self.record)
        self.save(self.state)

    def observe(self):
        facts = self.host.observe()
        require(isinstance(facts, dict) and sha(facts.get("head"))
                and sha(facts.get("base")) and type(facts.get("pr")) is int,
                "unknown remote identity")
        if "lifecycle" in self.state:
            require(facts["pr"] == self.record["pr"], "PR identity changed")
        require(facts.get("repository") == self.host.repository
                and facts.get("branch") == self.state["branch"], "remote scope mismatch")
        return facts

    def attach(self):
        require("lifecycle" not in self.state and self.state["phase"] in {"published", "publishing"},
                "attach requires verified Draft publication")
        facts = self.observe()
        require(facts.get("state") == "OPEN" and facts.get("draft") is True
                and facts["head"] == self.state["head"], "unverified Draft PR")
        self.state["phase"] = "published"
        self.state["draft_pr_created"] = True
        self.state["lifecycle"] = {
            "schema": 1, "phase": "awaiting-review", "head": facts["head"],
            "base": facts["base"], "pr": facts["pr"], "attempts": 0,
            "review": None, "findings": [], "merge_sha": None}
        self.persist()

    def current(self):
        facts = self.observe()
        require(facts.get("state") == "OPEN" and facts["head"] == self.record["head"]
                and facts["base"] == self.record["base"], "stale head/base or closed PR")
        return facts

    def review(self, allowed_paths):
        record = self.record
        require(record["phase"] == "awaiting-review", "review not admissible")
        self.current()
        result = self.host.review(record["head"], record["base"])
        require(isinstance(result, dict) and result.get("authenticated") is True
                and result.get("head") == record["head"]
                and result.get("base") == record["base"]
                and isinstance(result.get("reviewer"), str)
                and 0 < len(result["reviewer"]) <= 80
                and result["reviewer"] != self.host.implementer,
                "missing independent exact-head review")
        self.current()  # review may have taken long enough for the base to move
        findings = result.get("findings")
        require(isinstance(findings, list), "unknown review findings")
        candidate = dict(record, findings=findings)
        validate(candidate)
        require(all(f["path"] in allowed_paths for f in findings), "finding outside task scope")
        require(isinstance(result.get("verdict"), str)
                and result["verdict"] in {"ACCEPT", "CHANGES"}, "unknown verdict")
        require((result["verdict"] == "ACCEPT") == (not findings),
                "acceptance with unresolved findings or unactionable rejection")
        record["findings"] = findings
        record["review"] = None
        if findings:
            record["phase"] = "findings"
        else:
            record["review"] = {k: result[k] for k in ("reviewer", "head", "base")}
            record["phase"] = "awaiting-ci"
        self.persist()

    def retry(self):
        record = self.record
        require(record["phase"] == "findings" and record["findings"], "no actionable findings")
        require(record["attempts"] < 2, "finding retry budget exhausted")
        self.current()
        require(self.host.authorized("revise", record["head"], record["base"]) is True,
                "revision authority unknown or revoked")
        record["attempts"] += 1
        record["phase"] = "revising"
        self.persist()  # a crash consumes this attempt; never automatically replay
        # Host reuses run_task/commit_stage with the original scope and all gates.
        head = self.revise(record["head"], record["findings"])
        require(sha(head) and head != record["head"], "revision not verified")
        record["head"] = head
        record["review"] = None
        record["findings"] = []
        record["phase"] = "awaiting-review"
        self.state["head"] = head
        self.persist()

    def cancel(self):
        require(self.record["phase"] not in {"merge-pending", "merged", "verified"},
                "reconcile irreversible merge before cancellation")
        self.record["phase"] = "cancelled"
        self.record["review"] = None
        self.persist()

    def reconcile(self):
        """Observe, never repeat an uncertain revise/merge operation."""
        record = self.record
        require(record["phase"] != "cancelled", "run cancelled")
        facts = self.observe()
        if record["phase"] == "merge-pending":
            require(facts.get("state") == "MERGED" and facts["head"] == record["head"]
                    and sha(facts.get("merge_sha")), "merge outcome remains unknown")
            record["merge_sha"] = facts["merge_sha"]
            record["phase"] = "merged"
            self.persist()
            return
        require(record["phase"] != "revising", "revision outcome requires operator reconciliation")
        require(facts.get("state") == "OPEN" and facts["head"] == record["head"],
                "unexpected remote head/state")
        if facts["base"] != record["base"]:
            record["base"] = facts["base"]
            record["review"] = None
            record["findings"] = []
            record["phase"] = "awaiting-review"
            self.persist()

    def integrate(self):
        record = self.record
        require(record["phase"] == "awaiting-ci", "integration not admissible")
        # Specific vetoes override every generic owner grant and every host fact.
        require(not (self.host.repository.casefold() == "alexandrshapkin/codex-smart"
                     and record["pr"] in {125, 164}), "protected PR cannot be activated or merged")
        facts = self.current()
        require(record["review"] is not None and record["review"]["head"] == record["head"]
                and record["review"]["base"] == record["base"], "review stale")
        require(facts.get("checks_head") == record["head"]
                and facts.get("checks_base") == record["base"]
                and facts.get("checks_app") == 15368, "stale or untrusted CI evidence")
        require(all(facts.get(key) is True for key in (
            "ci", "security", "integration_checks", "protection", "formal_reviews", "threads")),
            "required checks, protection or review blockers unknown/failed")
        require(self.host.authorized("merge", record["head"], record["base"]) is True,
                "merge authority unknown or revoked")
        self.cancelled()
        record["phase"] = "merge-pending"
        self.persist()  # before any Ready/merge side effect, ambiguity is durable
        self.cancelled()
        self.host.merge(expected_head=record["head"], expected_base=record["base"])
        self.reconcile()

    def verify(self):
        record = self.record
        require(record["phase"] == "merged", "no observed merge to verify")
        require(self.host.postmerge(record["merge_sha"], record["head"]) is True,
                "post-merge ancestry/content or exact-SHA CI/Security unverified")
        record["phase"] = "verified"
        self.persist()
