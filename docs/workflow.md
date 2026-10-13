# Repository development workflow

GitHub [AlexandrShapkin/codex-smart main](https://github.com/AlexandrShapkin/codex-smart/tree/main)
is the canonical accepted source. Local branches, worktrees and deployed directories
are independent snapshots. A branch name or deployment directory name is not proof
of source identity. Every substantial task starts in a new branch and worktree from
an explicitly verified GitHub main commit. Never synchronize by overwriting files.

## Start a Codex task

Before editing, inspect the opened checkout and all applicable AGENTS.md files:

```bash
just status
git remote -v
git worktree list --porcelain
git status --porcelain=v1 --untracked-files=all
```

`just status` is offline/read-only: root, branch, HEAD, normalized canonical origin,
cached origin/main divergence, changes and registered worktrees. Remote freshness
stays **unknown** until an explicit network observation. Remote URLs outside the
canonical HTTPS/SSH forms are refused without printing them. Git inspection disables
fsmonitor, hooks and optional index writes. Use trusted Git/Python/just executables;
these developer commands do not invoke discovered capability tools.

Verify origin points to this repository before fetching. Do not publish diagnostic
output containing credential-bearing URLs or private filenames. Record state privately
when needed; share only sanitized findings. Then fetch and compare without checkout:

```bash
git fetch --no-tags --no-recurse-submodules origin refs/heads/main
git ls-remote --exit-code origin refs/heads/main
git rev-parse FETCH_HEAD origin/main
git rev-list --left-right --count HEAD...origin/main
git log --oneline --left-right HEAD...origin/main
```

The GitHub response, fetched commit and origin/main must agree. Record the full
40-character SHA and all local-only/main-only commits plus staged, unstaged and
untracked paths. Do not assume a historical SHA is still current. Select a new
absolute path **outside every existing worktree**, with an existing trusted parent:

```bash
just task-start chore/my-task /absolute/new/task-worktree FULL_MAIN_SHA
cd /absolute/new/task-worktree
just source-verify FULL_MAIN_SHA
just context
just issues
```

Replace placeholders with literal values. `task-start` uses the canonical public
HTTPS endpoint, validates origin, checks GitHub main before and after an explicit
fetch, and requires the fetched SHA to match the selected SHA. It creates a new
feat/fix/docs/chore branch at that commit. URL/HTTP overrides require manual inspection;
credential helpers, non-HTTPS protocols and hooks are disabled for this public fetch.
It never checks out, stashes, merges or edits the starting worktree. It writes shared
Git refs/worktree metadata, so concurrent operations in the same repository still
need coordination. GitHub main may advance after the observation; the recorded SHA
remains the task base, and PR integration rechecks freshness.

Dirty, detached or diverged starting checkouts are permitted and preserved. An
existing destination, existing task branch, relative/traversal/symlink path, nested
worktree destination, unexpected origin or changed main is a refusal. Inspect an
existing task instead of rerunning creation. Do not reset, clean, force checkout,
rebase destructively, stash, prune stale worktree registrations or automatically
merge somebody else's changes. Report conflicts/unexpected state and retain it.
`source-verify` requires exact HEAD and no tracked or untracked changes; ignored
benchmark artifacts are deliberately outside that source check.

Use `just` as the stable developer and CI command surface. Start with `just context`
or `just context STAGE`; read its contract and only the referenced docs/source needed
for the change. Context is capped at 8192 UTF-8 bytes and never launches discovered
tools or reads live GitHub state. A clipped excerpt points to the complete contract;
the byte limit never excuses missing evidence or verification.

Inside the isolated task, the loop is `just context`, `just issues`, implement one bounded stage slice,
`just docs-generate`, `just check`, inspect all diffs/new files, then record PR/CI
evidence. `just security-fetch` is the explicit public advisory refresh;
`just security` uses the cached database. CI runs the same `just check` gate.

## Validate and integrate

Read ROADMAP.md, the owning stage contract and relevant ADRs before nontrivial edits.
Keep one acceptance slice and add isolated offline regression tests for behavior.
Use [development prerequisites](development.md), then run:

```bash
python3 -B -m unittest discover -s scripts -p 'test_*.py'
just docs-check
CARGO_NET_OFFLINE=true just check
just security
git diff --check
git diff
git status --short
```

Prepare Cargo/advisory caches only through explicit `cargo fetch --locked` and
`just security-fetch` when needed. A missing cache is a reported blocker, not a
reason to weaken verification. Run installed `just nextest` where available.
Inspect new files as well as tracked diffs. Never run live benchmark calls to validate
repository workflow changes; the Python tests use isolated fixtures/fake hosts.

Commit only on the task branch with small Conventional Commits. With explicit
permission to push and open a PR, use native Git/gh and the existing PR template:

```bash
git push --set-upstream origin chore/my-task
gh pr create --repo AlexandrShapkin/codex-smart --base main --head chore/my-task --draft --body-file /absolute/pr-body.md
git rev-parse HEAD
gh run list --repo AlexandrShapkin/codex-smart --commit FULL_PROPOSED_SHA --json headSha,workflowName,status,conclusion,url
```

Record base SHA, proposed SHA, scope/issue, exact local results and unresolved limits.
Require successful **CI / check** and **Security / review** from GitHub Actions app
15368 for the exact proposed commit, plus owner review and current branch protection
requirements. Confirm the PR head still equals that SHA. Push runs verify the branch
commit; pull-request runs also test GitHub's synthetic merge commit. Neither stale
checks nor a local pass establish remote acceptance. After any new commit, rerun the
appropriate gates and collect new evidence. No automatic merge. After an authorized
merge, verify GitHub main again and create the next task worktree; no checkout cleanup
is required to start the next slice. GitHub Issues own outstanding decisions.

## Pinned source snapshots on ThinkPad and srv0

ThinkPad runs separately authorized model executions; srv0 independently grades
sanitized submissions using its qualified runtime. Pin each host's approved source
SHA, source receipt digest, runner/adapter and runtime inventory hashes, campaign
contract and qualification reference. Host roles can intentionally retain different
reviewed snapshots. Source verification alone does not qualify a runtime or authorize
execution. Product installation/release remains the separate planned
[distribution contract](distribution.md).

From a trusted repository with a verified fetched origin/main containing the
approved commit, export **committed files only** to a new directory:

```bash
just snapshot-export FULL_ACCEPTED_SHA /absolute/new/source-snapshot
just snapshot-verify /absolute/new/source-snapshot FULL_ACCEPTED_SHA RECORDED_RECEIPT_SHA256
```

Export accepts only an exact commit in cached origin/main history, rejects symlinks
and submodules, and never copies uncommitted/untracked/ignored files, credentials,
Git metadata or benchmark artifact directories. It records every tracked file's
SHA-256 and executable mode in `.codex-smart-source.json`, written last as completion
evidence. Save the returned receipt SHA-256 and source SHA in the reviewed host
deployment record, independently of the transferred directory. A checksum proves
integrity relative to that record; GitHub/PR review supplies source trust.

Transfer only this public snapshot into a separately reserved **new** host directory
with no existing contents; no automatic transfer or activation is provided. Use
already provisioned authenticated transport, preserve executable modes, and never
copy auth stores, keys or tokens. On each host use a trusted copy of the verifier:

```bash
python3 -B /trusted/checkout/scripts/workflow.py snapshot-verify --snapshot /absolute/host/source-snapshot --expected-sha FULL_ACCEPTED_SHA --receipt-sha256 RECORDED_RECEIPT_SHA256
```

This works without `.git` and performs no subprocess, network or writes. It checks
the external receipt digest, expected SHA, complete file inventory, file hashes,
executable modes, symlinks and hardlinks. Missing snapshots, receipts, extra files
(including build/cache files) or mismatches fail closed. Keep builds, runtime caches
and evidence outside source snapshots. Snapshot verification reports source/config
drift only; it does not inspect Codex auth/config or machine secrets. Inspect a
legacy deployment read-only, retain it, and document unknown identity until a reviewed
manifest can be reconstructed from its original accepted source. Do not attach a new
identity label to unverified bytes or replace the existing srv0 grading installation.

Only after source, runtime and role checks pass may an operator explicitly select a
new snapshot for a future authorized run. Record that selection and retain the older
snapshot and all accepted evidence. Repeated export/creation refuses even a partial
existing path; repeated verification is read-only. Snapshot directories and parents
must be controlled by the operator with no concurrent writer; these checks are not
a filesystem sandbox against racing adversaries.

## Interruption, resumption and mismatches

After a connection interruption, inspect status, HEAD, worktree registrations and
partial destinations before any action. Fetch failure can leave updated Git refs;
it cannot authorize proceeding with an unverified base. Failed worktree creation can
leave a branch/registration/directory. Export failure can leave partial files without
a valid receipt. Preserve each partial result, inspect it and use a new destination
for a fresh attempt; never automatically clean or overwrite it. Existing task work
resumes on its recorded branch/HEAD, without recreating or synchronizing the checkout.

Live model execution remains a separate explicitly authorized operation under
[benchmarking](benchmarking.md) and the [host contract](benchmark-host.md). Record
campaign/source identities, artifact paths, started-attempt ledger and authenticated
grading receipts before launch. Read the existing ledger after interruption: a
started attempt is spent even if its result is missing. Use only the campaign runner's
documented resume path with the same run ID, pins, budgets and retained evidence.
Never create a new run ID, delete a ledger or rerun a spent model execution to recover
a connection. The adaptive runner's retry authority and authenticated srv0 receipts
remain unchanged. Preserve accepted historical results; incomplete or contradictory
evidence stays visible. Any source/hash/host mismatch stops dependent operations
until the owner resolves it, without replacement, budget changes or inferred success.

## Sources of truth

The permanent [issue taxonomy and closeout rules](../CONTRIBUTING.md#issue-governance)
live in CONTRIBUTING.md. Every actionable issue has one primary area, one severity,
at most one current stage owner and one work-kind. Milestones group releases;
stage labels track mutable implementation ownership.

- `docs/stages.json` owns stable stage IDs, dependency order, issue links, context
  entry points and recorded implementation progress. Each stage has a contract
  defining scope, non-goals, acceptance, validation, context and follow-ups.
- `docs/documents.json` owns each Markdown document's maintainer, role and stages.
  [The generated index](index.md) is the entry point. Current docs describe delivered
  behavior; ADRs own durable decisions; dated diagnostics are historical evidence.
- GitHub Issues own live actionable state, dependencies and acceptance discussion.
  `just issues` explicitly fetches bounded metadata through authenticated gh. Local
  `docs/issues/*.md` are design references, not synchronized issue status or closure.
- Workspace Cargo version owns product SemVer. Recorded stage progress never bumps
  versions or implies a release, merged PR, closed issue or complete milestone.

## Offline correction gate

`just docs-check` validates schemas, unique IDs/ownership, dependency cycles, source
paths, required contract sections, local Markdown links/fragments and exact generated
views. It never calls git/gh, opens external URLs, executes registry commands, writes
files or consults clocks/auth/config. Python stdlib is sufficient; no reference
checkout or optional tools are required. Inputs are bounded to 32 stages, 128 owned
documents and 128 KiB per file. Document discovery is limited to root Markdown,
`docs/` and `.github/`; runtime and generated build trees are excluded.

`just docs-generate` is the separate explicit write: it rebuilds ROADMAP.md and
docs/index.md deterministically from the registries, without timestamps or live issue
states. Update registries/contracts first; inspect both generated diffs. Add ownership
for every new document. Never edit generated views directly.

Preserve validated stage evidence and contracts in later work. Reopen a validated
slice only for a reproducible finding, record the regression and use the smallest
repair. Baseline evidence is linked from its stage; later stages do not erase it.
Automatic stage advancement, runtime orchestration and issue-state copying are out
of scope. Workflow tooling remains outside the thin Rust launcher.

## Reference and dogfooding

The local rustcraft-b173 reference supplied the coherent-stage/acceptance pattern and
canonical `just` developer loop. This repository adds machine-readable registries and
offline governance for its own smaller scope; it has no runtime dependency on rustcraft.

The initial bounded-context implementation is retained in its
[dated evidence](diagnostics/2026-10-06-workflow.md). The
[normalization audit](diagnostics/2026-10-14-workflow-normalization.md) records the
observed repository divergences and host limitations; it is historical evidence,
not live deployment or issue state. Use `just context` for the current stage.
