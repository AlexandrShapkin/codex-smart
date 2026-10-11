//! In-memory #9 -> #10 -> #11 -> #12 sessions. No discovered tools are executed.
use codex_smart_core::routing::assessment::{
    Ambiguity, RiskLevel, RoutingFacts, SafetyFact, TaskKind, assess,
};
use codex_smart_core::routing::engine::{
    Backend, CapabilityNeed, CapabilityState, CapabilitySurface, decide,
};
use codex_smart_core::routing::fallback::{
    EvidenceState, Obligation, PlanEvidence, PlanReason, ReasoningApplication,
    RepositoryRequirement, RouteMode, RoutingPlan, plan_fallback,
};
use codex_smart_core::routing::reasoning::{ReasoningCompatibility, Support, select_reasoning};

fn evidence() -> PlanEvidence {
    PlanEvidence {
        native_fallback: EvidenceState::Satisfied,
        external_reference: EvidenceState::Unknown,
        repository_requirement: RepositoryRequirement::CurrentRemoteState,
        remote_state: EvidenceState::Unknown,
        verification: vec![],
        context_sufficient: true,
        reasoning_application: ReasoningApplication::RequiredSyntheticOverride,
    }
}
fn session(
    task: TaskKind,
    safety: Vec<SafetyFact>,
    needs: &[CapabilityNeed],
    state: CapabilityState,
    support: Support,
    evidence: &PlanEvidence,
) -> RoutingPlan {
    let assessment = assess(&RoutingFacts {
        task_hints: vec![task],
        safety,
        ..Default::default()
    });
    let surface = CapabilitySurface::new(
        [
            Backend::CodeGraph,
            Backend::Serena,
            Backend::Context7,
            Backend::GitHub,
        ]
        .map(|backend| (backend, state)),
    );
    let router = decide(&assessment, needs, &surface);
    let reasoning = select_reasoning(
        &router.assessment,
        None,
        ReasoningCompatibility {
            cli: Support::Supported,
            medium: support,
            high: support,
        },
    );
    plan_fallback(&router, &reasoning, evidence)
}

