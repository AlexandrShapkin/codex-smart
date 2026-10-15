use codex_smart_core::{
    playbook::{ProfileClass, ValidationObligation},
    routing::{
        Reasoning,
        assessment::{Ambiguity, RiskLevel, RoutingFacts, TaskKind, assess},
    },
    validation_policy::*,
    version::Version,
    workflow::{PlannedValidation, ValidationReadiness, ValidationRecipe},
};

fn spec<'a>(argv: &'a [Argument<'a>]) -> Specification<'a> {
    Specification {
        schema_version: SCHEMA_V1,
        executable: "/approved/bin/check",
        executable_pin: [1; 32],
        version: Version::new(1, 0, 0),
        source_identity: [2; 32],
        configuration_identity: [3; 32],
        argv,
        scope: "/workspace/repo",
        cwd: "/workspace/repo/tests",
        operation: ValidationObligation::RelevantTests,
        budgets: Budgets {
            wall_seconds: 30,
            cpu_seconds: 10,
            input_bytes: 1024,
            output_bytes: 1024,
            memory_bytes: 1_048_576,
            processes: 1,
        },
        profile: ProfileClass::Strong,
        reasoning: Reasoning::High,
    }
}
fn recipe() -> ValidationRecipe {
    ValidationRecipe {
        status: ValidationReadiness::Ready,
        checks: vec![PlannedValidation {
            obligation: ValidationObligation::RelevantTests,
            required_native: Default::default(),
            readiness: ValidationReadiness::Ready,
        }],
    }
}
fn run<'a>(s: &'a Specification<'a>, change: impl FnOnce(&mut Input<'a>)) -> Status {
    static RECIPE: std::sync::LazyLock<ValidationRecipe> = std::sync::LazyLock::new(recipe);
    static ASSESSMENT: std::sync::LazyLock<
        codex_smart_core::routing::assessment::TaskRiskAssessment,
    > = std::sync::LazyLock::new(|| {
        assess(&RoutingFacts {
            task_hints: vec![TaskKind::Edit],
            risk_hint: Some(RiskLevel::High),
            ..Default::default()
        })
    });
    let mut input = Input {
        specification: s,
        approval: Some(Approval {
            specification: s,
            provenance: Provenance::ExternallyVerifiedAssumption,
            observed_at: 100,
            expires_at: 200,
        }),
        current: s,
        current_provenance: Provenance::ExternallyVerifiedAssumption,
        current_observed_at: 110,
        current_expires_at: 190,
        recipe: &RECIPE,
        assessment: &ASSESSMENT,
        now: 150,
        last_observed_time: 140,
    };
    change(&mut input);
    evaluate(&input)
}
fn refused(s: &Specification<'_>, reason: Reason) {
    assert_eq!(run(s, |_| {}), Status::Refused(reason));
}

#[test]
fn structural_admissibility_is_never_attestation_readiness_authority_or_result() {
    let args = [
        Argument::Word("test"),
        Argument::Flag("--offline"),
        Argument::Path("src/check.rs"),
    ];
    let s = spec(&args);
    let result = run(&s, |_| {});
    assert_eq!(result, Status::ConditionallyPolicyAdmissible);
    assert!(!result.admitted());
    assert!(!result.attested());
    assert!(!result.runtime_ready());
    assert!(!result.execution_authorized());
    // Even a caller forging every provenance enum above cannot obtain actual trust.
    assert_eq!(format!("{result:?}"), "ConditionallyPolicyAdmissible");
}

#[test]
fn missing_and_declared_reviews_and_current_observations_fail_closed() {
    let s = spec(&[]);
    assert_eq!(
        run(&s, |i| i.approval = None),
        Status::Refused(Reason::MissingApproval)
    );
    assert_eq!(
        run(&s, |i| i.approval.as_mut().unwrap().provenance =
            Provenance::CallerDeclared),
        Status::Refused(Reason::UnverifiedEvidence)
    );
    assert_eq!(
        run(&s, |i| i.current_provenance = Provenance::CallerDeclared),
        Status::Refused(Reason::UnverifiedEvidence)
    );
}

