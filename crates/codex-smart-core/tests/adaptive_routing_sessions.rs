use codex_smart_core::adaptive::{
    AdaptiveController, AttemptOutcome, ExecutionBudget, ValidationOutcome,
};
use codex_smart_core::adaptive_routing::{
    CompatibilityState, ModelCatalog, ModelDescriptor, ModelIdentity, ModelKey, ProviderKey,
    ReasoningCompatibility, ResolutionReason, ResolutionStatus, resolve_controller,
};
use codex_smart_core::playbook::{Archetype, ProfileClass};
use codex_smart_core::routing::Reasoning;
use codex_smart_core::routing::assessment::{RoutingFacts, SafetyFact, TaskKind, assess};
use codex_smart_core::routing::engine::CapabilitySurface;
use codex_smart_core::workflow::{NativeSurface, ResourceCatalog, plan_workflow};

fn model(model: u16, profile: ProfileClass) -> ModelDescriptor {
    ModelDescriptor {
        identity: ModelIdentity {
            provider: ProviderKey(7),
            model: ModelKey(model),
        },
        profile,
        availability: CompatibilityState::Verified,
        reasoning: ReasoningCompatibility::VERIFIED,
    }
}

fn controller(
    task: TaskKind,
    archetype: Option<Archetype>,
    safety: Vec<SafetyFact>,
) -> AdaptiveController {
    let assessment = assess(&RoutingFacts {
        known_operations: vec![task],
        safety,
        ..Default::default()
    });
    let native = NativeSurface::verified_all();
    let workflow = plan_workflow(
        &assessment,
        archetype,
        &native,
        &CapabilitySurface::default(),
        &ResourceCatalog::default(),
    );
    let validation = workflow.validation_recipe(&native).unwrap();
    AdaptiveController::from_workflow(
        &workflow,
        &validation,
        ExecutionBudget::new(3, 2, 1).unwrap(),
    )
    .unwrap()
}

#[test]
fn one_catalog_tracks_controller_escalation_without_embedding_model_names() {
    let catalog = ModelCatalog::new([
        model(10, ProfileClass::Economy),
        model(20, ProfileClass::Standard),
        model(30, ProfileClass::Strong),
    ]);
    let mut adaptive = controller(TaskKind::Inspect, None, vec![]);

    let first = resolve_controller(&adaptive, &catalog).target.unwrap();
    assert_eq!(first.identity.model, ModelKey(10));
    assert_eq!(first.reasoning, Reasoning::Medium);

    adaptive.start_attempt().unwrap();
    adaptive
        .observe_attempt(AttemptOutcome::RuntimeFailure)
        .unwrap();
    let second = resolve_controller(&adaptive, &catalog).target.unwrap();
    assert_eq!(second.identity.model, ModelKey(20));
    assert_eq!(second.reasoning, Reasoning::Medium);

    adaptive.start_attempt().unwrap();
    adaptive.observe_attempt(AttemptOutcome::Completed).unwrap();
    adaptive
        .observe_validation(ValidationOutcome::Failed)
        .unwrap();
    let third = resolve_controller(&adaptive, &catalog).target.unwrap();
    assert_eq!(third.identity.model, ModelKey(30));
    assert_eq!(third.reasoning, Reasoning::High);
}

#[test]
fn security_floor_cannot_be_satisfied_by_economy_or_standard_only_catalog() {
    let adaptive = controller(TaskKind::Edit, None, vec![SafetyFact::SecuritySensitive]);
    let resolution = resolve_controller(
        &adaptive,
        &ModelCatalog::new([
            model(10, ProfileClass::Economy),
            model(20, ProfileClass::Standard),
        ]),
    );
    assert_eq!(resolution.status, ResolutionStatus::Unavailable);
    assert!(resolution.target.is_none());
    assert!(
        resolution
            .reasons
            .contains(&ResolutionReason::NoCompatibleCandidate)
    );
}

#[test]
fn unknown_model_support_never_counts_as_verified_compatibility() {
    let adaptive = controller(
        TaskKind::Edit,
        Some(Archetype::FeatureImplementation),
        vec![],
    );
    let unknown = ModelDescriptor {
        availability: CompatibilityState::Unknown,
        ..model(20, ProfileClass::Standard)
    };
    let resolution = resolve_controller(&adaptive, &ModelCatalog::new([unknown]));
    assert_eq!(resolution.status, ResolutionStatus::NeedsEvidence);
    assert!(resolution.target.is_none());
}

#[test]
fn verified_stronger_fallback_preserves_quality_when_exact_mapping_is_unknown() {
    let adaptive = controller(
        TaskKind::Edit,
        Some(Archetype::FeatureImplementation),
        vec![],
    );
    let unknown = ModelDescriptor {
        availability: CompatibilityState::Unknown,
        ..model(20, ProfileClass::Standard)
    };
    let strong = model(30, ProfileClass::Strong);
    let resolution = resolve_controller(&adaptive, &ModelCatalog::new([unknown, strong]));
    assert_eq!(resolution.status, ResolutionStatus::Resolved);
    assert_eq!(resolution.target.unwrap().identity, strong.identity);
    assert!(
        resolution
            .reasons
            .contains(&ResolutionReason::HigherProfileFallback)
    );
}
