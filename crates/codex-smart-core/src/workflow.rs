//! Deterministic playbook selection and lazy resource planning.
//!
//! The planner is pure. It never reads repository text, discovers tools, installs
//! software, authenticates, mutates configuration, prepares a resource, or launches
//! Codex. Callers provide typed routing/capability/resource evidence and receive an
//! inspectable plan.

use crate::playbook::{
    Archetype, CleanupObligation, ContextObligation, EscalationTrigger, FallbackPolicy,
    NativeCapability, PlaybookContract, ProfileClass, ValidationObligation, builtin,
};
use crate::routing::Reasoning;
use crate::routing::assessment::{
    Ambiguity, Reason, RiskLevel, SafetyFact, TaskKind, TaskRiskAssessment,
};
use crate::routing::engine::{
    Backend, CapabilityNeed, CapabilityState, CapabilitySurface, RouterDecision, decide,
};
use crate::version::Version;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum SelectionStatus {
    Selected,
    NeedsEvidence,
    Blocked,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum SelectionReason {
    ExplicitArchetype,
    DeterministicInspection,
    DeterministicRefactor,
    SecuritySafetyFact,
    MissingArchetypeIntent,
    AmbiguousAssessment,
    TaskMismatch,
    RiskAboveCeiling,
    MissingRequiredSafetyFact(SafetyFact),
    ContractRiskFloorApplied(RiskLevel),
    HighRiskExecutionFloor,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PlaybookSelection {
    pub status: SelectionStatus,
    pub archetype: Option<Archetype>,
    pub effective_risk: RiskLevel,
    pub profile: Option<ProfileClass>,
    pub reasoning: Option<Reasoning>,
    pub reasons: BTreeSet<SelectionReason>,
}

fn assessment_has_safety(assessment: &TaskRiskAssessment, fact: SafetyFact) -> bool {
    let reason = match fact {
        SafetyFact::SecuritySensitive => Reason::SecuritySensitive,
        SafetyFact::MigrationSensitive => Reason::MigrationSensitive,
        SafetyFact::ConcurrencySensitive => Reason::ConcurrencySensitive,
    };
    assessment.reasons.contains(&reason)
}

fn raised_floor(
    contract: &PlaybookContract,
    effective_risk: RiskLevel,
) -> (ProfileClass, Reasoning) {
    let mut profile = contract.execution_floor.profile;
    let mut reasoning = contract.execution_floor.reasoning;
    match effective_risk {
        RiskLevel::Low => {}
        RiskLevel::Medium => {
            profile = profile.max(ProfileClass::Standard);
        }
        RiskLevel::High => {
            profile = ProfileClass::Strong;
            reasoning = Reasoning::High;
        }
    }
    (profile, reasoning)
}

fn deterministic_archetype(
    assessment: &TaskRiskAssessment,
) -> (Option<Archetype>, SelectionReason) {
    match assessment.task {
        TaskKind::Inspect => (
            Some(Archetype::Inspection),
            SelectionReason::DeterministicInspection,
        ),
        TaskKind::Refactor if assessment_has_safety(assessment, SafetyFact::SecuritySensitive) => (
            Some(Archetype::SecuritySensitiveChange),
            SelectionReason::SecuritySafetyFact,
        ),
        TaskKind::Refactor => (
            Some(Archetype::Refactor),
            SelectionReason::DeterministicRefactor,
        ),
        TaskKind::Edit if assessment_has_safety(assessment, SafetyFact::SecuritySensitive) => (
            Some(Archetype::SecuritySensitiveChange),
            SelectionReason::SecuritySafetyFact,
        ),
        TaskKind::Edit | TaskKind::Unknown => (None, SelectionReason::MissingArchetypeIntent),
    }
}

/// Select a contract from explicit typed intent plus Router assessment.
///
/// Generic edits are deliberately not guessed into bug/feature/API/CI/dependency/docs
/// categories. An explicit archetype is required unless the mapping is unambiguous
/// (inspection/refactor) or a SecuritySensitive safety fact imposes the dedicated
/// security archetype.
pub fn select_playbook(
    assessment: &TaskRiskAssessment,
    explicit_archetype: Option<Archetype>,
) -> PlaybookSelection {
    let mut reasons = BTreeSet::new();
    if assessment.ambiguity == Ambiguity::Ambiguous || assessment.task == TaskKind::Unknown {
        reasons.insert(SelectionReason::AmbiguousAssessment);
        return PlaybookSelection {
            status: SelectionStatus::NeedsEvidence,
            archetype: None,
            effective_risk: assessment.risk,
            profile: None,
            reasoning: None,
            reasons,
        };
    }

    let archetype = match explicit_archetype {
        Some(archetype) => {
            reasons.insert(SelectionReason::ExplicitArchetype);
            Some(archetype)
        }
        None => {
            let (archetype, reason) = deterministic_archetype(assessment);
            reasons.insert(reason);
            archetype
        }
    };
    let Some(archetype) = archetype else {
        return PlaybookSelection {
            status: SelectionStatus::NeedsEvidence,
            archetype: None,
            effective_risk: assessment.risk,
            profile: None,
            reasoning: None,
            reasons,
        };
    };
    let contract = builtin(archetype);
    if !contract.applicability.task_kinds.contains(&assessment.task) {
        reasons.insert(SelectionReason::TaskMismatch);
        return PlaybookSelection {
            status: SelectionStatus::Blocked,
            archetype: Some(archetype),
            effective_risk: assessment.risk,
            profile: None,
            reasoning: None,
            reasons,
        };
    }
    if assessment.risk > contract.applicability.risk_ceiling {
        reasons.insert(SelectionReason::RiskAboveCeiling);
        return PlaybookSelection {
            status: SelectionStatus::Blocked,
            archetype: Some(archetype),
            effective_risk: assessment.risk,
            profile: None,
            reasoning: None,
            reasons,
        };
    }
    let missing_safety: Vec<_> = contract
        .applicability
        .safety_facts
        .iter()
        .copied()
        .filter(|fact| !assessment_has_safety(assessment, *fact))
        .collect();
    if !missing_safety.is_empty() {
        for fact in missing_safety {
            reasons.insert(SelectionReason::MissingRequiredSafetyFact(fact));
        }
        return PlaybookSelection {
            status: SelectionStatus::NeedsEvidence,
            archetype: Some(archetype),
            effective_risk: assessment.risk.max(contract.applicability.risk_floor),
            profile: None,
            reasoning: None,
            reasons,
        };
    }

    let effective_risk = assessment.risk.max(contract.applicability.risk_floor);
    if effective_risk > assessment.risk {
        reasons.insert(SelectionReason::ContractRiskFloorApplied(effective_risk));
    }
    let (profile, reasoning) = raised_floor(contract, effective_risk);
    if effective_risk == RiskLevel::High {
        reasons.insert(SelectionReason::HighRiskExecutionFloor);
    }
    PlaybookSelection {
        status: SelectionStatus::Selected,
        archetype: Some(archetype),
        effective_risk,
        profile: Some(profile),
        reasoning: Some(reasoning),
        reasons,
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum NativeState {
    Verified,
    Unknown,
    Unavailable,
    Blocked,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct NativeSurface(BTreeMap<NativeCapability, NativeState>);

impl NativeSurface {
    pub fn new(records: impl IntoIterator<Item = (NativeCapability, NativeState)>) -> Self {
        let mut states = BTreeMap::new();
        for (capability, state) in records {
            states
                .entry(capability)
                .and_modify(|previous: &mut NativeState| *previous = (*previous).max(state))
                .or_insert(state);
        }
        Self(states)
    }

    pub fn verified_all() -> Self {
        Self::new(
            [
                NativeCapability::ReadFiles,
                NativeCapability::Search,
                NativeCapability::Git,
                NativeCapability::Edit,
                NativeCapability::Build,
                NativeCapability::Tests,
            ]
            .into_iter()
            .map(|capability| (capability, NativeState::Verified)),
        )
    }

    pub fn state(&self, capability: NativeCapability) -> NativeState {
        self.0
            .get(&capability)
            .copied()
            .unwrap_or(NativeState::Unknown)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ResourceScope {
    Repository,
    Workspace,
    Session,
    RemoteRepository,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ResourceOwner {
    CodexSmart,
    User,
    Provider,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ResourceValidity {
    Current,
    Absent,
    Stale,
    Unknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum InvalidationTrigger {
    RepositoryIdentity,
    RelevantHeadOrConfig,
    CapabilityVersion,
    PlaybookSchema,
    ExplicitReset,
}

pub const REQUIRED_INVALIDATION_TRIGGERS: &[InvalidationTrigger] = &[
    InvalidationTrigger::RepositoryIdentity,
    InvalidationTrigger::RelevantHeadOrConfig,
    InvalidationTrigger::CapabilityVersion,
    InvalidationTrigger::PlaybookSchema,
    InvalidationTrigger::ExplicitReset,
];

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ResourcePrivacy {
    RepositoryLocal,
    PublicExternalReference,
    RemoteRepositoryMetadata,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ResourceCleanup {
    CodexSmartEphemeral,
    CodexSmartExplicitReset,
    OwnerManaged,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct ResourceIdentity {
    pub need: CapabilityNeed,
    pub backend: Backend,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResourceDescriptor {
    pub identity: ResourceIdentity,
    pub version: Version,
    pub scope: ResourceScope,
    pub owner: ResourceOwner,
    pub validity: ResourceValidity,
    pub invalidation: BTreeSet<InvalidationTrigger>,
    pub privacy: ResourcePrivacy,
    pub cleanup: ResourceCleanup,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ResourceCatalog {
    resources: BTreeMap<CapabilityNeed, ResourceDescriptor>,
    conflicts: BTreeSet<CapabilityNeed>,
}

impl ResourceCatalog {
    pub fn new(records: impl IntoIterator<Item = ResourceDescriptor>) -> Self {
        let mut resources = BTreeMap::new();
        let mut conflicts = BTreeSet::new();
        for resource in records {
            let need = resource.identity.need;
            if resources.insert(need, resource).is_some() {
                conflicts.insert(need);
            }
        }
        Self {
            resources,
            conflicts,
        }
    }

    pub fn get(&self, need: CapabilityNeed) -> Option<&ResourceDescriptor> {
        (!self.conflicts.contains(&need))
            .then(|| self.resources.get(&need))
            .flatten()
    }

    pub fn has_conflict(&self, need: CapabilityNeed) -> bool {
        self.conflicts.contains(&need)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ResourceDisposition {
    ReuseVerified,
    PrepareOwned,
    RefreshOwned,
    NativeFallback,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum PlanStatus {
    Ready,
    NeedsEvidence,
    Blocked,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ValidationReadiness {
    Ready,
    NeedsEvidence,
    Blocked,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PlannedValidation {
    pub obligation: ValidationObligation,
    pub required_native: BTreeSet<NativeCapability>,
    pub readiness: ValidationReadiness,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidationRecipe {
    pub status: ValidationReadiness,
    pub checks: Vec<PlannedValidation>,
}

const READ_ONLY_NATIVE: &[NativeCapability] = &[NativeCapability::ReadFiles, NativeCapability::Git];
const TEST_NATIVE: &[NativeCapability] = &[NativeCapability::Tests];
const BUILD_NATIVE: &[NativeCapability] = &[NativeCapability::Build];
const SEARCH_NATIVE: &[NativeCapability] = &[NativeCapability::ReadFiles, NativeCapability::Search];
const CI_NATIVE: &[NativeCapability] = &[
    NativeCapability::ReadFiles,
    NativeCapability::Search,
    NativeCapability::Build,
    NativeCapability::Tests,
];
const DEPENDENCY_NATIVE: &[NativeCapability] = &[
    NativeCapability::ReadFiles,
    NativeCapability::Build,
    NativeCapability::Tests,
];
const DOC_NATIVE: &[NativeCapability] = &[NativeCapability::ReadFiles, NativeCapability::Search];
const RELEASE_NATIVE: &[NativeCapability] = &[
    NativeCapability::ReadFiles,
    NativeCapability::Git,
    NativeCapability::Build,
    NativeCapability::Tests,
];

fn validation_native_requirements(obligation: ValidationObligation) -> &'static [NativeCapability] {
    match obligation {
        ValidationObligation::ReadOnlyInvariant => READ_ONLY_NATIVE,
        ValidationObligation::RelevantTests => TEST_NATIVE,
        ValidationObligation::BuildOrStaticCheck => BUILD_NATIVE,
        ValidationObligation::CallerCompatibility
        | ValidationObligation::ImpactReview
        | ValidationObligation::SecurityReview => SEARCH_NATIVE,
        ValidationObligation::CiConfigurationCheck => CI_NATIVE,
        ValidationObligation::DependencyValidation => DEPENDENCY_NATIVE,
        ValidationObligation::DocumentationCheck => DOC_NATIVE,
        ValidationObligation::ReleaseRehearsal => RELEASE_NATIVE,
    }
}

fn validation_readiness(
    requirements: &[NativeCapability],
    native: &NativeSurface,
) -> ValidationReadiness {
    let mut readiness = ValidationReadiness::Ready;
    for capability in requirements {
        match native.state(*capability) {
            NativeState::Verified => {}
            NativeState::Unknown => readiness = readiness.max(ValidationReadiness::NeedsEvidence),
            NativeState::Unavailable | NativeState::Blocked => {
                return ValidationReadiness::Blocked;
            }
        }
    }
    readiness
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum WorkflowPlanReason {
    Selection(SelectionReason),
    NativeUnknown(NativeCapability),
    NativeUnavailable(NativeCapability),
    NativeBlocked(NativeCapability),
    ExternalVerified(Backend),
    ExternalUnknown(Backend),
    ExternalUnavailable(Backend),
    ExternalBlocked(Backend),
    ResourceDescriptorMissing(CapabilityNeed),
    ResourceDescriptorConflict(CapabilityNeed),
    ResourceIdentityMismatch(CapabilityNeed),
    ResourceInvalidationIncomplete(CapabilityNeed),
    ResourceValidityUnknown(CapabilityNeed),
    PreparationNotAllowed(CapabilityNeed),
    ResourceOwnerMutationForbidden(CapabilityNeed),
    ReuseVerified(CapabilityNeed),
    PrepareOwned(CapabilityNeed),
    RefreshOwned(CapabilityNeed),
    NativeFallback(CapabilityNeed),
    HighRiskNativeBlockingFallback,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PlannedResource {
    pub identity: ResourceIdentity,
    pub disposition: ResourceDisposition,
    pub version: Option<Version>,
    pub scope: Option<ResourceScope>,
    pub owner: Option<ResourceOwner>,
    pub validity: Option<ResourceValidity>,
    pub invalidation: Option<BTreeSet<InvalidationTrigger>>,
    pub privacy: Option<ResourcePrivacy>,
    pub cleanup: Option<ResourceCleanup>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WorkflowPlan {
    pub status: PlanStatus,
    pub selection: PlaybookSelection,
    pub router: Option<RouterDecision>,
    pub resources: Vec<PlannedResource>,
    pub reasons: BTreeSet<WorkflowPlanReason>,
}

fn resource_metadata_valid(
    need: CapabilityNeed,
    descriptor: &ResourceDescriptor,
) -> Result<(), WorkflowPlanReason> {
    if descriptor.identity.need != need || descriptor.identity.backend != need.backend() {
        return Err(WorkflowPlanReason::ResourceIdentityMismatch(need));
    }
    if !REQUIRED_INVALIDATION_TRIGGERS
        .iter()
        .all(|trigger| descriptor.invalidation.contains(trigger))
    {
        return Err(WorkflowPlanReason::ResourceInvalidationIncomplete(need));
    }
    let owner_cleanup_ok = match descriptor.owner {
        ResourceOwner::CodexSmart => matches!(
            descriptor.cleanup,
            ResourceCleanup::CodexSmartEphemeral | ResourceCleanup::CodexSmartExplicitReset
        ),
        ResourceOwner::User | ResourceOwner::Provider => {
            descriptor.cleanup == ResourceCleanup::OwnerManaged
        }
    };
    if !owner_cleanup_ok {
        return Err(WorkflowPlanReason::ResourceOwnerMutationForbidden(need));
    }
    Ok(())
}

fn resource_for_fallback(need: CapabilityNeed) -> PlannedResource {
    PlannedResource {
        identity: ResourceIdentity {
            need,
            backend: need.backend(),
        },
        disposition: ResourceDisposition::NativeFallback,
        version: None,
        scope: None,
        owner: None,
        validity: None,
        invalidation: None,
        privacy: None,
        cleanup: None,
    }
}

fn resource_from_descriptor(
    need: CapabilityNeed,
    descriptor: &ResourceDescriptor,
    disposition: ResourceDisposition,
) -> PlannedResource {
    PlannedResource {
        identity: ResourceIdentity {
            need,
            backend: need.backend(),
        },
        disposition,
        version: Some(descriptor.version),
        scope: Some(descriptor.scope),
        owner: Some(descriptor.owner),
        validity: Some(descriptor.validity),
        invalidation: Some(descriptor.invalidation.clone()),
        privacy: Some(descriptor.privacy),
        cleanup: Some(descriptor.cleanup),
    }
}

fn apply_native_requirements(
    contract: &PlaybookContract,
    native: &NativeSurface,
    status: &mut PlanStatus,
    reasons: &mut BTreeSet<WorkflowPlanReason>,
) {
    for capability in contract.required_native {
        match native.state(*capability) {
            NativeState::Verified => {}
            NativeState::Unknown => {
                *status = (*status).max(PlanStatus::NeedsEvidence);
                reasons.insert(WorkflowPlanReason::NativeUnknown(*capability));
            }
            NativeState::Unavailable => {
                *status = PlanStatus::Blocked;
                reasons.insert(WorkflowPlanReason::NativeUnavailable(*capability));
            }
            NativeState::Blocked => {
                *status = PlanStatus::Blocked;
                reasons.insert(WorkflowPlanReason::NativeBlocked(*capability));
            }
        }
    }
}

fn external_state(surface: &CapabilitySurface, need: CapabilityNeed) -> CapabilityState {
    surface.state(need.backend())
}

/// Compose a pure workflow/resource plan.
///
/// External capabilities are optional augmentations. Unknown/unavailable/blocked
/// external state is never treated as ready: the planner records a native fallback.
/// Required native capabilities are different: unknown requires evidence, while
/// unavailable/blocked state blocks the plan.
pub fn plan_workflow(
    assessment: &TaskRiskAssessment,
    explicit_archetype: Option<Archetype>,
    native: &NativeSurface,
    external: &CapabilitySurface,
    catalog: &ResourceCatalog,
) -> WorkflowPlan {
    let selection = select_playbook(assessment, explicit_archetype);
    let mut reasons: BTreeSet<_> = selection
        .reasons
        .iter()
        .copied()
        .map(WorkflowPlanReason::Selection)
        .collect();
    let mut status = match selection.status {
        SelectionStatus::Selected => PlanStatus::Ready,
        SelectionStatus::NeedsEvidence => PlanStatus::NeedsEvidence,
        SelectionStatus::Blocked => PlanStatus::Blocked,
    };
    let Some(archetype) = selection
        .archetype
        .filter(|_| selection.status == SelectionStatus::Selected)
    else {
        return WorkflowPlan {
            status,
            selection,
            router: None,
            resources: Vec::new(),
            reasons,
        };
    };
    let contract = builtin(archetype);
    apply_native_requirements(contract, native, &mut status, &mut reasons);

    let router = decide(assessment, contract.optional_external, external);
    let mut resources = Vec::new();
    for need in contract.optional_external.iter().copied() {
        let backend = need.backend();
        match external_state(external, need) {
            CapabilityState::Verified => {
                reasons.insert(WorkflowPlanReason::ExternalVerified(backend));
                if catalog.has_conflict(need) {
                    reasons.insert(WorkflowPlanReason::ResourceDescriptorConflict(need));
                    reasons.insert(WorkflowPlanReason::NativeFallback(need));
                    resources.push(resource_for_fallback(need));
                    continue;
                }
                let Some(descriptor) = catalog.get(need) else {
                    reasons.insert(WorkflowPlanReason::ResourceDescriptorMissing(need));
                    reasons.insert(WorkflowPlanReason::NativeFallback(need));
                    resources.push(resource_for_fallback(need));
                    continue;
                };
                if let Err(reason) = resource_metadata_valid(need, descriptor) {
                    reasons.insert(reason);
                    reasons.insert(WorkflowPlanReason::NativeFallback(need));
                    resources.push(resource_for_fallback(need));
                    continue;
                }
                let disposition = match descriptor.validity {
                    ResourceValidity::Current => ResourceDisposition::ReuseVerified,
                    ResourceValidity::Absent
                        if !contract.prepared_state.is_empty()
                            && descriptor.owner == ResourceOwner::CodexSmart =>
                    {
                        ResourceDisposition::PrepareOwned
                    }
                    ResourceValidity::Stale
                        if !contract.prepared_state.is_empty()
                            && descriptor.owner == ResourceOwner::CodexSmart =>
                    {
                        ResourceDisposition::RefreshOwned
                    }
                    ResourceValidity::Unknown => {
                        reasons.insert(WorkflowPlanReason::ResourceValidityUnknown(need));
                        ResourceDisposition::NativeFallback
                    }
                    ResourceValidity::Absent | ResourceValidity::Stale
                        if contract.prepared_state.is_empty() =>
                    {
                        reasons.insert(WorkflowPlanReason::PreparationNotAllowed(need));
                        ResourceDisposition::NativeFallback
                    }
                    ResourceValidity::Absent | ResourceValidity::Stale => {
                        reasons.insert(WorkflowPlanReason::ResourceOwnerMutationForbidden(need));
                        ResourceDisposition::NativeFallback
                    }
                };
                match disposition {
                    ResourceDisposition::ReuseVerified => {
                        reasons.insert(WorkflowPlanReason::ReuseVerified(need));
                        resources.push(resource_from_descriptor(need, descriptor, disposition));
                    }
                    ResourceDisposition::PrepareOwned => {
                        reasons.insert(WorkflowPlanReason::PrepareOwned(need));
                        resources.push(resource_from_descriptor(need, descriptor, disposition));
                    }
                    ResourceDisposition::RefreshOwned => {
                        reasons.insert(WorkflowPlanReason::RefreshOwned(need));
                        resources.push(resource_from_descriptor(need, descriptor, disposition));
                    }
                    ResourceDisposition::NativeFallback => {
                        reasons.insert(WorkflowPlanReason::NativeFallback(need));
                        resources.push(resource_for_fallback(need));
                    }
                }
            }
            CapabilityState::Unknown => {
                reasons.insert(WorkflowPlanReason::ExternalUnknown(backend));
                reasons.insert(WorkflowPlanReason::NativeFallback(need));
                resources.push(resource_for_fallback(need));
            }
            CapabilityState::Unavailable => {
                reasons.insert(WorkflowPlanReason::ExternalUnavailable(backend));
                reasons.insert(WorkflowPlanReason::NativeFallback(need));
                resources.push(resource_for_fallback(need));
            }
            CapabilityState::Blocked => {
                reasons.insert(WorkflowPlanReason::ExternalBlocked(backend));
                reasons.insert(WorkflowPlanReason::NativeFallback(need));
                resources.push(resource_for_fallback(need));
            }
        }
    }

    if contract.fallback == FallbackPolicy::NativeThenBlock && status != PlanStatus::Ready {
        reasons.insert(WorkflowPlanReason::HighRiskNativeBlockingFallback);
        status = PlanStatus::Blocked;
    }

    WorkflowPlan {
        status,
        selection,
        router: Some(router),
        resources,
        reasons,
    }
}

impl WorkflowPlan {
    /// Build a bounded native validation recipe. External capability state and prepared
    /// resources never satisfy these checks: validation remains native-first and
    /// fail-closed when required native evidence is missing.
    pub fn validation_recipe(&self, native: &NativeSurface) -> Option<ValidationRecipe> {
        let contract = builtin(self.selection.archetype?);
        let mut status = match self.status {
            PlanStatus::Ready => ValidationReadiness::Ready,
            PlanStatus::NeedsEvidence => ValidationReadiness::NeedsEvidence,
            PlanStatus::Blocked => ValidationReadiness::Blocked,
        };
        let checks = contract
            .validation
            .iter()
            .copied()
            .map(|obligation| {
                let requirements = validation_native_requirements(obligation);
                let readiness = validation_readiness(requirements, native);
                status = status.max(readiness);
                PlannedValidation {
                    obligation,
                    required_native: requirements.iter().copied().collect(),
                    readiness,
                }
            })
            .collect();
        Some(ValidationRecipe { status, checks })
    }

    /// Enum/version-only explanation. It deliberately excludes prompt/source, paths,
    /// credentials, dynamic tool output and arbitrary resource labels. It describes
    /// semantic obligations only and grants no execution or preparation authority.
    pub fn render(&self) -> String {
        let contract = self.selection.archetype.map(builtin);
        let context: &[ContextObligation] = contract.map_or(&[], |value| value.context);
        let tools: &[NativeCapability] = contract.map_or(&[], |value| value.required_native);
        let validation: &[ValidationObligation] = contract.map_or(&[], |value| value.validation);
        let escalation: &[EscalationTrigger] = contract.map_or(&[], |value| value.escalation);
        let cleanup: &[CleanupObligation] = contract.map_or(&[], |value| value.cleanup);
        let fallback = contract.map(|value| value.fallback);
        format!(
            "Workflow plan (no execution)\nStatus: {:?}\nWorkflow: {:?}\nRisk: {:?}\nProfile: {:?}\nReasoning: {:?}\nContext: {:?}\nTools (required native): {:?}\nPreparation: {:?}\nValidation: {:?}\nEscalation: {:?}\nCleanup: {:?}\nFallback: {:?}\nReasons: {:?}\n",
            self.status,
            self.selection.archetype,
            self.selection.effective_risk,
            self.selection.profile,
            self.selection.reasoning,
            context,
            tools,
            self.resources,
            validation,
            escalation,
            cleanup,
            fallback,
            self.reasons,
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::routing::assessment::{RoutingFacts, assess};

    fn assessed(task: TaskKind, risk: Option<RiskLevel>) -> TaskRiskAssessment {
        assess(&RoutingFacts {
            known_operations: vec![task],
            risk_hint: risk,
            ..Default::default()
        })
    }

    fn secure(task: TaskKind) -> TaskRiskAssessment {
        assess(&RoutingFacts {
            known_operations: vec![task],
            safety: vec![SafetyFact::SecuritySensitive],
            ..Default::default()
        })
    }

    fn full_invalidation() -> BTreeSet<InvalidationTrigger> {
        REQUIRED_INVALIDATION_TRIGGERS.iter().copied().collect()
    }

    fn descriptor(
        need: CapabilityNeed,
        owner: ResourceOwner,
        validity: ResourceValidity,
    ) -> ResourceDescriptor {
        ResourceDescriptor {
            identity: ResourceIdentity {
                need,
                backend: need.backend(),
            },
            version: Version::new(1, 2, 3),
            scope: ResourceScope::Repository,
            owner,
            validity,
            invalidation: full_invalidation(),
            privacy: ResourcePrivacy::RepositoryLocal,
            cleanup: match owner {
                ResourceOwner::CodexSmart => ResourceCleanup::CodexSmartExplicitReset,
                ResourceOwner::User | ResourceOwner::Provider => ResourceCleanup::OwnerManaged,
            },
        }
    }

    #[test]
    fn generic_edit_requires_explicit_archetype_intent() {
        let result = select_playbook(&assessed(TaskKind::Edit, None), None);
        assert_eq!(result.status, SelectionStatus::NeedsEvidence);
        assert_eq!(result.archetype, None);
        assert!(
            result
                .reasons
                .contains(&SelectionReason::MissingArchetypeIntent)
        );
    }

    #[test]
    fn inspection_and_refactor_have_deterministic_defaults() {
        let inspection = select_playbook(&assessed(TaskKind::Inspect, None), None);
        assert_eq!(inspection.status, SelectionStatus::Selected);
        assert_eq!(inspection.archetype, Some(Archetype::Inspection));

        let refactor = select_playbook(&assessed(TaskKind::Refactor, None), None);
        assert_eq!(refactor.status, SelectionStatus::Selected);
        assert_eq!(refactor.archetype, Some(Archetype::Refactor));
        assert_eq!(refactor.effective_risk, RiskLevel::Medium);
        assert_eq!(refactor.reasoning, Some(Reasoning::High));
    }

    #[test]
    fn explicit_api_change_applies_contract_risk_floor() {
        let result = select_playbook(
            &assessed(TaskKind::Edit, Some(RiskLevel::Low)),
            Some(Archetype::ApiChange),
        );
        assert_eq!(result.status, SelectionStatus::Selected);
        assert_eq!(result.effective_risk, RiskLevel::Medium);
        assert_eq!(result.profile, Some(ProfileClass::Standard));
        assert_eq!(result.reasoning, Some(Reasoning::High));
        assert!(
            result
                .reasons
                .contains(&SelectionReason::ContractRiskFloorApplied(
                    RiskLevel::Medium
                ))
        );
    }

    #[test]
    fn high_risk_always_raises_execution_floor_and_respects_ceiling() {
        let inspection = select_playbook(
            &assessed(TaskKind::Inspect, Some(RiskLevel::High)),
            Some(Archetype::Inspection),
        );
        assert_eq!(inspection.status, SelectionStatus::Selected);
        assert_eq!(inspection.profile, Some(ProfileClass::Strong));
        assert_eq!(inspection.reasoning, Some(Reasoning::High));

        let bug = select_playbook(
            &assessed(TaskKind::Edit, Some(RiskLevel::High)),
            Some(Archetype::FocusedBugFix),
        );
        assert_eq!(bug.status, SelectionStatus::Blocked);
        assert!(bug.reasons.contains(&SelectionReason::RiskAboveCeiling));
    }

    #[test]
    fn security_archetype_requires_semantic_safety_fact() {
        let missing = select_playbook(
            &assessed(TaskKind::Edit, Some(RiskLevel::High)),
            Some(Archetype::SecuritySensitiveChange),
        );
        assert_eq!(missing.status, SelectionStatus::NeedsEvidence);
        assert!(
            missing
                .reasons
                .contains(&SelectionReason::MissingRequiredSafetyFact(
                    SafetyFact::SecuritySensitive
                ))
        );

        let selected = select_playbook(&secure(TaskKind::Edit), None);
        assert_eq!(selected.status, SelectionStatus::Selected);
        assert_eq!(selected.archetype, Some(Archetype::SecuritySensitiveChange));
        assert_eq!(selected.profile, Some(ProfileClass::Strong));
        assert_eq!(selected.reasoning, Some(Reasoning::High));
    }

    #[test]
    fn ambiguous_router_assessment_never_selects_even_with_hint() {
        let assessment = assess(&RoutingFacts {
            task_hints: vec![TaskKind::Edit, TaskKind::Inspect],
            ..Default::default()
        });
        let result = select_playbook(&assessment, Some(Archetype::FeatureImplementation));
        assert_eq!(result.status, SelectionStatus::NeedsEvidence);
        assert_eq!(result.archetype, None);
    }

    #[test]
    fn native_surface_is_conservative_and_missing_state_is_unknown() {
        let surface = NativeSurface::new([
            (NativeCapability::ReadFiles, NativeState::Verified),
            (NativeCapability::ReadFiles, NativeState::Unavailable),
        ]);
        assert_eq!(
            surface.state(NativeCapability::ReadFiles),
            NativeState::Unavailable
        );
        assert_eq!(
            surface.state(NativeCapability::Search),
            NativeState::Unknown
        );
    }

    #[test]
    fn required_native_unknown_needs_evidence_and_unavailable_blocks() {
        let assessment = assessed(TaskKind::Inspect, None);
        let unknown = plan_workflow(
            &assessment,
            None,
            &NativeSurface::default(),
            &CapabilitySurface::default(),
            &ResourceCatalog::default(),
        );
        assert_eq!(unknown.status, PlanStatus::NeedsEvidence);

        let unavailable = plan_workflow(
            &assessment,
            None,
            &NativeSurface::new([
                (NativeCapability::ReadFiles, NativeState::Unavailable),
                (NativeCapability::Search, NativeState::Verified),
                (NativeCapability::Git, NativeState::Verified),
            ]),
            &CapabilitySurface::default(),
            &ResourceCatalog::default(),
        );
        assert_eq!(unavailable.status, PlanStatus::Blocked);
    }

    #[test]
    fn verified_current_external_resource_is_reused() {
        let assessment = assessed(TaskKind::Refactor, None);
        let need = CapabilityNeed::StructuralImpact;
        let plan = plan_workflow(
            &assessment,
            None,
            &NativeSurface::verified_all(),
            &CapabilitySurface::new([(Backend::CodeGraph, CapabilityState::Verified)]),
            &ResourceCatalog::new([descriptor(
                need,
                ResourceOwner::CodexSmart,
                ResourceValidity::Current,
            )]),
        );
        assert_eq!(plan.status, PlanStatus::Ready);
        let item = plan
            .resources
            .iter()
            .find(|item| item.identity.need == need)
            .unwrap();
        assert_eq!(item.disposition, ResourceDisposition::ReuseVerified);
        assert_eq!(item.version, Some(Version::new(1, 2, 3)));
        assert_eq!(item.validity, Some(ResourceValidity::Current));
        assert_eq!(item.invalidation.as_ref().unwrap(), &full_invalidation());
    }

    #[test]
    fn owned_absent_and_stale_resources_only_produce_lazy_plan_actions() {
        let assessment = assessed(TaskKind::Refactor, None);
        for (validity, expected) in [
            (ResourceValidity::Absent, ResourceDisposition::PrepareOwned),
            (ResourceValidity::Stale, ResourceDisposition::RefreshOwned),
        ] {
            let plan = plan_workflow(
                &assessment,
                None,
                &NativeSurface::verified_all(),
                &CapabilitySurface::new([(Backend::CodeGraph, CapabilityState::Verified)]),
                &ResourceCatalog::new([descriptor(
                    CapabilityNeed::StructuralImpact,
                    ResourceOwner::CodexSmart,
                    validity,
                )]),
            );
            assert_eq!(plan.status, PlanStatus::Ready);
            assert!(
                plan.resources
                    .iter()
                    .any(|item| item.disposition == expected)
            );
        }
    }

    #[test]
    fn user_or_provider_resources_are_never_created_or_refreshed() {
        let assessment = assessed(TaskKind::Refactor, None);
        for owner in [ResourceOwner::User, ResourceOwner::Provider] {
            for validity in [ResourceValidity::Absent, ResourceValidity::Stale] {
                let plan = plan_workflow(
                    &assessment,
                    None,
                    &NativeSurface::verified_all(),
                    &CapabilitySurface::new([(Backend::CodeGraph, CapabilityState::Verified)]),
                    &ResourceCatalog::new([descriptor(
                        CapabilityNeed::StructuralImpact,
                        owner,
                        validity,
                    )]),
                );
                assert!(plan.resources.iter().any(|item| {
                    item.identity.need == CapabilityNeed::StructuralImpact
                        && item.disposition == ResourceDisposition::NativeFallback
                }));
                assert!(!plan.resources.iter().any(|item| matches!(
                    item.disposition,
                    ResourceDisposition::PrepareOwned | ResourceDisposition::RefreshOwned
                )));
            }
        }
    }

    #[test]
    fn unknown_external_capability_never_becomes_ready() {
        let assessment = assessed(TaskKind::Refactor, None);
        let plan = plan_workflow(
            &assessment,
            None,
            &NativeSurface::verified_all(),
            &CapabilitySurface::default(),
            &ResourceCatalog::new([descriptor(
                CapabilityNeed::StructuralImpact,
                ResourceOwner::CodexSmart,
                ResourceValidity::Current,
            )]),
        );
        assert_eq!(plan.status, PlanStatus::Ready);
        assert!(
            plan.reasons
                .contains(&WorkflowPlanReason::ExternalUnknown(Backend::CodeGraph))
        );
        assert!(plan.resources.iter().any(|item| {
            item.identity.need == CapabilityNeed::StructuralImpact
                && item.disposition == ResourceDisposition::NativeFallback
                && item.version.is_none()
        }));
    }

    #[test]
    fn duplicate_resource_descriptors_fail_closed_to_native() {
        let assessment = assessed(TaskKind::Refactor, None);
        let need = CapabilityNeed::StructuralImpact;
        let plan = plan_workflow(
            &assessment,
            None,
            &NativeSurface::verified_all(),
            &CapabilitySurface::new([(Backend::CodeGraph, CapabilityState::Verified)]),
            &ResourceCatalog::new([
                descriptor(need, ResourceOwner::CodexSmart, ResourceValidity::Current),
                descriptor(need, ResourceOwner::User, ResourceValidity::Current),
            ]),
        );
        assert!(
            plan.reasons
                .contains(&WorkflowPlanReason::ResourceDescriptorConflict(need))
        );
        assert!(plan.resources.iter().any(|item| {
            item.identity.need == need && item.disposition == ResourceDisposition::NativeFallback
        }));
    }

    #[test]
    fn incomplete_or_mismatched_resource_metadata_falls_back_native() {
        let assessment = assessed(TaskKind::Refactor, None);
        let need = CapabilityNeed::StructuralImpact;
        let mut bad = descriptor(need, ResourceOwner::CodexSmart, ResourceValidity::Current);
        bad.invalidation.remove(&InvalidationTrigger::ExplicitReset);
        let plan = plan_workflow(
            &assessment,
            None,
            &NativeSurface::verified_all(),
            &CapabilitySurface::new([(Backend::CodeGraph, CapabilityState::Verified)]),
            &ResourceCatalog::new([bad]),
        );
        assert!(
            plan.reasons
                .contains(&WorkflowPlanReason::ResourceInvalidationIncomplete(need))
        );
        assert!(plan.resources.iter().any(|item| {
            item.identity.need == need && item.disposition == ResourceDisposition::NativeFallback
        }));
    }

    #[test]
    fn high_risk_missing_native_evidence_blocks() {
        let plan = plan_workflow(
            &secure(TaskKind::Edit),
            None,
            &NativeSurface::default(),
            &CapabilitySurface::default(),
            &ResourceCatalog::default(),
        );
        assert_eq!(plan.status, PlanStatus::Blocked);
        assert!(
            plan.reasons
                .contains(&WorkflowPlanReason::HighRiskNativeBlockingFallback)
        );
    }

    #[test]
    fn validation_recipe_is_native_only_and_can_require_more_evidence_than_planning() {
        let native = NativeSurface::new([
            (NativeCapability::ReadFiles, NativeState::Verified),
            (NativeCapability::Search, NativeState::Verified),
            (NativeCapability::Edit, NativeState::Verified),
            (NativeCapability::Tests, NativeState::Verified),
        ]);
        let plan = plan_workflow(
            &assessed(TaskKind::Edit, None),
            Some(Archetype::FailingTestRepair),
            &native,
            &CapabilitySurface::new([(Backend::Serena, CapabilityState::Verified)]),
            &ResourceCatalog::default(),
        );
        assert_eq!(plan.status, PlanStatus::Ready);

        let recipe = plan.validation_recipe(&native).unwrap();
        assert_eq!(recipe.status, ValidationReadiness::NeedsEvidence);
        let tests = recipe
            .checks
            .iter()
            .find(|check| check.obligation == ValidationObligation::RelevantTests)
            .unwrap();
        assert_eq!(tests.readiness, ValidationReadiness::Ready);
        assert_eq!(
            tests.required_native,
            BTreeSet::from([NativeCapability::Tests])
        );
        let build = recipe
            .checks
            .iter()
            .find(|check| check.obligation == ValidationObligation::BuildOrStaticCheck)
            .unwrap();
        assert_eq!(build.readiness, ValidationReadiness::NeedsEvidence);
        assert_eq!(
            build.required_native,
            BTreeSet::from([NativeCapability::Build])
        );
    }

    #[test]
    fn validation_recipe_blocks_on_unavailable_native_check() {
        let native = NativeSurface::new([
            (NativeCapability::ReadFiles, NativeState::Verified),
            (NativeCapability::Search, NativeState::Verified),
            (NativeCapability::Edit, NativeState::Verified),
            (NativeCapability::Tests, NativeState::Verified),
            (NativeCapability::Build, NativeState::Unavailable),
        ]);
        let plan = plan_workflow(
            &assessed(TaskKind::Edit, None),
            Some(Archetype::FailingTestRepair),
            &native,
            &CapabilitySurface::default(),
            &ResourceCatalog::default(),
        );
        assert_eq!(plan.status, PlanStatus::Ready);
        let recipe = plan.validation_recipe(&native).unwrap();
        assert_eq!(recipe.status, ValidationReadiness::Blocked);
        assert!(recipe.checks.iter().any(|check| {
            check.obligation == ValidationObligation::BuildOrStaticCheck
                && check.readiness == ValidationReadiness::Blocked
        }));
    }

    #[test]
    fn builtin_validation_requirements_are_bounded_native_contracts() {
        for contract in crate::playbook::BUILTIN_PLAYBOOKS {
            for obligation in contract.validation {
                let required = validation_native_requirements(*obligation);
                assert!(!required.is_empty(), "{:?}", obligation);
                assert!(required.len() <= 4, "{:?}", obligation);
                let unique: BTreeSet<_> = required.iter().copied().collect();
                assert_eq!(unique.len(), required.len(), "{:?}", obligation);
            }
        }
    }

    #[test]
    fn render_is_bounded_and_contains_no_runtime_identity_strings() {
        let plan = plan_workflow(
            &assessed(TaskKind::Inspect, None),
            None,
            &NativeSurface::verified_all(),
            &CapabilitySurface::default(),
            &ResourceCatalog::default(),
        );
        let rendered = plan.render();
        for forbidden in [
            "gpt-",
            "openai",
            "anthropic",
            "gemini",
            "/home/",
            "api_key",
            "Bearer ",
            "install",
            "login",
        ] {
            assert!(
                !rendered
                    .to_ascii_lowercase()
                    .contains(&forbidden.to_ascii_lowercase())
            );
        }
        assert!(rendered.contains("no execution"));
        for section in [
            "Workflow:",
            "Profile:",
            "Reasoning:",
            "Context:",
            "Tools (required native):",
            "Preparation:",
            "Validation:",
            "Escalation:",
            "Cleanup:",
            "Fallback:",
        ] {
            assert!(rendered.contains(section), "missing {section}");
        }
    }
}
