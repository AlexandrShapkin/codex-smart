"""Privacy-preserving local aggregate telemetry for normalized benchmark records."""

import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import statistics

SCHEMA_VERSION = 1
MAX_RECORD_BYTES = 1024 * 1024
TOKEN_METRICS = (
    "input", "cached_input", "output", "reasoning", "fresh_input", "total",
)
FAILURE_BUCKETS = (
    "none", "launch-failure", "timeout", "agent-failure", "process-failure",
    "trace-invalid", "submission-export-refused", "submission-evidence-missing",
    "grading-refusal", "quality-failure", "not-runnable", "other",
)
ALLOWED_RECORD_KEYS = {
    "schema_version", "campaign_id", "scenario_id", "variant", "repetition", "seed",
    "frozen_references", "host_qualification_reference",
    "agent_execution_isolation_reference", "grading_isolation_reference",
    "production_grading_reference", "grading_runtime_inventory_reference",
    "terminal_status", "process_exit_status", "parser_valid", "parser_errors",
    "quality_pass", "failure_reason", "duration_seconds", "observed_tokens",
    "observed_tool_calls_lower_bound", "full_tool_calls", "retry_count",
    "attempt_count", "execution_kind", "model_calls",
    "split_host_topology_reference", "agent_trace_sha256", "submission_sha256",
    # Reserved privacy-safe numeric/classification fields for future normalized records.
    "cold_warm", "setup_seconds", "index_seconds", "bootstrap_seconds",
}
REQUIRED_RECORD_KEYS = {
    "schema_version", "campaign_id", "scenario_id", "variant", "repetition", "seed",
    "frozen_references", "terminal_status", "process_exit_status", "parser_valid",
    "parser_errors", "quality_pass", "failure_reason", "duration_seconds",
    "observed_tokens", "observed_tool_calls_lower_bound", "full_tool_calls",
    "retry_count", "attempt_count", "execution_kind", "model_calls",
}


class TelemetryRefusal(ValueError):
    pass


def _safe_number(value):
    return (
        value is None
        or (type(value) in (int, float) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)
    )


