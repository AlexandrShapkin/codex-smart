use super::*;

type Fields = Vec<(u8, Vec<u8>)>;
fn string(v: &[u8]) -> Vec<u8> {
    [(v.len() as u16).to_be_bytes().as_slice(), v].concat()
}
fn spec() -> Vec<u8> {
    let mut s = vec![0, 1];
    s.extend(string(b"/bin/true"));
    s.extend([0x11; 32]);
    for n in [1u32, 2, 3] {
        s.extend(n.to_be_bytes());
    }
    s.extend([0x22; 32]);
    s.extend([0x33; 32]);
    s.push(3);
    for (kind, arg) in [(1, b"check".as_slice()), (2, b"--offline"), (3, b"src")] {
        s.push(kind);
        s.extend(string(arg));
    }
    s.extend(string(b"/work"));
    s.extend(string(b"/work/repo"));
    s.push(2);
    for n in [30u64, 15, 1024, 1024, 1048576, 1] {
        s.extend(n.to_be_bytes());
    }
    s.extend([3, 2]);
    s
}
fn unhex(s: &str) -> [u8; 32] {
    std::array::from_fn(|i| u8::from_str_radix(&s[2 * i..2 * i + 2], 16).unwrap())
}
const SPEC: &str = "db38c03a0a016932acd0a2ee195e03af7abae7b76730801658c9a8b05bbfcd67";
const CONTEXT: &str = "d3ce91a75b3afe19b677e90ef9eb77d9e16a9a4f3221b055530fa98d06233c30";
const BODY: &str = "f9733c27521a922f8bf20e1b421781393bc61a62c6e3fb900a84248788393cec";
const WIRE: &str = "f224303817cc78770d4ff88fc6e40f49305c675da4aa3a30080135ce7706dccb";
fn fixture() -> Fields {
    let values = vec![
        vec![1],
        b"example/repo".to_vec(),
        vec![1],
        b"/work".to_vec(),
        b"offline-v1".to_vec(),
        7u64.to_be_bytes().to_vec(),
        vec![b'A'; 32],
        vec![b'O'; 32],
        vec![b'R'; 32],
        7u64.to_be_bytes().to_vec(),
        3u64.to_be_bytes().to_vec(),
        vec![b'X'; 16],
        vec![b'S'; 16],
        vec![b'U'; 16],
        vec![b'T'; 16],
        100u64.to_be_bytes().to_vec(),
        400u64.to_be_bytes().to_vec(),
        spec(),
        unhex(SPEC).to_vec(),
        vec![0x22; 32],
        vec![0x33; 32],
        vec![0x44; 32],
        vec![0x55; 32],
        unhex(CONTEXT).to_vec(),
        vec![0, 0],
        vec![],
    ];
    values
        .into_iter()
        .enumerate()
        .map(|(i, v)| ((i + 1) as u8, v))
        .collect()
}
fn build(f: &Fields) -> Vec<u8> {
    let mut e = [DOMAIN, &[0, 1]].concat();
    for (tag, v) in f {
        e.push(*tag);
        e.extend((v.len() as u16).to_be_bytes());
        e.extend(v);
    }
    e
}
fn change(tag: usize, v: &[u8]) -> Vec<u8> {
    let mut f = fixture();
    f[tag - 1].1 = v.to_vec();
    build(&f)
}
fn result(e: &[u8], external: &[u8], policy: &[u8]) -> Result<(), Diagnostic> {
    decode(e, external, policy).map(|p| {
        assert!(!p.admitted());
        assert!(!p.attested());
        assert!(!p.runtime_ready());
        assert!(!p.execution_authorized());
    })
}
#[test]
fn official_v00_through_v32() {
    let e = build(&fixture());
    let s = spec();
    let h = DOMAIN.len() + 2;
    let mut cases = vec![(e.clone(), vec![], vec![], Ok(()))];
    let mut over = e.clone();
    over.resize(16385, b'x');
    cases.push((over, vec![], vec![], Err(Oversize)));
    cases.push((
        e.clone(),
        vec![],
        vec![b'x'; 65537 - e.len()],
        Err(Oversize),
    ));
    let mut f = fixture();
    f.insert(3, (3, vec![1]));
    cases.push((build(&f), vec![], vec![], Err(DuplicateField)));
    let mut f = fixture();
    f.insert(25, (27, vec![]));
    cases.push((build(&f), vec![], vec![], Err(UnknownField)));
    let mut f = fixture();
    f.remove(1);
    cases.push((build(&f), vec![], vec![], Err(MissingField)));
    let mut f = fixture();
    f.swap(2, 3);
    cases.push((build(&f), vec![], vec![], Err(OutOfOrder)));
    cases.push((
        change(6, &[&[0], 7u64.to_be_bytes().as_slice()].concat()),
        vec![],
        vec![],
        Err(MalformedValue),
    ));
    cases.push((
        [e.as_slice(), &[0]].concat(),
        vec![],
        vec![],
        Err(TrailingPayload),
    ));
    let mut v = e.clone();
    v[h - 1] = 2;
    cases.push((v, vec![], vec![], Err(UnsupportedVersion)));
    cases.push((
        DOMAIN[..DOMAIN.len() - 1].to_vec(),
        vec![],
        vec![],
        Err(Truncated),
    ));
    let mut v = e.clone();
    *v.last_mut().unwrap() = 1;
    cases.push((v, vec![], vec![], Err(Truncated)));
    let mut v = e.clone();
    v[DOMAIN.len() - 1] = b'?';
    cases.push((v, vec![], vec![], Err(UnsupportedDomain)));
    cases.push((
        change(2, b"example/\xff"),
        vec![],
        vec![],
        Err(MalformedValue),
    ));
    cases.push((
        change(25, &[0, 1]),
        vec![],
        vec![],
        Err(UnsupportedProofSuite),
    ));
    cases.push((change(26, &[0]), vec![], vec![], Err(MalformedValue)));
    cases.push((change(1, &[2]), vec![], vec![], Ok(())));
    cases.push((change(22, &[0x45; 32]), vec![], vec![], Ok(())));
    cases.push((change(6, &8u64.to_be_bytes()), vec![], vec![], Ok(())));
    let mut v = s.clone();
    let len = v.len();
    v[len - 2] = 2;
    cases.push((change(18, &v), vec![], vec![], Ok(())));
    let mut v = s.clone();
    v[1] = 2;
    cases.push((change(18, &v), vec![], vec![], Err(UnsupportedSchema)));
    cases.push((change(24, &[0x66; 32]), vec![], vec![], Ok(())));
    cases.push((change(24, &[0; 32]), vec![], vec![], Err(MalformedValue)));
    let mut v = DOMAIN.to_vec();
    *v.last_mut().unwrap() = b'?';
    cases.push((v, vec![], vec![], Err(UnsupportedDomain)));
    cases.push((change(18, &[0, 2]), vec![], vec![], Err(UnsupportedSchema)));
    cases.push(([&e[..h], &[27]].concat(), vec![], vec![], Err(Truncated)));
    cases.push((
        [&e[..h], &[27, 0, 1]].concat(),
        vec![],
        vec![],
        Err(UnknownField),
    ));
    cases.push(([DOMAIN, &[0]].concat(), vec![], vec![], Err(Truncated)));
    let prefix = 2 + string(b"/bin/true").len() + 32 + 12 + 64;
    assert_eq!(s[prefix], 3);
    let mut v = s[..prefix].to_vec();
    v.extend([3, 1]);
    v.extend(string(&vec![b'A'; 3000]));
    v.push(1);
    v.extend(string(&vec![b'B'; 2000]));
    cases.push((change(18, &v), vec![], vec![], Err(MalformedValue)));
    v.truncate(v.len() - 1000);
    cases.push((change(18, &v), vec![], vec![], Err(Truncated)));
    for (v, expected) in [
        (&[0, 1, 4, 1][..], MalformedValue),
        (&[0, 1, 4, 0][..], Truncated),
        (&[0, 1, 4][..], Truncated),
    ] {
        cases.push((change(18, v), vec![], vec![], Err(expected)));
    }
    assert_eq!(cases.len(), 33);
    for (i, (e, ex, pol, expected)) in cases.iter().enumerate() {
        assert_eq!(&result(e, ex, pol), expected, "V{i:02}");
    }
}
#[test]
fn exact_hashes() {
    let e = build(&fixture());
    assert_eq!(e.len(), 765);
    assert_eq!(spec().len(), 218);
    let p = decode(&e, &[], &[]).ok().unwrap();
    assert_eq!(p.spec_digest, unhex(SPEC));
    assert_eq!(p.body_digest, unhex(BODY));
    assert_eq!(p.wire_digest, unhex(WIRE));
    // Fixture construction only; there is deliberately no public K helper.
    assert_eq!(
        hash(
            b"codex-smart/validation-context/v1",
            &[1, 3, 3, 3, 1, 0, 1, 1, 2, 1, 1, 6]
        ),
        unhex(CONTEXT)
    );
}
#[test]
fn mixed_fault_precedence() {
    let mut f = fixture();
    f[0].1 = vec![99];
    f.remove(1);
    assert_eq!(result(&build(&f), &[], &[]), Err(MissingField));
    f.insert(1, (27, vec![]));
    assert_eq!(result(&build(&f), &[], &[]), Err(UnknownField));
    let mut f = fixture();
    f[24].1 = vec![0, 1];
    f[25].1 = vec![1; 4097];
    assert_eq!(result(&build(&f), &[], &[]), Err(MalformedValue));
    f[25].1 = vec![1];
    assert_eq!(result(&build(&f), &[], &[]), Err(UnsupportedProofSuite));
    f[0].1 = vec![99];
    f[17].1 = vec![0, 2];
    assert_eq!(result(&build(&f), &[], &[]), Err(MalformedValue));
    let mut f = fixture();
    f.insert(3, (3, vec![1]));
    let mut e = build(&f);
    e.truncate(DOMAIN.len() + 2 + 3 + 1 + 3 + 12 + 3 + 1 + 3);
    assert_eq!(result(&e, &[], &[]), Err(DuplicateField));
}
#[test]
fn widths_ascii_labels_and_identities() {
    for tag in [
        6, 10, 11, 16, 17, 7, 8, 9, 19, 20, 21, 22, 23, 24, 12, 13, 14, 15, 25,
    ] {
        for n in [0, 1, 7, 9, 15, 17, 31, 33] {
            if n == fixture()[tag - 1].1.len() {
                continue;
            }
            assert_eq!(
                result(&change(tag, &vec![1; n]), &[], &[]),
                Err(MalformedValue),
                "tag {tag} size {n}"
            );
        }
    }
    for tag in [6, 10, 7, 8, 9, 19, 20, 21, 22, 23, 24, 12, 13, 14, 15] {
        let n = fixture()[tag - 1].1.len();
        assert_eq!(
            result(&change(tag, &vec![0; n]), &[], &[]),
            Err(MalformedValue)
        );
    }
    for (tag, vals) in [
        (1, vec![vec![], vec![0], vec![3], vec![1, 0]]),
        (3, vec![vec![0], vec![2]]),
        (
            2,
            vec![
                b"A/repo".to_vec(),
                b"a/b/c".to_vec(),
                b"/b".to_vec(),
                vec![b'a'; 130],
            ],
        ),
        (5, vec![b"UPPER".to_vec(), b"a/b".to_vec(), vec![b'a'; 65]]),
    ] {
        for v in vals {
            assert_eq!(result(&change(tag, &v), &[], &[]), Err(MalformedValue));
        }
    }
    for tag in [2, 4, 5] {
        for v in [vec![], vec![0], vec![32], vec![127], vec![255]] {
            assert_eq!(result(&change(tag, &v), &[], &[]), Err(MalformedValue));
        }
    }
    for n in [4096, 4097] {
        assert_eq!(
            result(&change(26, &vec![1; n]), &[], &[]),
            Err(MalformedValue)
        );
    }
}
#[test]
fn bounded_inputs_and_nested_boundaries() {
    let e = build(&fixture());
    assert_eq!(result(&e, &vec![0; 65536 - e.len()], &[]), Ok(()));
    assert_eq!(result(&e, &[0], &vec![0; 65536 - e.len()]), Err(Oversize));
    assert_eq!(result(&[], &vec![0; 65537], &[]), Err(Oversize));
    let mut full = e.clone();
    full.resize(16384, 0);
    assert_eq!(result(&full, &[], &[]), Err(TrailingPayload));
    full.push(0);
    assert_eq!(result(&full, &[], &[]), Err(Oversize));
    let s = spec();
    for n in 0..s.len() {
        assert_eq!(
            result(&change(18, &s[..n]), &[], &[]),
            Err(Truncated),
            "S prefix {n}"
        );
    }
    let mut extra = s.clone();
    extra.push(0);
    assert_eq!(result(&change(18, &extra), &[], &[]), Err(MalformedValue));
    for offset in [s.len() - 2, s.len() - 1] {
        for b in [0, 4, 255] {
            let mut v = s.clone();
            v[offset] = b;
            assert_eq!(result(&change(18, &v), &[], &[]), Err(MalformedValue));
        }
    }
    let prefix = 121;
    assert_eq!(s[prefix], 3);
    for count in [0usize, 32, 33] {
        let mut v = s[..prefix].to_vec();
        v.push(count as u8);
        for _ in 0..count {
            v.push(1);
            v.extend(string(b"x"));
        }
        v.extend(&s[148..]); // scope begins after the fixture's three arguments
        let expected = if count <= 32 {
            Ok(())
        } else {
            Err(MalformedValue)
        };
        assert_eq!(result(&change(18, &v), &[], &[]), expected);
    }
}

