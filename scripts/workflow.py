"""Repository-owned stage context and documentation checks; stdlib, offline only."""
import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
CONTEXT_BYTES = 8192
FILE_BYTES = 131072
ROLES = {"current", "contract", "reference", "historical", "generated", "input"}
SECTIONS = {"Scope", "Non-goals", "Acceptance", "Validation", "Context", "Follow-ups"}


class Repository:
    def __init__(self, root):
        self.root = root.resolve()
        self.stages = self.load("docs/stages.json")
        self.docs = self.load("docs/documents.json")
        self.issue_map = self.load("docs/issues/github-map.json")

    def path(self, name):
        if not isinstance(name, str):
            raise ValueError("Repository path must be a string")
        path = self.root / name
        if (Path(name).is_absolute()
                or ".." in Path(name).parts or path.resolve() != path
                or not path.exists()):
            raise ValueError("Invalid, missing or symlinked repository path")
        return path

    def read(self, name):
        path = self.path(name)
        if not path.is_file() or path.stat().st_size > FILE_BYTES:
            raise ValueError("Document missing or exceeds read budget")
        return path.read_text(encoding="utf-8")

    def load(self, name):
        return json.loads(self.read(name))

    def validate(self):
        if (set(self.stages) != {"schema", "active", "stages"}
                or self.stages["schema"] != 1
                or set(self.docs) != {"schema", "documents"} or self.docs["schema"] != 1):
            raise ValueError("Unsupported registry schema")
        stages = self.stages["stages"]
        documents = self.docs["documents"]
        if not 1 <= len(stages) <= 32 or not 1 <= len(documents) <= 128:
            raise ValueError("Registry item budget exceeded")
        ids = [s["id"] for s in stages]
        if len(set(ids)) != len(ids) or self.stages["active"] not in ids:
            raise ValueError("Duplicate stage or invalid active stage")
        known_docs = {d["path"] for d in documents}
        by_path = {d["path"]: d for d in documents}
        if len(known_docs) != len(documents):
            raise ValueError("Duplicate document")
        fields = {"id", "title", "milestone", "progress", "depends_on", "issues",
                  "contract", "reads", "sources", "evidence"}
        for stage in stages:
            if (set(stage) != fields or not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", stage["id"])
                    or stage["progress"] not in {"planned", "active", "validated", "partial"}
                    or not stage["issues"] or len(stage["reads"]) > 12
                    or stage["milestone"] not in {"0.1 Foundation", "0.2 Router v2", "0.3 Development Benchmark", "0.4 Hardening", "1.0 Stable"}
                    or not self.metadata(stage["title"])):
                raise ValueError("Invalid stage record")
            if (stage["contract"] not in by_path
                    or by_path[stage["contract"]]["role"] != "contract"
                    or stage["id"] not in by_path[stage["contract"]]["stages"]):
                raise ValueError("Stage contract ownership/role mismatch")
            if stage["progress"] == "validated" and not stage["evidence"]:
                raise ValueError("Validated stage requires recorded evidence")
            for issue in stage["issues"]:
                if type(issue) is not int or str(issue) not in self.issue_map:
                    raise ValueError("Stage issue has no canonical GitHub mapping")
                record = self.issue_map[str(issue)]
                if record != {"number": issue, "url": f"https://github.com/AlexandrShapkin/codex-smart/issues/{issue}"}:
                    raise ValueError("Invalid GitHub issue mapping")
            for dependency in stage["depends_on"]:
                if dependency not in ids or dependency == stage["id"]:
                    raise ValueError("Unknown or self-referencing stage dependency")
            for name in [stage["contract"], *stage["reads"], *stage["evidence"]]:
                if name not in known_docs:
                    raise ValueError("Stage references an unowned document")
                self.read(name)
            for name in stage["sources"]:
                self.path(name)
            headings = set(re.findall(r"^## (.+)$", self.read(stage["contract"]), re.M))
            if not SECTIONS <= headings:
                raise ValueError("Stage contract lacks required sections")
        visiting, visited = set(), set()
        by_id = {s["id"]: s for s in stages}

        def visit(stage_id):
            if stage_id in visiting:
                raise ValueError("Stage dependency cycle")
            if stage_id in visited:
                return
            visiting.add(stage_id)
            for dependency in by_id[stage_id]["depends_on"]:
                visit(dependency)
            visiting.remove(stage_id)
            visited.add(stage_id)

        for stage_id in ids:
            visit(stage_id)
        actual = {p.relative_to(self.root).as_posix() for p in self.root.glob("*.md")}
        for directory in ["docs", ".github"]:
            actual.update(p.relative_to(self.root).as_posix()
                          for p in (self.root / directory).rglob("*.md"))
        if actual != known_docs:
            raise ValueError("Documentation inventory differs from ownership registry")
        for doc in documents:
            if (set(doc) != {"path", "title", "owner", "role", "stages"}
                    or not self.metadata(doc["owner"]) or not self.metadata(doc["title"]) or doc["role"] not in ROLES
                    or not doc["stages"] or not set(doc["stages"]) <= set(ids)):
                raise ValueError("Invalid document ownership record")
            self.check_links(doc["path"])

    @staticmethod
    def metadata(value):
        return (isinstance(value, str) and 1 <= len(value) <= 256
                and value.isprintable() and "|" not in value)

    def check_links(self, name):
        source = re.sub(r"```.*?```", "", self.read(name), flags=re.S)
        for target in re.findall(r"\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)", source):
            target = target.strip("<>")
            url = urlsplit(target)
            if url.scheme or url.netloc:
                continue  # Offline check never requests an external URL.
            parent = (self.root / name).parent
            path = (parent / unquote(url.path)).resolve() if url.path else self.root / name
            if not path.is_relative_to(self.root):
                raise ValueError("Documentation link leaves repository")
            self.path(path.relative_to(self.root).as_posix())
            if url.fragment and path.suffix == ".md":
                text = self.read(path.relative_to(self.root).as_posix())
                anchors, counts = set(), {}
                for title in re.findall(r"^#{1,6} (.+)$", text, re.M):
                    slug = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
                    count = counts.get(slug, 0)
                    counts[slug] = count + 1
                    anchors.add(slug if count == 0 else f"{slug}-{count}")
                if unquote(url.fragment) not in anchors:
                    raise ValueError("Broken local Markdown fragment")

    def views(self):
        version = tomllib.loads(self.read("Cargo.toml"))["workspace"]["package"]["version"]
        roadmap = ["# Roadmap", "", "<!-- Generated by just docs-generate; edit docs/stages.json and stage contracts. -->",
                   "", f"Version: {version} unreleased; see [versioning](docs/versioning.md).",
                   "Recorded progress describes implementation evidence, not live issue closure or milestone completion.",
                   "GitHub Issues own actionable state; use `just issues`. No legacy archive or benchmark quality is assumed.",
                   "", f"Active stage: **{self.stages['active']}**. Start with `just context`.", ""]
        for stage in self.stages["stages"]:
            roadmap += [f"## {stage['id']} — {stage['title']}", "",
                        f"Milestone: {stage['milestone']}; recorded progress: **{stage['progress']}**.",
                        "Dependencies: " + (", ".join(stage["depends_on"]) or "none") + ".",
                        f"[Stage contract]({stage['contract']}); issues: " + ", ".join(
                            f"[#{n}]({self.issue_map[str(n)]['url']})" for n in stage["issues"]) + "."]
            if stage["evidence"]:
                roadmap += ["Evidence: " + ", ".join(f"[{p}]({p})" for p in stage["evidence"]) + "."]
            roadmap += [""]
        index = ["# Documentation index", "", "<!-- Generated by just docs-generate; edit docs/documents.json. -->",
                 "", "Owners maintain durable contracts. Historical/input documents are evidence, not current instructions.",
                 "GitHub Issues own live state; local issue files preserve design references.", "",
                 "| Document | Owner | Role | Stages |", "| --- | --- | --- | --- |"]
        for doc in sorted(self.docs["documents"], key=lambda d: d["path"]):
            relative = "../" + doc["path"]
            index.append(f"| [{doc['title']}]({relative}) | {doc['owner']} | {doc['role']} | {', '.join(doc['stages'])} |")
        return {"ROADMAP.md": "\n".join(roadmap), "docs/index.md": "\n".join(index) + "\n"}

    def check(self):
        self.validate()
        for name, expected in self.views().items():
            if self.read(name) != expected:
                raise ValueError("Generated documentation drift; run just docs-generate")

    def context(self, stage_id=None):
        self.validate()
        stage_id = stage_id or self.stages["active"]
        stage = next((s for s in self.stages["stages"] if s["id"] == stage_id), None)
        if stage is None:
            raise ValueError("Unknown stage; consult ROADMAP.md")
        lines = [f"Stage: {stage['id']} — {stage['title']}",
                 f"Recorded progress: {stage['progress']} (live state: just issues)",
                 "Dependencies: " + (", ".join(stage["depends_on"]) or "none"),
                 "Issues: " + ", ".join(self.issue_map[str(n)]["url"] for n in stage["issues"]),
                 "Source entry points: " + ", ".join(stage["sources"]),
                 "Read next: " + ", ".join(stage["reads"]),
                 "Evidence: " + (", ".join(stage["evidence"]) or "pending"),
                 "Mandatory gate: just check; inspect git diff; record PR/CI evidence.",
                 "Context is offline/read-only; paths are references, never commands to execute.",
                 "", f"Contract: {stage['contract']}", self.read(stage["contract"])]
        text = "\n".join(lines)
        suffix = "\n[Context excerpt bounded to 8192 UTF-8 bytes; read the referenced contract and paths for remaining evidence.]\n"
        if len(text.encode()) > CONTEXT_BYTES:
            text = text.encode()[:CONTEXT_BYTES - len(suffix.encode())].decode("utf-8", errors="ignore") + suffix
        return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["context", "check", "generate"])
    parser.add_argument("stage", nargs="?")
    args = parser.parse_args()
    if args.stage is not None and args.action != "context":
        parser.error("Only context accepts a stage")
    try:
        repo = Repository(ROOT)
        if args.action == "context":
            print(repo.context(args.stage), end="")
        elif args.action == "check":
            repo.check()
            print("Documentation ownership, stage contracts, links and generated views: PASS (offline)")
        else:
            repo.validate()
            for name, content in repo.views().items():
                repo.path(name).write_text(content, encoding="utf-8")
            print("Generated ROADMAP.md and docs/index.md")
    except (ValueError, KeyError, TypeError, OSError) as error:
        reason = str(error) if type(error) is ValueError else "Invalid registry/document input"
        print(f"E_DOCS: {reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
