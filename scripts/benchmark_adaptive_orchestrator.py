"""Explicit, pinned split-host stages around the existing adaptive campaign runner.

No automatic model/transport retries. Plan/status/offline preflight do not contact
srv0. Production transport always uses the existing reviewed ED25519 host pin.
"""
import argparse
import base64
import fcntl
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import tempfile

import benchmark_adaptive_campaign as live
import benchmark_adaptive_trusted_handoff as handoff
import repository_workflow as repository

ROOT = Path(__file__).resolve().parent.parent
STAGES = ("preflight", "initial", "transfer-1", "grade-1", "authenticate-1",
          "escalate", "transfer-2", "grade-2", "authenticate-2", "finalize", "archive")
MAX_WIRE_BYTES = 128 * 1024 * 1024
REMOTE_PATH = re.compile(r"/tmp/[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_.-]+)*\Z")


class OrchestrationRefusal(ValueError):
    pass


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise OrchestrationRefusal("duplicate JSON key")
        value[key] = item
    return value


def decode(raw):
    if len(raw) > MAX_WIRE_BYTES:
        raise OrchestrationRefusal("bounded transport input exceeded")
    return json.loads(raw, object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          OrchestrationRefusal("non-finite JSON value")))


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def regular(path):
    path = repository.safe_path(path)
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_mode & 0o022 or info.st_uid != os.getuid()):
        raise OrchestrationRefusal("unsafe campaign file")
    return path


def read(path):
    return decode(regular(path).read_bytes())


def private_directory(path, *, create=False):
    path = repository.safe_path(path, exists=not create)
    if create:
        path.mkdir(mode=0o700)
        path.chmod(0o700)
    info = path.stat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o022):
        raise OrchestrationRefusal("unsafe campaign directory")
    return path


def write(path, value):
    path = repository.safe_path(path, exists=False)
    with path.open("xb") as stream:
        stream.write(encoded(value))
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o600)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def file_record(path):
    path = regular(path)
    return {"sha256": live._sha256(path), "mode": stat.S_IMODE(path.stat().st_mode)}


def tree(path):
    root = private_directory(path)
    files = {}
    for current, directories, names in os.walk(root, followlinks=False):
        for name in directories:
            private_directory(Path(current) / name)
        for name in names:
            file = regular(Path(current) / name)
            if file.suffix == ".json":
                read(file)  # Duplicate keys/non-finite values cannot hide behind hashes.
            files[file.relative_to(root).as_posix()] = file_record(file)
    return files


def check_files(root, expected):
    for name, record in expected.items():
        if (Path(name).is_absolute() or ".." in Path(name).parts
                or file_record(Path(root) / name) != record):
            raise OrchestrationRefusal("immutable campaign receipt mismatch")


def _source(source):
    if set(source) != {"path", "sha", "receipt_sha256"}:
        raise OrchestrationRefusal("unexpected source identity fields")
    repository.full_sha(source["sha"])
    repository.safe_path(source["path"], exists=False)
    if not re.fullmatch(r"[0-9a-f]{64}", source["receipt_sha256"]):
        raise OrchestrationRefusal("source receipt digest required")


def verify_source(source):
    _source(source)
    return repository.verify_snapshot(source["path"], source["sha"], source["receipt_sha256"])


