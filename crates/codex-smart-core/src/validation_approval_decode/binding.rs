//! Pure comparisons of untrusted claims. No authentication, collection or consumption.
use super::ParseOnly;

struct Text<const N: usize> {
    bytes: [u8; N],
    len: usize,
}
impl<const N: usize> Text<N> {
    fn new(raw: &[u8]) -> Self {
        let mut bytes = [0; N];
        bytes[..raw.len()].copy_from_slice(raw);
        Self {
            bytes,
            len: raw.len(),
        }
    }
    fn equals(&self, raw: &[u8]) -> bool {
        raw == &self.bytes[..self.len]
    }
}
pub(super) struct Nested {
    scope: Text<1024>,
    source: [u8; 32],
    config: [u8; 32],
}
impl Nested {
    pub(super) fn new(scope: &[u8], source: &[u8], config: &[u8]) -> Self {
        Self {
            scope: Text::new(scope),
            source: source.try_into().unwrap(),
            config: config.try_into().unwrap(),
        }
    }
}
pub(super) struct Projection {
    repo: Text<129>,
    scope: Text<1024>,
    policy: Text<64>,
    fixed: [[u8; 32]; 26],
    nested: Nested,
    spec: [u8; 32],
    wire: [u8; 32],
}
impl Projection {
    pub(super) fn new(
        fields: &[&[u8]; 26],
        nested: Nested,
        spec: [u8; 32],
        wire: [u8; 32],
    ) -> Self {
        let mut fixed = [[0; 32]; 26];
        for tag in [
            1usize, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 19, 20, 21, 22, 23, 24,
        ] {
            let v = fields[tag - 1];
            fixed[tag - 1][..v.len()].copy_from_slice(v);
        }
        Self {
            repo: Text::new(fields[1]),
            scope: Text::new(fields[3]),
            policy: Text::new(fields[4]),
            fixed,
            nested,
            spec,
            wire,
        }
    }
    fn number(&self, tag: usize) -> u64 {
        u64::from_be_bytes(self.fixed[tag - 1][..8].try_into().unwrap())
    }
}

