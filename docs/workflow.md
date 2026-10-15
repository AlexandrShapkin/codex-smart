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

An outdated checkout may not yet contain `task-start`. After the same native GitHub
verification above, confirm the task branch and destination do not exist, the
destination's existing parent chain contains no symlinks, and the destination is
outside all registered worktrees. Bootstrap with native Git:

```bash
git worktree add -b chore/my-task /absolute/new/task-worktree FULL_MAIN_SHA
cd /absolute/new/task-worktree
just source-verify FULL_MAIN_SHA
just context
```

Use an accepted main commit containing the normalized tooling. Do not copy scripts
into, synchronize or overwrite the older checkout to obtain the new commands.

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

Commit only on the task branch with small Conventional Commits. With
in-scope task authority to push and open a PR (standing only once effective),
use native Git/gh and the existing PR template; separate merge gates apply:

```bash
git push --set-upstream origin chore/my-task
gh pr create --repo AlexandrShapkin/codex-smart --base main --head chore/my-task --draft --body-file /absolute/pr-body.md
git rev-parse HEAD
gh run list --repo AlexandrShapkin/codex-smart --commit FULL_PROPOSED_SHA --json headSha,workflowName,status,conclusion,url
```

### Review and merge authorization

This section defines bounded standing engineering authority under
[Issue #127](https://github.com/AlexandrShapkin/codex-smart/issues/127).
It becomes effective only after owner-authorized acceptance into GitHub `main`.
Bootstrap remains under the preceding main rules: separate personal owner merge
consent for this PR at its full head SHA, plus all other gates. This proposal does
not authorize its own merge or PR #125. The explicit owner prohibition on merging
PR #125 remains effective until the owner expressly lifts it.

Once effective, owner-provided standing authority covers ordinary bounded
codex-smart engineering within agreed issue/contract scope: task branches/worktrees,
commits, pushes, PRs, independent review, bounded check retries, Draft → Ready,
merge, postmerge verification and issue closeout. These steps and ordinary head
changes require no repeated personal owner approval. All safeguards below remain.

Separate explicit owner authority is required for production activation/deployment;
release/distribution; live benchmark campaigns or unplanned expenses;
secrets/credentials/auth or sensitive infrastructure; branch protection or mandatory
security-gate changes; destructive data loss or irreversible operations; material
escalation of authority/security boundaries; and any more specifically contracted
approval. A scoped one-shot owner decision may authorize an exception, but cannot
waive technical/security gates. An express prohibition requires an express owner
decision lifting it.
Individual owner veto, limitation or revocation overrides general delegation.
Uncertain eligibility or authority fails closed.

Record the public effective normative source (this section pinned to its accepted
main commit), version, owner-provided scope/eligibility and non-sensitive evidence
of authority and current limitations/revocations. Check that evidence remains valid
for the proposed action. Keep private chat private; record only a non-sensitive
attestation/reference sufficient to establish authority, without disclosing private
messages. If provenance cannot be established safely, stop. Assistant-written
GitHub comments, even through the linked owner account, are evidence transcription,
not personal owner decisions; account attribution alone establishes no authority.
This governance does not provision runtime/operator/reviewer credentials or alter
[ADR 0008](decisions/0008-deterministic-workflows.md) or security boundaries.

Record base SHA, full 40-character proposed PR head SHA, scope/issue, exact local
results and unresolved limits. Four independent gates apply; none substitutes for another:

| Gate | Required evidence |
| --- | --- |
| Independent technical/security review | Explicit ACCEPT by a reviewer distinct from the implementer (including ChatGPT independently reviewing Codex CLI work), with reviewer identity, scope, findings and unresolved limits, anchored to the exact full PR head SHA. The implementer's own report is not independent evidence. |
| GitHub Actions status checks | Successful **CI / check** and **Security / review**, status contexts `check` and `review` from GitHub Actions app ID **15368**, for the exact proposed head and applicable synthetic integration checks. `Security / review` is a machine status check, not a human or formal GitHub review. |
| Formal GitHub reviews and protection | All current formal reviews, unresolved review blockers and live protection requirements must permit integration. The recorded baseline `required_approving_review_count=0` waives neither independent acceptance nor authority; stronger current requirements always apply. |
| Valid scoped authority | Effective standing authority covering this ordinary action, with no applicable exception, veto or revocation; otherwise separate explicit owner authority for the identified exception/action and any PR/head binding it requires. Bootstrap requires personal PR/full-head consent under preceding main rules. |

| Example | Decision |
| --- | --- |
| Effective standing authority, covered ordinary PR, all four gates satisfied | Eligible without a new personal owner decision for each step or head. |
| Stale head or base; missing checks; unresolved blockers; unknown rules | DENY until fresh evidence satisfies every gate. |
| Special operation outside standing scope | DENY under standing authority; obtain separate explicit scoped owner authority and satisfy all other gates. |
| Owner veto/revocation, including the PR #125 merge ban | DENY; general delegation cannot override it. |
| Assistant-authored GitHub comment says “owner approved” | DENY as an authority source; establish independent owner provenance. |
| Green checks, independent ACCEPT or formal approval alone | DENY; none alone satisfies all four gates. |
| One-shot owner consent for PR #N at FULL_HEAD_SHA | Authority only within that explicit scope; a changed head requires renewed consent if that consent is the authority being relied on. |

### Draft, Ready and merge gates

Move **Draft → Ready** only after independent technical/security acceptance
and all applicable exact-head checks pass, with evidence recorded. Ready means
eligible for integration consideration; it does not authorize merge. A local pass
is not remote evidence. Push runs verify the branch commit; pull-request runs also
test GitHub's synthetic merge commit. Record their actual SHAs and relationship to
the proposed head/base; stale or unrelated runs do not establish acceptance.

Every commit changing the PR head requires new exact-head independent ACCEPT and
applicable checks. Ordinary covered PRs do not require renewed personal owner merge
consent. Re-evaluate any changed base, branch protection or CI configuration,
including strict up-to-date protection and applicable synthetic integration checks;
renew independent acceptance when the integration change is decision-relevant.
Stronger current rules always apply; a recorded baseline cannot weaken them.

Immediately before merge, re-read the actual PR head and base SHA, strict/live
branch protection, all formal reviews, required checks and unresolved blockers,
and confirm current scoped authority. Unknown, stale or conflicting state stops
integration. Bind the merge call's `expected_head_sha` (or equivalent enforced
precondition) to the reviewed full PR head SHA; if the tool cannot enforce it,
do not merge through it. This guards the head only, not an atomic base-SHA
compare-and-swap. Re-evaluate a changed base and its integration evidence before
proceeding; an earlier base observation does not prove current integration safety.
Do not synthesize approving reviews, bypass protection or use auto-merge.

