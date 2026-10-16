use codex_smart_core::{
    playbook::{Archetype, ProfileClass, ValidationObligation},
    routing::{
        Reasoning,
        assessment::{RiskLevel, RoutingFacts, TaskKind, assess},
        engine::CapabilitySurface,
    },
    validation_inspection::{
        CurrentAssumptions, EvidenceProvenance, Finding, Inspection, Readiness,
    },
    validation_policy::{
        Approval, Argument, Budgets, Provenance, Reason, SCHEMA_V1, Specification, Status,
    },
    version::Version,
    workflow::{NativeSurface, ResourceCatalog, plan_workflow},
};
fn spec<'a>(argv: &'a [Argument<'a>]) -> Specification<'a> {
    Specification {
        schema_version: SCHEMA_V1,
        executable: "/private/bin/check",
        executable_pin: [1; 32],
        version: Version::new(1, 0, 0),
        source_identity: [2; 32],
        configuration_identity: [3; 32],
        argv,
        scope: "/private/repo",
        cwd: "/private/repo/tests",
        operation: ValidationObligation::ReadOnlyInvariant,
        budgets: Budgets {
            wall_seconds: 30,
            cpu_seconds: 10,
            input_bytes: 1024,
            output_bytes: 1024,
            memory_bytes: 1024,
            processes: 1,
        },
        profile: ProfileClass::Strong,
        reasoning: Reasoning::High,
    }
}
fn inspect<'a>(
    candidate: &'a Specification<'a>,
    approval: Option<Approval<'a>>,
    current: Option<CurrentAssumptions<'a>>,
    native: &NativeSurface,
) -> Inspection {
    let assessment = assess(&RoutingFacts {
        task_hints: vec![TaskKind::Inspect],
        risk_hint: Some(RiskLevel::High),
        ..Default::default()
    });
    let plan = plan_workflow(
        &assessment,
        Some(Archetype::Inspection),
        native,
        &CapabilitySurface::default(),
        &ResourceCatalog::default(),
    );
    plan.inspect_validation(native, &assessment, candidate, approval, current)
}
fn approval<'a>(s: &'a Specification<'a>) -> Approval<'a> {
    Approval {
        specification: s,
        provenance: Provenance::ExternallyVerifiedAssumption,
        observed_at: 100,
        expires_at: 200,
    }
}
fn current<'a>(s: &'a Specification<'a>) -> CurrentAssumptions<'a> {
    CurrentAssumptions {
        specification: s,
        provenance: Provenance::ExternallyVerifiedAssumption,
        observed_at: 100,
        expires_at: 200,
        now: 150,
        last_observed_time: 140,
    }
}
fn check(s: &Specification<'_>, expected: Reason) {
    let result = inspect(
        s,
        Some(approval(s)),
        Some(current(s)),
        &NativeSurface::verified_all(),
    );
    assert_eq!(result.finding, Finding::Policy(Status::Refused(expected)));
    assert_ne!(result.readiness, Readiness::NeedsEvidence);
}
#[test]
fn positive_is_conditional_only_and_private_inputs_never_escape() {
    let args = [
        Argument::Word("private-secret"),
        Argument::Path("private-source.rs"),
    ];
    let candidate = spec(&args);
    let reviewed = candidate.clone();
    let observed = candidate.clone();
    let result = inspect(
        &candidate,
        Some(approval(&reviewed)),
        Some(current(&observed)),
        &NativeSurface::verified_all(),
    );
    assert_eq!(
        result.finding,
        Finding::Policy(Status::ConditionallyPolicyAdmissible)
    );
    assert_eq!(result.readiness, Readiness::NeedsEvidence);
    assert_eq!(result.provenance, EvidenceProvenance::Unknown);
    let rendered = format!("{result:?}");
    assert!(rendered.len() < 256);
    assert!(!rendered.contains("private"));
    if let Finding::Policy(status) = result.finding {
        assert!(!status.runtime_ready());
        assert!(!status.execution_authorized());
        assert!(!status.attested());
    }
}
#[test]
fn missing_declared_revoked_unverifiable_and_stale_evidence_fail_closed() {
    let s = spec(&[]);
    let native = NativeSurface::verified_all();
    for revoked in [false, true] {
        // Revocation is external: a revoked approval must be withheld, never refreshed here.
        let review = if revoked {
            None
        } else {
            Some(Approval {
                provenance: Provenance::CallerDeclared,
                ..approval(&s)
            })
        };
        let result = inspect(&s, review, Some(current(&s)), &native);
        assert_eq!(result.readiness, Readiness::NeedsEvidence);
        assert_eq!(result.provenance, EvidenceProvenance::Unknown);
        assert_eq!(
            result.finding,
            Finding::Policy(Status::Refused(if revoked {
                Reason::MissingApproval
            } else {
                Reason::UnverifiedEvidence
            }))
        );
    }
    assert_eq!(
        inspect(&s, Some(approval(&s)), None, &native).finding,
        Finding::MissingCurrentAssumptions
    );
    for provenance in [
        Provenance::CallerDeclared,
        Provenance::ExternallyVerifiedAssumption,
    ] {
        let mut c = current(&s);
        c.provenance = provenance;
        c.now = 200;
        let result = inspect(&s, Some(approval(&s)), Some(c), &native);
        assert_eq!(
            result.finding,
            Finding::Policy(Status::Refused(
                if provenance == Provenance::CallerDeclared {
                    Reason::UnverifiedEvidence
                } else {
                    Reason::InvalidFreshness
                }
            ))
        );
    }
    let mut c = current(&s);
    c.expires_at = 150;
    assert_eq!(
        inspect(&s, Some(approval(&s)), Some(c), &native).finding,
        Finding::Policy(Status::Refused(Reason::InvalidCurrentFreshness))
    );
}
#[test]
fn mismatched_approval_and_each_current_identity_pin_refuse() {
    let s = spec(&[]);
    for field in 0..4 {
        let mut other = s.clone();
        match field {
            0 => other.executable_pin = [8; 32],
            1 => other.source_identity = [8; 32],
            2 => other.configuration_identity = [8; 32],
            _ => other.version = Version::new(2, 0, 0),
        };
        let native = NativeSurface::verified_all();
        assert_eq!(
            inspect(&s, Some(approval(&other)), Some(current(&s)), &native).finding,
            Finding::Policy(Status::Refused(Reason::ApprovalMismatch))
        );
        assert_eq!(
            inspect(&s, Some(approval(&s)), Some(current(&other)), &native).finding,
            Finding::Policy(Status::Refused(Reason::CurrentMismatch))
        );
    }
}
#[test]
fn malformed_paths_argv_scope_budgets_and_risk_reuse_policy_refusals() {
    let original = spec(&[]);
    for (field, reason) in [
        (0, Reason::UnsupportedSchema),
        (1, Reason::UnsafePath),
        (2, Reason::OutsideScope),
        (3, Reason::InvalidBudgets),
        (4, Reason::RiskFloor),
        (5, Reason::InvalidIdentity),
        (6, Reason::MissingObligation),
    ] {
        let mut s = original.clone();
        match field {
            0 => s.schema_version = 0,
            1 => s.executable = "/private/../secret",
            2 => s.cwd = "/outside",
            3 => s.budgets.processes = 9,
            4 => s.profile = ProfileClass::Economy,
            5 => s.executable_pin = [0; 32],
            _ => s.operation = ValidationObligation::ReleaseRehearsal,
        };
        check(&s, reason);
    }
    check(
        &spec(&[Argument::Word("secret;payload")]),
        Reason::UnsafeArgument,
    );
    check(
        &spec(&[Argument::Path("../secret")]),
        Reason::UnsafeArgument,
    );
    check(&spec(&vec![Argument::Word("x"); 33]), Reason::ArgumentLimit);
    let result = inspect(
        &original,
        Some(approval(&original)),
        Some(current(&original)),
        &NativeSurface::default(),
    );
    assert_eq!(
        result.finding,
        Finding::Policy(Status::Refused(Reason::RecipeNotReady))
    );
}

