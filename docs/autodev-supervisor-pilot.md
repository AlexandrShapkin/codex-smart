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
     "paths": ["crates/relayforge-mcp/src/workstation_recovery.rs"]}
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
  --codex /absolute/verified/path/to/codex
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

- Three to five stages; each Codex call lasts at most 20 minutes.
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

## Deliberately incomplete

This is a controlled local pilot, not an installed autonomous system.
It does NOT perform independent source validation recipes, exact-SHA
GitHub CI checks, RelayForge job-chain adapter calls, restart scheduling,
production recovery, or automatic code review. A successful local commit
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