### Postmerge evidence and issue closeout

After an authorized merge, read GitHub `main` again and record the actual full main
SHA, the merge commit and its relationship to the authorized PR/head. Require
successful mandatory CI/check and Security/review checks for the actual main SHA,
with run URLs/IDs, attempt numbers, SHAs and conclusions. Collect this independent
postmerge machine evidence even when all premerge gates passed. PR-head or synthetic-merge
success alone does not prove postmerge success. If main advances, distinguish the
actual merge result from the newer main and collect the applicable evidence for each.

Retain failed and uncertain attempts alongside later results. One bounded retry
of a check on the same unchanged SHA may confirm a suspected flaky check; it does
not fix or erase the initial failure, or establish a permanently clean security or
quality claim. Record both attempts and the remaining uncertainty; continued failure
or uncertainty blocks clean closeout and requires investigation rather than repeated
retries until green.

Close the issue only after its acceptance and Definition of Done (DoD) are satisfied,
with immutable evidence identifying the reviewed head, applicable authority
source/version and scope, base/protection observation, merge/main SHA and exact-SHA
check attempts. Use SHA-pinned source references and stable run/decision references,
retaining non-sensitive authority/revocation provenance without private chat
disclosure or attributing assistant transcription to the owner. Missing evidence
keeps the issue open; partial delivery requires explicit residual acceptance and an owning follow-up.
These rules do not retroactively reinterpret the decisions for #119/#120.
GitHub Issues own outstanding decisions. Start the next slice in a new verified-main
worktree; no checkout cleanup is required.

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
SHA-256 and Git mode in `.codex-smart-source.json`, written last as completion
evidence. Export explicitly sets every snapshot directory to `0700`, tracked files
to `0644` or `0755` according to their Git mode, and the receipt to `0644`, regardless
of umask. Save the returned receipt SHA-256 and source SHA in the reviewed host
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
exact file permission modes (including refusal of special permission bits), receipt
mode `0644`, and symlinks/hardlinks. Snapshot roots and all subdirectories must have
no group/world write bits; harmless directory differences such as `0700` versus
`0755` are accepted. Verification never repairs permissions. Missing snapshots,
receipts, extra files (including build/cache files) or mismatches fail closed.
Keep builds, runtime caches
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

## Read-only consistency audit

