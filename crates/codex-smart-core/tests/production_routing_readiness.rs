//! Offline composition fixtures, deliberately disconnected from the CLI launcher.
use codex_smart_core::adaptive::{
    AdaptiveController, AdaptiveError, AttemptOutcome, ControllerState, ExecutionBudget,
    ValidationOutcome,
};
use codex_smart_core::adaptive_routing::{
    CompatibilityState, ModelCatalog, ModelDescriptor, ModelIdentity, ModelKey, ProviderKey,
    ReasoningCompatibility, ResolutionStatus, resolve_controller,
};
use codex_smart_core::playbook::{Archetype, ProfileClass};
use codex_smart_core::routing::Reasoning;
use codex_smart_core::routing::assessment::{
    RiskLevel, RoutingFacts, SafetyFact, TaskKind, assess,
};
use codex_smart_core::routing::engine::CapabilitySurface;
use codex_smart_core::workflow::{NativeSurface, ResourceCatalog, plan_workflow};

fn controller(
    task: TaskKind,
    archetype: Archetype,
    safety: Vec<SafetyFact>,
    native: &NativeSurface,
) -> Result<AdaptiveController, AdaptiveError> {
    let assessment = assess(&RoutingFacts {
        known_operations: vec![task],
        risk_hint: Some(RiskLevel::Low),
        safety,
        ..Default::default()
    });
    let workflow = plan_workflow(
        &assessment,
        Some(archetype),
        native,
        &CapabilitySurface::default(),
        &ResourceCatalog::default(),
    );
    let validation = workflow
        .validation_recipe(native)
        .ok_or(AdaptiveError::ValidationNotReady)?;
    AdaptiveController::from_workflow(
        &workflow,
        &validation,
        ExecutionBudget::new(2, 1, 0).unwrap(),
    )
}

fn model(key: u16, profile: ProfileClass, availability: CompatibilityState) -> ModelDescriptor {
    ModelDescriptor {
        identity: ModelIdentity {
            provider: ProviderKey(1),
            model: ModelKey(key),
        },
        profile,
        availability,
        reasoning: ReasoningCompatibility::VERIFIED,
    }
}

fn catalog() -> ModelCatalog {
    ModelCatalog::new([
        model(10, ProfileClass::Economy, CompatibilityState::Verified),
        model(20, ProfileClass::Standard, CompatibilityState::Verified),
        model(30, ProfileClass::Strong, CompatibilityState::Verified),
    ])
}

#[test]
fn ready_inspection_composes_all_policy_layers_without_runtime_authority() {
    let state = controller(
        TaskKind::Inspect,
        Archetype::Inspection,
        vec![],
        &NativeSurface::verified_all(),
    )
    .unwrap();
    let target = resolve_controller(&state, &catalog()).target.unwrap();
    assert_eq!(target.profile, ProfileClass::Economy);
    assert_eq!(target.reasoning, Reasoning::Medium);
    assert_eq!(state.attempts_started, 0);
    assert_eq!(state.delegations_used, 0);
    assert!(state.history.is_empty());
}

#[test]
fn unknown_native_or_model_evidence_cannot_become_execution_ready() {
    assert!(
        controller(
            TaskKind::Inspect,
            Archetype::Inspection,
            vec![],
            &NativeSurface::default()
        )
        .is_err()
    );
    let state = controller(
        TaskKind::Inspect,
        Archetype::Inspection,
        vec![],
        &NativeSurface::verified_all(),
    )
    .unwrap();
    let unknown = ModelCatalog::new([model(
        10,
        ProfileClass::Economy,
        CompatibilityState::Unknown,
    )]);
    let resolution = resolve_controller(&state, &unknown);
    assert_eq!(resolution.status, ResolutionStatus::NeedsEvidence);
    assert!(resolution.target.is_none());
}

#[test]
fn security_floor_survives_low_risk_hint_and_missing_strong_mapping() {
    let state = controller(
        TaskKind::Edit,
        Archetype::SecuritySensitiveChange,
        vec![SafetyFact::SecuritySensitive],
        &NativeSurface::verified_all(),
    )
    .unwrap();
    let cheap = ModelCatalog::new([model(
        10,
        ProfileClass::Economy,
        CompatibilityState::Verified,
    )]);
    assert!(resolve_controller(&state, &cheap).target.is_none());
    let target = resolve_controller(&state, &catalog()).target.unwrap();
    assert_eq!(target.profile, ProfileClass::Strong);
    assert_eq!(target.reasoning, Reasoning::High);
}

#[test]
fn validation_failure_re_resolves_and_exhaustion_retains_both_attempts() {
    let mut state = controller(
        TaskKind::Inspect,
        Archetype::Inspection,
        vec![],
        &NativeSurface::verified_all(),
    )
    .unwrap();
    state.start_attempt().unwrap();
    state.observe_attempt(AttemptOutcome::Completed).unwrap();
    assert_eq!(state.state, ControllerState::AwaitingValidation);
    state.observe_validation(ValidationOutcome::Failed).unwrap();
    assert_eq!(state.state, ControllerState::Ready);
    assert_eq!(
        resolve_controller(&state, &catalog())
            .target
            .unwrap()
            .profile,
        ProfileClass::Standard
    );
    state.start_attempt().unwrap();
    assert!(
        state
            .observe_attempt(AttemptOutcome::RuntimeFailure)
            .is_err()
    );
    assert_eq!(state.state, ControllerState::Exhausted);
    assert_eq!(state.attempts_started, 2);
    assert_eq!(state.retries_used, 1);
    assert_eq!(state.history.len(), 2);
    assert_eq!(state.history[0].validation, Some(ValidationOutcome::Failed));
    assert_eq!(
        state.history[1].outcome,
        Some(AttemptOutcome::RuntimeFailure)
    );
    assert!(state.start_attempt().is_err());
}
