//! Pure inspection-receipt binding, with no discovery, health or launch authority.
//!
//! The caller must acquire the reviewed record independently of the candidate and
//! project configuration. This API checks consistency, not authenticity or time.
use crate::playbook::NativeCapability;
use sha2::{Digest as _, Sha256};

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
    /// SHA-256 of the v1 canonical payload (see [`canonical_digest`]), excluding
    /// this field. Integrity alone does not authenticate an observation.
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
    CanonicalMismatch,
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

/// SHA-256 domain/version prefix, including the terminating NUL byte.
/// This exact byte sequence is part of the v1 wire contract.
pub const CANONICAL_DOMAIN_V1: &[u8] = b"codex-smart/native-inspection/receipt/v1\0";

/// Hash the fixed-format v1 payload, excluding `receipt.receipt`:
/// domain prefix; one byte capability (read-files=1, search=2, git=3);
/// source, configuration, tool, verifier (32 bytes each, in that order);
/// observed_at, expires_at (8 bytes each, unsigned big endian).
/// No lengths, padding, text formatting or implicit Rust enum representation.
/// Unsupported capabilities have no encoding. This is integrity, not authenticated
/// provenance: a self-computed hash and copied review record prove no observation.
pub fn canonical_digest(receipt: &Receipt) -> Result<Digest, Reason> {
    let capability = match receipt.identity.capability {
        NativeCapability::ReadFiles => 1,
        NativeCapability::Search => 2,
        NativeCapability::Git => 3,
        NativeCapability::Edit | NativeCapability::Build | NativeCapability::Tests => {
            return Err(Reason::UnsupportedCapability);
        }
    };
    let mut hash = Sha256::new();
    hash.update(CANONICAL_DOMAIN_V1);
    hash.update([capability]);
    for digest in [
        receipt.identity.source,
        receipt.identity.configuration,
        receipt.identity.tool,
        receipt.verifier,
    ] {
        hash.update(digest.0);
    }
    hash.update(receipt.observed_at.to_be_bytes());
    hash.update(receipt.expires_at.to_be_bytes());
    Ok(Digest(hash.finalize().into()))
}

/// Opt-in canonical integrity check plus the existing inspection binding checks.
/// Independent review/current identity/trusted time remain external obligations;
/// this helper never creates or upgrades provenance, readiness or execution rights.
pub fn assess_canonical(
    current: Identity,
    candidate: Option<&Receipt>,
    review: Option<&ReviewRecord>,
    now: u64,
) -> Assessment {
    let assessment = assess(current, candidate, review, now);
    if assessment != Assessment::AcceptedInspection {
        return assessment;
    }
    // `assess` has already required a candidate and matched the complete review.
    let Some(candidate) = candidate else {
        return Assessment::Unknown(Reason::MissingReceipt);
    };
    match canonical_digest(candidate) {
        Ok(digest) if digest == candidate.receipt => Assessment::AcceptedInspection,
        Ok(_) => Assessment::Unknown(Reason::CanonicalMismatch),
        Err(reason) => Assessment::Unknown(reason),
    }
}

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