Run the bounded repository-owned audit from a trusted current task checkout. Keep
the inventory and output outside Git: absolute paths and dirty filenames can be
private. This audit does not fetch, update refs/index, execute SSH, synchronize,
repair permissions or prune anything. It shares the existing Git and snapshot
verification helpers. Explicitly declare the scope; an empty snapshot list means
**no deployments audited**, not that every deployment agrees.

Create an operator-owned, single-link inventory file with mode `0600`, for example:

```json
{
  "schema": 1,
  "repositories": ["/absolute/development/checkout"],
  "snapshots": [
    {
      "name": "agent-historical-pin",
      "host": "local",
      "path": "/absolute/reviewed/source-snapshot",
      "sha": "FULL_ACCEPTED_SHA",
      "receipt_sha256": "INDEPENDENTLY_RECORDED_64_CHARACTER_DIGEST",
      "pin": "historical",
      "role": "agent"
    },
    {
      "name": "independent-grader",
      "host": "srv0",
      "path": null,
      "sha": null,
      "receipt_sha256": null,
      "pin": "unknown",
      "role": "grader"
    }
  ]
}
```

Replace placeholders with exact independently approved values; `null` explicitly
records a missing reference. Other roles are `development-source`; pins are
`current`, `historical`, `unknown`. A historical pin can legitimately differ from
main. A current pin differing from the selected main is reported as an outdated
reference, never replaced. Snapshot SHAs must also be in accepted main history;
hash-consistent synthetic source cannot become an accepted deployment.

```bash
just consistency-audit /absolute/private/inventory.json FULL_MAIN_SHA
python3 -B scripts/workflow.py consistency-audit --inventory /absolute/private/inventory.json --expected-sha FULL_MAIN_SHA --json
```

These commands are offline. `FULL_MAIN_SHA` is the operator's recorded reference;
GitHub freshness remains unknown. Only an explicit `--github` performs canonical
HTTPS `ls-remote` before and after the audit; it never fetches. A changed expected
main, failed network observation or missing Git objects produces an incomplete
report. Existing accepted objects from the trusted invoking repository may prove
identity for an older clone without writing its Git metadata. Save JSON with a
private umask and inspect the exit status, including when redirecting output:

```bash
umask 077
python3 -B scripts/workflow.py consistency-audit --inventory /absolute/private/inventory.json --expected-sha FULL_MAIN_SHA --github --json > /absolute/private/new-audit.json
```

Exit `0` means complete declared local scope with no attention items; `1` means
known dirty/divergent/stale work or snapshot drift; `2` means incomplete or unstable
evidence. Invalid input is an explicit `E_WORKFLOW` refusal. The two repository
observations compare HEAD, refs, registrations, dirty status and changed-path
metadata; they read no uncommitted file contents. This catches repeated edits to an
already dirty file, but is not an atomic snapshot or a lock against concurrent writers.
Stop dependent work on an incomplete report and coordinate concurrent sessions.

Optional caller-supplied `pull_requests` observations use
`{"number": 84, "branch": "chore/workflow-normalization", "head": "FULL_PR_SHA", "state": "merged", "merge": "FULL_ACCEPTED_MERGE_SHA"}`;
states are `open`, `merged`, `closed`, with `merge: null` for unmerged PRs.
`remote_branches` entries use `{"branch": "main", "head": "FULL_MAIN_SHA"}`.
Collect **all** GitHub pages explicitly when preparing these catalogs; their
freshness remains caller supplied even with `--github`. Content-equivalent
classification requires the exact PR head, an accepted merge ancestor, and equal
source trees. Ancestry alone is not evidence that squash-merged work is redundant.
Every branch has `cleanup_authorized: false`.

Remote declarations always require a separate host-side check using the trusted
`snapshot-verify` command above and the independently recorded SHA/digest. Record
host identity, path, verification output, runtime/adapter qualification and observed
time in the reviewed deployment record; branch names, filenames and a `CURRENT`
pointer alone do not establish these facts. Independent ThinkPad-to-srv0 SSH access
has succeeded. Codex's execution environment may reject system SSH configuration
permissions before connecting; report that specific limitation rather than calling
srv0 unavailable. Use already verified host access, keep host-key verification, and
do not edit SSH configuration or transport credentials to make the diagnostic pass.

Keep accepted source, uncommitted work, reviewed source snapshots, runtime
dependencies, immutable evidence, temporary fixtures, regenerable caches and private
credentials distinct. Inventory only public source identity and sanitized metadata;
never read credential stores or raw benchmark traces for a consistency audit. Retain
old benchmark pins. If references disagree, preserve the conflicting bytes, stop
dependent operations, verify independently, and create a new owner-approved record
or snapshot at a new path. Never rewrite historical evidence or attach an unverified
SHA to an existing installation. Branch/worktree cleanup needs a separate owner
decision after checking unique commits, dirty files, PRs and evidence references.

