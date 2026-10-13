use codex_smart_core::adaptive::{
    AdaptiveController, AdaptiveTrigger, AttemptOutcome, ControllerState, EvidenceResolution,
    ExecutionBudget, ValidationOutcome,
};
use codex_smart_core::adaptive_delegation::{
    AuthorityBoundary, BoundedHandoff, ChildBudget, ChildOutcome, ChildValidation, ContextKind,
    ContextReference, DelegationKind, DelegationLedger, DelegationOrigin, DelegationRequest,
    DelegationSafetyReview, DelegationStatus, EvidenceKey, HandoffDisposition, HandoffEvidence,
    ResourceKey, assess_delegation,
};
use codex_smart_core::adaptive_routing::{
    CompatibilityState, ModelCatalog, ModelDescriptor, ModelIdentity, ModelKey, ProviderKey,
    ReasoningCompatibility, ResolutionStatus, resolve_model,
};
use codex_smart_core::playbook::{Archetype, ProfileClass, ValidationObligation};
use codex_smart_core::routing::assessment::{RoutingFacts, SafetyFact, TaskKind, assess};
use codex_smart_core::routing::engine::CapabilitySurface;
use codex_smart_core::workflow::{NativeSurface, ResourceCatalog, plan_workflow};
use std::collections::BTreeSet;

