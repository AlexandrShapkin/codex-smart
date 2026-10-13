use codex_smart_core::adaptive::{
    AdaptiveController, AdaptiveError, AttemptOutcome, BlockReason, ControllerState,
    EvidenceResolution, ExecutionBudget, ValidationOutcome,
};
use codex_smart_core::playbook::{Archetype, ProfileClass};
use codex_smart_core::routing::Reasoning;
use codex_smart_core::routing::assessment::{RoutingFacts, SafetyFact, TaskKind, assess};
use codex_smart_core::routing::engine::CapabilitySurface;
use codex_smart_core::workflow::{NativeSurface, ResourceCatalog, plan_workflow};

fn controller(
    task: TaskKind,
    archetype: Option<Archetype>,
    safety: Vec<SafetyFact>,
    budget: ExecutionBudget,
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
    AdaptiveController::from_workflow(&workflow, &validation, budget).unwrap()
}

#[test]
fn completion_requires_independent_validation() {
    let mut controller = controller(
        TaskKind::Edit,
        Some(Archetype::FeatureImplementation),
        vec![],
        ExecutionBudget::new(2, 1, 0).unwrap(),
    );

    controller.start_attempt().unwrap();
    controller
        .observe_attempt(AttemptOutcome::Completed)
        .unwrap();
    assert_eq!(controller.state, ControllerState::AwaitingValidation);
    assert_eq!(controller.start_attempt(), Err(AdaptiveError::InvalidState));

    controller
        .observe_validation(ValidationOutcome::Passed)
        .unwrap();
    assert_eq!(controller.state, ControllerState::Completed);
    assert_eq!(controller.history.len(), 1);
    assert_eq!(
        controller.history[0].validation,
        Some(ValidationOutcome::Passed)
    );
}

#[test]
fn failed_attempts_are_preserved_across_bounded_escalation() {
    let mut controller = controller(
        TaskKind::Inspect,
        None,
        vec![],
        ExecutionBudget::new(3, 2, 1).unwrap(),
    );

    let first = controller.start_attempt().unwrap();
    assert_eq!(first.profile, ProfileClass::Economy);
    controller.observe_attempt(AttemptOutcome::Timeout).unwrap();

    let second = controller.start_attempt().unwrap();
    assert_eq!(second.profile, ProfileClass::Standard);
    controller
        .observe_attempt(AttemptOutcome::RuntimeFailure)
        .unwrap();

    let third = controller.start_attempt().unwrap();
    assert_eq!(third.profile, ProfileClass::Strong);
    assert_eq!(third.reasoning, Reasoning::High);
    controller
        .observe_attempt(AttemptOutcome::Completed)
        .unwrap();
    controller
        .observe_validation(ValidationOutcome::Passed)
        .unwrap();

    assert_eq!(controller.state, ControllerState::Completed);
    assert_eq!(controller.attempts_started, 3);
    assert_eq!(controller.retries_used, 2);
    assert_eq!(controller.history.len(), 3);
    assert_eq!(controller.history[0].outcome, Some(AttemptOutcome::Timeout));
    assert_eq!(
        controller.history[1].outcome,
        Some(AttemptOutcome::RuntimeFailure)
    );
    assert_eq!(
        controller.history[2].validation,
        Some(ValidationOutcome::Passed)
    );
    assert_eq!(controller.remaining_attempts(), 0);
    assert_eq!(controller.remaining_retries(), 0);
    assert_eq!(controller.remaining_delegations(), 1);
    assert_eq!(controller.delegations_used, 0);
}

#[test]
fn high_risk_never_uses_a_cheaper_initial_profile() {
    let mut controller = controller(
        TaskKind::Edit,
        None,
        vec![SafetyFact::SecuritySensitive],
        ExecutionBudget::new(2, 1, 0).unwrap(),
    );

    let first = controller.start_attempt().unwrap();
    assert_eq!(first.profile, ProfileClass::Strong);
    assert_eq!(first.reasoning, Reasoning::High);
    controller
        .observe_attempt(AttemptOutcome::RuntimeFailure)
        .unwrap();

    let second = controller.start_attempt().unwrap();
    assert_eq!(second.profile, ProfileClass::Strong);
    assert_eq!(second.reasoning, Reasoning::High);
}

#[test]
fn unresolved_evidence_never_becomes_execution_ready_by_assumption() {
    let mut controller = controller(
        TaskKind::Inspect,
        None,
        vec![],
        ExecutionBudget::new(2, 1, 0).unwrap(),
    );

    controller.start_attempt().unwrap();
    controller
        .observe_attempt(AttemptOutcome::MissingRequiredContext)
        .unwrap();
    assert!(matches!(
        controller.state,
        ControllerState::NeedsEvidence(_)
    ));

    controller
        .resolve_evidence(EvidenceResolution::StillUnknown)
        .unwrap();
    assert!(matches!(
        controller.state,
        ControllerState::NeedsEvidence(_)
    ));

    controller
        .resolve_evidence(EvidenceResolution::Unavailable)
        .unwrap();
    assert_eq!(
        controller.state,
        ControllerState::Blocked(BlockReason::EvidenceUnavailable)
    );
    assert_eq!(controller.retries_used, 0);
}

#[test]
fn validation_failure_consumes_retry_budget_and_cannot_be_hidden() {
    let mut controller = controller(
        TaskKind::Edit,
        Some(Archetype::FeatureImplementation),
        vec![],
        ExecutionBudget::new(2, 1, 0).unwrap(),
    );

    controller.start_attempt().unwrap();
    controller
        .observe_attempt(AttemptOutcome::Completed)
        .unwrap();
    controller
        .observe_validation(ValidationOutcome::Failed)
        .unwrap();
    assert_eq!(controller.retries_used, 1);
    assert_eq!(controller.current_profile, ProfileClass::Strong);

    controller.start_attempt().unwrap();
    controller
        .observe_attempt(AttemptOutcome::Completed)
        .unwrap();
    assert_eq!(
        controller.observe_validation(ValidationOutcome::Failed),
        Err(AdaptiveError::AttemptBudgetExhausted)
    );
    assert_eq!(controller.state, ControllerState::Exhausted);
    assert_eq!(
        controller.history[0].validation,
        Some(ValidationOutcome::Failed)
    );
    assert_eq!(
        controller.history[1].validation,
        Some(ValidationOutcome::Failed)
    );
}