#[test]
fn degraded_session_table() {
    let cases = [
        (
            TaskKind::Edit,
            None,
            CapabilityState::Verified,
            Support::Supported,
            RouteMode::Proceed,
            Obligation::RelevantTests,
        ),
        (
            TaskKind::Edit,
            Some(CapabilityNeed::StructuralImpact),
            CapabilityState::Verified,
            Support::Supported,
            RouteMode::Proceed,
            Obligation::ImpactAnalysis,
        ),
        (
            TaskKind::Edit,
            Some(CapabilityNeed::StructuralImpact),
            CapabilityState::Unknown,
            Support::Supported,
            RouteMode::ProceedWithFallback,
            Obligation::ImpactAnalysis,
        ),
        (
            TaskKind::Edit,
            Some(CapabilityNeed::StructuralImpact),
            CapabilityState::Unavailable,
            Support::Supported,
            RouteMode::ProceedWithFallback,
            Obligation::ImpactAnalysis,
        ),
        (
            TaskKind::Edit,
            Some(CapabilityNeed::StructuralImpact),
            CapabilityState::Blocked,
            Support::Supported,
            RouteMode::ProceedWithFallback,
            Obligation::ImpactAnalysis,
        ),
        (
            TaskKind::Refactor,
            Some(CapabilityNeed::SymbolNavigation),
            CapabilityState::Unavailable,
            Support::Supported,
            RouteMode::ProceedWithFallback,
            Obligation::SymbolReferences,
        ),
        (
            TaskKind::Edit,
            Some(CapabilityNeed::ExternalApiReference),
            CapabilityState::Unknown,
            Support::Supported,
            RouteMode::NeedsEvidence,
            Obligation::ExternalReferenceValidation,
        ),
        (
            TaskKind::Edit,
            Some(CapabilityNeed::RemoteRepository),
            CapabilityState::Unavailable,
            Support::Supported,
            RouteMode::NeedsEvidence,
            Obligation::RemoteStateValidation,
        ),
        (
            TaskKind::Unknown,
            Some(CapabilityNeed::StructuralImpact),
            CapabilityState::Verified,
            Support::Supported,
            RouteMode::NeedsEvidence,
            Obligation::ImpactAnalysis,
        ),
        (
            TaskKind::Edit,
            None,
            CapabilityState::Unknown,
            Support::Unknown,
            RouteMode::NeedsEvidence,
            Obligation::ReasoningCompatibilityValidation,
        ),
        (
            TaskKind::Edit,
            None,
            CapabilityState::Unknown,
            Support::Unsupported,
            RouteMode::Blocked,
            Obligation::ReasoningCompatibilityValidation,
        ),
    ];
    for (task, need, state, support, mode, obligation) in cases {
        let needs: Vec<_> = need.into_iter().collect();
        let plan = session(task, vec![], &needs, state, support, &evidence());
        assert_eq!(plan.mode, mode, "{task:?}/{need:?}/{state:?}/{support:?}");
        assert!(plan.obligations.contains(&obligation));
        assert!(plan.obligations.contains(&Obligation::RelevantTests));
        assert!(
            plan.obligations
                .contains(&Obligation::BuildOrStaticValidation)
        );
        assert_eq!(
            plan.render(),
            session(task, vec![], &needs, state, support, &evidence()).render()
        );
        if let Some(need) = need {
            let backend = match need {
                CapabilityNeed::StructuralImpact => Backend::CodeGraph,
                CapabilityNeed::SymbolNavigation => Backend::Serena,
                CapabilityNeed::ExternalApiReference => Backend::Context7,
                CapabilityNeed::RemoteRepository => Backend::GitHub,
            };
            let reason = match state {
                CapabilityState::Verified if task == TaskKind::Unknown => codex_smart_core::routing::engine::DecisionReason::CapabilityDeferredForAmbiguity(backend),
                CapabilityState::Verified => codex_smart_core::routing::engine::DecisionReason::VerifiedCapabilitySelected(backend),
                CapabilityState::Unknown => codex_smart_core::routing::engine::DecisionReason::CapabilityUnknown(backend),
                CapabilityState::Unavailable => codex_smart_core::routing::engine::DecisionReason::CapabilityUnavailable(backend),
                CapabilityState::Blocked => codex_smart_core::routing::engine::DecisionReason::CapabilityBlocked(backend),
            };
            assert!(plan.reasons.contains(&PlanReason::Router(reason)));
        }
    }
}

#[test]
fn authoritative_external_remote_and_native_prerequisites() {
    for need in [
        CapabilityNeed::ExternalApiReference,
        CapabilityNeed::RemoteRepository,
    ] {
        for state in [
            EvidenceState::Satisfied,
            EvidenceState::Unknown,
            EvidenceState::Unavailable,
        ] {
            let facts = PlanEvidence {
                external_reference: state,
                remote_state: state,
                ..evidence()
            };
            let expected = match state {
                EvidenceState::Satisfied => RouteMode::ProceedWithFallback,
                EvidenceState::Unknown => RouteMode::NeedsEvidence,
                EvidenceState::Unavailable => RouteMode::Blocked,
            };
            let plan = session(
                TaskKind::Inspect,
                vec![],
                &[need],
                CapabilityState::Unknown,
                Support::Supported,
                &facts,
            );
            assert_eq!(plan.mode, expected);
        }
        // Ready augmentation alone cannot certify authoritative prerequisite evidence.
        assert_eq!(
            session(
                TaskKind::Inspect,
                vec![],
                &[need],
                CapabilityState::Verified,
                Support::Supported,
                &evidence()
            )
            .mode,
            RouteMode::NeedsEvidence
        );
    }
    let local = PlanEvidence {
        repository_requirement: RepositoryRequirement::LocalHistory,
        ..evidence()
    };
    let plan = session(
        TaskKind::Inspect,
        vec![],
        &[CapabilityNeed::RemoteRepository],
        CapabilityState::Unavailable,
        Support::Supported,
        &local,
    );
    assert_eq!(plan.mode, RouteMode::ProceedWithFallback);
    assert!(
        plan.obligations
            .contains(&Obligation::LocalRepositoryEvidence)
    );
    assert!(
        !plan
            .obligations
            .contains(&Obligation::RemoteStateValidation)
    );
    for (native_fallback, expected) in [
        (EvidenceState::Unknown, RouteMode::NeedsEvidence),
        (EvidenceState::Unavailable, RouteMode::Blocked),
    ] {
        let input = PlanEvidence {
            native_fallback,
            ..evidence()
        };
        assert_eq!(
            session(
                TaskKind::Edit,
                vec![],
                &[CapabilityNeed::StructuralImpact],
                CapabilityState::Blocked,
                Support::Supported,
                &input
            )
            .mode,
            expected
        );
    }
}

