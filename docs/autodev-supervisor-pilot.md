# Bounded local autonomous development pilot

This is a **source-only, manually triggered experiment** for issue #163.
No daemon, scheduler, external account connection, model installation,
authentication change or background service is installed.

A user-supplied private JSON manifest declares a single repository, exact
initial commit SHA, and 3–5 short tasks with 1–2 permitted tracked source
files each. The operator must create a clean independent worktree on an
autodev/ branch and a private (0700) state directory OUTSIDE the worktree.
Run and PR creation both require explicit approval flags.

Example manifest (replace the SHA with the actual full checkout SHA):

~~~json
{
  "schema": 1,
  "repository": "AlexandrShapkin/relayforge",
  "expected_sha": "0123456789abcdef0123456789abcdef01234567",
  "tasks": [
    {"id": "guard-test", "prompt": "Add a small offline guard regression test",
     "paths": ["scripts/test_local_recovery.py"]},
    {"id": "docs-test", "prompt": "Clarify the verified recovery test contract",
     "paths": ["docs/independent-local-recovery.md"]},
    {"id": "parser-test", "prompt": "Add one bounded recovery parser regression",
     "paths": ["crates/relayforge-mcp/src/workstation_recovery.rs"],
     "recipe": "rust-cargo-test"}
  ]
}
~~~

Check the plan without running a model:

~~~sh
python3 scripts/autodev_supervisor.py plan --manifest /private/queue.json --repo /private/relayforge-worktree
~~~

Run using an existing, independently verified Codex executable only after
reviewing the manifest, repository scope and local account permissions:

~~~sh
python3 scripts/autodev_supervisor.py run --apply --manifest /private/queue.json \
  --repo /private/relayforge-worktree --state-dir /private/autodev-state \
  --codex /absolute/verified/path/to/codex \
  --codex-sha256 ACTUAL_64_CHAR_HEX_SHA256 \
  --codex-home /private/independently-authorized-codex-profile \
  --test-bwrap /absolute/verified/path/to/bwrap \
  --test-bwrap-sha256 ACTUAL_64_CHAR_HEX_SHA256
~~~

To run only one or two stages per invocation, pass `--max-stages 1`
or `--max-stages 2`. If the process finishes its allotted stages cleanly,
the private receipt stays at `ready` and another explicit `run --apply`
continues from the verified SHA without repeating prior commits. The
`--publish-draft` option refuses partial batches; a crashed or failed
`started` attempt still requires manual reconciliation, never retry.

Read progress or interruption status:

~~~sh
python3 scripts/autodev_supervisor.py status --manifest /private/queue.json \
  --repo /private/relayforge-worktree --state-dir /private/autodev-state
~~~

To create a Draft PR with the operator's existing local GitHub credentials
after all commits, choose --publish-draft during run, or explicitly invoke
publish --apply with the same manifest, repository and state directory.
It can push a dedicated autodev/ branch and create a Draft PR. It NEVER
auto-reviews, auto-merges or deploys.

## Execution contract

- Three to five stages; each Codex call lasts at most 20 minutes. Timeout or interruption terminates the private process group; the checkpoint remains ambiguous and cannot be retried automatically.
- The operator supplies an independently trusted SHA256 for the exact installed Codex executable; the runner hashes it before every model stage. This narrows replacement risk but does not eliminate filesystem execution races.
- Codex executes with a temporary HOME rather than the operator's normal
  home. To use an existing, separately authorized dedicated Codex profile,
  supply `--codex-home /absolute/private/profile` pointing to a trusted 0700
  directory outside the worktree and checkpoint state. No ambient CODEX_HOME
  is inherited. This avoids unintentionally forwarding the operator's
  GitHub/SSH configuration; it does NOT prove credential isolation from a
  malicious local process or replace an OS sandbox/security review.
- Codex receives a temporary copy of bounded, regular, tracked source files
  WITHOUT .git or untracked content. It receives no GitHub/SSH token,
  SSH_AUTH_SOCK or unrelated environment secrets from the supervisor.
