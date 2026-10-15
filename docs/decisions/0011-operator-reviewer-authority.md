# ADR-0011: Operator and reviewer authority qualification

Status: proposed; docs-only offline qualification for [Issue #121](https://github.com/AlexandrShapkin/codex-smart/issues/121).
Base: `5a51e9fcf9bee8144f4d8a13485fb9036a771a81`. **NO-GO for actual enrollment and production use.**
This follows [ADR-0010](0010-native-inspection-trust-boundary.md), narrows its
bootstrap question, and preserves [production routing readiness](../production-routing-readiness.md)
and the active [Adaptive 0.5 contract](../stages/adaptive.md). No implementation or
stage acceptance follows from this proposal.

## Source inventory and authority gap

The following are available design and code evidence, not approved provisioning sources:

| Actual source at the base | Evidence and limit |
| --- | --- |
| `crates/codex-smart-core/src/native_inspection.rs`, `Provenance`, `ReviewRecord`, `assess` | IndependentlyReviewed is a caller assertion; current source/configuration/tool and time are supplied. No root/operator/reviewer authentication or enrollment exists. |
| Same module, `canonical_digest`, `assess_canonical` | Fixed v1 canonical SHA-256 binds receipt fields, excluding its own digest. This proves offline integrity relative to supplied bytes, not origin authentication. No separate current verifier input exists. |
| Same module, `Assessment`, `summary`, `MAX_LIFETIME_SECONDS` | AcceptedInspection only; health Unknown, execution_authorized=false, lifetime at most 300 seconds. |
| `crates/codex-smart-core/tests/native_inspection.rs` | Synthetic binding, canonical encoding, provenance and interval regression evidence; no authenticated host provisioning. Tests are inspected, not executed in this docs task. |
| ADR-0010 | Proposed independent root/store, identity, clock and replay obligations; not delivered infrastructure. Its 16 KiB candidate and 64 KiB combined policy/envelope bounds are conceptual. |
| `docs/workflow.md`, review and merge authorization | Separates review, machine checks and owner authorization. ChatGPT transcription through an owner account does not establish owner intent. Repository governance is not native inspection credential provisioning. |
| `SECURITY.md`, Adaptive and production readiness contracts | Untrusted project/PATH, private-data restrictions, missing runtime joins and closed production admission. |

**Operator != reviewer != authenticated channel != candidate.** The operator is the
independently authorized administrator of enrollment policy and protected state. The
reviewer is an independently identified principal authorized to review a specific
scope; a signer is only a cryptographic principal until policy binds it to that
reviewer and authority. The channel authenticates delivery and its sender; it does
not itself grant review authority. The candidate is untrusted observation data.
Distinct roles require separate evidence even if a future policy permits one person
to hold multiple roles; independence from the candidate producer must still be proven.

No approved independently authenticated operator/reviewer provisioning channel,
root identity, delegated reviewer roster or protected operator trust-store is
established by these sources. No trusted clock, protected persistent state or current
identity observer is qualified. All remain **Unknown**. Issue text and this document
are requirements, not enrollment authority. Neither repository files, PATH, GitHub
comments, ChatGPT output/account attribution nor candidate hashes may supply the root.
A candidate digest is not origin authentication.

A future operator-controlled trust-store would need independently approved identity
and authorization provenance: who provisioned which root, reviewer, scope, epoch,
expiry and update authority, over which authenticated channel. Its location, ancestor
chain, ownership, ACLs, mount guarantees and stable handles need qualification.
Updates, rotation and revocation must be authorized by the already provisioned
operator policy, recorded atomically with monotone generations, and invalidate old
leases. A candidate cannot nominate a replacement store or authorize its own update.
No such store is created here.

## Exactly two offline options

Both options authenticate only relative to an independently provisioned authority.
Offline integrity checking cannot bootstrap that authority. Neither option is ready.

| Dimension | A — Independently delivered exact reviewed-envelope digest | B — Independently provisioned public verification key and signed canonical review envelope |
| --- | --- | --- |
| Bootstrap | Approved operator independently delivers the exact envelope digest plus reviewer identity, scope/authorization, epoch and expiry into protected policy. Receipt/candidate pin alone is insufficient. | Approved operator independently provisions a public verification key and policy binding key, signer, reviewer, scope/authorization, epoch and expiry. Candidate-provided public key is NOT independent. |
| Independent channel | Must authenticate sender and exact digest plus authorization metadata, separately from candidate transport. | Must authenticate key/policy delivery and authorized updates separately from signed-envelope transport. |
| Reviewer/signer authority | Policy authenticates the reviewer who approved those exact envelope bytes; copying a reviewed receipt supplies no authority. | Signature authenticates possession of the enrolled signing authority; policy must additionally establish reviewer identity, delegation and authorized scope. A signature alone is insufficient. |
| Forgery/substitution resistance | Exact canonical envelope digest mismatch rejects substitution, assuming trusted delivery/store and digest integrity. Recomputing a candidate hash cannot update the independent entry. | Signature binds every canonical envelope field under the independently enrolled key, assuming sound future cryptography/verifier. Embedded replacement key or valid signature outside scope rejects. |
| Signing/verifier responsibility | No signing implementation needed. Reviewer/operator own exact digest delivery and scope approval; verifier owns strict decoding, canonical hashing and policy comparison. | Reviewer/signing custodian owns protected signing and correct scoped assertions; verifier owns strict canonical decoding, signature verification and policy enforcement. No algorithm/library is selected here. |
| Rotation/revocation/freshness | Independently authorized digest/policy replacement and revocation generation, protected against rollback; short policy lease. | Independently authorized key/policy rotation and revocation generation, protected against rollback; short policy lease. Offline signatures cannot reveal unseen revocation. |
| Replay/rollback | Envelope observation/session/use IDs plus atomic protected consumption and epoch/time continuity; digest match alone permits replay. | Same ledger and continuity requirements; a valid old signature alone permits replay. |
| Accepted / Rejected / Unknown | Accepted only after all typed checks; known digest/scope/policy violations Rejected; missing/unobservable independent authority Unknown. Neither refusal admits. | Accepted only after all typed checks; known signature/key/scope/policy violations Rejected; missing/unobservable independent authority Unknown. Neither refusal admits. |
| Host assumptions | Independently protected store, uncompromised operator/kernel/verifier, trusted clock, current identities and durable anti-rollback ledger. Unqualified today. | Same host assumptions, plus independently qualified signing custody and cryptographic implementation. Unqualified today. |

Conditional future preference: B may simplify transporting many reviews through
untrusted storage after authority provisioning and cryptographic review are qualified.
This is no algorithm selection, infrastructure assertion or authorization to implement B.

## One future enrollment/use boundary

The following is one conceptual deterministic boundary, not an API delivered by the
product. All trusted handles require private constructors backed by independently
reviewed host evidence; names alone cannot manufacture trust. Host observations and
transaction results are explicit inputs; pure evaluation performs no discovery or I/O.

```text
Evidence<T> = Known(T) | Unknown
Mode = A(IndependentEnvelopeDigestBinding) | B(IndependentKeyBinding)
Request = Enroll(Mode) | Use(EnrollmentHandle, SessionId, UseId)
Inputs = {
  candidate: BytesBounded<16384>,
  policy_and_envelope: BytesBounded<65536>, // combined, including proof
  root_operator_reviewer: Evidence<AuthenticatedAuthoritySnapshot>,
  clock: Evidence<TrustedClockSnapshot>,
  state: Evidence<ProtectedPersistentSnapshot>,
  current: Evidence<HeldIdentitySnapshot>, // source/config/tool/verifier
  transaction: Evidence<AtomicGenerationAndConsumeResult>
}
EnrollmentState = Unenrolled | Enrolled(PrivateScopedHandle, PolicyEpoch) | Revoked
UseState = Unseen | Consumed(SessionId, UseId) | Invalidated
State = (EnrollmentState, UseState)
Result = Accepted(EnrolledHandle | InspectionUse)
       | Rejected(RejectReason) | Unknown(UnknownReason)
RejectReason = Oversize | Malformed | UnsupportedSchema | InvalidPolicy
  | RootMismatch | ReviewerUnauthorized | ScopeMismatch | DigestMismatch
  | InvalidSignature | Revoked | UnauthorizedUpdate | InvalidInterval
  | FutureObservation | Expired | IdentityMismatch | UnsafeStore
  | GenerationChanged | Replay | Rollback | InvalidTransition
UnknownReason = MissingAuthority | UnobservableAuthority | MissingClock
  | MissingProtectedState | MissingCurrentIdentity | UnstableSnapshot
  | UnknownTransaction
boundary(State, Request, Inputs) -> (State, Result)
```

Deterministic precedence is: (1) size and strict parse/schema/policy checks;
(2) evidence availability in authority, clock, state, current, transaction order;
(3) known safety/authentication failures in the RejectReason order above;
(4) valid transition. Select the first failing reason, expose only enum diagnostics,
and admit nothing on rejection or uncertainty. Invalid policy and unsupported schema
reject even if authority is missing. Absent or unobservable authority is Unknown,
never an implicit fallback. These classifications are future proposal semantics;
existing `Assessment` has only Unknown and AcceptedInspection.

Strict decoding permits one supported canonical version/domain, fixed digest widths,
no duplicates, unknown fields, ambiguous numbers, recursion, alternate encodings or
trailing bytes. The authenticated envelope binds decision, root/operator/reviewer,
repository/capability/scope, receipt digest, verifier identity, policy epoch,
revocation generation, observation/session/use IDs, clock domain and validity.
These are separate envelope fields, not changes to v1 receipt canonical bytes.
Only ReadFiles/Search/Git are eligible. A non-approval decision is InvalidPolicy.
Authorization must cover the complete envelope and current requested scope.

Enroll may transition Unenrolled to Enrolled only when authenticated policy and
all host prerequisites are Known and valid, with atomic generation recording.
Use must start Enrolled, bind the same session and one use ID, revalidate every
input, recompute the canonical receipt digest, compare actual current source,
effective configuration, selected tool/dependency closure and verifier, then apply
`assess_canonical` consistently. Exact identity coverage and acquisition budgets
remain approval prerequisites, not HEAD/path/version approximations.

The inherited conceptual bounds are candidate <=16 KiB, combined policy/envelope
<=64 KiB and positive lifetime <=300 seconds. Require observed <= now < expiry,
matching trusted clock domain/continuity, and policy authorization valid throughout
use; expiry is the earliest applicable envelope/policy deadline. No grace interval.
Each observation grants at most one new use; atomic compare-and-consume binds its
session/use ID before releasing inspection evidence. The authority enrollment remains Enrolled for other observations in the same
approved policy epoch; only this observation's UseState becomes Consumed.
Repeated Use is Replay, including the same ID, and cannot mint a second grant.
Evidence ends at expiry or any generation, identity, clock, revocation or snapshot
change. Revalidate at the use boundary; no reusable bearer grant or implicit renewal.
Other state/request combinations reject InvalidTransition; Consumed use rejects Replay.
A revoked or compromised root invalidates enrollment; a use-level violation
invalidates that observation, not all otherwise valid enrollments. Unknown suspends
admission and requires complete re-evaluation. Failed/uncertain consumption cannot be retried as a new grant
without protected reconciliation. Restart without continuity is MissingProtectedState;
proved backward time/epoch/ledger movement is Rollback. Races require held snapshots
and an atomic generation check through consumption; inability to hold them is Unknown.

At present root/operator/reviewer authentication, Trusted clock, Protected persistent
state and Current identity observer are all **Unknown**, so no real Accepted path
exists. InspectionUse has no direct conversion to `NativeSurface::Verified`, no
health, semantic sufficiency, validation or execution rights, and no product join.
Doctor/explain must remain read-only; no ledger writes or tool probes belong there.

## Bounded fake qualification matrix

All future cases below are **not implemented and not executed**. They specify
deterministic offline tests, not successful host checks. Existing test references
mean inspected source coverage only. Start each future case with a finite fake
policy/envelope, root A, reviewer R, epoch 7, observation O, session S/use U,
observed=100, expiry=400, fake now=101 and fixed identity bytes; inject exactly
one mutation. No real keys or credentials. B proofs, if modeled, are opaque fake
verification outcomes and cannot qualify cryptography.

| Case | Finite mutation and expected future result | Existing tests vs missing boundary |
| --- | --- | --- |
| N1 Copied review | Copy candidate into review; omit independent authority: Unknown(MissingAuthority), no admission. | `canonical_integrity_never_supplies_provenance_or_authority` covers caller assertion limits; authentication not implemented. |
| N2 Candidate pin | Only candidate/project supplies envelope digest: Unknown(MissingAuthority). | Canonical hashing exists; independent provisioning not implemented. |
| N3 Swapped root | Replace A with B while protected policy names A: Rejected(RootMismatch). | Root representation/check not implemented. |
| N4 Swapped reviewer | Replace R with unauthorized Q: Rejected(ReviewerUnauthorized). | Reviewer authorization not implemented. |
| N5 Stale envelope | Set fake now=400: Rejected(Expired). | `acceptance_is_inspection_only_and_expires_at_exact_boundary` checks arithmetic with Unknown(Expired); trusted clock not implemented. |
| N6 Forged envelope | Mutate one observation ID byte without updating independent A digest or valid B proof: Rejected(DigestMismatch) for A, Rejected(InvalidSignature) for B. | `canonical_hash_binds_each_field_even_when_review_is_copied` covers receipt integrity only; envelope authentication not implemented. |
| N7 Unauthorized rotation | Submit replacement key/digest at epoch 8 without operator update authority: Rejected(UnauthorizedUpdate). | Update authorization not implemented. |
| N8 Revoked key | B key appears in current fake revocation generation: Rejected(Revoked). A revoked binding likewise rejects. | Revocation not implemented. |
| N9 Symlinked malicious store | Fake held-store metadata says ancestor/store is a symlink: Rejected(UnsafeStore), never follow target. | Store boundary not implemented. |
| N10 Owner/ACL mismatch | Fake store owner or ACL grants untrusted write access: Rejected(UnsafeStore). | Store ownership/ACL qualification not implemented. |
| N11 TOCTOU | Fixed hook changes generation between assessment and consume: Rejected(GenerationChanged), zero released uses. If snapshot cannot be held: Unknown(UnstableSnapshot). | Snapshot/atomic consumption not implemented. |
| N12 Rollback | Restore ledger epoch 6 after protected epoch 7: Rejected(Rollback). Delete continuity instead: Unknown(MissingProtectedState). | No persistent state in evaluator; not implemented. |
| N13 Replay | Consume O/S/U once, submit it again or for another session: Rejected(Replay), total accepted uses <=1. | Pure evaluator has no consumption history; not implemented. |
| N14 Invalid encoding/policy | Unsupported schema or malformed authorization policy: Rejected(UnsupportedSchema) or Rejected(InvalidPolicy), even with missing authority. | Canonical receipt domain tests exist; strict envelope/policy parser not implemented. |
| N15 Unobservable prerequisites | Remove clock, state or held current identity individually: corresponding Unknown reason, zero admission. | Existing identity/interval checks use caller facts; host observers not implemented. |

Positive P1 is only an offline hypothetical model: supply all separate fake authority,
clock, protected state/current snapshot and successful atomic transaction inputs;
Enroll then Use yields one inspection-only result, then replay rejects. Model both A
and B with fake proof outcomes; no real credential, provisioning or host qualification.
Existing `canonical_fixture` demonstrates only pure receipt consistency. This task
adds no tests and executes none of these hypothetical cases.

Offline-testable work includes strict parsing, typed precedence, finite authority
policy, injected proof outcomes, interval arithmetic and simulated consumption/races.
Actual channel authentication, signing custody, kernel/ACL/mount protection, clock
continuity, identity capture and durable anti-rollback protection remain separately
unqualified host infrastructure. Passing the former cannot establish the latter.

## Decision, ownership and next gate

**NO-GO for actual enrollment or production unless an approved independently
authenticated operator/reviewer provisioning channel and protected host state truly
exist**, with independently accepted evidence. Missing authority cannot be repaired
by selecting a hash, signing bytes or naming a trusted type. Clock, current identity,
revocation freshness, parser, storage and atomic use remain additional blocking gates.

| Gate owner (role, actual authorized identity still unestablished) | Required future evidence |
| --- | --- |
| Project owner and independent security reviewer | Approve operator identity, authenticated provisioning channel, reviewer delegation/scope and update/revocation authority; separately record acceptance. |
| Host operator with security review | Demonstrate protected store/ancestors/ACLs, trusted time and continuity, persistent anti-rollback/atomic consumption and explicit failure behavior. |
| Architecture and security | Approve canonical envelope/schema, policy semantics, exact identity coverage/budgets, and any later cryptographic design. |
| Engineering under residual #94, independent reviewers | Implement only separately authorized slices, deterministic fake regressions, race-safe adapter and exact-source verification; keep runtime admission closed until all gates qualify. |
| Adaptive acceptance owners under #94/#95 | Independently accept remaining runtime/quality and separately authorized measurement evidence; no stage advancement from this document. |

Threat model: candidate producer controls repository, config, PATH, candidate/review
transport and can copy, substitute, replay or restore untrusted files. Assume no
operator-equivalent attacker, compromised kernel/verifier or broken future hash/
cryptographic primitive; these are unqualified prerequisites, not measured facts.
Same-owner write access can defeat a same-host store. Offline operation cannot see
new remote revocations, so require an independently refreshed short policy lease
and refuse when freshness is unavailable. No automatic refresh or repair is implied.

The next narrow **interface-only** slice may specify private authority-handle inputs,
canonical envelope fields and deterministic Result/reason precedence with fake
in-memory vectors, without a host adapter, keys, filesystem store or runtime caller.
It requires separate scope/review and cannot supply missing infrastructure by fiat.
Future implementation criteria include every negative case above, bounded resource
budgets, privacy-preserving enum diagnostics, approved host evidence and independent
exact-source security/owner acceptance before any enrollment or use.

Non-goals: actual keys, signature choice, dependencies, provisioning, trust-store
creation, runtime/tests/CI changes, health probes, validation/model execution,
benchmarks, production activation, credential/config mutation or publication.