fn model(model: u16, profile: ProfileClass) -> ModelDescriptor {
    ModelDescriptor {
        identity: ModelIdentity {
            provider: ProviderKey(11),
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

fn context() -> Vec<ContextReference> {
    vec![ContextReference {
        key: EvidenceKey(1),
        kind: ContextKind::RelevantFile,
        bytes: 256,
        digest: [3; 32],
    }]
}

fn read_only_request() -> DelegationRequest {
    DelegationRequest {
        origin: DelegationOrigin::Parent,
        kind: DelegationKind::ReadOnlyEvidence,
        context: context(),
        authority: AuthorityBoundary::read_only([ResourceKey(1)]),
        validation: BTreeSet::new(),
        parent_revalidation_required: true,
        safety: DelegationSafetyReview::verified_clear(),
        budget: ChildBudget::new(30, 100, 4096).unwrap(),
    }
}

fn mechanical_docs_request() -> DelegationRequest {
    DelegationRequest {
        origin: DelegationOrigin::Parent,
        kind: DelegationKind::MechanicalWorkspaceChange,
        context: context(),
        authority: AuthorityBoundary {
            readable: [ResourceKey(1), ResourceKey(2)].into_iter().collect(),
            writable: [ResourceKey(2)].into_iter().collect(),
            may_run_declared_validation: true,
        },
        validation: [ValidationObligation::DocumentationCheck]
            .into_iter()
            .collect(),
        parent_revalidation_required: true,
        safety: DelegationSafetyReview::verified_clear(),
        budget: ChildBudget::new(60, 200, 8192).unwrap(),
    }
}

#[test]
fn evidence_child_is_advisory_then_parent_resolves_and_reroutes() {
    let catalog = ModelCatalog::new([
        model(10, ProfileClass::Economy),
        model(20, ProfileClass::Standard),
        model(30, ProfileClass::Strong),
    ]);
    let mut parent = controller(TaskKind::Inspect, None, vec![]);
    parent.start_attempt().unwrap();
    parent.observe_attempt(AttemptOutcome::Ambiguous).unwrap();
    assert_eq!(
        parent.state,
        ControllerState::NeedsEvidence(AdaptiveTrigger::Ambiguity)
    );

    let mut ledger = DelegationLedger::new(&parent).unwrap();
    let authorization = ledger.authorize(&mut parent, read_only_request()).unwrap();
    let child_target = resolve_model(authorization.profile, authorization.reasoning, &catalog);
    assert_eq!(child_target.status, ResolutionStatus::Resolved);
    assert_eq!(child_target.target.unwrap().identity.model, ModelKey(10));

    let disposition = ledger
        .record_handoff(
            &parent,
            BoundedHandoff {
                ordinal: authorization.ordinal,
                outcome: ChildOutcome::Completed,
                wall_seconds_used: 4,
                cost_units_used: 15,
                output_bytes: 128,
                evidence: vec![HandoffEvidence {
                    key: EvidenceKey(9),
                    bytes: 64,
                    digest: [8; 32],
                }],
                changed_resources: BTreeSet::new(),
                child_validation: ChildValidation::NotRun,
            },
        )
        .unwrap();
    assert_eq!(disposition, HandoffDisposition::RequiresParentReview);
    assert_eq!(
        parent.state,
        ControllerState::NeedsEvidence(AdaptiveTrigger::Ambiguity)
    );

    parent
        .resolve_evidence(EvidenceResolution::Resolved)
        .unwrap();
    assert_eq!(parent.state, ControllerState::Ready);
    assert_eq!(parent.current_profile, ProfileClass::Standard);
}

#[test]
fn mechanical_child_has_standard_floor_and_cannot_complete_parent() {
    let catalog = ModelCatalog::new([
        model(10, ProfileClass::Economy),
        model(20, ProfileClass::Standard),
    ]);
    let mut parent = controller(TaskKind::Edit, Some(Archetype::DocumentationChange), vec![]);
    assert_eq!(parent.current_profile, ProfileClass::Economy);

    let request = mechanical_docs_request();
    let plan = assess_delegation(&parent, &request);
    assert_eq!(plan.status, DelegationStatus::Ready);
    assert_eq!(plan.profile, Some(ProfileClass::Standard));

    let mut ledger = DelegationLedger::new(&parent).unwrap();
    let authorization = ledger.authorize(&mut parent, request).unwrap();
    let child_target = resolve_model(authorization.profile, authorization.reasoning, &catalog);
    assert_eq!(child_target.status, ResolutionStatus::Resolved);
    assert_eq!(child_target.target.unwrap().identity.model, ModelKey(20));

    let disposition = ledger
        .record_handoff(
            &parent,
            BoundedHandoff {
                ordinal: authorization.ordinal,
                outcome: ChildOutcome::Completed,
                wall_seconds_used: 8,
                cost_units_used: 30,
                output_bytes: 512,
                evidence: vec![],
                changed_resources: [ResourceKey(2)].into_iter().collect(),
                child_validation: ChildValidation::Passed,
            },
        )
        .unwrap();
    assert_eq!(disposition, HandoffDisposition::RequiresParentReview);
    assert_eq!(parent.state, ControllerState::Ready);
    assert_eq!(parent.current_profile, ProfileClass::Economy);

    parent.start_attempt().unwrap();
    parent.observe_attempt(AttemptOutcome::Completed).unwrap();
    parent
        .observe_validation(ValidationOutcome::Passed)
        .unwrap();
    assert_eq!(parent.state, ControllerState::Completed);
}

#[test]
fn high_risk_parent_never_reaches_child_model_resolution() {
    let parent = controller(TaskKind::Edit, None, vec![SafetyFact::SecuritySensitive]);
    let plan = assess_delegation(&parent, &read_only_request());
    assert_eq!(plan.status, DelegationStatus::Blocked);
    assert!(plan.profile.is_none());
    assert!(plan.reasoning.is_none());
}

#[test]
fn one_child_budget_prevents_delegation_fanout() {
    let mut parent = controller(TaskKind::Inspect, None, vec![]);
    let mut ledger = DelegationLedger::new(&parent).unwrap();
    ledger.authorize(&mut parent, read_only_request()).unwrap();
    assert_eq!(parent.delegations_used, 1);
    assert_eq!(ledger.remaining(&parent).unwrap(), 0);
    assert_eq!(
        assess_delegation(&parent, &read_only_request()).status,
        DelegationStatus::Blocked
    );
}
