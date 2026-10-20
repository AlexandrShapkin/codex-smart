"""Read-only fake RelayForge chain receipt tests: no MCP, token or network."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("autodev_relayforge.py")
spec = importlib.util.spec_from_file_location("autodev_relayforge", SCRIPT)
relayforge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relayforge)
JOB = "relayforge-job-1792429049-07f0cb"


def bundle():
    n = 3
    return {
        "schema": 1,
        "status": {
            "job_id": JOB, "chain": True, "steps": n, "completed_steps": n,
            "state": "finished", "exit_code": 0,
        },
        "outputs": [
            {
                "job_id": JOB, "step": i, "steps": n,
                "result": {
                    "step": i, "exit_code": 0,
                    "stdout_truncated": False, "stderr_truncated": False,
                    "handoff_accepted": True,
                },
                "stdout": "ok\n", "stderr": "",
            }
            for i in range(1, n + 1)
        ],
    }


def inspect(data, job=JOB):
    return relayforge.inspect_export(json.dumps(data).encode(), job)


class ChainEvidenceTests(unittest.TestCase):
    def test_three_step_success_is_sanitized_but_not_authenticated(self):
        example = bundle()
        example["outputs"][1]["stderr"] = "operator_private_logs_are_not_rendered"
        result = inspect(example)
        self.assertEqual(result["steps"], 3)
        self.assertEqual(result["result"], "reported_success")
        self.assertEqual(result["trust"], "unverified_external_export")
        self.assertEqual(len(result["receipt_digest_sha256"]), 64)
        self.assertNotIn("operator_private", str(result))

    def test_fail_closed_for_incomplete_failed_or_mismatched_receipts(self):
        cases = []
        a = bundle(); a["status"]["completed_steps"] = 2; cases.append(a)
        a = bundle(); a["status"]["state"] = "running"; cases.append(a)
        a = bundle(); a["status"]["exit_code"] = 17; cases.append(a)
        a = bundle(); a["outputs"][1]["result"]["exit_code"] = 17; cases.append(a)
        a = bundle(); a["outputs"][1]["result"]["handoff_accepted"] = False; cases.append(a)
        a = bundle(); a["outputs"][2]["result"]["stdout_truncated"] = True; cases.append(a)
        a = bundle(); a["outputs"][1]["job_id"] = "relayforge-job-1792429049-cccccc"; cases.append(a)
        a = bundle(); a["outputs"][0]["result"]["step"] = 2; cases.append(a)
        a = bundle(); a["outputs"].pop(); cases.append(a)
        a = bundle(); a["outputs"][0]["stderr"] = "\0"; cases.append(a)
        a = bundle(); a["outputs"][0]["stdout"] = "x" * 9000; cases.append(a)
        a = bundle(); a["outputs"][0]["result"]["exit_code"] = True; cases.append(a)
        a = bundle(); a["status"]["completed_steps"] = True; cases.append(a)
        a = bundle(); a["status"]["surprise"] = "unsafe"; cases.append(a)
        for idx, value in enumerate(cases):
            with self.subTest(idx=idx), self.assertRaises(relayforge.InvalidChain):
                inspect(value)

    def test_schema_job_id_and_large_payload_denied(self):
        with self.assertRaises(relayforge.InvalidChain):
            inspect(bundle(), "relayforge-job-1792429049-000000")
        with self.assertRaises(relayforge.InvalidChain):
            relayforge.inspect_export(b"x" * (relayforge.MAX_BUNDLE_BYTES + 1), JOB)
        for blob in [b"", b"<html>not json</html>", b'{"schema":999}', b"{}\x00"]:
            with self.subTest(blob=blob), self.assertRaises(relayforge.InvalidChain):
                relayforge.inspect_export(blob, JOB)

    def test_local_read_only_entrypoint_does_not_write_export(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "chain.json"
            path.write_text(json.dumps(bundle()))
            before = path.read_bytes()
            relayforge.main(["--bundle", str(path), "--expected-job-id", JOB])
            self.assertEqual(path.read_bytes(), before)

    def test_rejects_symlink_input(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "actual.json"
            path.write_text(json.dumps(bundle()))
            alias = Path(d) / "chain.json"
            alias.symlink_to(path)
            with self.assertRaises(relayforge.InvalidChain):
                relayforge.main(["--bundle", str(alias), "--expected-job-id", JOB])


if __name__ == "__main__":
    unittest.main()