#[test]
fn degradation_risk_ambiguity_and_added_needs_never_remove_obligations() {
    let needs = [
        CapabilityNeed::StructuralImpact,
        CapabilityNeed::SymbolNavigation,
    ];
    let mut previous = session(
        TaskKind::Edit,
        vec![],
        &needs,
        CapabilityState::Verified,
        Support::Supported,
        &evidence(),
    );
    for state in [
        CapabilityState::Unknown,
        CapabilityState::Unavailable,
        CapabilityState::Blocked,
    ] {
        let next = session(
            TaskKind::Edit,
            vec![],
            &needs,
            state,
            Support::Supported,
            &evidence(),
        );
        assert!(previous.obligations.is_subset(&next.obligations));
        assert!(previous.mode <= next.mode);
        previous = next;
    }
    let hazards = [
        SafetyFact::SecuritySensitive,
        SafetyFact::MigrationSensitive,
        SafetyFact::ConcurrencySensitive,
    ];
    for state in [
        CapabilityState::Verified,
        CapabilityState::Unknown,
        CapabilityState::Unavailable,
        CapabilityState::Blocked,
    ] {
        let low = session(
            TaskKind::Edit,
            vec![],
            &needs,
            state,
            Support::Supported,
            &evidence(),
        );
        for (hazard, obligation) in hazards.into_iter().zip([
            Obligation::SecurityReview,
            Obligation::MigrationRollbackValidation,
            Obligation::ConcurrencyReview,
        ]) {
            let high = session(
                TaskKind::Edit,
                vec![hazard],
                &needs,
                state,
                Support::Supported,
                &evidence(),
            );
            assert!(low.obligations.is_subset(&high.obligations));
            assert!(
                high.obligations
                    .contains(&Obligation::AdditionalVerification)
            );
            assert!(high.obligations.contains(&obligation));
        }
    }
    let mut assessment = assess(&RoutingFacts {
        task_hints: vec![TaskKind::Refactor],
        ..Default::default()
    });
    for risk in [RiskLevel::Low, RiskLevel::Medium, RiskLevel::High] {
        assessment.risk = risk;
        let surface = CapabilitySurface::new([(Backend::CodeGraph, CapabilityState::Verified)]);
        let router = decide(&assessment, &needs, &surface);
        let compatibility = ReasoningCompatibility {
            cli: Support::Supported,
            medium: Support::Supported,
            high: Support::Supported,
        };
        let clear = plan_fallback(
            &router,
            &select_reasoning(&router.assessment, None, compatibility),
            &evidence(),
        );
        let mut ambiguous_assessment = assessment.clone();
        ambiguous_assessment.ambiguity = Ambiguity::Ambiguous;
        ambiguous_assessment.task = TaskKind::Unknown;
        let router = decide(&ambiguous_assessment, &needs, &surface);
        let ambiguous = plan_fallback(
            &router,
            &select_reasoning(&router.assessment, None, compatibility),
            &evidence(),
        );
        assert!(clear.mode <= ambiguous.mode);
        assert!(clear.obligations.is_subset(&ambiguous.obligations));
    }
    let mut previous_risk_plan = None::<RoutingPlan>;
    for risk in [RiskLevel::Low, RiskLevel::Medium, RiskLevel::High] {
        assessment.risk = risk;
        let router = decide(&assessment, &needs, &CapabilitySurface::default());
        let compatibility = ReasoningCompatibility {
            cli: Support::Supported,
            medium: Support::Supported,
            high: Support::Supported,
        };
        let plan = plan_fallback(
            &router,
            &select_reasoning(&router.assessment, None, compatibility),
            &evidence(),
        );
        if let Some(previous) = previous_risk_plan {
            assert!(previous.obligations.is_subset(&plan.obligations));
        }
        previous_risk_plan = Some(plan);
    }
    for count in 0..=needs.len() {
        let before = session(
            TaskKind::Edit,
            vec![],
            &needs[..count],
            CapabilityState::Unknown,
            Support::Supported,
            &evidence(),
        );
        let after = session(
            TaskKind::Edit,
            vec![],
            &needs,
            CapabilityState::Unknown,
            Support::Supported,
            &evidence(),
        );
        assert!(before.obligations.is_subset(&after.obligations));
    }
}