#[test]
fn nested_limits_and_representation_not_policy() {
    let s = spec();
    let argc_offset = 121;
    let tail = &s[148..];
    let with_args = |args: &[(u8, Vec<u8>)]| {
        let mut v = s[..argc_offset].to_vec();
        v.push(args.len() as u8);
        for (kind, raw) in args {
            v.push(*kind);
            v.extend(string(raw));
        }
        v.extend(tail);
        v
    };
    for (args, expected) in [
        (vec![(1, vec![b'x'; 4096])], Ok(())),
        (vec![(1, vec![b'x'; 4097])], Err(MalformedValue)),
        (vec![(1, vec![b'x'; 2048]), (2, vec![b'y'; 2048])], Ok(())),
        (
            vec![(1, vec![b'x'; 2048]), (2, vec![b'y'; 2049])],
            Err(MalformedValue),
        ),
        (vec![(3, vec![b'x'; 1024])], Ok(())),
        (vec![(3, vec![b'x'; 1025])], Err(MalformedValue)),
        (vec![(0, b"x".to_vec())], Err(MalformedValue)),
        (vec![(4, b"x".to_vec())], Err(MalformedValue)),
        (vec![(1, vec![])], Err(MalformedValue)),
        (vec![(1, vec![32])], Err(MalformedValue)),
    ] {
        assert_eq!(result(&change(18, &with_args(&args)), &[], &[]), expected);
    }
    for n in [0usize, 1024, 1025] {
        let mut v = vec![0, 1];
        v.extend(string(&vec![b'x'; n]));
        v.extend(&s[13..]);
        assert_eq!(
            result(&change(18, &v), &[], &[]),
            if n == 1024 {
                Ok(())
            } else {
                Err(MalformedValue)
            }
        );
    }
    for offset in [13, 57, 89] {
        let mut v = s.clone();
        v[offset..offset + 32].fill(0);
        assert_eq!(result(&change(18, &v), &[], &[]), Err(MalformedValue));
    }
    let operation = s.len() - 51;
    for op in 0..=11 {
        let mut v = s.clone();
        v[operation] = op;
        assert_eq!(
            result(&change(18, &v), &[], &[]),
            if (1..=10).contains(&op) {
                Ok(())
            } else {
                Err(MalformedValue)
            }
        );
    }
    // Arbitrary unsigned budgets and versions, unsafe lexical paths/argv,
    // mismatched scope and asserted hashes are for a separate policy evaluator.
    for byte in [0, 255] {
        let mut v = s.clone();
        v[45..57].fill(byte);
        v[operation + 1..operation + 49].fill(byte);
        assert_eq!(result(&change(18, &v), &[], &[]), Ok(()));
    }
    assert_eq!(result(&change(4, b"relative;unsafe"), &[], &[]), Ok(()));
    assert_eq!(result(&change(19, &[99; 32]), &[], &[]), Ok(()));
    let mut f = fixture();
    f[1].1 = [vec![b'a'; 64], vec![b'/'], vec![b'b'; 64]].concat();
    f[4].1 = vec![b'a'; 64];
    f[3].1 = vec![b'x'; 1024];
    assert_eq!(result(&build(&f), &[], &[]), Ok(()));
    f[3].1.push(b'x');
    assert_eq!(result(&build(&f), &[], &[]), Err(MalformedValue));
}

