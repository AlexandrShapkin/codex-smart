# ADR-0010: Native inspection trust boundary

Status: proposed; offline qualification for #119, based on
`91d1d057205baa8861b12b1d9fa5311cd62cd471`. Decision: **NO-GO for production admission**.
Architecture owns this proposed contract; engineering owns any future offline adapter
under #94. Independent security/owner review is required before implementation.
Adaptive remains active. This document implements no collector or runtime join.

The bounded [#121 operator/reviewer authority follow-up](0011-operator-reviewer-authority.md)
qualifies two offline bootstrap choices and preserves actual enrollment NO-GO.

## Evidence inventory

References below are exact source lines at the base SHA, not claims of host qualification.
Paths are relative to the repository root; line ranges make review reproducible with
`nl -ba PATH` and a targeted `sed` range. The existing contracts are
[ADR-0007](0007-owned-executable-pins.md), [ADR-0008](0008-deterministic-workflows.md),
[ADR-0009](0009-child-descriptor-isolation.md), [architecture](../architecture.md)
and [workflow intelligence](../workflow-intelligence.md).

| Source / lines | Observed contract and limit |
| --- | --- |
| `crates/codex-smart-core/src/native_inspection.rs:1–4,13–46` | Caller supplies current source/config/tool identity and a separate review with an asserted provenance enum. No root, reviewer identity, authentication mechanism or current verifier argument exists. |
| `crates/codex-smart-core/src/native_inspection.rs:64–88` | AcceptedInspection concerns only an observation; summary fixes health=Unknown and execution_authorized=false; maximum lifetime is 300 seconds. |
| `crates/codex-smart-core/src/native_inspection.rs:90–147` | Domain-separated fixed binary v1 SHA-256 and opt-in assess_canonical; excludes receipt digest. Hash integrity does not authenticate observation. |
| `crates/codex-smart-core/src/native_inspection.rs:150–205` | Pure assess reads no host state. Requires supplied independent provenance, supported capability, nonzero digests, current identity equality, full review equality, positive bounded lifetime, observed_at <= now < expires_at. No replay history or clock validation. |
| `crates/codex-smart-core/tests/native_inspection.rs:3–45,199–243` | Synthetic fixture and positive canonical vector; caller controls all identities/time. These prove deterministic policy, not independent review. |
| `crates/codex-smart-core/tests/native_inspection.rs:245–271,274–325,328–404,407–450` | Mutation/domain/provenance/authority/interval/current-binding regressions. Legacy assess intentionally accepts some noncanonical digests that assess_canonical rejects. |
| `crates/codex-smart-core/src/workflow.rs:213–255,438–446,567–580` | NativeSurface accepts caller states, defaults Unknown; Verified drives readiness. No authenticated projection from AcceptedInspection exists. |
| `crates/codex-smart-core/src/tool_lock.rs:238–280,321–375` | Artifact evidence leaves runtime version absent and readiness unknown except explicit refusal; Linux fingerprint uses held no-symlink descriptor and metadata checks. This is executable integrity, not a review-store implementation or independent root. |
| `crates/codex-smart-core/src/capability.rs:79–96,125–176` | Bounded discovery and writable-path rejection do not establish runtime health or reviewer authority. |
| `crates/codex-smart-core/src/process.rs:34–64,80–112` | Launch planning/rechecks and OS arguments; pathname execution race is explicitly unresolved. This cannot supply inspection admission. |
| `crates/codex-smart-core/src/preparation_worker.rs:7–10,58–74,220–295` | The supervised worker requires an independently supplied artifact pin and verifies its own executable bytes. This does not authenticate native-inspection reviewer provenance or establish a trusted receipt producer. |
| `crates/codex-smart-core/src/preparation_supervision.rs:11–33,67–110` | Supervision consumes caller facts and a parent-owned post-spawn deadline, not an attested observation clock or reviewer authority. |
| `crates/codex-smart-cli/src/plan.rs:1–13,92–120` | Explicit plan-only preview uses Unknown native evidence and grants no execution rights; it does not acquire reviewed inspection receipts. |
| `crates/codex-smart-cli/src/prepare.rs:1–13,40–112` | Explicit worker path/digest/protocol are caller CLI inputs to local preparation, not proof of an independently enrolled native-inspection trust root. |
| `crates/codex-smart-cli/src/main.rs:144–184,185–208` | Ordinary `run` remains the separate Codex passthrough and `plan`/`prepare` are explicit branches; no native-inspection review ingress or authority projection is joined. |
| [Pinned source snapshot workflow](../PROJECT_WORKFLOW.md#pinned-source-snapshots-on-thinkpad-and-srv0) | Snapshot verification depends on an external independently recorded source receipt digest, and cannot itself qualify reviewer authority, current runtime identity, or clock/replay protection. |

A targeted repository search for `native_inspection` and `IndependentlyReviewed` in
`crates` finds the module export, evaluator and synthetic tests, without a product
caller acquiring independently trusted reviews. The inventory is scoped to these
admission-relevant paths; it is not an audit of every execution subsystem.

## Boundaries and admission contract

The candidate, repository contents, project config, PATH, nominated review files,
and any pins/keys/reviewer names inside them are untrusted input. They may nominate
data, never select the authority that authenticates that data. Copying a receipt
into ReviewRecord and setting IndependentlyReviewed can satisfy the pure API; that
is an invalid caller assertion, not independent evidence. A verifier digest inside
a candidate does not identify the verifier currently running.

A future explicit offline adapter must meet all of these requirements before calling
assess_canonical. Failure or missing evidence returns Unknown with bounded enum-only
diagnostics, no partial promotion and no fallback to candidate declarations.

1. Bootstrap an operator-controlled review root independently of project/candidate
   configuration. Bind its identity, storage policy and current trust-policy epoch
   through a separately reviewed installation/operator channel. Reject project-selected
   roots even when their bytes are identical to a known fixture. Check the root and
   ancestor ownership, permissions, symlinks and applicable ACL/mount guarantees;
   a process sharing the trusted owner's write authority is outside the proposed
   protection and must not be assumed isolated.
2. Authenticate a reviewer authorized by that root for this capability, repository,
   scope and epoch. Bind reviewer identity, review decision, receipt digest, schema,
   scope, unique observation ID, validity and revocation generation in an authenticated
   envelope. Neither a signer name nor a matching digest is authority by itself.
   Rotation/revocation requires independent policy update and invalidates older leases.
3. Independently collect actual current identities: source includes repository identity,
   relevant tree bytes and dirty/untracked inputs, not HEAD alone; configuration includes
   effective defaults, precedence, overrides and relevant environment; tool includes
   actual selected artifact plus relevant interpreter/dependency closure; verifier includes
   actual adapter/verifier artifact and policy/schema version. Define and review exact
   byte coverage before implementing hashes. Path/version declarations are insufficient.
   Compare current verifier to the reviewed verifier before entering the existing API.
4. Decode a bounded envelope strictly: one supported schema/domain, fixed digest widths,
   exact canonical bytes, no duplicate fields, unknown authority fields, ambiguous numbers,
   alternate encodings or trailing payload. Recompute v1 canonical digest and compare
   the independently authenticated record. Do not silently upgrade legacy assess.
5. Obtain trusted current time in the authenticated observation's clock domain; require
   `0 < expires_at - observed_at <= 300` and `observed_at <= now < expires_at`.
   Independently protect last-seen time/policy epoch against rollback; missing continuity,
   clock uncertainty, restart without protected state or a backward step invalidates
   the observation. A monotonic process clock alone cannot authenticate persisted UTC.
6. Check revocation, policy generation and observation ID against protected offline state.
   Bind each admission to a local session/use ID; reject a copied envelope in another
   session or a consumed use. Re-evaluation within the same bounded use may be idempotent,
   but is never a fresh grant. Atomic compare-and-consume is required; restoring an older
   ledger must fail closed. Do not change v1 receipt bytes to pretend they bind these
   extra fields: the separately authenticated versioned envelope must bind them.
7. Hold a stable bounded snapshot of root, review and current inputs through assessment
   and consumption. Recheck generation/identity at use; invalidate on mutation, expiry,
   reset, source/config/tool/verifier change, reviewer/root rotation, revocation or clock
   discontinuity. If immutable snapshots or race exclusion cannot be established, refuse.
8. Return only inspection evidence for ReadFiles/Search/Git. Health, semantic sufficiency,
   NativeSurface.Verified, validation, model execution and production admission remain
   separate ungranted authorities. No discovered executable is run to establish health.

## Independent digest and signature alternatives

| Alternative | Independent anchor required | Limits / qualification |
| --- | --- | --- |
| Protected digest allowlist | Operator provisions exact reviewed envelope/receipt digest plus reviewer authority, scope, epoch and validity through an independent channel | Simple offline comparison; allowlist delivery, writable storage, revocation and rollback protection remain trust obligations. A digest copied from project config is not this alternative. NO-GO until independently qualified. |
| Signed envelope | Independently provisioned public verification key and authorization policy; signature binds all envelope fields including receipt digest | Can transport reviews through untrusted storage. Embedded keys cannot bootstrap trust. Algorithm/library, key lifecycle, canonical envelope, revocation distribution and rollback protection require separate review. A valid signature does not prove current identity, health or freshness. NO-GO until qualified. |

No signing algorithm, real key, credential, service or new dependency is selected here.
An offline signature cannot discover unseen revocation: require a short independently
provisioned policy lease and refuse when it expires. Digest and signature alternatives
share the trusted clock/state/current-identity obligations. Neither is implemented.

## GO / NO-GO qualification

| Gate | Evidence now | Decision |
| --- | --- | --- |
| Pure binding and canonical integrity | Existing isolated synthetic contracts/tests | GO for offline consistency testing only |
| Independently bootstrapped root and reviewer authorization | No product acquisition/authentication boundary | NO-GO |
| Actual current source/config/tool/verifier provenance | Opaque caller inputs; verifier lacks separate current input | NO-GO |
| Trusted clock, expiry continuity, rollback/replay/revocation state | Interval arithmetic only; no protected history | NO-GO |
| Strict envelope parser and race-safe store/use | No adapter/store/envelope | NO-GO |
| Tool health, semantic sufficiency, readiness or execution authority | Explicitly unknown/ungranted | NO-GO; inspection acceptance cannot promote these |
| Production integration / Adaptive acceptance | Missing independent prerequisites and runtime qualification | NO-GO; stage remains active |

Unknowns include the independently administered root location and delivery mechanism,
reviewer policy owner/operator identities, storage/ACL/mount threat model, clock source
and continuity guarantees, persistent anti-rollback mechanism, exact identity coverage,
envelope format and size budget, signature choice if any, revocation freshness and
cross-session consumption policy implementation. No fixture resolves these Unknowns.
Assumptions of an uncompromised operator, kernel, hash implementation and protected
local state are **unqualified assumptions**, not measured guarantees. An attacker with
root/operator-equivalent write access can defeat a same-host trust store; qualifying
that threat requires a separate platform/security decision.

## Bounded future offline adapter (proposal only)

Engineering owns a future host-side adapter in a separately reviewed #94 slice;
architecture/security own authority and storage-policy approval. Keep core pure and
unchanged. Conceptual types below describe obligations, not existing public Rust APIs:

```text
qualify_offline(
    candidate: BoundedUntrustedEnvelope,       // <= 16 KiB, one record
    root: IndependentlyProvisionedRootHandle, // cannot construct from project config
    snapshot: HeldCurrentIdentitySnapshot,    // source/config/tool AND verifier
    time: TrustedClockSnapshot,               // clock domain, continuity, uncertainty
    ledger: ProtectedAdmissionLedger,         // epoch, revocation, use ID, last time
    limits: OfflineLimits                    // <= 64 KiB total envelope/policy input,
                                             // no recursion; <= 300 second lease
) -> InspectionLease | Unknown(AdmissionReason)
```

Handles must have private constructors at the trusted host boundary; naming a type
Trusted does not prove provenance. Reject oversize input before decoding; identity
collection needs separately approved file/byte/time budgets and an explicit bounded
snapshot supplied here. No discovery, subprocess, network, credentials, automatic
clock repair, policy refresh or writable index belongs to this function. Diagnostics
must omit private source, prompts, credentials, raw paths, signer/key material and
receipt payloads; expose only bounded enum reasons and sanitized counts. On inability
to obtain/hold bounded inputs return Unknown. Ledger consumption is an explicit local
transaction, never a side effect of doctor/explain. InspectionLease is scoped, expiring
and revalidated at use, with no conversion to NativeSurface or execution permission.
These proposed bounds and ownership require review and are not implementation evidence.

## Reproducible offline qualification fixtures

Existing tests can be reproduced without a host clock, PATH, keys or discovered tools:

```bash
CARGO_NET_OFFLINE=true cargo test -p codex-smart-core --test native_inspection --locked
```

Positive P0: use `canonical_fixture` in
`crates/codex-smart-core/tests/native_inspection.rs:199–203`: Search, source `[1;32]`,
config `[2;32]`, tool `[3;32]`, verifier `[4;32]`, observed=100, expires=400, canonical
hash, matching review marked IndependentlyReviewed. At now=100 and 399 expect
AcceptedInspection and `health=Unknown; execution_authorized=false`; at 400 expect
Expired. This is a positive **pure contract** fixture, not authentication proof.

Future adapter positive P1 (not implemented or executed): in a disposable fake store,
provision a separate operator fixture root A, authorized reviewer R, epoch 7 and
independently stored digest of an envelope for P0, scope S, observation O, session U.
Inject held identities matching P0, trusted fake time=101/continuity C and an unused
protected fake ledger. Expect one inspection lease for U only. No real keys needed
for the digest alternative. This models independence; it cannot qualify host storage.

For every row below, start from P0 for existing evaluator behavior and P1 for the
future adapter method. Fake root B, reviewer Q, epochs, time and replacement hooks
are deterministic fixture data. Proposed adapter tests are specifications only;
**none exist yet**, and current acceptance in a row exposes an external obligation.
All future refusals mean Unknown/no lease, with no readiness or execution promotion.

| # / negative scenario | Current behavior | Future guard and fail-closed result | Reproducible offline method |
| --- | --- | --- | --- |
| 1 Copied review | P0 copied and marked independent accepts; missing/declared review refuses | Authenticate independent origin/authorization; Unknown | Copy candidate into review and assert current acceptance; omit independent allowlist entry in P1 and expect refusal. |
| 2 Self-hash | Recomputing canonical digest with a matching asserted review accepts | Self-hash cannot populate trusted digest store; Unknown | Change tool bytes, recompute hash, copy review/current; P0 accepts. Retain original independent P1 digest; refuse. |
| 3 Config-provided pin | API has no pin origin; asserted matching inputs accept | Ignore project authority/pin fields, require independent anchor; Unknown | Put matching digest/root nomination only in fake project config, leave operator store empty; refuse. Model current call with all matching values. |
| 4 Swapped root/reviewer | Neither identity is represented | Bind root A, R, scope and epoch to policy; Unknown | Replace A with B, then R with unauthorized Q while preserving receipt; both P1 variants refuse. P0 remains unchanged. |
| 5 Expired | now=400 returns Expired | Trusted time and exclusive expiry; Unknown | Inject 399 then 400; positive then refusal. Existing boundary test covers arithmetic. |
| 6 Replayed | Repeated now=101 calls accept; no state | Atomic observation/session consumption; Unknown | Admit O for U, replay for session V; race two consumers, require at most one new admission. P0 accepts repeated calls. |
| 7 Future | now=99 returns FutureObservation | Trusted clock domain and no future tolerance; Unknown | Inject fake now=99 for observed=100; existing arithmetic refuses, future adapter must also reject domain mismatch. |
| 8 Rollback | After now=400 refusal, now=101 accepts | Protected last time/epoch continuity; Unknown | Run [399,400,101], restore epoch 6/older ledger after 7, simulate restart with missing continuity; P1 refuses each rollback. |
| 9 Identity drift | Supplied source/config/tool drift gives IdentityMismatch; stale supplied values can accept; current verifier unrepresented | Independently snapshot all four actual identities; Unknown | Mutate each held source/config/tool/verifier in turn while candidate unchanged; P1 refuses. Existing current-binding tests cover only represented fields. |
| 10 Missing verifier | Zero verifier gives MissingIdentity; nonzero asserted verifier can accept without installed verifier | Require actual verifier artifact/policy identity; Unknown | Zero candidate verifier in P0; then keep `[4;32]` but remove fake installed verifier from P1 snapshot; both refuse for different gates. |
| 11 Malformed/noncanonical | Typed API has no decoder; assess_canonical rejects canonical mismatch; legacy assess can accept | Strict bounded single-schema decoder plus canonical check; Unknown | Existing domain/mutation tests; future byte fixtures truncate digest, duplicate field, append bytes, use alternate domain/oversize envelope; all refuse before admission. |
| 12 Symlink/writable store | No store access/check | Held no-follow root chain, owner/ACL/mount checks; Unknown | Disposable P1 directory: replace review/root by symlink, mark store or ancestor writable to untrusted principal; inject unsafe ACL metadata; each refuses without following target. |
| 13 TOCTOU | Values assessed only at call instant; no held store/use | Stable snapshots and generation recheck through consumption; Unknown | Deterministic hook swaps review/root or mutates source after open/assessment before consume; no lease/use on mismatch. No timing sleeps required. |
| 14 Tool health unknown | Acceptance summary preserves Unknown | Never infer health from presence/hash/receipt; health remains Unknown | P0 acceptance summary exact assertion; P1 valid lease with absent health evidence must still expose Unknown and launch no probe. |
| 15 Authority promotion | No evaluator conversion to NativeSurface; caller can construct Verified independently | Adapter exports inspection-only lease, forbids readiness/execution projection | Existing summary/unsupported Edit/Build/Tests tests; future compile/API test denies conversion and fake effect counters remain zero for validation/model/tool launches. |

Before any future GO, implement and independently review these adapter regressions,
qualify the real root/time/identity/state mechanisms and rerun exact-source gates.
Passing pure fixtures alone cannot satisfy that admission decision.
