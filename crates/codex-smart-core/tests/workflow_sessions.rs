use codex_smart_core::playbook::{Archetype, NativeCapability};
use codex_smart_core::routing::assessment::{
    RiskLevel, RoutingFacts, SafetyFact, TaskKind, assess,
};
use codex_smart_core::routing::engine::{
    Backend, CapabilityNeed, CapabilityState, CapabilitySurface,
};
use codex_smart_core::version::Version;
use codex_smart_core::workflow::{
    InvalidationTrigger, NativeState, NativeSurface, PlanStatus, REQUIRED_INVALIDATION_TRIGGERS,
    ResourceCatalog, ResourceCleanup, ResourceDescriptor, ResourceDisposition, ResourceIdentity,
    ResourceOwner, ResourcePrivacy, ResourceScope, ResourceValidity, WorkflowPlanReason,
    plan_workflow,
};

fn native_ready() -> NativeSurface {
    NativeSurface::verified_all()
}

fn metadata(
    need: CapabilityNeed,
    validity: ResourceValidity,
    owner: ResourceOwner,
) -> ResourceDescriptor {
    ResourceDescriptor {
        identity: ResourceIdentity {
            need,
            backend: need.backend(),
        },
        version: Version::new(1, 0, 0),
        scope: ResourceScope::Repository,
        owner,
        validity,
        invalidation: REQUIRED_INVALIDATION_TRIGGERS.iter().copied().collect(),
        privacy: ResourcePrivacy::RepositoryLocal,
        cleanup: match owner {
            ResourceOwner::CodexSmart => ResourceCleanup::CodexSmartExplicitReset,
            ResourceOwner::User | ResourceOwner::Provider => ResourceCleanup::OwnerManaged,
        },
    }
}

#[test]
fn explicit_feature_plan_is_native_first_and_only_prepares_owned_verified_resources() {
    let assessment = assess(&RoutingFacts {
        known_operations: vec![TaskKind::Edit],
        ..Default::default()
    });
    let external = CapabilitySurface::new([
        (Backend::CodeGraph, CapabilityState::Verified),
        (Backend::Serena, CapabilityState::Unknown),
    ]);
    let plan = plan_workflow(
        &assessment,
        Some(Archetype::FeatureImplementation),
        &native_ready(),
        &external,
        &ResourceCatalog::new([metadata(
            CapabilityNeed::StructuralImpact,
            ResourceValidity::Absent,
            ResourceOwner::CodexSmart,
        )]),
    );

    assert_eq!(plan.status, PlanStatus::Ready);
    assert_eq!(
        plan.selection.archetype,
        Some(Archetype::FeatureImplementation)
    );
    assert!(plan.resources.iter().any(|resource| {
        resource.identity.need == CapabilityNeed::StructuralImpact
            && resource.disposition == ResourceDisposition::PrepareOwned
            && resource.validity == Some(ResourceValidity::Absent)
            && resource.invalidation.as_ref().is_some_and(|set| {
                set.contains(&InvalidationTrigger::RepositoryIdentity)
                    && set.contains(&InvalidationTrigger::ExplicitReset)
            })
    }));
    assert!(plan.resources.iter().any(|resource| {
        resource.identity.need == CapabilityNeed::SymbolNavigation
            && resource.disposition == ResourceDisposition::NativeFallback
            && resource.version.is_none()
    }));
}

#[test]
fn generic_edit_and_unknown_native_evidence_never_cross_into_execution_ready_state() {
    let generic = assess(&RoutingFacts {
        known_operations: vec![TaskKind::Edit],
        ..Default::default()
    });
    let no_intent = plan_workflow(
        &generic,
        None,
        &native_ready(),
        &CapabilitySurface::default(),
        &ResourceCatalog::default(),
    );
    assert_eq!(no_intent.status, PlanStatus::NeedsEvidence);
    assert!(no_intent.router.is_none());

    let inspection = assess(&RoutingFacts {
        known_operations: vec![TaskKind::Inspect],
        ..Default::default()
    });
    let missing_native = plan_workflow(
        &inspection,
        None,
        &NativeSurface::new([
            (NativeCapability::ReadFiles, NativeState::Verified),
            (NativeCapability::Search, NativeState::Unknown),
            (NativeCapability::Git, NativeState::Verified),
        ]),
        &CapabilitySurface::default(),
        &ResourceCatalog::default(),
    );
    assert_eq!(missing_native.status, PlanStatus::NeedsEvidence);
    assert!(
        missing_native
            .reasons
            .contains(&WorkflowPlanReason::NativeUnknown(NativeCapability::Search))
    );
}

#[test]
fn security_floor_blocks_when_required_native_evidence_is_not_verified() {
    let assessment = assess(&RoutingFacts {
        known_operations: vec![TaskKind::Edit],
        risk_hint: Some(RiskLevel::Low),
        safety: vec![SafetyFact::SecuritySensitive],
        ..Default::default()
    });
    let plan = plan_workflow(
        &assessment,
        None,
        &NativeSurface::default(),
        &CapabilitySurface::new([(Backend::CodeGraph, CapabilityState::Verified)]),
        &ResourceCatalog::new([metadata(
            CapabilityNeed::StructuralImpact,
            ResourceValidity::Current,
            ResourceOwner::User,
        )]),
    );

    assert_eq!(plan.status, PlanStatus::Blocked);
    assert_eq!(
        plan.selection.archetype,
        Some(Archetype::SecuritySensitiveChange)
    );
    assert!(
        plan.reasons
            .contains(&WorkflowPlanReason::HighRiskNativeBlockingFallback)
    );
}
