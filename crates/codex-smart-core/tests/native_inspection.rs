use codex_smart_core::native_inspection::*;
use codex_smart_core::playbook::NativeCapability;

// Entirely synthetic environment; no host tools, files, clock or PATH are used.
fn fixture() -> (Identity, Receipt, ReviewRecord) {
    let identity = Identity {
        capability: NativeCapability::Search,
        source: Digest([1; 32]),
        configuration: Digest([2; 32]),
        tool: Digest([3; 32]),
    };
    let receipt = Receipt {
        identity,
        verifier: Digest([4; 32]),
        receipt: Digest([5; 32]),
        observed_at: 100,
        expires_at: 400,
    };
    (
        identity,
        receipt,
        ReviewRecord {
            receipt,
            provenance: Provenance::IndependentlyReviewed,
        },
    )
}

#[test]
fn acceptance_is_inspection_only_and_expires_at_exact_boundary() {
    let (identity, receipt, review) = fixture();
    for now in [100, 101, 399] {
        let result = assess(identity, Some(&receipt), Some(&review), now);
        assert_eq!(result, Assessment::AcceptedInspection);
        assert_eq!(
            result.summary(),
            "native inspection: BoundInspectionEvidence; health=Unknown; execution_authorized=false"
        );
    }
    for now in [400, u64::MAX] {
        assert_eq!(
            assess(identity, Some(&receipt), Some(&review), now),
            Assessment::Unknown(Reason::Expired)
        );
    }
    assert_eq!(
        assess(identity, Some(&receipt), Some(&review), 99),
        Assessment::Unknown(Reason::FutureObservation)
    );
}

#[test]
fn missing_or_declared_provenance_never_becomes_accepted() {
    let (identity, receipt, mut review) = fixture();
    assert_eq!(
        assess(identity, None, Some(&review), 100),
        Assessment::Unknown(Reason::MissingReceipt)
    );
    assert_eq!(
        assess(identity, Some(&receipt), None, 100),
        Assessment::Unknown(Reason::MissingReview)
    );
    for provenance in [Provenance::UserDeclared, Provenance::PathDiscovery] {
        review.provenance = provenance;
        assert_eq!(
            assess(identity, Some(&receipt), Some(&review), 100),
            Assessment::Unknown(Reason::UntrustedProvenance)
        );
    }
}

#[test]
fn every_current_identity_binding_is_required() {
    let (identity, receipt, review) = fixture();
    let mut changes = [identity; 4];
    changes[0].capability = NativeCapability::Git;
    changes[1].source = Digest([6; 32]);
    changes[2].configuration = Digest([6; 32]);
    changes[3].tool = Digest([6; 32]);
    for changed in changes {
        assert_eq!(
            assess(changed, Some(&receipt), Some(&review), 100),
            Assessment::Unknown(Reason::IdentityMismatch)
        );
    }
}

#[test]
fn every_reviewed_receipt_binding_is_required() {
    let (identity, receipt, review) = fixture();
    let mut changes = [receipt; 8];
    changes[0].identity.capability = NativeCapability::Git;
    changes[1].identity.source = Digest([6; 32]);
    changes[2].identity.configuration = Digest([6; 32]);
    changes[3].identity.tool = Digest([6; 32]);
    changes[4].verifier = Digest([6; 32]);
    changes[5].receipt = Digest([6; 32]);
    changes[6].observed_at += 1;
    changes[7].expires_at -= 1;
    for changed in changes {
        let changed_review = ReviewRecord {
            receipt: changed,
            ..review
        };
        assert_eq!(
            assess(identity, Some(&receipt), Some(&changed_review), 100),
            Assessment::Unknown(Reason::ReviewMismatch)
        );
    }
}

#[test]
fn intervals_fail_closed_without_arithmetic_overflow() {
    let (identity, receipt, review) = fixture();
    for (start, end) in [
        (100, 100),
        (100, 99),
        (100, 401),
        (0, u64::MAX),
        (u64::MAX, 0),
    ] {
        let changed = Receipt {
            observed_at: start,
            expires_at: end,
            ..receipt
        };
        let review = ReviewRecord {
            receipt: changed,
            ..review
        };
        assert_eq!(
            assess(identity, Some(&changed), Some(&review), start),
            Assessment::Unknown(Reason::InvalidInterval)
        );
    }
    let changed = Receipt {
        observed_at: u64::MAX - 1,
        expires_at: u64::MAX,
        ..receipt
    };
    let review = ReviewRecord {
        receipt: changed,
        ..review
    };
    assert_eq!(
        assess(identity, Some(&changed), Some(&review), u64::MAX - 1),
        Assessment::AcceptedInspection
    );
}

#[test]
fn no_validation_or_edit_capability_authority() {
    let (identity, receipt, review) = fixture();
    for capability in [
        NativeCapability::Edit,
        NativeCapability::Build,
        NativeCapability::Tests,
    ] {
        let current = Identity {
            capability,
            ..identity
        };
        let receipt = Receipt {
            identity: current,
            ..receipt
        };
        let review = ReviewRecord { receipt, ..review };
        assert_eq!(
            assess(current, Some(&receipt), Some(&review), 100),
            Assessment::Unknown(Reason::UnsupportedCapability)
        );
    }
}

#[test]
fn zero_identity_is_missing_and_diagnostics_are_enum_only() {
    let (identity, receipt, review) = fixture();
    for field in 0..5 {
        let mut identity = identity;
        let mut receipt = receipt;
        match field {
            0 => identity.source = Digest([0; 32]),
            1 => identity.configuration = Digest([0; 32]),
            2 => identity.tool = Digest([0; 32]),
            3 => receipt.verifier = Digest([0; 32]),
            _ => receipt.receipt = Digest([0; 32]),
        }
        receipt.identity = identity;
        let review = ReviewRecord { receipt, ..review };
        let result = assess(identity, Some(&receipt), Some(&review), 100);
        assert_eq!(result, Assessment::Unknown(Reason::MissingIdentity));
        assert_eq!(
            result.summary(),
            "native inspection: MissingIdentity; health=Unknown; execution_authorized=false"
        );
    }
}
