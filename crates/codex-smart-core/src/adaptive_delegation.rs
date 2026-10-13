//! Bounded delegation and evidence-preserving handoff contract.
//!
//! This module is policy only. It never launches a child, resolves provider/model names,
//! reads source, performs network access, authenticates, edits files, runs validation, or
//! advances the parent adaptive controller to completion. Runtime adapters must map the
//! opaque resource/evidence handles after independent authorization.

use crate::adaptive::{AdaptiveController, ControllerState};
use crate::playbook::{Archetype, ProfileClass, ValidationObligation, builtin};
use crate::routing::Reasoning;
use crate::routing::assessment::RiskLevel;
use std::collections::BTreeSet;

pub const DELEGATION_SCHEMA_VERSION: u16 = 1;
pub const MAX_DELEGATION_CONTEXT_ITEMS: usize = 16;
pub const MAX_DELEGATION_CONTEXT_BYTES: u32 = 65_536;
pub const MAX_DELEGATION_SCOPE_ITEMS: usize = 16;
pub const MAX_DELEGATION_WRITE_ITEMS: usize = 8;
pub const MAX_DELEGATION_WALL_SECONDS: u16 = 120;
pub const MAX_DELEGATION_COST_UNITS: u32 = 10_000;
pub const MAX_DELEGATION_OUTPUT_BYTES: u32 = 65_536;
pub const MAX_HANDOFF_EVIDENCE_ITEMS: usize = 16;
pub const MAX_HANDOFF_EVIDENCE_BYTES: u32 = 65_536;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct ResourceKey(pub u16);

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct EvidenceKey(pub u16);

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ContextKind {
    TaskDefinition,
    Requirement,
    RelevantFile,
    ExistingTest,
    FailureEvidence,
    PublicContract,
    ValidationHistory,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ContextReference {
    pub key: EvidenceKey,
    pub kind: ContextKind,
    /// Size of the externally held context represented by this reference. The policy
    /// layer intentionally carries no source text or prompt content.
    pub bytes: u32,
    pub digest: [u8; 32],
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DelegationKind {
    ReadOnlyEvidence,
    MechanicalWorkspaceChange,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DelegationOrigin {
    Parent,
    DelegatedChild,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum DelegationHazard {
    SecuritySensitive,
    ConcurrencySensitive,
    DestructiveMigration,
    AmbiguousApiContract,
    ConflictingEvidence,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SafetyReviewState {
    VerifiedClear,
    Unknown,
    Conflicting,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DelegationSafetyReview {
    pub state: SafetyReviewState,
    pub hazards: BTreeSet<DelegationHazard>,
}

impl DelegationSafetyReview {
    pub fn verified_clear() -> Self {
        Self {
            state: SafetyReviewState::VerifiedClear,
            hazards: BTreeSet::new(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AuthorityBoundary {
    /// Opaque caller-owned scope handles. No path strings are accepted by policy.
    pub readable: BTreeSet<ResourceKey>,
    pub writable: BTreeSet<ResourceKey>,
    /// Allows only the validation obligations carried in the request. It does not grant
    /// arbitrary command/process authority.
    pub may_run_declared_validation: bool,
}

impl AuthorityBoundary {
    pub fn read_only(resources: impl IntoIterator<Item = ResourceKey>) -> Self {
        Self {
            readable: resources.into_iter().collect(),
            writable: BTreeSet::new(),
            may_run_declared_validation: false,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ChildBudget {
    pub max_wall_seconds: u16,
    /// Opaque accounting units supplied by the caller. They are not currency and encode
    /// no provider pricing assumption.
    pub max_cost_units: u32,
    pub max_output_bytes: u32,
}

impl ChildBudget {
    pub fn new(
        max_wall_seconds: u16,
        max_cost_units: u32,
        max_output_bytes: u32,
    ) -> Result<Self, DelegationError> {
        if max_wall_seconds == 0
            || max_wall_seconds > MAX_DELEGATION_WALL_SECONDS
            || max_cost_units == 0
            || max_cost_units > MAX_DELEGATION_COST_UNITS
            || max_output_bytes == 0
            || max_output_bytes > MAX_DELEGATION_OUTPUT_BYTES
        {
            return Err(DelegationError::InvalidBudget);
        }
        Ok(Self {
            max_wall_seconds,
            max_cost_units,
            max_output_bytes,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DelegationRequest {
    pub origin: DelegationOrigin,
    pub kind: DelegationKind,
    pub context: Vec<ContextReference>,
    pub authority: AuthorityBoundary,
    pub validation: BTreeSet<ValidationObligation>,
    /// Every child result is advisory. Mechanical output must be independently validated
    /// by the parent boundary before it can contribute to completion.
    pub parent_revalidation_required: bool,
    pub safety: DelegationSafetyReview,
    pub budget: ChildBudget,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum DelegationReason {
    ParentStateNotEligible,
    ParentHighRisk,
    ParentDelegationBudgetExhausted,
    NestedDelegationForbidden,
    SafetyReviewUnknown,
    SafetyReviewConflicting,
    Hazard(DelegationHazard),
    EmptyContext,
    InvalidContextReference,
    DuplicateContextReference,
    ContextLimitExceeded,
    ScopeLimitExceeded,
    WriteScopeLimitExceeded,
    ReadOnlyWriteAuthority,
    MechanicalWriteScopeMissing,
    MechanicalWriteOutsideReadScope,
    MechanicalDelegationDuringEvidenceGate,
    ValidationAuthorityMismatch,
    MechanicalValidationMissing,
    ParentRevalidationMissing,
    InvalidChildBudget,
    ValidationOutsideParentContract,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DelegationStatus {
    Ready,
    NeedsEvidence,
    Blocked,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DelegationPlan {
    pub schema_version: u16,
    pub status: DelegationStatus,
    pub kind: DelegationKind,
    pub profile: Option<ProfileClass>,
    pub reasoning: Option<Reasoning>,
    pub context_items: usize,
    pub context_bytes: u32,
    pub readable_resources: usize,
    pub writable_resources: usize,
    pub reasons: BTreeSet<DelegationReason>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DelegationError {
    InvalidBudget,
    ParentMismatch,
    PlanNotReady,
    LedgerOutOfSync,
    UnknownAuthorization,
    DuplicateHandoff,
    HandoffProtocolViolation(HandoffViolation),
}

fn context_summary(context: &[ContextReference]) -> (usize, u32, BTreeSet<DelegationReason>) {
    let mut reasons = BTreeSet::new();
    if context.is_empty() {
        reasons.insert(DelegationReason::EmptyContext);
        return (0, 0, reasons);
    }
    let mut keys = BTreeSet::new();
    let mut total = 0_u32;
    for item in context {
        if item.bytes == 0 || item.digest == [0; 32] {
            reasons.insert(DelegationReason::InvalidContextReference);
        }
        if !keys.insert(item.key) {
            reasons.insert(DelegationReason::DuplicateContextReference);
        }
        total = total.saturating_add(item.bytes);
    }
    if context.len() > MAX_DELEGATION_CONTEXT_ITEMS || total > MAX_DELEGATION_CONTEXT_BYTES {
        reasons.insert(DelegationReason::ContextLimitExceeded);
    }
    (context.len(), total, reasons)
}

fn child_floor(controller: &AdaptiveController, kind: DelegationKind) -> (ProfileClass, Reasoning) {
    let profile = match kind {
        DelegationKind::ReadOnlyEvidence => controller.current_profile,
        DelegationKind::MechanicalWorkspaceChange => {
            controller.current_profile.max(ProfileClass::Standard)
        }
    };
    (profile, controller.current_reasoning)
}

/// Pure eligibility assessment. No budget counter is consumed here.
///
/// High-risk parent work is never delegated. Explicit security/concurrency/destructive
/// migration/ambiguous-API/conflicting-evidence hazards are likewise blocked rather than
/// treated as cheap-safe. Unknown safety evidence remains NeedsEvidence.
pub fn assess_delegation(
    controller: &AdaptiveController,
    request: &DelegationRequest,
) -> DelegationPlan {
    let mut reasons = BTreeSet::new();

    match controller.state {
        ControllerState::Ready | ControllerState::NeedsEvidence(_) => {}
        ControllerState::Running
        | ControllerState::AwaitingValidation
        | ControllerState::Completed
        | ControllerState::Blocked(_)
        | ControllerState::Exhausted => {
            reasons.insert(DelegationReason::ParentStateNotEligible);
        }
    }
    if controller.risk == RiskLevel::High {
        reasons.insert(DelegationReason::ParentHighRisk);
    }
    if controller.remaining_delegations() == 0 {
        reasons.insert(DelegationReason::ParentDelegationBudgetExhausted);
    }
    if request.origin != DelegationOrigin::Parent {
        reasons.insert(DelegationReason::NestedDelegationForbidden);
    }

    match request.safety.state {
        SafetyReviewState::VerifiedClear => {}
        SafetyReviewState::Unknown => {
            reasons.insert(DelegationReason::SafetyReviewUnknown);
        }
        SafetyReviewState::Conflicting => {
            reasons.insert(DelegationReason::SafetyReviewConflicting);
        }
    }
    for hazard in &request.safety.hazards {
        reasons.insert(DelegationReason::Hazard(*hazard));
    }

    let (context_items, context_bytes, context_reasons) = context_summary(&request.context);
    reasons.extend(context_reasons);

    let scope: BTreeSet<_> = request
        .authority
        .readable
        .union(&request.authority.writable)
        .copied()
        .collect();
    if scope.len() > MAX_DELEGATION_SCOPE_ITEMS {
        reasons.insert(DelegationReason::ScopeLimitExceeded);
    }
    if request.authority.writable.len() > MAX_DELEGATION_WRITE_ITEMS {
        reasons.insert(DelegationReason::WriteScopeLimitExceeded);
    }
    if !request.parent_revalidation_required {
        reasons.insert(DelegationReason::ParentRevalidationMissing);
    }
    if request.budget.max_wall_seconds == 0
        || request.budget.max_wall_seconds > MAX_DELEGATION_WALL_SECONDS
        || request.budget.max_cost_units == 0
        || request.budget.max_cost_units > MAX_DELEGATION_COST_UNITS
        || request.budget.max_output_bytes == 0
        || request.budget.max_output_bytes > MAX_DELEGATION_OUTPUT_BYTES
    {
        reasons.insert(DelegationReason::InvalidChildBudget);
    }
    let parent_validation: BTreeSet<_> = builtin(controller.archetype)
        .validation
        .iter()
        .copied()
        .collect();
    if !request.validation.is_subset(&parent_validation) {
        reasons.insert(DelegationReason::ValidationOutsideParentContract);
    }

    match request.kind {
        DelegationKind::ReadOnlyEvidence => {
            if !request.authority.writable.is_empty() {
                reasons.insert(DelegationReason::ReadOnlyWriteAuthority);
            }
            if request.authority.may_run_declared_validation || !request.validation.is_empty() {
                reasons.insert(DelegationReason::ValidationAuthorityMismatch);
            }
        }
        DelegationKind::MechanicalWorkspaceChange => {
            if matches!(controller.state, ControllerState::NeedsEvidence(_)) {
                reasons.insert(DelegationReason::MechanicalDelegationDuringEvidenceGate);
            }
            if request.authority.writable.is_empty() {
                reasons.insert(DelegationReason::MechanicalWriteScopeMissing);
            }
            if !request
                .authority
                .writable
                .is_subset(&request.authority.readable)
            {
                reasons.insert(DelegationReason::MechanicalWriteOutsideReadScope);
            }
            if request.validation.is_empty() {
                reasons.insert(DelegationReason::MechanicalValidationMissing);
            }
            if !request.authority.may_run_declared_validation {
                reasons.insert(DelegationReason::ValidationAuthorityMismatch);
            }
        }
    }

    let needs_evidence = reasons.contains(&DelegationReason::SafetyReviewUnknown);
    let blocked = reasons
        .iter()
        .any(|reason| !matches!(reason, DelegationReason::SafetyReviewUnknown));
    let status = if blocked {
        DelegationStatus::Blocked
    } else if needs_evidence {
        DelegationStatus::NeedsEvidence
    } else {
        DelegationStatus::Ready
    };
    let (profile, reasoning) = child_floor(controller, request.kind);

    DelegationPlan {
        schema_version: DELEGATION_SCHEMA_VERSION,
        status,
        kind: request.kind,
        profile: (status == DelegationStatus::Ready).then_some(profile),
        reasoning: (status == DelegationStatus::Ready).then_some(reasoning),
        context_items,
        context_bytes,
        readable_resources: request.authority.readable.len(),
        writable_resources: request.authority.writable.len(),
        reasons,
    }
}

impl DelegationPlan {
    /// Enum/count-only explanation. No source, prompt, paths, model/provider names,
    /// credentials or tool output are rendered.
    pub fn render(&self) -> String {
        format!(
            "Delegation plan (no execution)\nSchema: {}\nStatus: {:?}\nKind: {:?}\nFloor: profile={:?}; reasoning={:?}\nContext: items={}; bytes={}\nAuthority: read={}; write={}\nReasons: {:?}\n",
            self.schema_version,
            self.status,
            self.kind,
            self.profile,
            self.reasoning,
            self.context_items,
            self.context_bytes,
            self.readable_resources,
            self.writable_resources,
            self.reasons,
        )
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DelegationAuthorization {
    pub ordinal: u8,
    pub kind: DelegationKind,
    pub profile: ProfileClass,
    pub reasoning: Reasoning,
    pub context: Vec<ContextReference>,
    pub authority: AuthorityBoundary,
    pub validation: BTreeSet<ValidationObligation>,
    pub parent_revalidation_required: bool,
    pub budget: ChildBudget,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChildOutcome {
    Completed,
    Failed,
    TimedOut,
    Refused,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChildValidation {
    NotRun,
    Passed,
    Failed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct HandoffEvidence {
    pub key: EvidenceKey,
    pub bytes: u32,
    pub digest: [u8; 32],
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BoundedHandoff {
    pub ordinal: u8,
    pub outcome: ChildOutcome,
    pub wall_seconds_used: u16,
    pub cost_units_used: u32,
    pub output_bytes: u32,
    pub evidence: Vec<HandoffEvidence>,
    pub changed_resources: BTreeSet<ResourceKey>,
    pub child_validation: ChildValidation,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HandoffViolation {
    OrdinalMismatch,
    WallTimeExceeded,
    CostExceeded,
    OutputExceeded,
    EvidenceLimitExceeded,
    InvalidEvidenceReference,
    DuplicateEvidenceReference,
    UnauthorizedWrite,
    MissingMechanicalValidation,
    UnexpectedValidationForReadOnly,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HandoffDisposition {
    /// The bounded child result is advisory and requires parent review/revalidation.
    RequiresParentReview,
    /// Failure is retained in the ledger and consumes the delegation budget.
    RetainedFailure,
    /// Unsafe/unbounded metadata is not retained; the violation itself is retained.
    ProtocolViolation(HandoffViolation),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DelegationRecordState {
    Authorized,
    HandoffRecorded(HandoffDisposition),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DelegationRecord {
    pub authorization: DelegationAuthorization,
    pub state: DelegationRecordState,
    pub handoff: Option<BoundedHandoff>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DelegationLedger {
    pub schema_version: u16,
    pub parent_archetype: Archetype,
    pub parent_risk: RiskLevel,
    pub parent_max_delegations: u8,
    pub records: Vec<DelegationRecord>,
}

impl DelegationLedger {
    pub fn new(controller: &AdaptiveController) -> Result<Self, DelegationError> {
        if controller.delegations_used != 0 {
            return Err(DelegationError::LedgerOutOfSync);
        }
        Ok(Self {
            schema_version: DELEGATION_SCHEMA_VERSION,
            parent_archetype: controller.archetype,
            parent_risk: controller.risk,
            parent_max_delegations: controller.budget.max_delegations,
            records: Vec::new(),
        })
    }

    fn check_parent(&self, controller: &AdaptiveController) -> Result<(), DelegationError> {
        if self.parent_archetype != controller.archetype
            || self.parent_risk != controller.risk
            || self.parent_max_delegations != controller.budget.max_delegations
            || usize::from(controller.delegations_used) != self.records.len()
        {
            return Err(DelegationError::ParentMismatch);
        }
        Ok(())
    }

    /// Consume one parent delegation slot only after a pure plan is Ready.
    /// This method grants no runtime authority beyond returning bounded metadata.
    pub fn authorize(
        &mut self,
        controller: &mut AdaptiveController,
        request: DelegationRequest,
    ) -> Result<DelegationAuthorization, DelegationError> {
        self.check_parent(controller)?;
        let plan = assess_delegation(controller, &request);
        if plan.status != DelegationStatus::Ready {
            return Err(DelegationError::PlanNotReady);
        }
        controller.delegations_used = controller
            .delegations_used
            .checked_add(1)
            .ok_or(DelegationError::LedgerOutOfSync)?;
        let authorization = DelegationAuthorization {
            ordinal: controller.delegations_used,
            kind: request.kind,
            profile: plan.profile.expect("ready delegation has profile"),
            reasoning: plan.reasoning.expect("ready delegation has reasoning"),
            context: request.context,
            authority: request.authority,
            validation: request.validation,
            parent_revalidation_required: request.parent_revalidation_required,
            budget: request.budget,
        };
        self.records.push(DelegationRecord {
            authorization: authorization.clone(),
            state: DelegationRecordState::Authorized,
            handoff: None,
        });
        Ok(authorization)
    }

    fn violation(
        record: &mut DelegationRecord,
        violation: HandoffViolation,
    ) -> Result<HandoffDisposition, DelegationError> {
        let disposition = HandoffDisposition::ProtocolViolation(violation);
        record.state = DelegationRecordState::HandoffRecorded(disposition);
        record.handoff = None;
        Err(DelegationError::HandoffProtocolViolation(violation))
    }

    /// Validate and retain a bounded handoff. A valid completed handoff never changes
    /// the parent controller state; it only becomes input to independent parent review.
    pub fn record_handoff(
        &mut self,
        controller: &AdaptiveController,
        handoff: BoundedHandoff,
    ) -> Result<HandoffDisposition, DelegationError> {
        self.check_parent(controller)?;
        let Some(record) = self
            .records
            .iter_mut()
            .find(|record| record.authorization.ordinal == handoff.ordinal)
        else {
            return Err(DelegationError::UnknownAuthorization);
        };
        if record.state != DelegationRecordState::Authorized {
            return Err(DelegationError::DuplicateHandoff);
        }
        if handoff.wall_seconds_used > record.authorization.budget.max_wall_seconds {
            return Self::violation(record, HandoffViolation::WallTimeExceeded);
        }
        if handoff.cost_units_used > record.authorization.budget.max_cost_units {
            return Self::violation(record, HandoffViolation::CostExceeded);
        }
        if handoff.output_bytes > record.authorization.budget.max_output_bytes {
            return Self::violation(record, HandoffViolation::OutputExceeded);
        }

        let mut evidence_keys = BTreeSet::new();
        let mut evidence_bytes = 0_u32;
        for evidence in &handoff.evidence {
            if evidence.bytes == 0 || evidence.digest == [0; 32] {
                return Self::violation(record, HandoffViolation::InvalidEvidenceReference);
            }
            if !evidence_keys.insert(evidence.key) {
                return Self::violation(record, HandoffViolation::DuplicateEvidenceReference);
            }
            evidence_bytes = evidence_bytes.saturating_add(evidence.bytes);
        }
        if handoff.evidence.len() > MAX_HANDOFF_EVIDENCE_ITEMS
            || evidence_bytes > MAX_HANDOFF_EVIDENCE_BYTES
        {
            return Self::violation(record, HandoffViolation::EvidenceLimitExceeded);
        }

        match record.authorization.kind {
            DelegationKind::ReadOnlyEvidence => {
                if !handoff.changed_resources.is_empty() {
                    return Self::violation(record, HandoffViolation::UnauthorizedWrite);
                }
                if handoff.child_validation != ChildValidation::NotRun {
                    return Self::violation(
                        record,
                        HandoffViolation::UnexpectedValidationForReadOnly,
                    );
                }
            }
            DelegationKind::MechanicalWorkspaceChange => {
                if !handoff
                    .changed_resources
                    .is_subset(&record.authorization.authority.writable)
                {
                    return Self::violation(record, HandoffViolation::UnauthorizedWrite);
                }
                if handoff.outcome == ChildOutcome::Completed
                    && handoff.child_validation != ChildValidation::Passed
                {
                    return Self::violation(record, HandoffViolation::MissingMechanicalValidation);
                }
            }
        }

        let disposition = if handoff.outcome == ChildOutcome::Completed {
            HandoffDisposition::RequiresParentReview
        } else {
            HandoffDisposition::RetainedFailure
        };
        record.handoff = Some(handoff);
        record.state = DelegationRecordState::HandoffRecorded(disposition);
        Ok(disposition)
    }

    pub fn remaining(&self, controller: &AdaptiveController) -> Result<u8, DelegationError> {
        self.check_parent(controller)?;
        Ok(controller.remaining_delegations())
    }

    /// Counter/status-only explanation. Evidence digests and opaque scope handles are not
    /// rendered even though the ledger retains them for verification.
    pub fn render(&self) -> String {
        let states: Vec<_> = self.records.iter().map(|record| record.state).collect();
        format!(
            "Delegation ledger (no execution)\nSchema: {}\nParent: archetype={:?}; risk={:?}\nBudget: delegations={}\nUsed: {}\nStates: {:?}\n",
            self.schema_version,
            self.parent_archetype,
            self.parent_risk,
            self.parent_max_delegations,
            self.records.len(),
            states,
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::adaptive::{ExecutionBudget, ValidationOutcome};
    use crate::playbook::Archetype;
    use crate::routing::assessment::{RoutingFacts, SafetyFact, TaskKind, assess};
    use crate::routing::engine::CapabilitySurface;
    use crate::workflow::{NativeSurface, ResourceCatalog, plan_workflow};

    fn controller(
        task: TaskKind,
        archetype: Archetype,
        safety: Vec<SafetyFact>,
        risk: Option<RiskLevel>,
    ) -> AdaptiveController {
        let assessment = assess(&RoutingFacts {
            task_hints: vec![task],
            risk_hint: risk,
            known_operations: vec![],
            safety,
        });
        let native = NativeSurface::verified_all();
        let workflow = plan_workflow(
            &assessment,
            Some(archetype),
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
            bytes: 128,
            digest: [7; 32],
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

    fn mechanical_request() -> DelegationRequest {
        DelegationRequest {
            origin: DelegationOrigin::Parent,
            kind: DelegationKind::MechanicalWorkspaceChange,
            context: context(),
            authority: AuthorityBoundary {
                readable: [ResourceKey(1), ResourceKey(2)].into_iter().collect(),
                writable: [ResourceKey(2)].into_iter().collect(),
                may_run_declared_validation: true,
            },
            validation: [ValidationObligation::RelevantTests].into_iter().collect(),
            parent_revalidation_required: true,
            safety: DelegationSafetyReview::verified_clear(),
            budget: ChildBudget::new(60, 200, 8192).unwrap(),
        }
    }

    #[test]
    fn safe_read_only_delegation_is_bounded_and_consumed_once() {
        let mut parent = controller(TaskKind::Inspect, Archetype::Inspection, vec![], None);
        let plan = assess_delegation(&parent, &read_only_request());
        assert_eq!(plan.status, DelegationStatus::Ready);
        assert_eq!(plan.profile, Some(parent.current_profile));
        assert_eq!(plan.reasoning, Some(parent.current_reasoning));

        let mut ledger = DelegationLedger::new(&parent).unwrap();
        let authorization = ledger.authorize(&mut parent, read_only_request()).unwrap();
        assert_eq!(authorization.ordinal, 1);
        assert_eq!(parent.delegations_used, 1);
        assert_eq!(ledger.remaining(&parent).unwrap(), 0);
        assert_eq!(
            assess_delegation(&parent, &read_only_request()).status,
            DelegationStatus::Blocked
        );
    }

    #[test]
    fn high_risk_and_explicit_hazards_never_become_cheap_safe() {
        let mut parent = controller(
            TaskKind::Edit,
            Archetype::FocusedBugFix,
            vec![],
            Some(RiskLevel::Low),
        );
        parent.risk = RiskLevel::High;
        let plan = assess_delegation(&parent, &read_only_request());
        assert_eq!(plan.status, DelegationStatus::Blocked);
        assert!(plan.reasons.contains(&DelegationReason::ParentHighRisk));

        let parent = controller(
            TaskKind::Edit,
            Archetype::FocusedBugFix,
            vec![],
            Some(RiskLevel::Low),
        );
        for hazard in [
            DelegationHazard::SecuritySensitive,
            DelegationHazard::ConcurrencySensitive,
            DelegationHazard::DestructiveMigration,
            DelegationHazard::AmbiguousApiContract,
            DelegationHazard::ConflictingEvidence,
        ] {
            let mut request = read_only_request();
            request.safety.hazards.insert(hazard);
            let plan = assess_delegation(&parent, &request);
            assert_eq!(plan.status, DelegationStatus::Blocked);
            assert!(plan.reasons.contains(&DelegationReason::Hazard(hazard)));
        }
    }

    #[test]
    fn unknown_safety_requires_evidence_and_nested_delegation_is_blocked() {
        let parent = controller(TaskKind::Inspect, Archetype::Inspection, vec![], None);
        let mut unknown = read_only_request();
        unknown.safety.state = SafetyReviewState::Unknown;
        let plan = assess_delegation(&parent, &unknown);
        assert_eq!(plan.status, DelegationStatus::NeedsEvidence);
        assert_eq!(
            plan.reasons,
            [DelegationReason::SafetyReviewUnknown]
                .into_iter()
                .collect()
        );

        let mut nested = read_only_request();
        nested.origin = DelegationOrigin::DelegatedChild;
        let plan = assess_delegation(&parent, &nested);
        assert_eq!(plan.status, DelegationStatus::Blocked);
        assert!(
            plan.reasons
                .contains(&DelegationReason::NestedDelegationForbidden)
        );
    }

    #[test]
    fn mechanical_authority_and_validation_are_explicit() {
        let parent = controller(
            TaskKind::Edit,
            Archetype::FocusedBugFix,
            vec![],
            Some(RiskLevel::Low),
        );
        let plan = assess_delegation(&parent, &mechanical_request());
        assert_eq!(plan.status, DelegationStatus::Ready);
        assert!(plan.profile.expect("ready profile") >= ProfileClass::Standard);

        let mut missing_write = mechanical_request();
        missing_write.authority.writable.clear();
        assert!(
            assess_delegation(&parent, &missing_write)
                .reasons
                .contains(&DelegationReason::MechanicalWriteScopeMissing)
        );

        let mut missing_validation = mechanical_request();
        missing_validation.validation.clear();
        assert!(
            assess_delegation(&parent, &missing_validation)
                .reasons
                .contains(&DelegationReason::MechanicalValidationMissing)
        );

        let mut no_parent_review = mechanical_request();
        no_parent_review.parent_revalidation_required = false;
        assert!(
            assess_delegation(&parent, &no_parent_review)
                .reasons
                .contains(&DelegationReason::ParentRevalidationMissing)
        );

        let mut outside_validation = mechanical_request();
        outside_validation.validation = [ValidationObligation::ReleaseRehearsal]
            .into_iter()
            .collect();
        assert!(
            assess_delegation(&parent, &outside_validation)
                .reasons
                .contains(&DelegationReason::ValidationOutsideParentContract)
        );

        let mut invalid_budget = mechanical_request();
        invalid_budget.budget.max_wall_seconds = MAX_DELEGATION_WALL_SECONDS + 1;
        assert!(
            assess_delegation(&parent, &invalid_budget)
                .reasons
                .contains(&DelegationReason::InvalidChildBudget)
        );
    }

    #[test]
    fn evidence_gate_allows_only_read_only_delegation() {
        let mut parent = controller(
            TaskKind::Edit,
            Archetype::FocusedBugFix,
            vec![],
            Some(RiskLevel::Low),
        );
        parent.start_attempt().unwrap();
        parent
            .observe_attempt(crate::adaptive::AttemptOutcome::Ambiguous)
            .unwrap();
        assert_eq!(
            parent.state,
            ControllerState::NeedsEvidence(crate::adaptive::AdaptiveTrigger::Ambiguity)
        );
        assert_eq!(
            assess_delegation(&parent, &read_only_request()).status,
            DelegationStatus::Ready
        );
        let mechanical = assess_delegation(&parent, &mechanical_request());
        assert_eq!(mechanical.status, DelegationStatus::Blocked);
        assert!(
            mechanical
                .reasons
                .contains(&DelegationReason::MechanicalDelegationDuringEvidenceGate)
        );
    }

    #[test]
    fn completed_handoff_requires_parent_review_and_never_completes_parent() {
        let mut parent = controller(TaskKind::Inspect, Archetype::Inspection, vec![], None);
        let mut ledger = DelegationLedger::new(&parent).unwrap();
        let authorization = ledger.authorize(&mut parent, read_only_request()).unwrap();
        let handoff = BoundedHandoff {
            ordinal: authorization.ordinal,
            outcome: ChildOutcome::Completed,
            wall_seconds_used: 5,
            cost_units_used: 10,
            output_bytes: 512,
            evidence: vec![HandoffEvidence {
                key: EvidenceKey(10),
                bytes: 128,
                digest: [9; 32],
            }],
            changed_resources: BTreeSet::new(),
            child_validation: ChildValidation::NotRun,
        };
        assert_eq!(
            ledger.record_handoff(&parent, handoff).unwrap(),
            HandoffDisposition::RequiresParentReview
        );
        assert_eq!(parent.state, ControllerState::Ready);
        assert_ne!(parent.state, ControllerState::Completed);
    }

    #[test]
    fn mechanical_handoff_cannot_write_outside_scope_or_skip_validation() {
        let mut parent = controller(
            TaskKind::Edit,
            Archetype::FocusedBugFix,
            vec![],
            Some(RiskLevel::Low),
        );
        let mut ledger = DelegationLedger::new(&parent).unwrap();
        let authorization = ledger.authorize(&mut parent, mechanical_request()).unwrap();
        let invalid = BoundedHandoff {
            ordinal: authorization.ordinal,
            outcome: ChildOutcome::Completed,
            wall_seconds_used: 5,
            cost_units_used: 20,
            output_bytes: 512,
            evidence: vec![],
            changed_resources: [ResourceKey(99)].into_iter().collect(),
            child_validation: ChildValidation::Passed,
        };
        assert_eq!(
            ledger.record_handoff(&parent, invalid),
            Err(DelegationError::HandoffProtocolViolation(
                HandoffViolation::UnauthorizedWrite
            ))
        );
        assert_eq!(
            ledger.records[0].state,
            DelegationRecordState::HandoffRecorded(HandoffDisposition::ProtocolViolation(
                HandoffViolation::UnauthorizedWrite
            ))
        );

        let mut parent = controller(
            TaskKind::Edit,
            Archetype::FocusedBugFix,
            vec![],
            Some(RiskLevel::Low),
        );
        let mut ledger = DelegationLedger::new(&parent).unwrap();
        let authorization = ledger.authorize(&mut parent, mechanical_request()).unwrap();
        let invalid = BoundedHandoff {
            ordinal: authorization.ordinal,
            outcome: ChildOutcome::Completed,
            wall_seconds_used: 5,
            cost_units_used: 20,
            output_bytes: 512,
            evidence: vec![],
            changed_resources: [ResourceKey(2)].into_iter().collect(),
            child_validation: ChildValidation::NotRun,
        };
        assert_eq!(
            ledger.record_handoff(&parent, invalid),
            Err(DelegationError::HandoffProtocolViolation(
                HandoffViolation::MissingMechanicalValidation
            ))
        );
    }

    #[test]
    fn failed_child_is_retained_and_consumes_budget() {
        let mut parent = controller(TaskKind::Inspect, Archetype::Inspection, vec![], None);
        let mut ledger = DelegationLedger::new(&parent).unwrap();
        let authorization = ledger.authorize(&mut parent, read_only_request()).unwrap();
        let handoff = BoundedHandoff {
            ordinal: authorization.ordinal,
            outcome: ChildOutcome::TimedOut,
            wall_seconds_used: authorization.budget.max_wall_seconds,
            cost_units_used: 50,
            output_bytes: 64,
            evidence: vec![],
            changed_resources: BTreeSet::new(),
            child_validation: ChildValidation::NotRun,
        };
        assert_eq!(
            ledger.record_handoff(&parent, handoff).unwrap(),
            HandoffDisposition::RetainedFailure
        );
        assert_eq!(parent.delegations_used, 1);
        assert_eq!(ledger.remaining(&parent).unwrap(), 0);
    }

    #[test]
    fn over_budget_handoff_is_a_retained_protocol_failure_without_payload() {
        let mut parent = controller(TaskKind::Inspect, Archetype::Inspection, vec![], None);
        let mut ledger = DelegationLedger::new(&parent).unwrap();
        let authorization = ledger.authorize(&mut parent, read_only_request()).unwrap();
        let handoff = BoundedHandoff {
            ordinal: authorization.ordinal,
            outcome: ChildOutcome::Completed,
            wall_seconds_used: authorization.budget.max_wall_seconds + 1,
            cost_units_used: 1,
            output_bytes: 1,
            evidence: vec![],
            changed_resources: BTreeSet::new(),
            child_validation: ChildValidation::NotRun,
        };
        assert_eq!(
            ledger.record_handoff(&parent, handoff),
            Err(DelegationError::HandoffProtocolViolation(
                HandoffViolation::WallTimeExceeded
            ))
        );
        assert!(ledger.records[0].handoff.is_none());
        assert_eq!(
            ledger.records[0].state,
            DelegationRecordState::HandoffRecorded(HandoffDisposition::ProtocolViolation(
                HandoffViolation::WallTimeExceeded
            ))
        );
    }

    #[test]
    fn parent_running_and_awaiting_validation_are_not_delegation_states() {
        let mut parent = controller(TaskKind::Inspect, Archetype::Inspection, vec![], None);
        parent.start_attempt().unwrap();
        assert!(
            assess_delegation(&parent, &read_only_request())
                .reasons
                .contains(&DelegationReason::ParentStateNotEligible)
        );
        parent
            .observe_attempt(crate::adaptive::AttemptOutcome::Completed)
            .unwrap();
        assert!(
            assess_delegation(&parent, &read_only_request())
                .reasons
                .contains(&DelegationReason::ParentStateNotEligible)
        );
        parent
            .observe_validation(ValidationOutcome::Passed)
            .unwrap();
        assert_eq!(parent.state, ControllerState::Completed);
        assert_eq!(
            assess_delegation(&parent, &read_only_request()).status,
            DelegationStatus::Blocked
        );
    }

    #[test]
    fn render_is_metadata_only() {
        let parent = controller(TaskKind::Inspect, Archetype::Inspection, vec![], None);
        let plan = assess_delegation(&parent, &read_only_request());
        let rendered = plan.render();
        assert!(rendered.contains("Delegation plan (no execution)"));
        assert!(rendered.contains("Context: items=1; bytes=128"));
        assert!(!rendered.contains("EvidenceKey"));
        let ledger = DelegationLedger::new(&parent).unwrap();
        assert!(ledger.render().contains("Delegation ledger (no execution)"));
    }
}