## Operational source register and host-side checkpoint

[source-register.json](source-register.json) is a versioned observation using the
existing consistency-inventory schema. Its main/PR heads are recorded references,
not automatically refreshed truth. Accepted main comes from a new explicit GitHub
observation. Development worktrees are discovered locally; deployment paths and
receipt digests remain `null` until independently established. Never fill them with
guessed filenames or a candidate's self-asserted identity. A missing normalized
receipt on an intentionally historical Git copy remains unverified without making
that old source a defect.

Runtime qualification/inventory and immutable measurement evidence already have
authoritative versioned JSON registers: `benchmarks/host-contract-v1.json`,
`benchmarks/submission-grading-v1.json`,
`benchmarks/representative-measurement-candidate-v1.json` and
`benchmarks/adaptive-lifecycle-v1.json`. The [host contract](benchmark-host.md) and
[benchmarking protocol](benchmarking.md) own their interpretation. The source register
does not duplicate these frozen contracts or confer their execution authority.

Before development, run the read-only source audit, then the task-start procedure.
Before deployment or benchmark work, independently verify each approved host pin and
runtime; source equality alone is insufficient:

```bash
just consistency-audit /absolute/reviewed/checkout/docs/source-register.json FULL_CURRENT_MAIN_SHA
python3 -B scripts/workflow.py consistency-audit --inventory /absolute/reviewed/checkout/docs/source-register.json --expected-sha FULL_CURRENT_MAIN_SHA --github --json
```

The public register initially returns exit `2`: deployment identities are missing.
Copy the register into an operator-controlled private file for actual host paths,
reviewed receipt digests and additional repositories. Keep the private copy outside
Git, version its approved identities/roles, and retain earlier observations. Changing
an expected pin requires owner review; an audit never changes a pin or installation.
Update public main/PR observations only through a factual reviewed change. A stale
catalog cannot establish that source is current or accepted.

When Codex's pinned SSH configuration diagnostic refuses before connection, use an
independently authorized operator's already verified ThinkPad/srv0 access. Do not
bypass system configuration, alter credentials or weaken host-key checks. On each
host run the trusted reviewed verifier locally against explicitly identified paths:

```bash
python3 -B /trusted/reviewed/scripts/verify_host_snapshot.py --snapshot /absolute/approved/source --source-sha FULL_APPROVED_SOURCE_SHA --receipt-sha256 INDEPENDENT_SOURCE_RECEIPT_SHA256
python3 -B /trusted/reviewed/scripts/verify_host_snapshot.py --snapshot /absolute/approved/source --source-sha FULL_APPROVED_SOURCE_SHA --receipt-sha256 INDEPENDENT_SOURCE_RECEIPT_SHA256 --runtime-root /tmp/benchmark-runtime-APPROVED --inventory-dir /absolute/approved/inventory --qualification /absolute/approved/qualification.json --qualification-sha256 INDEPENDENT_QUALIFICATION_SHA256
```

Replace all placeholders from approved independent records. Missing legacy receipts
require investigation; do not mint a new receipt around unverified installed bytes.
The verifier launches no subprocess, SSH, grader, model or toolchain. It checks source
permissions/hashes through the normalized verifier, then the frozen runtime manifest
hashes, complete topology, all file sizes/modes/hashes, symlink targets, directory modes,
saved qualification and grading implementation pins. It rejects writable identity
files/directories and aliased regular files; it never repairs them. Do not refactor
the evidence-pinned production grading implementation simply to reuse its executable
preflight. The read-only helper reuses its contract and manifest parsers.

JSON `PASS` / exit `0` covers only declared bytes and the saved accepted receipt.
Physical host identity and **fresh isolation qualification stay NOT VERIFIED**;
`operation_authorized` stays false. Source-only inspection exits `2` with runtime
unknown. Missing evidence or permission-denied access gives exit `2`; known identity
or permission drift gives `FAIL` / exit `1`. No status authorizes grading or model
execution. Fresh runtime/isolation preflight remains the accepted runner's separate
operator-controlled gate.

Retain the sanitized JSON result, expected/observed identities and observation time
in a new deployment record. Investigate any historical `CURRENT` pointer against its
exact manifests and installed runtime; differing adjacent hashes prove an ambiguous
reference, not which version is installed. Keep the old pointer, manifests, installation
and benchmark evidence untouched. This host-side checkpoint must complete before
dependent operations; source drift is not resolved by synchronization.

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