/// Every field is a caller assertion, including externally verified provenance.
/// Labels are compared only after constant size bounds (no allocation).
/// No Debug/Display/serialization is provided for evidence containing identities.
#[derive(Clone)]
pub struct BindingClaims<'a> {
    pub repository: &'a str,
    pub scope: &'a str,
    pub policy: &'a str,
    pub policy_epoch: u64,
    pub root: [u8; 32],
    pub operator: [u8; 32],
    pub reviewer: [u8; 32],
    pub delegation_epoch: u64,
    pub revocation_generation: u64,
    pub observation: [u8; 16],
    pub session: [u8; 16],
    pub one_use: [u8; 16],
    pub clock_domain: [u8; 16],
    pub observed_at: u64,
    pub expires_at: u64,
    pub spec_digest: [u8; 32],
    pub source: [u8; 32],
    pub configuration: [u8; 32],
    pub tool_closure: [u8; 32],
    pub verifier: [u8; 32],
    pub context: [u8; 32],
    pub provenance: crate::validation_policy::Provenance,
}
/// Separate claimed review of the exact wire, never a body-only digest.
pub struct ReviewEvidence<'a> {
    pub wire_digest: [u8; 32],
    pub authorization: BindingClaims<'a>,
}
/// Supplied time and continuity claims, not a trusted clock.
pub struct TimeObservation {
    pub clock_domain: [u8; 16],
    pub now: u64,
    pub last_observed: u64,
}
/// One separate claimed previously consumed observation/use. No protected store.
pub struct PriorUse {
    pub observation: [u8; 16],
    pub one_use: [u8; 16],
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EvidenceKind {
    Review,
    Current,
    Time,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BindingField {
    Wire,
    Specification,
    Repository,
    Scope,
    Policy,
    PolicyEpoch,
    Root,
    Operator,
    Reviewer,
    DelegationEpoch,
    RevocationGeneration,
    Observation,
    Session,
    OneUse,
    ClockDomain,
    ObservedAt,
    ExpiresAt,
    Source,
    Configuration,
    ToolClosure,
    Verifier,
    Context,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BindingResult {
    NeedsIndependentAuthority,
    Missing(EvidenceKind),
    OversizeEvidence(EvidenceKind),
    Conflict(BindingField),
    Mismatch(EvidenceKind, BindingField),
    Denied,
    InvalidInterval,
    FutureObservation,
    Expired,
    StaleSuppliedTime,
    RepeatedUseClaim,
}

/// First failure: denial, internal conflicts (scope/spec/source/config), availability
/// (review/current/time), label bounds, review wire/claims, current claims, clock,
/// interval, future/expiry, time continuity, prior-use claim. All results deny authority.
/// Absent prior-use history proves nothing; matching claims still need independent
/// trust-root/provenance, protected state/clock, current collector and anti-replay.
pub fn compare_evidence(
    parsed: &ParseOnly,
    review: Option<&ReviewEvidence<'_>>,
    current: Option<&BindingClaims<'_>>,
    time: Option<&TimeObservation>,
    prior_use: Option<&PriorUse>,
) -> BindingResult {
    use BindingField::*;
    use BindingResult::*;
    let p = &parsed.binding;
    if p.fixed[0][0] == 2 {
        return Denied;
    }
    for (field, equal) in [
        (Scope, p.nested.scope.equals(&p.scope.bytes[..p.scope.len])),
        (Specification, p.spec == p.fixed[18]),
        (Source, p.nested.source == p.fixed[19]),
        (Configuration, p.nested.config == p.fixed[20]),
    ] {
        if !equal {
            return Conflict(field);
        }
    }
    let Some(review) = review else {
        return Missing(EvidenceKind::Review);
    };
    let Some(current) = current else {
        return Missing(EvidenceKind::Current);
    };
    let Some(time) = time else {
        return Missing(EvidenceKind::Time);
    };
    for (kind, claims) in [
        (EvidenceKind::Review, &review.authorization),
        (EvidenceKind::Current, current),
    ] {
        if claims.repository.len() > 129 || claims.scope.len() > 1024 || claims.policy.len() > 64 {
            return OversizeEvidence(kind);
        }
    }
    if review.wire_digest != p.wire {
        return Mismatch(EvidenceKind::Review, Wire);
    }
    for (kind, c) in [
        (EvidenceKind::Review, &review.authorization),
        (EvidenceKind::Current, current),
    ] {
        macro_rules! equal {
            ($field:ident, $a:expr, $b:expr) => {
                if $a != $b {
                    return Mismatch(kind, $field);
                }
            };
        }
        equal!(Specification, c.spec_digest, p.spec);
        for (field, matches) in [
            (Repository, p.repo.equals(c.repository.as_bytes())),
            (Scope, p.scope.equals(c.scope.as_bytes())),
            (Policy, p.policy.equals(c.policy.as_bytes())),
        ] {
            if !matches {
                return Mismatch(kind, field);
            }
        }
        equal!(PolicyEpoch, c.policy_epoch, p.number(6));
        equal!(Root, c.root, p.fixed[6]);
        equal!(Operator, c.operator, p.fixed[7]);
        equal!(Reviewer, c.reviewer, p.fixed[8]);
        equal!(DelegationEpoch, c.delegation_epoch, p.number(10));
        equal!(RevocationGeneration, c.revocation_generation, p.number(11));
        equal!(Observation, c.observation.as_slice(), &p.fixed[11][..16]);
        equal!(Session, c.session.as_slice(), &p.fixed[12][..16]);
        equal!(OneUse, c.one_use.as_slice(), &p.fixed[13][..16]);
        equal!(ClockDomain, c.clock_domain.as_slice(), &p.fixed[14][..16]);
        equal!(ObservedAt, c.observed_at, p.number(16));
        equal!(ExpiresAt, c.expires_at, p.number(17));
        equal!(Source, c.source, p.fixed[19]);
        equal!(Configuration, c.configuration, p.fixed[20]);
        equal!(ToolClosure, c.tool_closure, p.fixed[21]);
        equal!(Verifier, c.verifier, p.fixed[22]);
        equal!(Context, c.context, p.fixed[23]);
    }
    if time.clock_domain.as_slice() != &p.fixed[14][..16] {
        return Mismatch(EvidenceKind::Time, ClockDomain);
    }
    let observed = p.number(16);
    let expires = p.number(17);
    if observed == 0
        || !expires.checked_sub(observed).is_some_and(|life| {
            (1..=crate::validation_policy::MAX_LIFETIME_SECONDS).contains(&life)
        })
    {
        return InvalidInterval;
    }
    if time.now < observed {
        return FutureObservation;
    }
    if time.now >= expires {
        return Expired;
    }
    if time.now < time.last_observed {
        return StaleSuppliedTime;
    }
    if prior_use.is_some_and(|used| {
        used.observation.as_slice() == &p.fixed[11][..16]
            || used.one_use.as_slice() == &p.fixed[13][..16]
    }) {
        return RepeatedUseClaim;
    }
    NeedsIndependentAuthority
}