def validate_config(config):
    if (set(config) != {"schema_version", "run_id", "state", "agent", "grader"}
            or type(config["schema_version"]) is not int or config["schema_version"] != 1):
        raise OrchestrationRefusal("unsupported operator configuration")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", config["run_id"]):
        raise OrchestrationRefusal("unsafe campaign identifier")
    repository.safe_path(config["state"], exists=False)
    agent, grader = config["agent"], config["grader"]
    if (set(agent) != {"source", "codex", "code_mode_host", "runtime_root", "inventory_dir",
                      "adapter", "adapter_sha256"}
            or set(grader) != {"source", "runtime_root", "inventory_dir", "qualification_evidence",
                              "qualification_sha256", "remote_root"}):
        raise OrchestrationRefusal("unexpected host configuration fields")
    for role in (agent, grader):
        _source(role["source"])
        for key in set(role) - {"source", "adapter_sha256", "qualification_sha256"}:
            repository.safe_path(role[key], exists=False)
    for value in (agent["adapter_sha256"], grader["qualification_sha256"]):
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise OrchestrationRefusal("explicit adapter/qualification digest required")
    for value in [grader["remote_root"], grader["source"]["path"], grader["runtime_root"],
                  grader["inventory_dir"], grader["qualification_evidence"]]:
        if (len(value) > 256 or not REMOTE_PATH.fullmatch(value)
                or str(Path(value)) != value or ".." in Path(value).parts):
            raise OrchestrationRefusal("safe absolute /tmp grader paths required")
    remote_summary = f"{grader['remote_root']}/{'0' * 64}/grades-1/summary.json"
    if len(remote_summary) > 256 or not handoff.REMOTE_SUMMARY.fullmatch(remote_summary):
        raise OrchestrationRefusal("artifact destination incompatible with pinned handoff")
    if any(Path(grader["remote_root"]).is_relative_to(Path(value))
           for value in [grader["source"]["path"], grader["runtime_root"], grader["inventory_dir"]]):
        raise OrchestrationRefusal("grader artifacts overlap immutable inputs")
    return config


def make_plan(config, *, resolver=live.adaptive._adapter_output):
    config = validate_config(config)
    verify_source(config["agent"]["source"])
    adapter = regular(config["agent"]["adapter"])
    if live._sha256(adapter) != config["agent"]["adapter_sha256"]:
        raise OrchestrationRefusal("adapter identity mismatch")
    contract = live.adaptive.load_contract()
    jobs = live.jobs()
    if len(jobs) != 20 or len(set(jobs)) != 20 or contract["adaptive_campaign"] != {
            "authorization_required": True, "jobs": 20, "max_attempts_per_job": 2,
            "max_delegations_per_job": 0, "max_retries_per_job": 1,
            "maximum_codex_executions": 40, "profile_mapping_evidence_required": True,
            "repetitions": 2, "seed": 14}:
        raise OrchestrationRefusal("frozen execution budget mismatch")
    matrix = []
    for scenario, repetition, seed in jobs:
        policy = live.adaptive.SCENARIO_POLICY[scenario]
        decision = resolver(adapter, policy)
        model, reasoning = live._profile_target(decision)
        if (decision["attempts_started"] != 0 or decision["retries_used"] != 0
                or decision["delegations_used"] != 0
                or (policy["risk"] == "high" and (decision["model_key"] != 30 or reasoning != "high"))):
            raise OrchestrationRefusal("initial controller state or safety floor mismatch")
        matrix.append({"job_id": live._job_id(scenario, repetition, seed), "scenario": scenario,
                       "repetition": repetition, "seed": seed, "decision": decision, "model": model})
    return {"schema_version": 1, "kind": "adaptive-split-host-operational-plan", "config": config,
            "jobs": matrix, "budget": contract["adaptive_campaign"],
            "contract_sha256": digest(contract), "ssh_host": handoff.TRUSTED_ALIAS,
            "ssh_fingerprint": handoff.TRUSTED_ED25519_SHA256,
            "runtime_reference": live.split.RUNTIME_INVENTORY_REFERENCE,
            "model_execution_enabled": False, "performance_evidence_accepted": False}


def initialize(path, plan):
    path = repository.safe_path(path, exists=False)
    if str(path) != plan["config"]["state"]:
        raise OrchestrationRefusal("state destination differs from reviewed plan")
    for role in (plan["config"]["agent"], plan["config"]["grader"]):
        for value in [role["source"]["path"], role["runtime_root"], role["inventory_dir"]]:
            if path.is_relative_to(Path(value)) or Path(value).is_relative_to(path):
                raise OrchestrationRefusal("campaign state overlaps source/runtime")
    private_directory(path, create=True)
    private_directory(path / "stages", create=True)
    write(path / "plan.json", plan)
    return {"state": str(path), "plan_sha256": digest(plan), "model_execution_enabled": False}