#[test]
fn review_and_current_bind_every_specification_field() {
    let original = spec(&[]);
    let other_args = [Argument::Word("other")];
    let mut variants = Vec::new();
    macro_rules! variant {
        ($field:ident, $value:expr) => {{
            let mut s = original.clone();
            s.$field = $value;
            variants.push(s);
        }};
    }
    variant!(executable, "/other/check");
    variant!(executable_pin, [4; 32]);
    variant!(version, Version::new(2, 0, 0));
    variant!(source_identity, [4; 32]);
    variant!(configuration_identity, [4; 32]);
    variant!(argv, &other_args);
    variant!(scope, "/workspace");
    variant!(cwd, "/workspace/repo");
    variant!(operation, ValidationObligation::BuildOrStaticCheck);
    variant!(
        budgets,
        Budgets {
            output_bytes: 2048,
            ..original.budgets
        }
    );
    variant!(profile, ProfileClass::Standard);
    variant!(reasoning, Reasoning::Medium);
    let recipe = recipe();
    let assessment = assess(&RoutingFacts {
        task_hints: vec![TaskKind::Edit],
        ..Default::default()
    });
    for changed in &variants {
        let mut i = Input {
            specification: &original,
            approval: Some(Approval {
                specification: changed,
                provenance: Provenance::ExternallyVerifiedAssumption,
                observed_at: 100,
                expires_at: 200,
            }),
            current: &original,
            current_provenance: Provenance::ExternallyVerifiedAssumption,
            current_observed_at: 110,
            current_expires_at: 190,
            recipe: &recipe,
            assessment: &assessment,
            now: 150,
            last_observed_time: 140,
        };
        assert_eq!(evaluate(&i), Status::Refused(Reason::ApprovalMismatch));
        i.approval.as_mut().unwrap().specification = &original;
        i.current = changed;
        assert_eq!(evaluate(&i), Status::Refused(Reason::CurrentMismatch));
    }
}

#[test]
fn freshness_rejects_expiry_future_observation_rollback_and_excess_lifetime() {
    let s = spec(&[]);
    for (observed, expires, now, previous) in [
        (100, 200, 200, 140),
        (151, 200, 150, 140),
        (100, 200, 150, 151),
        (100, 401, 150, 140),
        (100, 100, 150, 140),
        (0, 200, 150, 140),
    ] {
        assert_eq!(
            run(&s, |i| {
                let a = i.approval.as_mut().unwrap();
                a.observed_at = observed;
                a.expires_at = expires;
                i.now = now;
                i.last_observed_time = previous;
            }),
            Status::Refused(Reason::InvalidFreshness)
        );
    }
}

#[test]
fn hostile_arguments_and_ambiguous_paths_are_rejected_without_echo() {
    for raw in [
        "",
        "--exec=x",
        "a;b",
        "$(secret)",
        "a\nb",
        "a\0b",
        "@response",
        "../secret",
        "a b",
        "\\host",
        "é",
        "-x",
    ] {
        let args = [Argument::Word(raw)];
        let result = run(&spec(&args), |_| {});
        assert_eq!(result, Status::Refused(Reason::UnsafeArgument));
        assert_eq!(format!("{result:?}"), "Refused(UnsafeArgument)");
    }
    for raw in ["--", "---exec", "--exec=x", "-c", "--a;b", "--a\nb"] {
        refused(&spec(&[Argument::Flag(raw)]), Reason::UnsafeArgument);
    }
    for raw in [
        "/absolute",
        "../private",
        "a/../b",
        "a//b",
        "./a",
        "a/",
        "C:/a",
        "a\\b",
        "-flag",
        "a/.hidden/../x",
    ] {
        refused(&spec(&[Argument::Path(raw)]), Reason::UnsafeArgument);
    }
    for raw in ["relative", "/a/../b", "//repo", "/repo/", "/", "/a\\b"] {
        let mut s = spec(&[]);
        s.cwd = raw;
        refused(&s, Reason::UnsafePath);
    }
    let mut s = spec(&[]);
    s.cwd = "/workspace/repository";
    refused(&s, Reason::OutsideScope);
    let long = "a".repeat(MAX_PATH_BYTES + 1);
    s.cwd = &long;
    refused(&s, Reason::UnsafePath);
}

