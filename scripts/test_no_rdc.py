import base64
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from github_admin import AdminError, label_schema, milestones, plan_labels, sync_labels
from development_router import Decision, Evidence, select

SCHEMA = {
    "schema_version": 1, "note": "", "priority_order": ["priority:P0"],
    "labels": [{"name": "priority:P0", "color": "B60205", "description": "Critical"}],
    "legacy_aliases": [], "not_automated": [],
}


class FakeAPI:
    def __init__(self, schema=None, labels=None, milestones_=None):
        self.schema = SCHEMA if schema is None else schema
        self.labels = list(labels or [])
        self.milestones = list(milestones_ or [])
        self.calls = []

    def request(self, method, endpoint, body=None):
        self.calls.append((method, endpoint, body))
        if "contents/.github/labels.json" in endpoint:
            return {"encoding": "base64", "content": base64.b64encode(
                json.dumps(self.schema).encode()).decode()}
        if endpoint.endswith("labels?per_page=100&page=1"):
            return self.labels.copy()
        if "/labels/" in endpoint and method == "PATCH":
            name = endpoint.rsplit("/", 1)[1]
            next(x for x in self.labels if x["name"] == name).update(body)
            return body
        if endpoint.endswith("/labels") and method == "POST":
            if any(x["name"].casefold() == body["name"].casefold() for x in self.labels):
                raise AdminError("GitHub label already exists (case-insensitive)")
            self.labels.append(dict(body))
            return body
        if "milestones?state=all" in endpoint:
            return self.milestones.copy()
        if "/milestones/" in endpoint and method == "GET":
            number = int(endpoint.rsplit("/", 1)[1])
            return next(x for x in self.milestones if x["number"] == number)
        if "/milestones/" in endpoint and method == "PATCH":
            number = int(endpoint.rsplit("/", 1)[1])
            next(x for x in self.milestones if x["number"] == number).update(body)
            return body
        if endpoint.endswith("/milestones") and method == "POST":
            created = {"number": len(self.milestones) + 1, "state": "open", **body}
            self.milestones.append(created)
            return created
        raise AssertionError((method, endpoint))