- The Codex call requests workspace-write sandbox and never-approve mode.
  It cannot get filesystem/network powers from this wrapper.
- Only explicitly allowlisted changed source files are copied back.
  The wrapper refuses symlinks, staged/untracked paths, binary changes,
  whitespace errors and more than 180 changed lines per task.
- Every candidate receives a bounded pre-commit source check: Python uses
  AST parsing without execution, TOML uses the standard parser, Markdown must
  be nonempty; Rust uses an explicitly nominated executable via
  `--rustfmt /absolute/verified/path/to/rustfmt` with `--check`, before
  any candidate is copied back. Shell/YAML edits are refused until audited
  validators exist. These are **syntax/format checks, not project tests**.
- Each task can select one of two **fixed, allowlisted** test recipes:
  `python-unittest` (default) or `rust-cargo-test` (required for any
  `.rs` path). The Rust recipe uses only the system-installed
  `/usr/bin/cargo test --locked --offline --workspace`, with distro
  `/usr/bin/rustc` and direct `/usr/bin/gcc` linker available for compilation/linking,
  and with `HOME` and
  `CARGO_HOME` isolated under `/tmp` and the entire source tree mounted
  read-only. It intentionally does **not** expose a user's rustup profile,
  crates.io login, registry cache, SSH agent or network. Therefore projects
  with unvendored dependencies will fail closed; it does not yet replace
  the normal CI Rust checks.
- Before **every** local commit, the changed candidate snapshot must
  pass an isolated, fixed Python unittest discovery command:
  `/usr/bin/python3 -I -B -m unittest discover -s scripts -p 'test_*.py'`.
  An explicitly SHA256-pinned, locally installed `bubblewrap` executable
  is required. The project source is mounted read-only, network namespaces
  are unshared, HOME is temporary, and the runner never inherits operator
  credentials. The bounded timeout is `--test-seconds` (15–240 seconds,
  default 120). A failing/timed-out test leaves the attempt ambiguous, with
  **no commit**. Only the fixed Python and offline Cargo recipes are supported; general
  repo-specific recipes and authenticated CI attestations are NOT yet
  implemented. Python tests can fail on repositories without
  `scripts/test_*.py`, and offline Cargo requires self-contained dependencies.
- CI tests use a **fake bubblewrap** to assert the gate contract; they do
  not prove bubblewrap works on the operator's Linux kernel or that the
  snapshot's untrusted tests cannot abuse a host kernel. A real isolated
  deployment requires an independent containment test and review.
- After each accepted stage, only a local commit is made on the dedicated
  branch. A private 0600 receipt is fsynced after every checkpoint.
- Receipt reads use NOFOLLOW descriptor opening, ownership and exact 0600 checks. A symlink, corrupt or oversized ledger fails closed.
- The receipt stores only task IDs, manifest SHA256, commit SHAs and coarse
  states. No prompts, raw model output, source or credentials are logged.
- The supervisor writes a STARTED receipt before invoking Codex. A crash
  or failed run leaves this ambiguous state and cannot automatically retry.
  A crash between commit and receipt leaves a SHA mismatch and also refuses.
- Single-writer file lock prevents concurrent runs on the same state.
- Publishing is separately gated. An ambiguous push/PR operation leaves
  PUBLISHING, with NO automatic retry or duplicate PR.

## RelayForge job.chain: read-only evidence adapter

The separate `scripts/autodev_relayforge.py` adapter accepts a JSON export
assembled by an authorized RelayForge client. It **never calls MCP**, opens
network connections or modifies any service. Export schema 1 contains
`status` (the JSON returned by `job.chain.status`) and ordered `outputs`
(one JSON object from `job.chain.output` for each 1-based step), plus
`schema: 1`. Use an operator-owned private 0600 export file and the exact
returned job ID:

~~~sh
python3 scripts/autodev_relayforge.py \
  --bundle /private/chain-export.json \
  --expected-job-id relayforge-job-1792429049-07f0cb
~~~

