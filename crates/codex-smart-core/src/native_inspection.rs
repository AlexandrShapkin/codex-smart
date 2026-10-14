//! Pure inspection-receipt binding, with no discovery, health or launch authority.
//!
//! The caller must acquire the reviewed record independently of the candidate and
//! project configuration. This API checks consistency, not authenticity or time.
use crate::playbook::NativeCapability;

/// Opaque SHA-256 bytes. Diagnostics intentionally omit identity values.
#[derive(Clone, Copy, PartialEq, Eq)]
pub struct Digest(pub [u8; 32]);

#[derive(Clone, Copy, PartialEq, Eq)]
pub struct Identity {
    pub capability: NativeCapability,
    pub source: Digest,
    pub configuration: Digest,
    pub tool: Digest,
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub struct Receipt {
    pub identity: Identity,
    pub verifier: Digest,
    /// Independently computed digest of the canonical receipt payload, excluding
    /// this digest field and including its interval and observation. The future
    /// adapter owns canonicalization.
    pub receipt: Digest,
    /// Caller-supplied seconds in a single trusted clock domain.
    pub observed_at: u64,
    pub expires_at: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Provenance {
    /// A trust-boundary assertion, never inferred by this module.
    IndependentlyReviewed,
    UserDeclared,
    PathDiscovery,
}

/// Separate reviewed observation, including the exact interval. Copying a
/// candidate into this record cannot establish independent provenance.
#[derive(Clone, Copy, PartialEq, Eq)]
pub struct ReviewRecord {
    pub receipt: Receipt,
    pub provenance: Provenance,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Reason {
    MissingReceipt,
    MissingReview,
    UntrustedProvenance,
    UnsupportedCapability,
    MissingIdentity,
    IdentityMismatch,
    ReviewMismatch,
    InvalidInterval,
    FutureObservation,
    Expired,
    BoundInspectionEvidence,
}

/// Acceptance concerns only this inspection observation. There is deliberately
/// no conversion to NativeSurface, capability health or execution permission.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Assessment {
    Unknown(Reason),
    AcceptedInspection,
}
impl Assessment {
    pub fn reason(self) -> Reason {
        match self {
            Self::Unknown(reason) => reason,
            Self::AcceptedInspection => Reason::BoundInspectionEvidence,
        }
    }

    pub fn summary(self) -> String {
        format!(
            "native inspection: {:?}; health=Unknown; execution_authorized=false",
            self.reason()
        )
    }
}

/// Hard ceiling, not a cache default or permission to reuse an observation.
pub const MAX_LIFETIME_SECONDS: u64 = 300;

/// Deterministic, inspection-only assessment. `current` must be independently
/// observed; `now` must come from the same trusted clock as the reviewed interval.
/// Re-evaluate on every use. No system clock, PATH, filesystem or config is read.
pub fn assess(
    current: Identity,
    candidate: Option<&Receipt>,
    review: Option<&ReviewRecord>,
    now: u64,
) -> Assessment {
    let unknown = Assessment::Unknown;
    let Some(candidate) = candidate else {
        return unknown(Reason::MissingReceipt);
    };
    let Some(review) = review else {
        return unknown(Reason::MissingReview);
    };
    if review.provenance != Provenance::IndependentlyReviewed {
        return unknown(Reason::UntrustedProvenance);
    }
    if !matches!(
        current.capability,
        NativeCapability::ReadFiles | NativeCapability::Search | NativeCapability::Git
    ) {
        return unknown(Reason::UnsupportedCapability);
    }
    if [
        current.source,
        current.configuration,
        current.tool,
        candidate.verifier,
        candidate.receipt,
    ]
    .iter()
    .any(|digest| digest.0 == [0; 32])
    {
        return unknown(Reason::MissingIdentity);
    }
    if candidate.identity != current {
        return unknown(Reason::IdentityMismatch);
    }
    if candidate != &review.receipt {
        return unknown(Reason::ReviewMismatch);
    }
    let Some(lifetime) = candidate.expires_at.checked_sub(candidate.observed_at) else {
        return unknown(Reason::InvalidInterval);
    };
    if lifetime == 0 || lifetime > MAX_LIFETIME_SECONDS {
        return unknown(Reason::InvalidInterval);
    }
    if now < candidate.observed_at {
        return unknown(Reason::FutureObservation);
    }
    if now >= candidate.expires_at {
        return unknown(Reason::Expired);
    }
    Assessment::AcceptedInspection
}