class GitHubAdminTests(unittest.TestCase):
    def test_dry_run_does_not_write(self):
        api = FakeAPI()
        plan = sync_labels(api, "relayforge", False)
        self.assertEqual(plan["actions"][0]["action"], "create")
        self.assertTrue(all(method == "GET" for method, _, _ in api.calls))

    def test_apply_and_converge_idempotently(self):
        api = FakeAPI()
        self.assertTrue(sync_labels(api, "rustcraft", True)["verified"])
        writes = len([x for x in api.calls if x[0] != "GET"])
        self.assertEqual(writes, 1)
        self.assertEqual(plan_labels(api, "rustcraft"), [])
        sync_labels(api, "rustcraft", True)
        self.assertEqual(writes, len([x for x in api.calls if x[0] != "GET"]))

    def test_update_is_exact_and_non_destructive(self):
        api = FakeAPI(labels=[{"name": "priority:P0", "color": "ffffff", "description": "Old"},
                               {"name": "legacy", "color": "111111", "description": "keep"}])
        sync_labels(api, "codex-smart", True)
        self.assertEqual(len(api.labels), 2)
        self.assertEqual(api.labels[1]["name"], "legacy")

    def test_case_only_difference_is_an_empty_dry_run(self):
        for name in ["priority:P0", "Priority:P0", "PRIORITY:P0"]:
            with self.subTest(name=name):
                api = FakeAPI(labels=[{"name": name, "color": "b60205", "description": "Critical"}])
                self.assertEqual(sync_labels(api, "relayforge", False)["actions"], [])
                sync_labels(api, "relayforge", True)
                self.assertTrue(all(call[0] == "GET" for call in api.calls))
                self.assertEqual(api.labels[0]["name"], name)

    def test_casefold_update_keeps_actual_name_and_converges(self):
        api = FakeAPI(labels=[{"name": "Priority:P0", "color": "ffffff", "description": "Old"}])
        plan = sync_labels(api, "relayforge", False)
        self.assertEqual(plan["actions"], [{"action": "update", "label": {
            "name": "Priority:P0", "color": "b60205", "description": "Critical"}}])
        sync_labels(api, "relayforge", True)
        writes = [call for call in api.calls if call[0] != "GET"]
        self.assertEqual(len(writes), 1)
        method, path, body = writes[0]
        self.assertEqual(method, "PATCH")
        self.assertTrue(path.endswith("/labels/Priority:P0"))
        self.assertEqual(body["name"], "Priority:P0")
        self.assertNotIn("new_name", body)
        self.assertEqual(api.labels[0]["name"], "Priority:P0")
        self.assertEqual(sync_labels(api, "relayforge", False)["actions"], [])
        sync_labels(api, "relayforge", True)
        self.assertEqual(writes, [call for call in api.calls if call[0] != "GET"])

    def test_case_colliding_schema_is_rejected_without_writes(self):
        schema = {**SCHEMA, "labels": [SCHEMA["labels"][0],
                  {**SCHEMA["labels"][0], "name": "Priority:P0"}]}
        api = FakeAPI(schema=schema)
        with self.assertRaises(AdminError):
            sync_labels(api, "relayforge", True)
        self.assertTrue(all(call[0] == "GET" for call in api.calls))

    def test_case_colliding_live_definitions_are_rejected(self):
        api = FakeAPI(labels=[{"name": "priority:P0"}, {"name": "Priority:P0"}])
        with self.assertRaises(AdminError):
            sync_labels(api, "relayforge", True)
        self.assertTrue(all(call[0] == "GET" for call in api.calls))

    def test_unknown_project_denied(self):
        with self.assertRaises(AdminError):
            plan_labels(FakeAPI(), "../outside")

    def test_duplicate_schema_label_denied(self):
        doc = {**SCHEMA, "labels": SCHEMA["labels"] * 2}
        with self.assertRaises(AdminError):
            label_schema(FakeAPI(schema=doc), "relayforge")

    def test_injected_label_name_denied(self):
        doc = {**SCHEMA, "labels": [{"name": "test;id", "color": "FFFFFF", "description": ""}]}
        with self.assertRaises(AdminError):
            label_schema(FakeAPI(schema=doc), "relayforge")

    def test_unknown_schema_field_denied(self):
        with self.assertRaises(AdminError):
            label_schema(FakeAPI(schema={**SCHEMA, "auth": "allow"}), "relayforge")

    def test_bad_color_denied(self):
        doc = {**SCHEMA, "labels": [{"name": "good", "color": "red", "description": ""}]}
        with self.assertRaises(AdminError):
            label_schema(FakeAPI(schema=doc), "relayforge")

    def test_milestone_create_dry_run_and_apply(self):
        api = FakeAPI()
        milestones(api, "relayforge", "create", title="Release 1", apply=False)
        self.assertFalse(any(c[0] == "POST" for c in api.calls))
        self.assertTrue(milestones(api, "relayforge", "create", title="Release 1", apply=True)["verified"])
        with self.assertRaises(AdminError):
            milestones(api, "relayforge", "create", title="Release 1", apply=True)

    def test_milestone_update_requires_existing_number(self):
        api = FakeAPI()
        with self.assertRaises(AdminError):
            milestones(api, "relayforge", "update", number=0, title="Other")
        with self.assertRaises(AdminError):
            milestones(api, "relayforge", "update", number=1, title="Other")

    def test_bad_due_date_denied(self):
        with self.assertRaises(AdminError):
            milestones(FakeAPI(), "rustcraft", "create", title="Q", due_on="tomorrow")

    def test_milestone_no_op(self):
        api = FakeAPI(milestones_=[{"number": 1, "title": "A", "state": "open"}])
        milestones(api, "relayforge", "update", number=1, title="A", apply=True)
        self.assertFalse(any(c[0] == "PATCH" for c in api.calls))


class RouterTests(unittest.TestCase):
    def test_github_source_first(self):
        self.assertEqual(select("source.edit", Evidence(github_capabilities=frozenset({"push"}))).destination, "github")

    def test_admin_no_implicit_connector_write(self):
        self.assertEqual(select("labels.sync", Evidence(github_capabilities=frozenset({"push"}))).status, "blocked")

    def test_relay_capability_and_grant_needed(self):
        e = Evidence(relay_operations=frozenset({"build.start"}))
        self.assertEqual(select("workstation.build", e).status, "blocked")
        self.assertEqual(select("workstation.build", Evidence(
            relay_operations=e.relay_operations, relay_development_grant=True)).destination, "relayforge")

    def test_no_rdc_fallback_even_when_requested(self):
        for op in ("source.edit", "workstation.inventory", "gui.interactive", "unknown"):
            d = select(op, Evidence(rdc_quota_available=True))
            self.assertIsNone(d.destination)
        self.assertEqual(select("gui.interactive", Evidence(), explicit_interactive=True).status, "blocked")

    def test_unknown_manifest_never_grants(self):
        self.assertEqual(select("shell.unrestricted", Evidence()).status, "blocked")


if __name__ == "__main__":
    unittest.main()
