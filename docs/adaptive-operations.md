# Adaptive split-host operator runbook

This benchmark-only workflow composes the existing authenticated adaptive runner.
It does not enable production model routing or authorize a campaign. Source,
qualification, frozen budgets and independently graded evidence remain separate
gates. [Benchmarking](benchmarking.md) owns interpretation;
[repository workflow](PROJECT_WORKFLOW.md) owns source snapshots.

## Source and roles

Implementations start from verified GitHub main in isolated worktrees. This slice
started at `5102c0ebefeb53c3dbd56021266b340524be7ad3`, verified by fetch and
ls-remote. The opened checkout at `5cd1b95` stayed on its branch (4 local-only /
38 main-only commits). Existing historical dirty worktrees and the stale registration
were inspected and preserved. Implementation uses the dedicated
`feat/adaptive-split-host-orchestrator` worktree; no existing source or evidence was
synchronized. Roadmap progress and all frozen benchmark JSON contracts are unchanged.

After review/merge, independently select accepted source snapshots containing
`scripts/benchmark_adaptive_orchestrator.py` on both hosts. Use `just snapshot-export`
and `just snapshot-verify`; record the full source SHA and independent receipt digest.
Keep the existing srv0 installation and accepted runtime snapshot. New source and
campaign directories are separate; do not replace the accepted deployment.

ThinkPad executes models. srv0 grades sanitized public-fixture submissions using
the accepted production grader and immutable runtime. Direct pinned SSH from the
authorized ThinkPad has been independently verified. A Codex environment may reject
its system SSH configuration before connection; that is not evidence that srv0 is
generally unavailable. Diagnose the environment separately, without modifying SSH
configuration, bypassing host verification or transferring keys/authentication.

## Plan and offline preflight

Use a reviewed operator-owned configuration (mode 0600) with these exact fields.
Replace every placeholder with a literal approved path, full SHA or SHA-256 digest.
All grader paths must be canonical absolute `/tmp/...` paths. The state destination
is part of the reviewed plan and must be new, outside source/runtime snapshots.
Production preflight requires agent state, source and adapter paths outside `/tmp`
and the invoking TMPDIR: these must remain outside model-writable temporary roots.
Keep the accepted immutable runtime closure unchanged. Existing parent directories
must be operator-controlled; do not relocate old snapshots or evidence to prepare them.

```json
{
  "schema_version": 1,
  "run_id": "adaptive-lifecycle-operator-v1",
  "state": "/home/user/codex-smart-evidence/adaptive-operator-v1",
  "agent": {
    "source": {"path": "/home/user/codex-smart-snapshots/source-agent", "sha": "FULL_ACCEPTED_SHA", "receipt_sha256": "SOURCE_RECEIPT_SHA256"},
    "codex": "/absolute/pinned/codex",
    "code_mode_host": "/absolute/pinned/codex-code-mode-host",
    "runtime_root": "/tmp/benchmark-runtime-agent",
    "inventory_dir": "/tmp/agent-inventory",
    "adapter": "/home/user/codex-smart-adapters/pinned-adaptive-adapter",
    "adapter_sha256": "ADAPTER_SHA256"
  },
  "grader": {
    "source": {"path": "/tmp/source-grader", "sha": "FULL_ACCEPTED_SHA", "receipt_sha256": "SOURCE_RECEIPT_SHA256"},
    "runtime_root": "/tmp/benchmark-runtime-grader",
    "inventory_dir": "/tmp/grader-inventory",
    "qualification_evidence": "/tmp/qualified-host-candidate.json",
    "qualification_sha256": "QUALIFICATION_FILE_SHA256",
    "remote_root": "/tmp/adaptive-operator-grading-v1"
  }
}
```

Run from the verified agent source snapshot, with caches and the compiled adapter
outside it. Default diagnostics never contact SSH or invoke a model. An explicit
configuration resolves profiles through the hash-pinned pure Rust replay adapter;
Python cannot choose a cheaper replacement. Planning verifies the source receipt
and freezes all 20 job identities, policy decisions, host/runtime/source pins and
the 40-attempt ceiling. Record the printed plan SHA-256 independently for every
subsequent command.

