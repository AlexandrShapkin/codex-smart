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

fn canonical_fixture() -> (Identity, Receipt, ReviewRecord) {
    let (identity, mut receipt, review) = fixture();
    receipt.receipt = canonical_digest(&receipt).unwrap();
    (identity, receipt, ReviewRecord { receipt, ..review })
}

#[test]
fn canonical_v1_has_exact_fixed_bytes_and_capability_tags() {
    use sha2::{Digest as _, Sha256};
    let (_, receipt, _) = canonical_fixture();
    for (capability, tag) in [
        (NativeCapability::ReadFiles, 1),
        (NativeCapability::Search, 2),
        (NativeCapability::Git, 3),
    ] {
        let receipt = Receipt {
            identity: Identity {
                capability,
                ..receipt.identity
            },
            ..receipt
        };
        // Independent byte construction pins boundaries, order and endianness.
        let mut bytes = b"codex-smart/native-inspection/receipt/v1\0".to_vec();
        bytes.push(tag);
        for value in 1..=4 {
            bytes.extend_from_slice(&[value; 32]);
        }
        bytes.extend_from_slice(&[0, 0, 0, 0, 0, 0, 0, 100]);
        bytes.extend_from_slice(&[0, 0, 0, 0, 0, 0, 1, 144]);
        assert_eq!(bytes.len(), CANONICAL_DOMAIN_V1.len() + 145);
        assert!(canonical_digest(&receipt).unwrap() == Digest(Sha256::digest(&bytes).into()));
        let mut changed = receipt;
        changed.receipt = Digest([99; 32]);
        assert!(canonical_digest(&changed) == canonical_digest(&receipt));
    }
    // Independently generated SHA-256 known answer for the Search fixture.
    assert_eq!(
        canonical_digest(&receipt).unwrap().0,
        [
            20, 129, 32, 225, 163, 76, 164, 36, 161, 166, 86, 152, 143, 246, 85, 195, 57, 41, 84,
            211, 173, 106, 93, 86, 145, 75, 195, 109, 195, 105, 251, 194
        ]
    );
}

#[test]
fn canonical_hash_binds_each_field_even_when_review_is_copied() {
    let (_, receipt, review) = canonical_fixture();
    let mut changes = [receipt; 8];
    changes[0].identity.capability = NativeCapability::Git;
    changes[1].identity.source.0[31] ^= 1;
    changes[2].identity.configuration.0[0] ^= 1;
    changes[3].identity.tool.0[31] ^= 1;
    changes[4].verifier.0[0] ^= 1;
    changes[5].observed_at += 1;
    changes[6].expires_at -= 1;
    changes[7].receipt.0[0] ^= 1;
    for changed in changes {
        let copied = ReviewRecord {
            receipt: changed,
            ..review
        };
        assert_eq!(
            assess_canonical(changed.identity, Some(&changed), Some(&copied), 101),
            Assessment::Unknown(Reason::CanonicalMismatch)
        );
        // The legacy evaluator continues to check binding without canonicalization.
        assert_eq!(
            assess(changed.identity, Some(&changed), Some(&copied), 101),
            Assessment::AcceptedInspection
        );
    }
}

#[test]
fn domain_version_and_boundary_confusion_fail_closed() {
    use sha2::{Digest as _, Sha256};
    let (identity, receipt, review) = canonical_fixture();
    for domain in [
        b"codex-smart/native-inspection/receipt/v2\0".as_slice(),
        b"codex-smart/other/receipt/v1\0",
        b"codex-smart/native-inspection/receipt/v1",
    ] {
        let mut hash = Sha256::new();
        hash.update(domain);
        hash.update([2]);
        for value in 1..=4 {
            hash.update([value; 32]);
        }
        hash.update(100_u64.to_be_bytes());
        hash.update(400_u64.to_be_bytes());
        let changed = Receipt {
            receipt: Digest(hash.finalize().into()),
            ..receipt
        };
        let copied = ReviewRecord {
            receipt: changed,
            ..review
        };
        assert_eq!(
            assess_canonical(identity, Some(&changed), Some(&copied), 100),
            Assessment::Unknown(Reason::CanonicalMismatch)
        );
    }
    // Decimal concatenation would collide for these pairs; fixed u64s cannot.
    let left = Receipt {
        observed_at: 1,
        expires_at: 234,
        ..receipt
    };
    let right = Receipt {
        observed_at: 12,
        expires_at: 34,
        ..receipt
    };
    assert!(canonical_digest(&left) != canonical_digest(&right));
    let swapped = Receipt {
        identity: Identity {
            source: receipt.identity.configuration,
            configuration: receipt.identity.source,
            ..identity
        },
        ..receipt
    };
    assert!(canonical_digest(&swapped) != canonical_digest(&receipt));
}