fn claims() -> BindingClaims<'static> {
    BindingClaims {
        repository: "example/repo",
        scope: "/work",
        policy: "offline-v1",
        policy_epoch: 7,
        root: [b'A'; 32],
        operator: [b'O'; 32],
        reviewer: [b'R'; 32],
        delegation_epoch: 7,
        revocation_generation: 3,
        observation: [b'X'; 16],
        session: [b'S'; 16],
        one_use: [b'U'; 16],
        clock_domain: [b'T'; 16],
        observed_at: 100,
        expires_at: 400,
        spec_digest: unhex(SPEC),
        source: [0x22; 32],
        configuration: [0x33; 32],
        tool_closure: [0x44; 32],
        verifier: [0x55; 32],
        context: unhex(CONTEXT),
        provenance: crate::validation_policy::Provenance::ExternallyVerifiedAssumption,
    }
}
fn review() -> ReviewEvidence<'static> {
    ReviewEvidence {
        wire_digest: unhex(WIRE),
        authorization: claims(),
    }
}
fn time() -> TimeObservation {
    TimeObservation {
        clock_domain: [b'T'; 16],
        now: 101,
        last_observed: 100,
    }
}
fn compare(p: &ParseOnly, r: &ReviewEvidence<'_>, c: &BindingClaims<'_>) -> BindingResult {
    compare_evidence(p, Some(r), Some(c), Some(&time()), None)
}
#[test]
fn binding_matching_claims_never_supply_authority() {
    let mut parsed = decode(&build(&fixture()), &[], &[]).unwrap();
    assert_eq!(
        compare(&parsed, &review(), &claims()),
        BindingResult::NeedsIndependentAuthority
    );
    let mut c = claims();
    c.provenance = crate::validation_policy::Provenance::CallerDeclared;
    let mut r = review();
    r.authorization.provenance = c.provenance;
    assert_eq!(
        compare(&parsed, &r, &c),
        BindingResult::NeedsIndependentAuthority
    );
    // Public format digests cannot rewrite the private binding projection.
    parsed.spec_digest = [99; 32];
    parsed.body_digest = [99; 32];
    parsed.wire_digest = [99; 32];
    assert_eq!(
        compare(&parsed, &r, &c),
        BindingResult::NeedsIndependentAuthority
    );
    r.wire_digest = parsed.wire_digest;
    assert_eq!(
        compare(&parsed, &r, &c),
        BindingResult::Mismatch(EvidenceKind::Review, BindingField::Wire)
    );
}
#[test]
fn binding_each_separate_claim_is_compared_in_both_roles() {
    use BindingField::*;
    let p = decode(&build(&fixture()), &[], &[]).unwrap();
    macro_rules! mismatch {
        ($member:ident, $value:expr, $field:ident) => {{
            let mut c = claims();
            c.$member = $value;
            assert_eq!(
                compare(&p, &review(), &c),
                BindingResult::Mismatch(EvidenceKind::Current, $field)
            );
            let mut r = review();
            r.authorization = c;
            assert_eq!(
                compare(&p, &r, &claims()),
                BindingResult::Mismatch(EvidenceKind::Review, $field)
            );
        }};
    }
    mismatch!(spec_digest, [99; 32], Specification);
    mismatch!(repository, "example/other", Repository);
    mismatch!(scope, "/other", Scope);
    mismatch!(policy, "other", Policy);
    mismatch!(policy_epoch, 8, PolicyEpoch);
    mismatch!(root, [99; 32], Root);
    mismatch!(operator, [99; 32], Operator);
    mismatch!(reviewer, [99; 32], Reviewer);
    mismatch!(delegation_epoch, 8, DelegationEpoch);
    mismatch!(revocation_generation, 4, RevocationGeneration);
    mismatch!(observation, [99; 16], Observation);
    mismatch!(session, [99; 16], Session);
    mismatch!(one_use, [99; 16], OneUse);
    mismatch!(clock_domain, [99; 16], ClockDomain);
    mismatch!(observed_at, 99, ObservedAt);
    mismatch!(expires_at, 399, ExpiresAt);
    mismatch!(source, [99; 32], Source);
    mismatch!(configuration, [99; 32], Configuration);
    mismatch!(tool_closure, [99; 32], ToolClosure);
    mismatch!(verifier, [99; 32], Verifier);
    mismatch!(context, [99; 32], Context);
    let mut r = review();
    r.wire_digest = unhex(BODY);
    assert_eq!(
        compare(&p, &r, &claims()),
        BindingResult::Mismatch(EvidenceKind::Review, Wire)
    );
}
#[test]
fn binding_missing_bounds_conflicts_and_precedence() {
    use BindingResult::*;
    let p = decode(&build(&fixture()), &[], &[]).unwrap();
    assert_eq!(
        compare_evidence(&p, None, None, None, None),
        Missing(EvidenceKind::Review)
    );
    assert_eq!(
        compare_evidence(&p, Some(&review()), None, None, None),
        Missing(EvidenceKind::Current)
    );
    assert_eq!(
        compare_evidence(&p, Some(&review()), Some(&claims()), None, None),
        Missing(EvidenceKind::Time)
    );
    for (tag, value, field) in [
        (4, b"/other".as_slice(), BindingField::Scope),
        (19, &[99; 32], BindingField::Specification),
        (20, &[99; 32], BindingField::Source),
        (21, &[99; 32], BindingField::Configuration),
    ] {
        let parsed = decode(&change(tag, value), &[], &[]).unwrap();
        assert_eq!(
            compare_evidence(&parsed, None, None, None, None),
            Conflict(field)
        );
    }
    let mut f = fixture();
    f[0].1 = vec![2];
    f[3].1 = b"/other".to_vec();
    let denied = decode(&build(&f), &[], &[]).unwrap();
    assert_eq!(compare_evidence(&denied, None, None, None, None), Denied);
    for (member, cap) in [(0, 129), (1, 1024), (2, 64)] {
        let over = "X".repeat(cap + 1);
        let mut c = claims();
        match member {
            0 => c.repository = &over,
            1 => c.scope = &over,
            _ => c.policy = &over,
        }
        assert_eq!(
            compare(&p, &review(), &c),
            OversizeEvidence(EvidenceKind::Current)
        );
        let r = ReviewEvidence {
            wire_digest: [99; 32],
            authorization: c,
        };
        assert_eq!(
            compare(&p, &r, &claims()),
            OversizeEvidence(EvidenceKind::Review)
        );
    }
}
#[test]
fn binding_time_and_repeated_use_are_only_supplied_observations() {
    use BindingResult::*;
    let p = decode(&build(&fixture()), &[], &[]).unwrap();
    for (now, last, expected) in [
        (99, 0, FutureObservation),
        (400, 100, Expired),
        (401, 500, Expired),
        (101, 102, StaleSuppliedTime),
        (399, 100, NeedsIndependentAuthority),
    ] {
        let t = TimeObservation {
            now,
            last_observed: last,
            ..time()
        };
        assert_eq!(
            compare_evidence(&p, Some(&review()), Some(&claims()), Some(&t), None),
            expected
        );
    }
    let t = TimeObservation {
        clock_domain: [99; 16],
        ..time()
    };
    assert_eq!(
        compare_evidence(&p, Some(&review()), Some(&claims()), Some(&t), None),
        Mismatch(EvidenceKind::Time, BindingField::ClockDomain)
    );
    for (observed, expires) in [(0, 100), (100, 100), (100, 99), (100, 401), (u64::MAX, 1)] {
        let mut f = fixture();
        f[15].1 = u64::to_be_bytes(observed).to_vec();
        f[16].1 = u64::to_be_bytes(expires).to_vec();
        let bytes = build(&f);
        let parsed = decode(&bytes, &[], &[]).unwrap();
        let mut c = claims();
        c.observed_at = observed;
        c.expires_at = expires;
        let r = ReviewEvidence {
            wire_digest: hash(b"codex-smart/validation-approval-wire/v1", &bytes),
            authorization: c.clone(),
        };
        assert_eq!(compare(&parsed, &r, &c), InvalidInterval);
    }
    for (observation, one_use, expected) in [
        ([b'X'; 16], [99; 16], RepeatedUseClaim),
        ([99; 16], [b'U'; 16], RepeatedUseClaim),
        ([99; 16], [99; 16], NeedsIndependentAuthority),
    ] {
        let prior = PriorUse {
            observation,
            one_use,
        };
        assert_eq!(
            compare_evidence(
                &p,
                Some(&review()),
                Some(&claims()),
                Some(&time()),
                Some(&prior)
            ),
            expected
        );
    }
}