def pack(path):
    manifest = tree(path)
    return {name: base64.b64encode((Path(path) / name).read_bytes()).decode()
            for name in manifest}


def validate_transfer(files, manifest, allowed):
    if (not isinstance(files, dict) or set(files) != set(manifest)
            or len(encoded(files)) > MAX_WIRE_BYTES):
        raise OrchestrationRefusal("invalid bounded transfer")
    for name, value in files.items():
        if (not isinstance(name, str) or not allowed(name) or not isinstance(value, str)
                or Path(name).is_absolute() or ".." in Path(name).parts
                or Path(name).as_posix() != name):
            raise OrchestrationRefusal("unexpected transfer file")
        raw = base64.b64decode(value, validate=True)
        decode(raw)  # Only bounded JSON files cross this boundary.
        if (set(manifest[name]) != {"sha256", "mode"}
                or manifest[name]["mode"] not in (0o400, 0o600, 0o644)
                or hashlib.sha256(raw).hexdigest() != manifest[name]["sha256"]):
            raise OrchestrationRefusal("transport manifest mismatch")


def unpack(files, path, *, allowed, manifest, resume=False):
    validate_transfer(files, manifest, allowed)
    path = Path(path)
    if path.exists():
        if not resume:
            raise OrchestrationRefusal("existing transfer destination requires explicit resume")
        actual = tree(path)
        if not set(actual) <= set(manifest) or any(actual[name] != manifest[name] for name in actual):
            raise OrchestrationRefusal("partial/different transfer preserved; no overwrite")
    else:
        private_directory(path, create=True)
    # Write completion summaries/markers last; only missing files may be copied.
    for name in sorted(files, key=lambda n: (n in {"grading-bundle.json", "summary.json"}, n)):
        value = files[name]
        destination = path / name
        if destination.exists():
            continue
        for relative in reversed(Path(name).parents):
            if relative != Path(".") and not (path / relative).exists():
                private_directory(path / relative, create=True)
        with destination.open("xb") as stream:
            stream.write(base64.b64decode(value, validate=True))
        destination.chmod(manifest[name]["mode"])
    return path


def bundle_name(name):
    if name == "grading-bundle.json":
        return True
    parts = Path(name).parts
    return (len(parts) == 3 and parts[0] in {live._job_id(*job) for job in live.jobs()}
            and parts[1] in {"attempt-1", "attempt-2"}
            and parts[2] in {"started.json", "agent-result.json", "trace-summary.json", "submission.json"})


def grade_name(name):
    return name in {"summary.json", *(live._job_id(*job) + ".json" for job in live.jobs())}


