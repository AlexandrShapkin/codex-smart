"""Offline representative lifecycle proof; no credentials or live GitHub writes."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "autodev_lifecycle", Path(__file__).with_name("autodev_lifecycle.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

HEAD, BASE, REVISION, MERGE = (x * 40 for x in "abcd")
FINDING = {"id": "F1", "path": "small.py", "instruction": "Add the missing edge case test"}


class FakeHost:
    repository = "example/sandbox"
    implementer = "author-session"

    def __init__(self):
        self.facts = dict(pr=42, head=HEAD, base=BASE, repository=self.repository,
                          branch="autodev/test", state="OPEN", draft=True,
                          ci=True, security=True, integration_checks=True, protection=True,
                          formal_reviews=True, threads=True, checks_head=HEAD,
                          checks_base=BASE, checks_app=15368)
        self.result = dict(authenticated=True, reviewer="independent-session",
                           head=HEAD, base=BASE, verdict="ACCEPT", findings=[])
        self.authority = True
        self.merge_calls = self.revise_calls = 0
        self.postmerge_ok = True
        self.crash = False

    def observe(self):
        return copy.deepcopy(self.facts)

    def review(self, head, base):
        return copy.deepcopy(self.result)

    def authorized(self, operation, head, base):
        return self.authority

    def revise(self, head, findings):
        self.revise_calls += 1
        if self.crash:
            raise TimeoutError("revision acknowledgement lost")
        self.facts.update(head=REVISION, checks_head=REVISION)
        return REVISION

    def merge(self, *, expected_head, expected_base):
        self.merge_calls += 1
        if (expected_head, expected_base) != (self.facts["head"], self.facts["base"]):
            raise module.LifecycleRefused("remote compare-and-swap rejected")
        self.facts.update(state="MERGED", merge_sha=MERGE)
        if self.crash:
            raise TimeoutError("merge acknowledgement lost")

    def postmerge(self, merge_sha, head):
        assert merge_sha == MERGE
        return self.postmerge_ok


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.state = dict(phase="published", head=HEAD, branch="autodev/test")
        self.host = FakeHost()
        self.saved = []
        self.controller = module.Lifecycle(self.state, self.save, self.host)
        self.controller.attach()

    def save(self, state):
        self.saved.append(copy.deepcopy(state))

    def accept(self):
        self.controller.review({"small.py"})

    def test_findings_revision_independent_accept_ci_merge_and_verification(self):
        self.host.result.update(verdict="CHANGES", findings=[FINDING])
        self.controller.review({"small.py"})
        self.controller.retry()
        self.assertEqual(self.saved[-2]["lifecycle"]["phase"], "revising")
        self.assertIsNone(self.controller.record["review"])
        self.assertEqual(self.state["head"], REVISION)
        self.host.result.update(head=REVISION, verdict="ACCEPT", findings=[])
        self.accept()
        self.controller.integrate()
        self.assertEqual(self.saved[-2]["lifecycle"]["phase"], "merge-pending")
        self.controller.verify()
        restored = module.Lifecycle(copy.deepcopy(self.saved[-1]), self.save, self.host)
        self.assertEqual(restored.record["phase"], "verified")
        self.assertEqual((self.host.revise_calls, self.host.merge_calls), (1, 1))

    def test_failed_unknown_or_stale_gates_never_merge(self):
        self.accept()
        good = copy.deepcopy(self.host.facts)
        for key, value in [("ci", False), ("security", None), ("integration_checks", False),
                           ("protection", None), ("formal_reviews", False), ("threads", None),
                           ("checks_head", BASE), ("checks_base", HEAD), ("checks_app", 7),
                           ("head", BASE), ("base", HEAD)]:
            with self.subTest(key=key):
                self.host.facts = dict(good, **{key: value})
                with self.assertRaises(module.LifecycleRefused):
                    self.controller.integrate()
        self.assertEqual(self.host.merge_calls, 0)

    def test_unknown_revoked_authority_and_specific_veto_override_green(self):
        self.accept()
        for authority in (False, None):
            self.host.authority = authority
            with self.assertRaises(module.LifecycleRefused):
                self.controller.integrate()
        self.host.authority = True
        self.host.repository = "aLeXaNdRsHaPkIn/CODEX-smart"
        self.host.facts["repository"] = self.host.repository
        for number in (125, 164):
            self.controller.record["pr"] = self.host.facts["pr"] = number
            with self.assertRaisesRegex(module.LifecycleRefused, "protected PR"):
                self.controller.integrate()
        self.assertEqual(self.host.merge_calls, 0)

    def test_review_must_be_independent_authenticated_current_and_actionable(self):
        good = copy.deepcopy(self.host.result)
        for changes in ({"reviewer": self.host.implementer}, {"authenticated": None},
                        {"head": BASE}, {"base": HEAD}, {"verdict": "UNKNOWN"},
                        {"verdict": "CHANGES", "findings": []},
                        {"findings": [FINDING]},
                        {"verdict": "CHANGES", "findings": [dict(FINDING, path="other.py")]},
                        {"verdict": "CHANGES", "findings": [FINDING, FINDING]}):
            self.host.result = dict(good, **changes)
            with self.assertRaises(module.LifecycleRefused):
                self.accept()
        self.assertEqual(self.controller.record["phase"], "awaiting-review")

    def test_base_movement_invalidates_review_and_requires_fresh_ci(self):
        self.accept()
        self.host.facts["base"] = REVISION
        self.controller.reconcile()
        self.assertEqual(self.controller.record["phase"], "awaiting-review")
        self.assertIsNone(self.controller.record["review"])
        with self.assertRaises(module.LifecycleRefused):
            self.controller.integrate()

    def test_ambiguous_merge_reconciles_without_duplicate_effect(self):
        self.accept()
        self.host.crash = True
        with self.assertRaises(TimeoutError):
            self.controller.integrate()
        restored = module.Lifecycle(copy.deepcopy(self.saved[-1]), self.save, self.host)
        with self.assertRaises(module.LifecycleRefused):
            restored.integrate()
        restored.reconcile()
        restored.verify()
        self.assertEqual(self.host.merge_calls, 1)

    def test_open_pr_after_ambiguous_merge_stays_unknown(self):
        self.accept()
        self.controller.record["phase"] = "merge-pending"
        with self.assertRaises(module.LifecycleRefused):
            self.controller.reconcile()
        with self.assertRaises(module.LifecycleRefused):
            self.controller.cancel()
        self.assertEqual(self.host.merge_calls, 0)

    def test_ambiguous_revision_is_never_replayed(self):
        self.host.result.update(verdict="CHANGES", findings=[FINDING])
        self.accept()
        self.host.crash = True
        with self.assertRaises(TimeoutError):
            self.controller.retry()
        restored = module.Lifecycle(copy.deepcopy(self.saved[-1]), self.save, self.host)
        for action in (restored.retry, restored.reconcile):
            with self.assertRaises(module.LifecycleRefused):
                action()
        self.assertEqual(self.host.revise_calls, 1)

    def test_retry_budget_and_cancel_are_terminal(self):
        self.host.result.update(verdict="CHANGES", findings=[FINDING])
        self.accept()
        self.controller.record["attempts"] = 2
        with self.assertRaisesRegex(module.LifecycleRefused, "budget"):
            self.controller.retry()
        self.controller.cancel()
        for action in (self.controller.retry, self.controller.integrate, self.controller.reconcile):
            with self.assertRaises(module.LifecycleRefused):
                action()
        self.assertEqual(self.host.revise_calls, 0)

    def test_postmerge_failure_is_visible_and_can_be_reobserved(self):
        self.accept()
        self.controller.integrate()
        self.host.postmerge_ok = False
        with self.assertRaises(module.LifecycleRefused):
            self.controller.verify()
        self.assertEqual(self.controller.record["phase"], "merged")
        self.host.postmerge_ok = True
        self.controller.verify()

    def test_cancellation_during_authority_observation_blocks_merge(self):
        self.accept()
        requested = []
        def authority(*args):
            requested.append(True)
            return True
        def cancelled():
            if requested:
                raise module.LifecycleRefused("cancelled")
        self.host.authorized = authority
        self.controller.cancelled = cancelled
        with self.assertRaisesRegex(module.LifecycleRefused, "cancelled"):
            self.controller.integrate()
        self.assertEqual(self.host.merge_calls, 0)
        self.assertEqual(self.controller.record["phase"], "awaiting-ci")

    def test_malformed_restored_receipt_is_rejected(self):
        self.state["lifecycle"]["attempts"] = -1
        with self.assertRaises(module.LifecycleRefused):
            module.Lifecycle(self.state, self.save, self.host)


if __name__ == "__main__":
    unittest.main()