```bash
umask 077
cd /home/user/codex-smart-snapshots/source-agent
python3 -B scripts/benchmark_adaptive_orchestrator.py
python3 -B scripts/benchmark_adaptive_orchestrator.py plan --config /tmp/operator-config.json
python3 -B scripts/benchmark_adaptive_orchestrator.py initialize --config /tmp/operator-config.json --state /home/user/codex-smart-evidence/adaptive-operator-v1
python3 -B scripts/benchmark_adaptive_orchestrator.py preflight --state /home/user/codex-smart-evidence/adaptive-operator-v1 --plan-sha256 PLAN_SHA256
python3 -B scripts/benchmark_adaptive_orchestrator.py status --state /home/user/codex-smart-evidence/adaptive-operator-v1 --plan-sha256 PLAN_SHA256
```

Offline preflight checks local source/runtime/adapter readiness and reports grading
readiness as **unknown**. It does not create a successful preflight receipt. Full
preflight requires the independently working ThinkPad SSH environment:

```bash
python3 -B scripts/benchmark_adaptive_orchestrator.py preflight --state /home/user/codex-smart-evidence/adaptive-operator-v1 --plan-sha256 PLAN_SHA256 --online
```

Every request resolves the existing srv0 alias against the reviewed ED25519 pin,
keeps strict host-key checking and disables key updates/forwarding. A fixed isolated
Python bootstrap reuses the normalized snapshot verifier before importing remote
campaign code. It then verifies qualification evidence and the full accepted grading
runtime. New remote artifacts are bound to the exact plan digest. SSH identity does
not replace runtime qualification or source integrity.

## Separately authorized execution and grading

The following are **future operator commands after separate campaign authorization**.
Do not run them as implementation tests. `--online` permits pinned transport;
`--authorize-execution` separately permits model attempts. Grading has its own flag.
There is no automatic multi-stage launch or transport/model retry.

```bash
python3 -B scripts/benchmark_adaptive_orchestrator.py initial --state /home/user/codex-smart-evidence/adaptive-operator-v1 --plan-sha256 PLAN_SHA256 --online --authorize-execution
python3 -B scripts/benchmark_adaptive_orchestrator.py transfer-1 --state /home/user/codex-smart-evidence/adaptive-operator-v1 --plan-sha256 PLAN_SHA256 --online
python3 -B scripts/benchmark_adaptive_orchestrator.py grade-1 --state /home/user/codex-smart-evidence/adaptive-operator-v1 --plan-sha256 PLAN_SHA256 --online --authorize-grading
python3 -B scripts/benchmark_adaptive_orchestrator.py authenticate-1 --state /home/user/codex-smart-evidence/adaptive-operator-v1 --plan-sha256 PLAN_SHA256 --online
python3 -B scripts/benchmark_adaptive_orchestrator.py escalate --state /home/user/codex-smart-evidence/adaptive-operator-v1 --plan-sha256 PLAN_SHA256 --online --authorize-execution
python3 -B scripts/benchmark_adaptive_orchestrator.py transfer-2 --state /home/user/codex-smart-evidence/adaptive-operator-v1 --plan-sha256 PLAN_SHA256 --online
python3 -B scripts/benchmark_adaptive_orchestrator.py grade-2 --state /home/user/codex-smart-evidence/adaptive-operator-v1 --plan-sha256 PLAN_SHA256 --online --authorize-grading
python3 -B scripts/benchmark_adaptive_orchestrator.py authenticate-2 --state /home/user/codex-smart-evidence/adaptive-operator-v1 --plan-sha256 PLAN_SHA256 --online
python3 -B scripts/benchmark_adaptive_orchestrator.py finalize --state /home/user/codex-smart-evidence/adaptive-operator-v1 --plan-sha256 PLAN_SHA256 --online
python3 -B scripts/benchmark_adaptive_orchestrator.py archive --state /home/user/codex-smart-evidence/adaptive-operator-v1 --plan-sha256 PLAN_SHA256
```