#[test]
fn canonical_integrity_never_supplies_provenance_or_authority() {
    let (identity, receipt, review) = canonical_fixture();
    assert_eq!(
        assess_canonical(identity, None, Some(&review), 100),
        Assessment::Unknown(Reason::MissingReceipt)
    );
    assert_eq!(
        assess_canonical(identity, Some(&receipt), None, 100),
        Assessment::Unknown(Reason::MissingReview)
    );
    for provenance in [Provenance::UserDeclared, Provenance::PathDiscovery] {
        let copied = ReviewRecord {
            provenance,
            ..review
        };
        assert_eq!(
            assess_canonical(identity, Some(&receipt), Some(&copied), 100),
            Assessment::Unknown(Reason::UntrustedProvenance)
        );
    }
    for capability in [
        NativeCapability::Edit,
        NativeCapability::Build,
        NativeCapability::Tests,
    ] {
        let changed = Receipt {
            identity: Identity {
                capability,
                ..identity
            },
            ..receipt
        };
        assert!(canonical_digest(&changed) == Err(Reason::UnsupportedCapability));
        let copied = ReviewRecord {
            receipt: changed,
            ..review
        };
        assert_eq!(
            assess_canonical(changed.identity, Some(&changed), Some(&copied), 100),
            Assessment::Unknown(Reason::UnsupportedCapability)
        );
    }
    for now in [100, 399] {
        let result = assess_canonical(identity, Some(&receipt), Some(&review), now);
        assert_eq!(result, Assessment::AcceptedInspection);
        assert_eq!(
            result.summary(),
            "native inspection: BoundInspectionEvidence; health=Unknown; execution_authorized=false"
        );
    }
    for (now, reason) in [
        (99, Reason::FutureObservation),
        (400, Reason::Expired),
        (u64::MAX, Reason::Expired),
    ] {
        assert_eq!(
            assess_canonical(identity, Some(&receipt), Some(&review), now),
            Assessment::Unknown(reason)
        );
    }
    for (start, end) in [(100, 100), (100, 99), (100, 401), (0, u64::MAX)] {
        let mut changed = Receipt {
            observed_at: start,
            expires_at: end,
            ..receipt
        };
        changed.receipt = canonical_digest(&changed).unwrap();
        let copied = ReviewRecord {
            receipt: changed,
            ..review
        };
        assert_eq!(
            assess_canonical(identity, Some(&changed), Some(&copied), start),
            Assessment::Unknown(Reason::InvalidInterval)
        );
    }
}

#[test]
fn canonical_assessment_retains_identity_and_review_gates() {
    let (identity, receipt, review) = canonical_fixture();
    let mut current = identity;
    current.tool.0[0] ^= 1;
    assert_eq!(
        assess_canonical(current, Some(&receipt), Some(&review), 100),
        Assessment::Unknown(Reason::IdentityMismatch)
    );
    let mut mismatched = review;
    mismatched.receipt.verifier.0[0] ^= 1;
    assert_eq!(
        assess_canonical(identity, Some(&receipt), Some(&mismatched), 100),
        Assessment::Unknown(Reason::ReviewMismatch)
    );
    let mut missing = receipt;
    missing.identity.source = Digest([0; 32]);
    missing.receipt = canonical_digest(&missing).unwrap();
    let copied = ReviewRecord {
        receipt: missing,
        ..review
    };
    assert_eq!(
        assess_canonical(missing.identity, Some(&missing), Some(&copied), 100),
        Assessment::Unknown(Reason::MissingIdentity)
    );
    let mut last_second = Receipt {
        observed_at: u64::MAX - 1,
        expires_at: u64::MAX,
        ..receipt
    };
    last_second.receipt = canonical_digest(&last_second).unwrap();
    let review = ReviewRecord {
        receipt: last_second,
        ..review
    };
    assert_eq!(
        assess_canonical(identity, Some(&last_second), Some(&review), u64::MAX - 1),
        Assessment::AcceptedInspection
    );
    assert_eq!(
        assess_canonical(identity, Some(&last_second), Some(&review), u64::MAX),
        Assessment::Unknown(Reason::Expired)
    );
}