#[test]
fn context_verification_and_user_owned_reasoning_never_weaken_work() {
    let baseline = session(
        TaskKind::Edit,
        vec![],
        &[CapabilityNeed::StructuralImpact],
        CapabilityState::Unknown,
        Support::Supported,
        &evidence(),
    );
    for (state, mode) in [
        (EvidenceState::Satisfied, RouteMode::ProceedWithFallback),
        (EvidenceState::Unknown, RouteMode::NeedsEvidence),
        (EvidenceState::Unavailable, RouteMode::Blocked),
    ] {
        let input = PlanEvidence {
            verification: vec![(Obligation::RelevantTests, state)],
            ..evidence()
        };
        let plan = session(
            TaskKind::Edit,
            vec![],
            &[CapabilityNeed::StructuralImpact],
            CapabilityState::Unknown,
            Support::Supported,
            &input,
        );
        assert_eq!(plan.mode, mode);
        assert!(baseline.obligations.is_subset(&plan.obligations));
    }
    let input = PlanEvidence {
        context_sufficient: false,
        ..evidence()
    };
    let plan = session(
        TaskKind::Edit,
        vec![],
        &[CapabilityNeed::StructuralImpact],
        CapabilityState::Unknown,
        Support::Supported,
        &input,
    );
    assert_eq!(plan.mode, RouteMode::NeedsEvidence);
    assert_eq!(plan.obligations, baseline.obligations);
    for (status, expected) in [
        (Support::Supported, RouteMode::Proceed),
        (Support::Unknown, RouteMode::NeedsEvidence),
        (Support::Unsupported, RouteMode::Blocked),
    ] {
        let input = PlanEvidence {
            reasoning_application: ReasoningApplication::UserOwned(status),
            ..evidence()
        };
        // Unsupported automatic candidate cannot override a supported user effort.
        let plan = session(
            TaskKind::Edit,
            vec![],
            &[],
            CapabilityState::Unknown,
            Support::Unsupported,
            &input,
        );
        assert_eq!(plan.reasoning_status, status);
        assert_eq!(plan.mode, expected);
    }
    let input = PlanEvidence {
        reasoning_application: ReasoningApplication::Passthrough,
        ..evidence()
    };
    assert_eq!(
        session(
            TaskKind::Edit,
            vec![],
            &[],
            CapabilityState::Unknown,
            Support::Unknown,
            &input
        )
        .mode,
        RouteMode::Proceed
    );
}

