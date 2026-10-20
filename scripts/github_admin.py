#!/usr/bin/env python3
"""Bounded GitHub metadata administration via the operator's existing gh login.

No RelayForge tunnel, RDC, CI credentials, shell expansion or token input.
Reads the reviewed default-branch label schema, never deletes labels or
rewrites issue history. All writes need an explicit --apply flag.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import re
import subprocess
import sys

OWNER = "AlexandrShapkin"
PROJECTS = ("codex-smart", "relayforge", "assistant-hub", "rustcraft")
LABEL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9:._-]{0,63}\Z")
COLOR = re.compile(r"[0-9A-Fa-f]{6}\Z")
MAX_BYTES = 65536


class AdminError(Exception):
    pass


class GhAPI:
    def request(self, method: str, endpoint: str, body: dict | None = None):
        if method not in ("GET", "POST", "PATCH"):
            raise AdminError("method denied")
        args = ["gh", "api", "--method", method, endpoint]
        if body is not None:
            args += ["--input", "-"]
        try:
            result = subprocess.run(args, input=json.dumps(body) if body is not None else None,
                                    text=True, capture_output=True, timeout=25, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AdminError("gh unavailable or timed out") from exc
        if result.returncode:
            # Do not echo gh stderr, which might include sensitive auth details.
            raise AdminError("GitHub API rejected operation or authorization")
        if len(result.stdout.encode("utf-8")) > MAX_BYTES * 4:
            raise AdminError("GitHub response too large")
        try:
            return json.loads(result.stdout)
        except (ValueError, TypeError) as exc:
            raise AdminError("invalid GitHub response") from exc


def endpoint(project: str, suffix: str) -> str:
    if project not in PROJECTS:
        raise AdminError("project not allowlisted")
    return f"repos/{OWNER}/{project}/{suffix}"


def paged(api: GhAPI, project: str, collection: str):
    if collection not in ("labels", "milestones?state=all"):
        raise AdminError("collection denied")
    results = []
    for page in range(1, 11):
        join = "&" if "?" in collection else "?"
        part = api.request("GET", endpoint(project, f"{collection}{join}per_page=100&page={page}"))
        if not isinstance(part, list) or len(part) > 100:
            raise AdminError("invalid GitHub collection")
        results.extend(part)
        if len(part) < 100:
            return results
    raise AdminError("GitHub collection exceeds safe pagination limit")


def label_schema(api: GhAPI, project: str) -> list[dict]:
    result = api.request("GET", endpoint(project, "contents/.github/labels.json?ref=main"))
    if not isinstance(result, dict) or result.get("encoding") != "base64":
        raise AdminError("reviewed main label schema unavailable")
    try:
        raw = base64.b64decode(result["content"], validate=False)
        if len(raw) > MAX_BYTES:
            raise ValueError("oversize")
        doc = json.loads(raw)
    except (ValueError, TypeError, KeyError) as exc:
        raise AdminError("invalid label schema") from exc
    if not isinstance(doc, dict) or doc.get("schema_version") != 1:
        raise AdminError("unsupported label schema")
    if set(doc) != {"schema_version", "note", "priority_order", "labels",
                    "legacy_aliases", "not_automated"}:
        raise AdminError("unknown label schema keys")
    labels = doc["labels"]
    if not isinstance(labels, list) or not 0 < len(labels) <= 100:
        raise AdminError("invalid label count")
    seen = set()
    for item in labels:
        if not isinstance(item, dict) or set(item) != {"name", "color", "description"}:
            raise AdminError("invalid label fields")
        name, color, description = item["name"], item["color"], item["description"]
        if not isinstance(name, str) or not LABEL_NAME.fullmatch(name) or name in seen:
            raise AdminError("invalid or duplicate label name")
        if not isinstance(color, str) or not COLOR.fullmatch(color):
            raise AdminError("invalid label color")
        if not isinstance(description, str) or len(description) > 200 or "\n" in description:
            raise AdminError("invalid label description")
        seen.add(name)
    return labels


def plan_labels(api: GhAPI, project: str) -> list[dict]:
    desired = label_schema(api, project)
    current = paged(api, project, "labels")
    by_name = {}
    for label in current:
        if not isinstance(label, dict) or not isinstance(label.get("name"), str):
            raise AdminError("invalid live label")
        if label["name"] in by_name:
            raise AdminError("duplicate live label")
        by_name[label["name"]] = label
    actions = []
    for item in desired:
        old = by_name.get(item["name"])
        new = {"name": item["name"], "color": item["color"].lower(),
               "description": item["description"]}
        if old is None:
            actions.append({"action": "create", "label": new})
        elif (str(old.get("color", "")).lower() != new["color"]
              or (old.get("description") or "") != new["description"]):
            actions.append({"action": "update", "label": new})
    return actions


def sync_labels(api: GhAPI, project: str, apply: bool) -> dict:
    actions = plan_labels(api, project)
    if apply:
        for entry in actions:
            label = entry["label"]
            if entry["action"] == "create":
                api.request("POST", endpoint(project, "labels"), label)
            else:
                # Only exact allowlisted names; never rename or delete.
                api.request("PATCH", endpoint(project, f"labels/{label['name']}"), label)
        # Verify through a fresh read, not success responses alone.
        remaining = plan_labels(api, project)
        if remaining:
            raise AdminError("GitHub labels not yet converged")
    return {"repository": f"{OWNER}/{project}", "mode": "apply" if apply else "dry-run",
            "actions": actions, "verified": bool(apply)}


def milestone_fields(title=None, description=None, state=None, due_on=None):
    fields = {}
    if title is not None:
        if not isinstance(title, str) or not 1 <= len(title) <= 100 or title != title.strip():
            raise AdminError("invalid milestone title")
        fields["title"] = title
    if description is not None:
        if not isinstance(description, str) or len(description) > 1000:
            raise AdminError("invalid milestone description")
        fields["description"] = description
    if state is not None:
        if state not in ("open", "closed"):
            raise AdminError("invalid milestone state")
        fields["state"] = state
    if due_on is not None:
        try:
            parsed = dt.date.fromisoformat(due_on)
        except (TypeError, ValueError) as exc:
            raise AdminError("invalid milestone due date") from exc
        fields["due_on"] = parsed.isoformat() + "T00:00:00Z"
    return fields


def milestones(api: GhAPI, project: str, action: str, apply=False, number=None, **kwargs):
    existing = paged(api, project, "milestones?state=all")
    if action == "list":
        return {"repository": f"{OWNER}/{project}", "milestones": [
            {"number": x["number"], "title": x["title"], "state": x["state"],
             "description": x.get("description"), "due_on": x.get("due_on")}
            for x in existing]}
    fields = milestone_fields(**kwargs)
    if action == "create":
        if "title" not in fields:
            raise AdminError("milestone title required")
        if any(x.get("title") == fields["title"] for x in existing):
            raise AdminError("milestone title already exists; use update")
        target = endpoint(project, "milestones")
        method = "POST"
    elif action == "update":
        if type(number) is not int or number < 1:
            raise AdminError("valid milestone number required")
        record = next((x for x in existing if x.get("number") == number), None)
        if record is None:
            raise AdminError("milestone not found")
        fields = {k: v for k, v in fields.items() if record.get(k) != v}
        target = endpoint(project, f"milestones/{number}")
        method = "PATCH"
    else:
        raise AdminError("operation denied")
    if apply and fields:
        api.request(method, target, fields)
        verified = api.request("GET", target) if action == "update" else paged(api, project, "milestones?state=all")
        if action == "update" and any(verified.get(k) != v for k, v in fields.items()):
            raise AdminError("milestone update not verified")
        if action == "create" and not any(
            all(x.get(k) == v for k, v in fields.items()) for x in verified
        ):
            raise AdminError("milestone creation not verified")
    return {"repository": f"{OWNER}/{project}", "mode": "apply" if apply else "dry-run",
            "action": action, "changes": fields, "verified": bool(apply and fields)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, choices=PROJECTS)
    sub = parser.add_subparsers(dest="operation", required=True)
    labels = sub.add_parser("labels", help="read definitions, plan or explicitly apply")
    labels.add_argument("--apply", action="store_true")
    sub.add_parser("milestones-list")
    create = sub.add_parser("milestones-create")
    update = sub.add_parser("milestones-update")
    for p in (create, update):
        p.add_argument("--title")
        p.add_argument("--description")
        p.add_argument("--state", choices=["open", "closed"])
        p.add_argument("--due-on")
        p.add_argument("--apply", action="store_true")
    update.add_argument("--number", type=int, required=True)
    args = parser.parse_args(argv)
    api = GhAPI()
    try:
        if args.operation == "labels":
            output = sync_labels(api, args.project, args.apply)
        elif args.operation == "milestones-list":
            output = milestones(api, args.project, "list")
        else:
            action = args.operation.removeprefix("milestones-")
            output = milestones(api, args.project, action, apply=args.apply,
                                number=getattr(args, "number", None), title=args.title,
                                description=args.description, state=args.state, due_on=args.due_on)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except AdminError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