def _load_record(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise TelemetryRefusal("unsafe normalized record")
    info = path.stat()
    if info.st_size > MAX_RECORD_BYTES:
        raise TelemetryRefusal("normalized record exceeds size limit")
    try:
        record = json.loads(path.read_text())
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise TelemetryRefusal("invalid normalized record") from None
    if type(record) is not dict:
        raise TelemetryRefusal("normalized record must be an object")
    keys = set(record)
    if not REQUIRED_RECORD_KEYS <= keys or not keys <= ALLOWED_RECORD_KEYS:
        raise TelemetryRefusal("normalized record field contract rejected")
    if record["schema_version"] != 1:
        raise TelemetryRefusal("unsupported normalized record version")
    if type(record["campaign_id"]) is not str or type(record["scenario_id"]) is not str:
        raise TelemetryRefusal("invalid normalized record identity")
    if type(record["variant"]) is not str or not record["variant"]:
        raise TelemetryRefusal("invalid normalized variant")
    if type(record["repetition"]) is not int or type(record["seed"]) is not int:
        raise TelemetryRefusal("invalid normalized ordering identity")
    if type(record["quality_pass"]) is not bool:
        raise TelemetryRefusal("invalid normalized quality state")
    if record["failure_reason"] is not None and type(record["failure_reason"]) is not str:
        raise TelemetryRefusal("invalid normalized failure state")
    if not _safe_number(record["duration_seconds"]):
        raise TelemetryRefusal("invalid normalized duration")
    if type(record["observed_tokens"]) is not dict:
        raise TelemetryRefusal("invalid normalized token counters")
    if set(record["observed_tokens"]) != set(TOKEN_METRICS):
        raise TelemetryRefusal("normalized token field contract rejected")
    if any(not _safe_number(record["observed_tokens"][key]) for key in TOKEN_METRICS):
        raise TelemetryRefusal("invalid normalized token counter")
    for key in (
        "observed_tool_calls_lower_bound", "full_tool_calls", "model_calls",
        "setup_seconds", "index_seconds", "bootstrap_seconds",
    ):
        if key in record and not _safe_number(record[key]):
            raise TelemetryRefusal("invalid normalized numeric counter")
    if type(record["retry_count"]) is not int or record["retry_count"] < 0:
        raise TelemetryRefusal("invalid normalized retry count")
    if type(record["attempt_count"]) is not int or record["attempt_count"] < 0:
        raise TelemetryRefusal("invalid normalized attempt count")
    if "cold_warm" in record and record["cold_warm"] not in ("cold", "warm", "unknown"):
        raise TelemetryRefusal("invalid normalized cache classification")
    return record


def _record_files(directory):
    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise TelemetryRefusal("normalized record directory rejected")
    paths = []
    for path in sorted(root.iterdir(), key=lambda p: p.name):
        if not path.name.endswith(".json"):
            continue
        if path.name == "summary.json" or path.name.endswith(".grade.json"):
            continue
        if path.is_symlink():
            raise TelemetryRefusal("symlink normalized record rejected")
        if path.is_file():
            paths.append(path)
    if not paths:
        raise TelemetryRefusal("no normalized records found")
    return paths


def _manifest_sha(paths):
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _metric(values):
    known = [value for value in values if value is not None]
    if not known:
        return {"samples": 0, "sum": None, "median": None, "range": None}
    return {
        "samples": len(known),
        "sum": sum(known),
        "median": statistics.median(known),
        "range": [min(known), max(known)],
    }


def _cold_warm(record):
    explicit = record.get("cold_warm")
    if explicit in ("cold", "warm", "unknown"):
        return explicit
    refs = record.get("frozen_references")
    if type(refs) is dict:
        protocol = refs.get("cold_warm")
        if type(protocol) is dict and protocol.get("classification") in ("cold", "warm", "unknown"):
            return protocol["classification"]
    return "unknown"


def _failure_bucket(value):
    bucket = "none" if value is None else value
    return bucket if bucket in FAILURE_BUCKETS else "other"


def _aggregate(rows):
    failure_counts = {key: 0 for key in FAILURE_BUCKETS}
    cold_warm = {"cold": 0, "warm": 0, "unknown": 0}
    for row in rows:
        failure_counts[_failure_bucket(row["failure_reason"])] += 1
        cold_warm[_cold_warm(row)] += 1
    return {
        "runs": len(rows),
        "quality_passes": sum(row["quality_pass"] for row in rows),
        "quality_failures": sum(not row["quality_pass"] for row in rows),
        "failure_counts": failure_counts,
        "cold_warm": cold_warm,
        "retry_count": _metric([row["retry_count"] for row in rows]),
        "attempt_count": _metric([row["attempt_count"] for row in rows]),
        "duration_seconds": _metric([row["duration_seconds"] for row in rows]),
        "setup_seconds": _metric([row.get("setup_seconds") for row in rows]),
        "index_seconds": _metric([row.get("index_seconds") for row in rows]),
        "bootstrap_seconds": _metric([row.get("bootstrap_seconds") for row in rows]),
        "tokens": {
            key: _metric([row["observed_tokens"][key] for row in rows])
            for key in TOKEN_METRICS
        },
        "observed_tool_calls_lower_bound": _metric(
            [row["observed_tool_calls_lower_bound"] for row in rows]
        ),
        "full_tool_calls": _metric([row["full_tool_calls"] for row in rows]),
        "model_calls": _metric([row["model_calls"] for row in rows]),
    }


def aggregate_directory(directory, *, include_scenario_breakdown=False):
    paths = _record_files(directory)
    rows = [_load_record(path) for path in paths]
    campaigns = {row["campaign_id"] for row in rows}
    if len(campaigns) != 1:
        raise TelemetryRefusal("mixed campaign records rejected")
    variants = sorted({row["variant"] for row in rows})
    report = {
        "schema_version": SCHEMA_VERSION,
        "telemetry_kind": "benchmark-aggregate-v1",
        "campaign_id": next(iter(campaigns)),
        "record_count": len(rows),
        "records_manifest_sha256": _manifest_sha(paths),
        "privacy": {
            "input_contract": "normalized-records-only",
            "raw_trace_ingested": False,
            "prompt_ingested": False,
            "source_ingested": False,
            "stderr_ingested": False,
            "credential_data_ingested": False,
            "network_export": False,
            "scenario_breakdown_included": bool(include_scenario_breakdown),
        },
        "overall": _aggregate(rows),
        "variants": {
            variant: _aggregate([row for row in rows if row["variant"] == variant])
            for variant in variants
        },
    }
    if include_scenario_breakdown:
        report["scenarios"] = {
            scenario: _aggregate([row for row in rows if row["scenario_id"] == scenario])
            for scenario in sorted({row["scenario_id"] for row in rows})
        }
    return report


def _write_private(path, report):
    target = Path(path)
    if target.exists() or target.is_symlink():
        raise TelemetryRefusal("telemetry output already exists")
    if not target.parent.is_dir() or target.parent.is_symlink():
        raise TelemetryRefusal("telemetry output parent rejected")
    with target.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    target.chmod(0o600)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records-dir", required=True)
    parser.add_argument("--include-scenario-breakdown", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        report = aggregate_directory(
            args.records_dir,
            include_scenario_breakdown=args.include_scenario_breakdown,
        )
        if args.output:
            _write_private(args.output, report)
        else:
            print(json.dumps(report, indent=2, sort_keys=True))
    except (OSError, TelemetryRefusal) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