class Transport:
    def request(self, plan, action, **payload):
        if action not in {"preflight", "upload", "grade", "fetch"}:
            raise OrchestrationRefusal("unknown pinned transport operation")
        if action == "upload":
            validate_transfer(payload["files"], payload["manifest"], bundle_name)
        # The bootstrap reuses the normalized verifier BEFORE importing remote source.
        verifier = "\n".join(inspect.getsource(function) for function in
                             (repository.safe_path, repository.full_sha,
                              repository.snapshot_directory, repository.verify_snapshot))
        bootstrap = ("import os,stat,json,hashlib,sys,re\nfrom pathlib import Path\n" +
                     f"CANONICAL={repository.CANONICAL!r}\nRECEIPT={repository.RECEIPT!r}\n" + verifier +
                     "\nr=json.loads(sys.stdin.read(134217729))\n"
                     "s=r['plan']['config']['grader']['source']\n"
                     "verify_snapshot(s['path'],s['sha'],s['receipt_sha256'])\n"
                     "assert (Path(s['path'])/'scripts/benchmark_adaptive_orchestrator.py').is_file()\n"
                     "sys.path.insert(0,str(Path(s['path'])/'scripts'))\n"
                     "from benchmark_adaptive_orchestrator import host_request\n"
                     "print(json.dumps(host_request(r)))\n")
        body = encoded({"plan": plan, "action": action, **payload})
        if len(body) > MAX_WIRE_BYTES:
            raise OrchestrationRefusal("bounded transport input exceeded")
        options = handoff.pinned_srv0_options()
        command = shlex.join(["/usr/bin/python3", "-I", "-B", "-c", bootstrap])
        try:
            timeout = 20 * live.submission_grading.RUNTIME_MAX_SECONDS + 120 if action == "grade" else 120
            result = subprocess.run([handoff.SSH, *options, "-T", handoff.TRUSTED_ALIAS, command],
                                    input=body, capture_output=True, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise OrchestrationRefusal("pinned transport interrupted/unavailable; inspect and resume") from error
        if result.returncode:
            raise OrchestrationRefusal("pinned host operation refused; no model replay")
        reply = decode(result.stdout)
        if not isinstance(reply, dict):
            raise OrchestrationRefusal("malformed pinned host response")
        return reply

    def summary_digest(self, path):
        return handoff.pinned_srv0_summary_sha256(str(path))


class Backend:
    def preflight(self, plan):
        agent = plan["config"]["agent"]
        temporary_roots = {Path("/tmp"), Path(os.environ.get("TMPDIR", "/tmp")).resolve()}
        for value in (plan["config"]["state"], agent["source"]["path"], agent["adapter"]):
            if any(Path(value).is_relative_to(root) for root in temporary_roots):
                raise OrchestrationRefusal("agent control state/source/adapter in model-writable temporary root")
        if Path(agent["source"]["path"]) != ROOT:
            raise OrchestrationRefusal("execute from the verified agent source snapshot")
        live.agent_preflight(*(agent[key] for key in
                              ("codex", "code_mode_host", "runtime_root", "inventory_dir",
                               "adapter", "adapter_sha256")))
        for row in plan["jobs"]:
            decision = live.adaptive._adapter_output(agent["adapter"], live.adaptive.SCENARIO_POLICY[row["scenario"]])
            if decision != row["decision"]:
                raise OrchestrationRefusal("Rust profile plan changed before execution")
        return {"runtime_reference": live.split.RUNTIME_INVENTORY_REFERENCE,
                "adapter_sha256": agent["adapter_sha256"]}

    def execute(self, plan, state, *, retry=False):
        agent = plan["config"]["agent"]
        args = [agent[key] for key in ("codex", "code_mode_host", "runtime_root", "inventory_dir",
                                      "adapter", "adapter_sha256")]
        args.append(plan["config"]["run_id"])
        if retry:
            return live.run_retry(*args, state / "grades-1", authorized=True,
                                  initial_grades_sha256=live._sha256(state / "grades-1/summary.json"),
                                  agent_artifacts=state / "agent")
        return live.run_initial(*args, authorized=True, resume=(state / "agent").exists(),
                                agent_artifacts=state / "agent")


class Campaign:
    def __init__(self, state, expected, *, backend=None, transport=None):
        self.state = private_directory(state)
        self.plan = read(self.state / "plan.json")
        if not re.fullmatch(r"[0-9a-f]{64}", expected) or digest(self.plan) != expected:
            raise OrchestrationRefusal("reviewed plan digest mismatch")
        self.identity = expected
        validate_config(self.plan["config"])
        if str(self.state) != self.plan["config"]["state"]:
            raise OrchestrationRefusal("state destination differs from reviewed plan")
        if (self.plan["contract_sha256"] != digest(live.adaptive.load_contract())
                or self.plan["budget"] != live.adaptive.load_contract()["adaptive_campaign"]
                or [row["job_id"] for row in self.plan["jobs"]] != [live._job_id(*job) for job in live.jobs()]):
            raise OrchestrationRefusal("plan no longer matches frozen contract/matrix")
        self.backend = backend or Backend()
        self.transport = transport or Transport()

    def receipt(self, stage):
        path = self.state / "stages" / f"{stage}.json"
        if not path.exists():
            return None
        value = read(path)
        if (set(value) != {"stage", "plan_sha256", "dependencies", "outputs", "result"}
                or value["plan_sha256"] != self.identity or value["stage"] != stage):
            raise OrchestrationRefusal("stage receipt identity mismatch")
        expected = {previous: live._sha256(regular(self.state / "stages" / f"{previous}.json"))
                    for previous in STAGES[:STAGES.index(stage)]}
        if value["dependencies"] != expected:
            raise OrchestrationRefusal("stage dependency receipt drift")
        check_files(self.state, value["outputs"])
        return value

    def status(self):
        states = {stage: ("complete" if self.receipt(stage) else
                         "interrupted-or-running" if (self.state / "stages" / f"{stage}.started.json").exists()
                         else "pending") for stage in STAGES}
        return {"plan_sha256": self.identity, "stages": states,
                "started_attempts": live._started_count(self.state / "agent") if (self.state / "agent").exists() else 0,
                "maximum_attempts": 40, "model_execution_enabled": False}

    def remote_root(self):
        return Path(self.plan["config"]["grader"]["remote_root"]) / self.identity

    def preflight(self, *, online=False):
        source = verify_source(self.plan["config"]["agent"]["source"])
        agent = self.backend.preflight(self.plan)
        if not online:
            return {"source": source, "agent": agent, "grader": "unknown (offline)",
                    "model_execution_enabled": False}
        remote = self.transport.request(self.plan, "preflight")
        source_receipt = remote.get("source_receipt")
        expected_remote = {"source": self.plan["config"]["grader"]["source"],
                      "runtime_reference": live.split.RUNTIME_INVENTORY_REFERENCE,
                      "qualified_host_reference": live.split.GRADING_HOST_RECEIPT,
                      "plan_sha256": self.identity, "source_receipt": source_receipt}
        if (remote != expected_remote or hashlib.sha256(repository.encode(source_receipt)).hexdigest()
                != self.plan["config"]["grader"]["source"]["receipt_sha256"]):
            raise OrchestrationRefusal("grader preflight identity mismatch")
        return {"source": source, "agent": agent, "grader": remote, "model_execution_enabled": False}

    def _agent_files(self, ordinal):
        output = {}
        live._started_count(self.state / "agent")
        for job in live.jobs():
            directory = self.state / "agent" / live._job_id(*job) / f"attempt-{ordinal}"
            if directory.exists():
                live._load_attempt_result(directory, *job, ordinal)
                if ordinal == 1:
                    started = live._load_started(directory, *job, ordinal)
                    planned = next(row for row in self.plan["jobs"] if row["job_id"] == live._job_id(*job))
                    if any(started[key] != planned["decision"][key] for key in ("profile", "reasoning", "model_key")):
                        raise OrchestrationRefusal("execution differs from reviewed profile plan")
                output.update({str(Path("agent") / live._job_id(*job) / directory.name / name): record
                               for name, record in tree(directory).items()})
        summary = "initial-agent-summary.json" if ordinal == 1 else "retry-agent-summary.json"
        output[str(Path("agent") / summary)] = file_record(self.state / "agent" / summary)
        return output

    def _authenticate(self, ordinal):
        remote = self.remote_root() / f"grades-{ordinal}" / "summary.json"
        authoritative = self.transport.summary_digest(remote)
        directory = self.state / f"grades-{ordinal}"
        tree(directory)
        if authoritative != self.receipt(f"grade-{ordinal}")["result"]["summary_sha256"]:
            raise OrchestrationRefusal("grading receipt changed after independent grading")
        _, rows = live._load_grade_round(directory, ordinal, authoritative)
        for job in live.jobs():
            attempt = self.state / "agent" / live._job_id(*job) / f"attempt-{ordinal}"
            if attempt.exists():
                live._match_grade(rows.get(live._job_id(*job)), live._load_started(attempt, *job, ordinal),
                                  live._load_attempt_result(attempt, *job, ordinal))
        return authoritative

    def stage(self, stage, *, online=False, authorized=False, grading_authorized=False, resume=False):
        if stage not in STAGES:
            raise OrchestrationRefusal("unknown campaign stage")
        if stage in {"initial", "escalate"} and authorized is not True:
            raise OrchestrationRefusal("separate model execution authorization required")
        if stage.startswith("grade-") and grading_authorized is not True:
            raise OrchestrationRefusal("separate independent grading authorization required")
        if stage != "archive" and not online:
            if stage == "preflight":
                return self.preflight()
            raise OrchestrationRefusal("explicit --online transport authority required")
        lock = self.state / "campaign.lock"
        if lock.exists():
            regular(lock)
        descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise OrchestrationRefusal("campaign operation already running") from error
            prior = self.receipt(stage)
            if prior:
                return prior
            index = STAGES.index(stage)
            dependencies = {}
            for previous in STAGES[:index]:
                if not self.receipt(previous):
                    raise OrchestrationRefusal("previous stage incomplete")
                dependencies[previous] = live._sha256(self.state / "stages" / f"{previous}.json")
            started = self.state / "stages" / f"{stage}.started.json"
            start_value = {"stage": stage, "plan_sha256": self.identity, "dependencies": dependencies}
            if started.exists():
                if not resume or read(started) != start_value:
                    raise OrchestrationRefusal("interrupted stage requires explicit matching resume")
            else:
                if resume:
                    raise OrchestrationRefusal("no interrupted stage to resume")
                write(started, start_value)
            outputs, result = self._perform(stage, resume=resume)
            receipt = {**start_value, "outputs": outputs, "result": result}
            write(self.state / "stages" / f"{stage}.json", receipt)
            return receipt
        finally:
            os.close(descriptor)  # Never unlink the lock; locks survive process interruption safely.

    def _perform(self, stage, *, resume):
        if stage == "preflight":
            return {}, self.preflight(online=True)
        if stage in {"initial", "escalate"}:
            self.preflight(online=True)
            if (self.state / "agent").exists():
                tree(self.state / "agent")
            if stage == "escalate":
                self._authenticate(1)
            result = self.backend.execute(self.plan, self.state, retry=stage == "escalate")
            if stage == "initial" and any(not (self.state / "agent" / live._job_id(*job) / "attempt-1").exists()
                                          for job in live.jobs()):
                raise OrchestrationRefusal("all 20 initial ledgers required")
            return self._agent_files(1 if stage == "initial" else 2), result
        if stage.startswith("transfer-"):
            ordinal = int(stage[-1])
            bundle = self.state / f"bundle-{ordinal}"
            with tempfile.TemporaryDirectory(prefix="bundle-export-", dir=self.state) as temporary:
                complete = Path(temporary) / "complete"
                live.export_grading_bundle(self.state / "agent", complete)
                unpack(pack(complete), bundle, allowed=bundle_name, manifest=tree(complete), resume=resume)
            live._validate_grading_bundle(bundle)
            # Resume copies only missing bytes from the same validated ledger.
            manifest = tree(bundle)
            result = self.transport.request(self.plan, "upload", round=ordinal,
                                            files=pack(bundle), manifest=manifest, resume=resume)
            if result != {"bundle_sha256": digest(manifest), "plan_sha256": self.identity}:
                raise OrchestrationRefusal("remote bundle receipt mismatch")
            return {f"bundle-{ordinal}/{name}": record for name, record in manifest.items()}, result
        if stage.startswith("grade-"):
            ordinal = int(stage[-1])
            result = self.transport.request(self.plan, "grade", round=ordinal,
                                            authorize_grading=True, resume=resume)
            if (set(result) != {"summary_sha256", "plan_sha256"}
                    or result["plan_sha256"] != self.identity
                    or not re.fullmatch(r"[0-9a-f]{64}", result["summary_sha256"])):
                raise OrchestrationRefusal("malformed independent grading receipt")
            return {}, result
        if stage.startswith("authenticate-"):
            ordinal = int(stage[-1])
            directory = self.state / f"grades-{ordinal}"
            response = self.transport.request(self.plan, "fetch", round=ordinal)
            unpack(response["files"], directory, allowed=grade_name,
                   manifest=response["manifest"], resume=resume)
            manifest = tree(directory)
            if manifest != response["manifest"]:
                raise OrchestrationRefusal("transferred grading bytes mismatch")
            authoritative = self._authenticate(ordinal)
            return {f"grades-{ordinal}/{name}": record for name, record in manifest.items()}, {
                "summary_sha256": authoritative, "ssh_fingerprint": handoff.TRUSTED_ED25519_SHA256}
        if stage == "finalize":
            initial, retry = self._authenticate(1), self._authenticate(2)
            target = self.state / "final"
            if target.exists():
                tree(target)
            result = live.finalize(self.state / "agent", self.state / "grades-1", self.state / "grades-2",
                                   target, initial_grades_sha256=initial, retry_grades_sha256=retry,
                                   resume=resume)
            return {f"final/{name}": record for name, record in tree(target).items()}, result
        return self._archive(resume=resume)

    def _archive(self, *, resume):
        root = self.state / "archive"
        if (root / "archive-receipt.json").exists():
            marker = read(root / "archive-receipt.json")
            actual = tree(root)
            actual.pop("archive-receipt.json")
            if marker != {"plan_sha256": self.identity, "files": actual, "evidence_accepted": False}:
                raise OrchestrationRefusal("existing archive mismatch; no overwrite")
            if resume:
                (root / "archive-receipt.json").chmod(0o400)
                root.chmod(0o500)
        else:
            if root.exists():
                if not resume:
                    raise OrchestrationRefusal("partial archive requires explicit resume")
                tree(root)
            else:
                private_directory(root, create=True)
            values = {"plan.json": self.plan,
                      "execution.json": {"started_attempts": live._started_count(self.state / "agent"),
                                         "files": {**self._agent_files(1), **self._agent_files(2)},
                                         "attempts": {
                                             f"{live._job_id(*job)}/attempt-{ordinal}": {
                                                 "started": read(self.state / "agent" / live._job_id(*job) / f"attempt-{ordinal}/started.json"),
                                                 "result": read(self.state / "agent" / live._job_id(*job) / f"attempt-{ordinal}/agent-result.json")
                                                 if (self.state / "agent" / live._job_id(*job) / f"attempt-{ordinal}/agent-result.json").exists() else None}
                                             for job in live.jobs() for ordinal in (1, 2)
                                             if (self.state / "agent" / live._job_id(*job) / f"attempt-{ordinal}").exists()}}}
            for role in ("agent", "grader"):
                source_receipt = (read(Path(self.plan["config"][role]["source"]["path"]) / repository.RECEIPT)
                                  if role == "agent" else self.receipt("preflight")["result"]["grader"]["source_receipt"])
                values[f"source-{role}.json"] = {"identity": self.plan["config"][role]["source"],
                                                "receipt": source_receipt}
            values["stage-receipts.json"] = {stage: self.receipt(stage) for stage in STAGES[:-1]}
            values["grading.json"] = {str(ordinal): {
                "authentication": self.receipt(f"authenticate-{ordinal}")["result"],
                "summary": read(self.state / f"grades-{ordinal}/summary.json"),
                "rows": {name: read(self.state / f"grades-{ordinal}" / name)
                         for name in tree(self.state / f"grades-{ordinal}") if name != "summary.json"}}
                for ordinal in (1, 2)}
            final = self.receipt("finalize")["result"]
            if final["runs"] != 20 or final["handoff_count"] != 0 or final["handoff_overhead_seconds"] != 0:
                raise OrchestrationRefusal("frozen finalization invariant mismatch")
            values["final.json"] = {"summary": final,
                                    "jobs": {name: read(self.state / "final" / name)
                                             for name in tree(self.state / "final") if name != "summary.json"},
                                    "unmeasured_operational_latency_seconds": None}
            if any(file.name not in values for file in root.iterdir()):
                raise OrchestrationRefusal("unexpected partial archive file")
            for name, value in values.items():
                path = root / name
                if path.exists():
                    if encoded(read(path)) != encoded(value):
                        raise OrchestrationRefusal("partial archive differs; no overwrite")
                else:
                    write(path, value)
            for file in root.iterdir():
                file.chmod(0o400)
            write(root / "archive-receipt.json", {"plan_sha256": self.identity, "files": tree(root),
                                                 "evidence_accepted": False})
            (root / "archive-receipt.json").chmod(0o400)
            root.chmod(0o500)
        return {f"archive/{name}": record for name, record in tree(root).items()}, {
            "archive_sha256": live._sha256(root / "archive-receipt.json"), "evidence_accepted": False}


def host_request(request):
    """Only the pinned host invokes this after the trusted bootstrap verifies source."""
    plan, action = request["plan"], request["action"]
    validate_config(plan["config"])
    grader = plan["config"]["grader"]
    verify_source(grader["source"])
    if Path(grader["source"]["path"]) != ROOT:
        raise OrchestrationRefusal("execute from verified grading source snapshot")
    if live._sha256(regular(grader["qualification_evidence"])) != grader["qualification_sha256"]:
        raise OrchestrationRefusal("qualification evidence identity mismatch")
    qualification = live.host.load_evidence(grader["qualification_evidence"])
    live._grading_runtime(qualification, grader["runtime_root"], grader["inventory_dir"])
    identity = digest(plan)
    base = Path(grader["remote_root"])
    root = base / identity
    if action == "preflight":
        if not repository.safe_path(base.parent).is_dir():
            raise OrchestrationRefusal("grading destination parent missing")
        if base.exists():
            private_directory(base)
        if root.exists() and read(root / "plan.json") != plan:
            raise OrchestrationRefusal("existing remote campaign identity mismatch")
        return {"source": grader["source"], "runtime_reference": live.split.RUNTIME_INVENTORY_REFERENCE,
                "qualified_host_reference": live.split.GRADING_HOST_RECEIPT, "plan_sha256": identity,
                "source_receipt": read(Path(grader["source"]["path"]) / repository.RECEIPT)}
    if not base.exists():
        private_directory(base, create=True)
    if not root.exists():
        private_directory(root, create=True)
        write(root / "plan.json", plan)
    if read(root / "plan.json") != plan:
        raise OrchestrationRefusal("remote campaign identity mismatch")
    lock = root / "host.lock"
    if lock.exists():
        regular(lock)
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ordinal = request.get("round")
        if type(ordinal) is not int or ordinal not in (1, 2):
            raise OrchestrationRefusal("invalid grading round")
        if action == "upload":
            target = root / f"bundle-{ordinal}"
            unpack(request["files"], target, allowed=bundle_name, manifest=request["manifest"],
                   resume=request.get("resume") is True)
            if tree(target) != request["manifest"]:
                raise OrchestrationRefusal("partial/different remote transfer preserved")
            live._validate_grading_bundle(target)
            return {"bundle_sha256": digest(request["manifest"]), "plan_sha256": identity}
        if action == "grade":
            if request.get("authorize_grading") is not True:
                raise OrchestrationRefusal("independent grading authorization required")
            target = root / f"grades-{ordinal}"
            if target.exists():
                tree(target)
                if not request.get("resume"):
                    raise OrchestrationRefusal("existing grading evidence requires explicit resume")
            live.grade_round(root / f"bundle-{ordinal}", ordinal, qualification,
                             grader["runtime_root"], grader["inventory_dir"], target, authorized=True,
                             resume=request.get("resume") is True)
            return {"summary_sha256": live._sha256(target / "summary.json"), "plan_sha256": identity}
        if action == "fetch":
            target = root / f"grades-{ordinal}"
            live._load_grade_round(target, ordinal)
            return {"files": pack(target), "manifest": tree(target)}
        raise OrchestrationRefusal("unknown pinned host operation")
    finally:
        os.close(descriptor)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", default="plan", choices=("plan", "initialize", "status", *STAGES))
    parser.add_argument("--config")
    parser.add_argument("--state")
    parser.add_argument("--plan-sha256")
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--authorize-execution", action="store_true")
    parser.add_argument("--authorize-grading", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "plan":
            result = make_plan(read(args.config)) if args.config else live.plan()
        elif args.action == "initialize":
            result = initialize(args.state, make_plan(read(args.config)))
        else:
            campaign = Campaign(args.state, args.plan_sha256)
            result = campaign.status() if args.action == "status" else campaign.stage(
                args.action, online=args.online, authorized=args.authorize_execution,
                grading_authorized=args.authorize_grading, resume=args.resume)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.error(str(error) if isinstance(error, OrchestrationRefusal) else "campaign operation refused; inspect state")
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