#[test]
fn workflow_risk_floor_missing_recipe_and_malformed_independent_inputs() {
    let high = assess(&RoutingFacts {
        task_hints: vec![TaskKind::Inspect],
        risk_hint: Some(RiskLevel::High),
        ..Default::default()
    });
    let low = assess(&RoutingFacts {
        task_hints: vec![TaskKind::Inspect],
        risk_hint: Some(RiskLevel::Low),
        ..Default::default()
    });
    let native = NativeSurface::verified_all();
    let plan = plan_workflow(
        &high,
        Some(Archetype::Inspection),
        &native,
        &CapabilitySurface::default(),
        &ResourceCatalog::default(),
    );
    let mut weak = spec(&[]);
    weak.profile = ProfileClass::Economy;
    assert_eq!(
        plan.inspect_validation(
            &native,
            &low,
            &weak,
            Some(approval(&weak)),
            Some(current(&weak))
        )
        .finding,
        Finding::Policy(Status::Refused(Reason::RiskFloor))
    );
    let s = spec(&[]);
    let mut malformed = s.clone();
    malformed.schema_version = 0;
    assert_eq!(
        inspect(&s, Some(approval(&malformed)), Some(current(&s)), &native).finding,
        Finding::Policy(Status::Refused(Reason::InvalidApprovalEvidence))
    );
    assert_eq!(
        inspect(&s, Some(approval(&s)), Some(current(&malformed)), &native).finding,
        Finding::Policy(Status::Refused(Reason::InvalidCurrentEvidence))
    );
    let mut rollback = current(&s);
    rollback.last_observed_time = 151;
    assert_eq!(
        inspect(&s, Some(approval(&s)), Some(rollback), &native).finding,
        Finding::Policy(Status::Refused(Reason::InvalidFreshness))
    );
    let unknown = assess(&RoutingFacts::default());
    let plan = plan_workflow(
        &unknown,
        None,
        &native,
        &CapabilitySurface::default(),
        &ResourceCatalog::default(),
    );
    assert_eq!(
        plan.inspect_validation(&native, &unknown, &s, None, None)
            .finding,
        Finding::MissingWorkflowRecipe
    );
}