The adapter checks the fixed chain ID, 2–6 completed stages, consistent
step receipts, zero exit codes and bounded UTF-8 output, then prints only
the stage count and a SHA256 fingerprint. It never prints stage stdout,
stderr or scripts. **The file itself is not authenticated**; even a valid
report means only that the exported JSON *claims* successful offline work,
not that the current source checkout was tested or that a live RelayForge
worker was queried. Until live read-only MCP authentication and source-SHA
binding are implemented, this adapter MUST NOT be used to authorize a
commit, source edit, merge, deployment or unsafe operation.

## Fixed one-night systemd schedule (source-only, NOT activated)

`scripts/autodev_timer.py` provides a one-night, one-stage-per-hour,
**finite** user-systemd timer design. It is safer than an indefinitely
recurring automation: it renders an exact set of 3–5 UTC `OnCalendar`
entries derived from the manifest. Missed windows are not caught up
(`Persistent=false`); finished runs are no-ops; stale, failed or ambiguous
stages are never silently repeated. The service invokes the supervisor
with `--max-stages 1` and no auto-publish. It never merges or deploys.

The operator must create a private (0600) JSON configuration whose
`schema: 1` fields are:

~~~json
{
  "schema": 1,
  "manifest": "/private/queue.json",
  "repo": "/private/linked-autodev-worktree",
  "state_dir": "/private/stage-state",
  "codex": "/usr/bin/codex",
  "codex_sha256": "REPLACE_WITH_64_HEX",
  "test_bwrap": "/usr/bin/bwrap",
  "test_bwrap_sha256": "REPLACE_WITH_64_HEX",
  "codex_home": "/private/authorized-codex-profile",
  "consent_file": "/private/allow-autodev",
  "runner": "/absolute/trusted/codex-smart/scripts/autodev_timer.py",
  "start_utc": "2026-10-21T00:15:00Z",
  "interval_minutes": 60,
  "stage_seconds": 900,
  "test_seconds": 120
}
~~~

`start_utc` is an **example**, not an installed schedule. Paths and
executable hashes must be replaced and verified by the operator. The
`repo`, state and Codex profile directories must remain disjoint.
To preview exact unit contents without enabling anything:

~~~sh
python3 -I scripts/autodev_timer.py render --config /private/autodev-night.json
~~~

Render prints the service and timer definitions as JSON. Manually review
them and place them into the appropriate user systemd unit files **only
after separate local acceptance**. It never writes those files. To permit
the finite run, the local operator must separately create a private 0600
consent file with the precise contents
`ALLOW_CODEX_SMART_AUTODEV\n`. The real `run` entrypoint refuses
without it, outside the UTC schedule, or if a checkpoint is inconsistent.

The timer intentionally does not auto-install, enable, run or publish.
Live activation depends on a proved bubblewrap user-namespace environment,
Codex access with separate authorization, a complete offline recipe and
independent source review. Do not disable Ubuntu's AppArmor user-namespace
policy to make a sandbox test green.

## Deliberately incomplete

This is a controlled local pilot, not an installed autonomous system.
It performs fixed offline Python unittest or offline Cargo recipes in a
required bubblewrap namespace, but does NOT implement dependency-cache
provisioning, approved repository-specific test recipes, exact-SHA GitHub
CI checks, live RelayForge
job-chain RPC calls, automatic scheduler installation, production recovery, or automatic
code review. A successful local commit
is not evidence of correct implementation. Every PR requires normal
independent CI and review. The stage timeout is a time budget, NOT a
monetary token/API limit.

Do not deploy a live Codex runner on ThinkPad before independent review,
separate explicit local consent and security/fault-injection verification.
No ChatGPT Tasks slot is needed for the pilot. A future native supervisor
can adopt the same durable fail-closed checkpoint semantics while treating
RelayForge jobs only as offline evidence-producing steps.

Run isolated fake-Codex tests without any account/network:

~~~sh
python3 -B -m unittest scripts/test_autodev_supervisor.py
~~~