#[test]
fn hard_argument_limits_and_identity_presence() {
    let args = vec![Argument::Word("a"); MAX_ARGS + 1];
    refused(&spec(&args), Reason::ArgumentLimit);
    let raw = "a".repeat(MAX_ARG_BYTES + 1);
    refused(&spec(&[Argument::Word(&raw)]), Reason::ArgumentLimit);
    let raw = "a".repeat(MAX_ARG_BYTES);
    assert_eq!(
        run(&spec(&[Argument::Word(&raw)]), |_| {}),
        Status::ConditionallyPolicyAdmissible
    );
    for field in 0..3 {
        let mut s = spec(&[]);
        match field {
            0 => s.executable_pin = [0; 32],
            1 => s.source_identity = [0; 32],
            _ => s.configuration_identity = [0; 32],
        };
        refused(&s, Reason::InvalidIdentity);
    }
}

#[test]
fn every_budget_has_a_nonzero_hard_ceiling() {
    for value in [0, u64::MAX] {
        for field in 0..6 {
            let mut s = spec(&[]);
            let b = &mut s.budgets;
            match field {
                0 => b.wall_seconds = value,
                1 => b.cpu_seconds = value,
                2 => b.input_bytes = value,
                3 => b.output_bytes = value,
                4 => b.memory_bytes = value,
                _ => b.processes = value,
            };
            refused(&s, Reason::InvalidBudgets);
        }
    }
    let mut s = spec(&[]);
    s.budgets.cpu_seconds = 31;
    refused(&s, Reason::InvalidBudgets);
}

#[test]
fn risk_and_recipe_floors_remain_closed() {
    let mut s = spec(&[]);
    s.profile = ProfileClass::Standard;
    refused(&s, Reason::RiskFloor);
    s.profile = ProfileClass::Strong;
    s.reasoning = Reasoning::Medium;
    refused(&s, Reason::RiskFloor);
    let s = spec(&[]);
    let mut r = recipe();
    r.status = ValidationReadiness::NeedsEvidence;
    let assessment = assess(&RoutingFacts {
        task_hints: vec![TaskKind::Edit],
        ..Default::default()
    });
    let mut i = Input {
        specification: &s,
        approval: None,
        recipe: &r,
        current: &s,
        current_provenance: Provenance::CallerDeclared,
        current_observed_at: 110,
        current_expires_at: 190,
        assessment: &assessment,
        now: 150,
        last_observed_time: 140,
    };
    assert_eq!(evaluate(&i), Status::Refused(Reason::RecipeNotReady));
    let mut empty_recipe = recipe();
    empty_recipe.checks.clear();
    i.recipe = &empty_recipe;
    assert_eq!(evaluate(&i), Status::Refused(Reason::MissingObligation));
}

#[test]
fn inconsistent_or_excess_recipe_checks_do_not_gain_readiness() {
    let s = spec(&[]);
    let assessment = assess(&RoutingFacts {
        task_hints: vec![TaskKind::Edit],
        ..Default::default()
    });
    let mut r = recipe();
    r.checks[0].readiness = ValidationReadiness::Blocked;
    for oversized in [false, true] {
        if oversized {
            r = recipe();
            r.checks = vec![r.checks[0].clone(); MAX_RECIPE_CHECKS + 1];
        }
        let i = Input {
            specification: &s,
            approval: None,
            recipe: &r,
            current: &s,
            current_provenance: Provenance::CallerDeclared,
            current_observed_at: 110,
            current_expires_at: 190,
            assessment: &assessment,
            now: 150,
            last_observed_time: 140,
        };
        assert_eq!(evaluate(&i), Status::Refused(Reason::RecipeNotReady));
    }
}