#[test]
fn ordering_duplicates_size_and_explanation_are_stable() {
    let needs = [
        CapabilityNeed::StructuralImpact,
        CapabilityNeed::SymbolNavigation,
    ];
    let input = PlanEvidence {
        verification: vec![
            (Obligation::RelevantTests, EvidenceState::Unknown),
            (Obligation::ImpactAnalysis, EvidenceState::Unavailable),
        ],
        ..evidence()
    };
    let expected = session(
        TaskKind::Edit,
        vec![],
        &needs,
        CapabilityState::Unknown,
        Support::Supported,
        &input,
    );
    let mut reordered = input.clone();
    reordered.verification.reverse();
    reordered.verification.extend(input.verification.clone());
    let reversed_needs = [needs[1], needs[0], needs[1]];
    for repository_bytes in [0_u64, 1, u64::MAX] {
        let external = (repository_bytes, &reordered);
        let actual = session(
            TaskKind::Edit,
            vec![],
            &reversed_needs,
            CapabilityState::Unknown,
            Support::Supported,
            external.1,
        );
        assert_eq!(actual, expected);
        assert_eq!(actual.render(), expected.render());
    }
    let ordinary = session(
        TaskKind::Edit,
        vec![],
        &[],
        CapabilityState::Verified,
        Support::Supported,
        &evidence(),
    );
    assert_eq!(
        ordinary.render(),
        "Routing plan (no execution)\nMode: Proceed\nNative baseline: shell/git/search/build/test (subject to host availability)\nNative fallback: false\nRequired obligations: {RelevantTests, BuildOrStaticValidation, ReasoningCompatibilityValidation}\nReasons: {Router(NativeBaseline), Router(NoExternalNeed), RequiredVerificationPreserved}\nEvidence escalation required: false\nReasoning compatibility: Supported\n"
    );
}

#[test]
fn offline_wrapper_never_becomes_rescue_and_reasoning_is_not_reselected() {
    use codex_smart_core::capability::Capability;
    use codex_smart_core::tool_lock::{ArtifactEvidence, CapabilityEvidence};
    let assessment = assess(&RoutingFacts {
        task_hints: vec![TaskKind::Refactor],
        ..Default::default()
    });
    let surface = CapabilitySurface::from_offline([
        (
            Capability::CodeGraph,
            CapabilityEvidence::assess(Capability::CodeGraph, true, None, ArtifactEvidence::Match),
        ),
        (
            Capability::CodeGraphWrapper,
            CapabilityEvidence::assess(
                Capability::CodeGraphWrapper,
                true,
                None,
                ArtifactEvidence::Match,
            ),
        ),
    ]);
    let router = decide(&assessment, &[CapabilityNeed::StructuralImpact], &surface);
    assert!(router.augmentations.is_empty());
    let reasoning = select_reasoning(&router.assessment, None, ReasoningCompatibility::default());
    let before = reasoning.clone();
    let input = PlanEvidence {
        reasoning_application: ReasoningApplication::Passthrough,
        ..evidence()
    };
    let plan = plan_fallback(&router, &reasoning, &input);
    assert_eq!(plan.mode, RouteMode::ProceedWithFallback);
    assert!(plan.obligations.contains(&Obligation::ImpactAnalysis));
    assert!(plan.obligations.contains(&Obligation::RelevantTests));
    assert_eq!(reasoning, before);
    assert!(
        plan.reasons
            .contains(&PlanReason::ReasoningCompatibilityUnknown)
    );
    assert!(
        !plan
            .render()
            .contains("VerifiedCapabilitySelected(CodeGraphWrapper)")
    );
    let mut malformed = router;
    malformed.reasons.insert(
        codex_smart_core::routing::engine::DecisionReason::VerifiedCapabilitySelected(
            Backend::CodeGraphWrapper,
        ),
    );
    assert_eq!(
        plan_fallback(&malformed, &reasoning, &input).mode,
        RouteMode::Blocked
    );
}