The first stage writes all 20 first-attempt ledgers. A flushed/fsynced `started.json`
consumes budget before launch, including launch failures and uncertain interruptions.
Only the existing Rust controller can authorize attempt two after independently
graded failure and strict escalation. At Strong/High there is no higher profile;
those failures remain failures. Each job has at most two attempts and one retry;
the global maximum remains 40. Delegation is disabled, with zero model handoffs
and zero delegation overhead. No configuration field can increase these limits.

Only bounded JSON from the existing sanitized bundle allowlist crosses to srv0.
Raw trace/stderr, credential files and keys stay out of transport. The host grades
using the accepted independent production boundary. Authentication retrieves the
fresh summary digest with the existing pinned SSH handoff, compares it with the
grading-stage receipt, verifies every returned row/hash, and binds rows to local
started/result/submission identities. Missing, duplicate, changed or malformed
evidence stops escalation and finalization.

## Recovery and archival

Inspect `status` and the private `stages/*.started.json`/completion receipts first.
One persistent lock per campaign prevents concurrent operations; process exit
releases the OS lock without deleting evidence. An incomplete stage requires
explicit `--resume` and the same state path and reviewed plan digest:

```bash
python3 -B scripts/benchmark_adaptive_orchestrator.py transfer-1 --state /home/user/codex-smart-evidence/adaptive-operator-v1 --plan-sha256 PLAN_SHA256 --online --resume
python3 -B scripts/benchmark_adaptive_orchestrator.py grade-1 --state /home/user/codex-smart-evidence/adaptive-operator-v1 --plan-sha256 PLAN_SHA256 --online --authorize-grading --resume
python3 -B scripts/benchmark_adaptive_orchestrator.py initial --state /home/user/codex-smart-evidence/adaptive-operator-v1 --plan-sha256 PLAN_SHA256 --online --authorize-execution --resume
```

Transfer copies only missing files and rejects different existing bytes/modes.
Grading retains validated completed rows and grades only missing rows. Finalization
and archive creation similarly preserve and compare completed outputs. Completed
stages return their checked receipts; they do not launch another model invocation.
Agent resume skips every started attempt, including those without results. Transport
or grading failure cannot cause agent replay. A remote operation may still hold its
lock after a connection loss: wait for it to finish before an explicit resume.

Do not change run IDs, reinitialize a spent campaign, remove locks/ledgers, repair
evidence in place or choose a fresh state path to hide uncertain attempts. A partial
initial plan write, unreadable/truncated file or unbound remote directory is a
non-destructive refusal requiring operator inspection; it is not permission to
discard evidence. Source/runtime/receipt mismatches require independent resolution.

Finalization keeps all 20 jobs and failed/uncertain attempts in denominators. Missing
tokens, latency and cost remain unknown. Archive receipts contain source manifests,
execution-file integrity hashes, authenticated grading rows and stage/final receipts;
raw logs remain local. Archive files are created exclusively and frozen read-only.
Repeated archive calls verify integrity and refuse to overwrite conflicting evidence.
Completion checks require the matching start receipt, complete output inventory,
typed stage result and unchanged safe directory permissions. Archival rechecks source
bytes and completed archive modes; diagnostics never repair drift. The
[adversarial audit](diagnostics/2026-10-14-adaptive-orchestrator-audit.md) records the
confirmed defects, transition boundaries and fake process-interruption evidence.
Archives are **not accepted performance evidence**: no winner or savings claim exists
without independent comparative acceptance. Operational transport/recovery latency
is not fabricated as model-delegation overhead or a measured cost saving.

## Offline implementation evidence and limits

The operator-supplied rehearsal at
`/home/user/codex-smart-evidence/srv0-20261012/adaptive-offline-split-host-rehearsal-20261014`
is retained. Its full-matrix receipts explicitly say zero real Codex executions,
synthetic interrupted attempts and no accepted quality/cost evidence. It informs
protocol coverage; it does not authorize this campaign or qualify a new snapshot.

Tests inject fake model, transport, runtime and grading boundaries; production CLI
has no fake acceptance mode. Exact local/CI/Security results belong in the draft PR.
Remaining operational gates are owner review, accepted source/adapter selection,
fresh host-side preflight, and separate live execution/grading authorization.