#[test]
fn schema_is_explicit_and_unsupported_versions_refuse_in_every_position() {
    let original = spec(&[]);
    assert_eq!(
        run(&original, |_| {}),
        Status::ConditionallyPolicyAdmissible
    );
    for version in [0, SCHEMA_V1 + 1, u16::MAX] {
        let mut changed = original.clone();
        changed.schema_version = version;
        refused(&changed, Reason::UnsupportedSchema);
        assert_eq!(
            run(&original, |i| i.approval.as_mut().unwrap().specification =
                &changed),
            Status::Refused(Reason::InvalidApprovalEvidence)
        );
        assert_eq!(
            run(&original, |i| i.current = &changed),
            Status::Refused(Reason::InvalidCurrentEvidence)
        );
    }
}

#[test]
fn current_observation_has_an_independent_bounded_lifetime() {
    let s = spec(&[]);
    for (observed, expires) in [
        (100, 150), // expired at boundary while approval remains live
        (151, 200), // future
        (1, 302),   // stale: excessive lifetime even though now is inside
        (100, 100), // empty
        (120, 110), // reversed
        (0, 200),   // missing
        (1, u64::MAX),
    ] {
        assert_eq!(
            run(&s, |i| {
                i.current_observed_at = observed;
                i.current_expires_at = expires;
            }),
            Status::Refused(Reason::InvalidCurrentFreshness)
        );
    }
    assert_eq!(
        run(&s, |i| {
            i.current_observed_at = 150;
            i.current_expires_at = 450;
        }),
        Status::ConditionallyPolicyAdmissible
    );
    assert_eq!(
        run(&s, |i| i.last_observed_time = 151),
        Status::Refused(Reason::InvalidFreshness)
    );
}

#[test]
fn independent_evidence_is_bounded_before_comparison() {
    let original = spec(&[]);
    let too_many = vec![Argument::Word("a"); MAX_ARGS + 1];
    let huge = "a".repeat(1_000_000);
    let huge_args = [Argument::Word(&huge)];
    let mut variants = vec![spec(&too_many), spec(&huge_args)];
    for field in 0..3 {
        let mut changed = original.clone();
        match field {
            0 => changed.executable = &huge,
            1 => changed.cwd = &huge,
            _ => changed.scope = &huge,
        }
        variants.push(changed);
    }
    let huge_path = [Argument::Path(&huge[..MAX_PATH_BYTES + 1])];
    variants.push(spec(&huge_path));
    for changed in &variants {
        assert_eq!(
            run(&original, |i| i.approval.as_mut().unwrap().specification =
                changed),
            Status::Refused(Reason::InvalidApprovalEvidence)
        );
        assert_eq!(
            run(&original, |i| i.current = changed),
            Status::Refused(Reason::InvalidCurrentEvidence)
        );
        // Current is validated even when review would otherwise mismatch.
        let mut mismatch = original.clone();
        mismatch.version = Version::new(2, 0, 0);
        assert_eq!(
            run(&original, |i| {
                i.approval.as_mut().unwrap().specification = &mismatch;
                i.current = changed;
            }),
            Status::Refused(Reason::InvalidCurrentEvidence)
        );
    }
}

#[test]
fn high_risk_cannot_resolve_missing_or_conflicting_task_facts() {
    let s = spec(&[]);
    for hints in [vec![], vec![TaskKind::Edit, TaskKind::Inspect]] {
        let assessment = assess(&RoutingFacts {
            task_hints: hints,
            risk_hint: Some(RiskLevel::High),
            ..Default::default()
        });
        assert_eq!(
            run(&s, |i| i.assessment = &assessment),
            Status::Refused(Reason::UnclearTask)
        );
    }
    let mut assessment = assess(&RoutingFacts {
        task_hints: vec![TaskKind::Edit],
        ..Default::default()
    });
    assessment.ambiguity = Ambiguity::Ambiguous;
    assert_eq!(
        run(&s, |i| i.assessment = &assessment),
        Status::Refused(Reason::UnclearTask)
    );
    assessment.ambiguity = Ambiguity::Clear;
    assessment.task = TaskKind::Unknown;
    assert_eq!(
        run(&s, |i| i.assessment = &assessment),
        Status::Refused(Reason::UnclearTask)
    );
}