#[test]
fn binding_sensitive_types_have_no_debug_or_display() {
    // Inference becomes ambiguous if either forbidden trait is ever implemented.
    macro_rules! no_trait {
        ($ty:ty, $bound:path) => {{
            trait AmbiguousIfImplemented<A> {
                fn marker() {}
            }
            impl<T: ?Sized> AmbiguousIfImplemented<()> for T {}
            impl<T: ?Sized + $bound> AmbiguousIfImplemented<u8> for T {}
            let _ = <$ty as AmbiguousIfImplemented<_>>::marker;
        }};
    }
    macro_rules! private {
        ($ty:ty) => {
            no_trait!($ty, std::fmt::Debug);
            no_trait!($ty, std::fmt::Display);
        };
    }
    private!(ParseOnly);
    private!(BindingClaims<'static>);
    private!(ReviewEvidence<'static>);
    private!(TimeObservation);
    private!(PriorUse);
    private!(binding::Projection);
    private!(binding::Nested);
    assert!(std::mem::size_of::<ParseOnly>() < 4096);
    // Diagnostics cannot contain any candidate bytes, even for sensitive labels.
    let p = decode(&build(&fixture()), &[], &[]).unwrap();
    let c = BindingClaims {
        scope: "/private-sensitive-label",
        ..claims()
    };
    assert_eq!(
        format!("{:?}", compare(&p, &review(), &c)),
        "Mismatch(Current, Scope)"
    );
}
