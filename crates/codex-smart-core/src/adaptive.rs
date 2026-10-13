//! Pure bounded adaptive-execution state machine.
//!
//! This module grants no model, tool, filesystem, network, delegation or retry authority.
//! It consumes an already-reviewed workflow plan plus validation readiness and produces
//! typed next-state decisions. Runtime adapters remain separate work.

use crate::playbook::{Archetype, EscalationTrigger, ProfileClass, builtin};
use crate::routing::Reasoning;
use crate::routing::assessment::RiskLevel;
use crate::workflow::{PlanStatus, ValidationReadiness, ValidationRecipe, WorkflowPlan};
use std::collections::BTreeSet;

pub const ADAPTIVE_SCHEMA_VERSION: u16 = 1;
pub const MAX_ATTEMPTS: u8 = 4;
pub const MAX_RETRIES: u8 = 3;
pub const MAX_DELEGATIONS: u8 = 1;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ExecutionBudget {
    pub max_attempts: u8,
    pub max_retries: u8,
    /// Reserved ceiling for the later bounded-delegation stage. This controller does
    /// not execute or authorize delegation.
    pub max_delegations: u8,
}

impl ExecutionBudget {
    pub fn new(
        max_attempts: u8,
        max_retries: u8,
        max_delegations: u8,
    ) -> Result<Self, AdaptiveError> {
        if max_attempts == 0 || max_attempts > MAX_ATTEMPTS {
            return Err(AdaptiveError::InvalidBudget);
        }
        if max_retries > MAX_RETRIES || max_retries >= max_attempts {
            return Err(AdaptiveError::InvalidBudget);
        }
        if max_delegations > MAX_DELEGATIONS {
            return Err(AdaptiveError::InvalidBudget);
        }
        Ok(Self {
            max_attempts,
            max_retries,
            max_delegations,
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum AdaptiveTrigger {
    RuntimeFailure,
    Timeout,
    Ambiguity,
    MissingRequiredContext,
    RequiredCapabilityUnknown,
    RequiredCapabilityUnavailable,
    ValidationFailure,
    SafetyEvidenceConflict,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AttemptOutcome {
    Completed,
    RuntimeFailure,
    Timeout,
    Ambiguous,
    MissingRequiredContext,
    RequiredCapabilityUnknown,
    RequiredCapabilityUnavailable,
    SafetyEvidenceConflict,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ValidationOutcome {
    Passed,
    Failed,
    Blocked,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EvidenceResolution {
    Resolved,
    StillUnknown,
    Unavailable,
    Conflict,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BlockReason {
    RequiredCapabilityUnavailable,
    SafetyEvidenceConflict,
    ValidationBlocked,
    EvidenceUnavailable,
    EvidenceConflict,
    TriggerNotAllowed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ControllerState {
    Ready,
    Running,
    AwaitingValidation,
    NeedsEvidence(AdaptiveTrigger),
    Completed,
    Blocked(BlockReason),
    Exhausted,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AdaptiveError {
    InvalidBudget,
    WorkflowNotReady,
    ValidationNotReady,
    MissingWorkflowIdentity,
    InvalidState,
    AttemptBudgetExhausted,
    RetryBudgetExhausted,
    TriggerNotAllowed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AttemptAuthorization {
    pub ordinal: u8,
    pub profile: ProfileClass,
    pub reasoning: Reasoning,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AttemptRecord {
    pub ordinal: u8,
    pub profile: ProfileClass,
    pub reasoning: Reasoning,
    pub outcome: Option<AttemptOutcome>,
    pub validation: Option<ValidationOutcome>,
    pub trigger: Option<AdaptiveTrigger>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AdaptiveController {
    pub schema_version: u16,
    pub archetype: Archetype,
    pub risk: RiskLevel,
    pub floor_profile: ProfileClass,
    pub floor_reasoning: Reasoning,
    pub current_profile: ProfileClass,
    pub current_reasoning: Reasoning,
    pub budget: ExecutionBudget,
    pub attempts_started: u8,
    pub retries_used: u8,
    /// Delegation is intentionally not implemented in #43. Keeping the observed count
    /// explicit prevents later work from hiding handoffs outside the lifecycle budget.
    pub delegations_used: u8,
    pub state: ControllerState,
    pub allowed_triggers: BTreeSet<AdaptiveTrigger>,
    pub history: Vec<AttemptRecord>,
}

fn mapped_trigger(trigger: EscalationTrigger) -> AdaptiveTrigger {
    match trigger {
        EscalationTrigger::Ambiguity => AdaptiveTrigger::Ambiguity,
        EscalationTrigger::MissingRequiredContext => AdaptiveTrigger::MissingRequiredContext,
        EscalationTrigger::RequiredCapabilityUnknown => AdaptiveTrigger::RequiredCapabilityUnknown,
        EscalationTrigger::RequiredCapabilityUnavailable => {
            AdaptiveTrigger::RequiredCapabilityUnavailable
        }
        EscalationTrigger::ValidationFailure => AdaptiveTrigger::ValidationFailure,
        EscalationTrigger::SafetyEvidenceConflict => AdaptiveTrigger::SafetyEvidenceConflict,
    }
}

fn next_profile(profile: ProfileClass) -> ProfileClass {
    match profile {
        ProfileClass::Economy => ProfileClass::Standard,
        ProfileClass::Standard | ProfileClass::Strong => ProfileClass::Strong,
    }
}

fn reasoning_for(profile: ProfileClass, current: Reasoning) -> Reasoning {
    match profile {
        ProfileClass::Strong => Reasoning::High,
        ProfileClass::Economy | ProfileClass::Standard => current,
    }
}

fn max_reasoning(left: Reasoning, right: Reasoning) -> Reasoning {
    if left == Reasoning::High || right == Reasoning::High {
        Reasoning::High
    } else {
        Reasoning::Medium
    }
}

impl AdaptiveController {
    pub fn from_workflow(
        workflow: &WorkflowPlan,
        validation: &ValidationRecipe,
        budget: ExecutionBudget,
    ) -> Result<Self, AdaptiveError> {
        if workflow.status != PlanStatus::Ready {
            return Err(AdaptiveError::WorkflowNotReady);
        }
        if validation.status != ValidationReadiness::Ready {
            return Err(AdaptiveError::ValidationNotReady);
        }
        let archetype = workflow
            .selection
            .archetype
            .ok_or(AdaptiveError::MissingWorkflowIdentity)?;
        let profile = workflow
            .selection
            .profile
            .ok_or(AdaptiveError::MissingWorkflowIdentity)?;
        let reasoning = workflow
            .selection
            .reasoning
            .ok_or(AdaptiveError::MissingWorkflowIdentity)?;
        let contract = builtin(archetype);
        let mut allowed_triggers: BTreeSet<_> = contract
            .escalation
            .iter()
            .copied()
            .map(mapped_trigger)
            .collect();
        // Runtime process failure and timeout are controller-level observations rather
        // than playbook semantics. They are always explicit and budgeted.
        allowed_triggers.insert(AdaptiveTrigger::RuntimeFailure);
        allowed_triggers.insert(AdaptiveTrigger::Timeout);

        Ok(Self {
            schema_version: ADAPTIVE_SCHEMA_VERSION,
            archetype,
            risk: workflow.selection.effective_risk,
            floor_profile: profile,
            floor_reasoning: reasoning,
            current_profile: profile,
            current_reasoning: reasoning,
            budget,
            attempts_started: 0,
            retries_used: 0,
            delegations_used: 0,
            state: ControllerState::Ready,
            allowed_triggers,
            history: Vec::new(),
        })
    }

    pub fn start_attempt(&mut self) -> Result<AttemptAuthorization, AdaptiveError> {
        if self.state != ControllerState::Ready {
            return Err(AdaptiveError::InvalidState);
        }
        if self.attempts_started >= self.budget.max_attempts {
            self.state = ControllerState::Exhausted;
            return Err(AdaptiveError::AttemptBudgetExhausted);
        }
        self.attempts_started += 1;
        let authorization = AttemptAuthorization {
            ordinal: self.attempts_started,
            profile: self.current_profile,
            reasoning: self.current_reasoning,
        };
        self.history.push(AttemptRecord {
            ordinal: authorization.ordinal,
            profile: authorization.profile,
            reasoning: authorization.reasoning,
            outcome: None,
            validation: None,
            trigger: None,
        });
        self.state = ControllerState::Running;
        Ok(authorization)
    }

    fn current_record_mut(&mut self) -> Result<&mut AttemptRecord, AdaptiveError> {
        self.history.last_mut().ok_or(AdaptiveError::InvalidState)
    }

    fn schedule_retry(&mut self, trigger: AdaptiveTrigger) -> Result<(), AdaptiveError> {
        if !self.allowed_triggers.contains(&trigger) {
            self.state = ControllerState::Blocked(BlockReason::TriggerNotAllowed);
            return Err(AdaptiveError::TriggerNotAllowed);
        }
        if self.attempts_started >= self.budget.max_attempts {
            self.state = ControllerState::Exhausted;
            return Err(AdaptiveError::AttemptBudgetExhausted);
        }
        if self.retries_used >= self.budget.max_retries {
            self.state = ControllerState::Exhausted;
            return Err(AdaptiveError::RetryBudgetExhausted);
        }

        self.retries_used += 1;
        let raised = next_profile(self.current_profile).max(self.floor_profile);
        self.current_profile = raised;
        self.current_reasoning = max_reasoning(
            reasoning_for(raised, self.current_reasoning),
            self.floor_reasoning,
        );
        self.state = ControllerState::Ready;
        Ok(())
    }

    pub fn observe_attempt(&mut self, outcome: AttemptOutcome) -> Result<(), AdaptiveError> {
        if self.state != ControllerState::Running {
            return Err(AdaptiveError::InvalidState);
        }

        let trigger = match outcome {
            AttemptOutcome::Completed => None,
            AttemptOutcome::RuntimeFailure => Some(AdaptiveTrigger::RuntimeFailure),
            AttemptOutcome::Timeout => Some(AdaptiveTrigger::Timeout),
            AttemptOutcome::Ambiguous => Some(AdaptiveTrigger::Ambiguity),
            AttemptOutcome::MissingRequiredContext => Some(AdaptiveTrigger::MissingRequiredContext),
            AttemptOutcome::RequiredCapabilityUnknown => {
                Some(AdaptiveTrigger::RequiredCapabilityUnknown)
            }
            AttemptOutcome::RequiredCapabilityUnavailable => {
                Some(AdaptiveTrigger::RequiredCapabilityUnavailable)
            }
            AttemptOutcome::SafetyEvidenceConflict => Some(AdaptiveTrigger::SafetyEvidenceConflict),
        };

        {
            let record = self.current_record_mut()?;
            record.outcome = Some(outcome);
            record.trigger = trigger;
        }

        match outcome {
            AttemptOutcome::Completed => {
                self.state = ControllerState::AwaitingValidation;
                Ok(())
            }
            AttemptOutcome::RuntimeFailure | AttemptOutcome::Timeout => {
                self.schedule_retry(trigger.expect("runtime failure has trigger"))
            }
            AttemptOutcome::Ambiguous
            | AttemptOutcome::MissingRequiredContext
            | AttemptOutcome::RequiredCapabilityUnknown => {
                let trigger = trigger.expect("evidence outcome has trigger");
                if !self.allowed_triggers.contains(&trigger) {
                    self.state = ControllerState::Blocked(BlockReason::TriggerNotAllowed);
                    return Err(AdaptiveError::TriggerNotAllowed);
                }
                self.state = ControllerState::NeedsEvidence(trigger);
                Ok(())
            }
            AttemptOutcome::RequiredCapabilityUnavailable => {
                self.state = ControllerState::Blocked(BlockReason::RequiredCapabilityUnavailable);
                Ok(())
            }
            AttemptOutcome::SafetyEvidenceConflict => {
                self.state = ControllerState::Blocked(BlockReason::SafetyEvidenceConflict);
                Ok(())
            }
        }
    }

    pub fn resolve_evidence(
        &mut self,
        resolution: EvidenceResolution,
    ) -> Result<(), AdaptiveError> {
        let ControllerState::NeedsEvidence(trigger) = self.state else {
            return Err(AdaptiveError::InvalidState);
        };
        match resolution {
            EvidenceResolution::Resolved => self.schedule_retry(trigger),
            EvidenceResolution::StillUnknown => Ok(()),
            EvidenceResolution::Unavailable => {
                self.state = ControllerState::Blocked(BlockReason::EvidenceUnavailable);
                Ok(())
            }
            EvidenceResolution::Conflict => {
                self.state = ControllerState::Blocked(BlockReason::EvidenceConflict);
                Ok(())
            }
        }
    }

    pub fn observe_validation(&mut self, outcome: ValidationOutcome) -> Result<(), AdaptiveError> {
        if self.state != ControllerState::AwaitingValidation {
            return Err(AdaptiveError::InvalidState);
        }
        self.current_record_mut()?.validation = Some(outcome);
        match outcome {
            ValidationOutcome::Passed => {
                self.state = ControllerState::Completed;
                Ok(())
            }
            ValidationOutcome::Failed => {
                self.current_record_mut()?.trigger = Some(AdaptiveTrigger::ValidationFailure);
                self.schedule_retry(AdaptiveTrigger::ValidationFailure)
            }
            ValidationOutcome::Blocked => {
                self.state = ControllerState::Blocked(BlockReason::ValidationBlocked);
                Ok(())
            }
        }
    }

    pub fn remaining_attempts(&self) -> u8 {
        self.budget
            .max_attempts
            .saturating_sub(self.attempts_started)
    }

    pub fn remaining_retries(&self) -> u8 {
        self.budget.max_retries.saturating_sub(self.retries_used)
    }

    pub fn remaining_delegations(&self) -> u8 {
        self.budget
            .max_delegations
            .saturating_sub(self.delegations_used)
    }

    /// Enum/counter-only explanation. It intentionally contains no prompts, source,
    /// paths, provider/model names, credentials, tool output or execution authority.
    pub fn render(&self) -> String {
        format!(
            "Adaptive execution contract (no execution)\nSchema: {}\nWorkflow: {:?}\nRisk: {:?}\nState: {:?}\nFloor: profile={:?}; reasoning={:?}\nCurrent: profile={:?}; reasoning={:?}\nBudget: attempts={}; retries={}; delegations={} (delegation not implemented)\nUsed: attempts={}; retries={}; delegations={}\nAllowed triggers: {:?}\nHistory: {:?}\n",
            self.schema_version,
            self.archetype,
            self.risk,
            self.state,
            self.floor_profile,
            self.floor_reasoning,
            self.current_profile,
            self.current_reasoning,
            self.budget.max_attempts,
            self.budget.max_retries,
            self.budget.max_delegations,
            self.attempts_started,
            self.retries_used,
            self.delegations_used,
            self.allowed_triggers,
            self.history,
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::playbook::Archetype;
    use crate::routing::assessment::{RoutingFacts, SafetyFact, TaskKind, assess};
    use crate::routing::engine::CapabilitySurface;
    use crate::workflow::{NativeSurface, ResourceCatalog, plan_workflow};

    fn ready_plan(
        task: TaskKind,
        archetype: Option<Archetype>,
        safety: Vec<SafetyFact>,
    ) -> (WorkflowPlan, ValidationRecipe) {
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
        (workflow, validation)
    }

    #[test]
    fn inspection_can_start_economy_but_security_starts_strong_high() {
        let (inspection, validation) = ready_plan(TaskKind::Inspect, None, vec![]);
        let mut controller = AdaptiveController::from_workflow(
            &inspection,
            &validation,
            ExecutionBudget::new(3, 2, 1).unwrap(),
        )
        .unwrap();
        let first = controller.start_attempt().unwrap();
        assert_eq!(first.profile, ProfileClass::Economy);
        assert_eq!(first.reasoning, Reasoning::Medium);

        let (security, validation) =
            ready_plan(TaskKind::Edit, None, vec![SafetyFact::SecuritySensitive]);
        let mut controller = AdaptiveController::from_workflow(
            &security,
            &validation,
            ExecutionBudget::new(2, 1, 0).unwrap(),
        )
        .unwrap();
        let first = controller.start_attempt().unwrap();
        assert_eq!(first.profile, ProfileClass::Strong);
        assert_eq!(first.reasoning, Reasoning::High);
    }

    #[test]
    fn runtime_failure_is_retained_and_escalates_monotonically() {
        let (workflow, validation) = ready_plan(TaskKind::Inspect, None, vec![]);
        let mut controller = AdaptiveController::from_workflow(
            &workflow,
            &validation,
            ExecutionBudget::new(3, 2, 1).unwrap(),
        )
        .unwrap();

        assert_eq!(
            controller.start_attempt().unwrap().profile,
            ProfileClass::Economy
        );
        controller
            .observe_attempt(AttemptOutcome::RuntimeFailure)
            .unwrap();
        assert_eq!(controller.state, ControllerState::Ready);
        assert_eq!(controller.retries_used, 1);
        assert_eq!(controller.current_profile, ProfileClass::Standard);
        assert_eq!(
            controller.history[0].outcome,
            Some(AttemptOutcome::RuntimeFailure)
        );
        assert_eq!(
            controller.history[0].trigger,
            Some(AdaptiveTrigger::RuntimeFailure)
        );

        assert_eq!(
            controller.start_attempt().unwrap().profile,
            ProfileClass::Standard
        );
        controller
            .observe_attempt(AttemptOutcome::Completed)
            .unwrap();
        controller
            .observe_validation(ValidationOutcome::Passed)
            .unwrap();
        assert_eq!(controller.state, ControllerState::Completed);
        assert_eq!(controller.history.len(), 2);
    }

    #[test]
    fn validation_failure_escalates_standard_to_strong_high() {
        let (workflow, validation) = ready_plan(
            TaskKind::Edit,
            Some(Archetype::FeatureImplementation),
            vec![],
        );
        let mut controller = AdaptiveController::from_workflow(
            &workflow,
            &validation,
            ExecutionBudget::new(2, 1, 0).unwrap(),
        )
        .unwrap();

        assert_eq!(
            controller.start_attempt().unwrap().profile,
            ProfileClass::Standard
        );
        controller
            .observe_attempt(AttemptOutcome::Completed)
            .unwrap();
        controller
            .observe_validation(ValidationOutcome::Failed)
            .unwrap();
        assert_eq!(controller.current_profile, ProfileClass::Strong);
        assert_eq!(controller.current_reasoning, Reasoning::High);
        assert_eq!(controller.state, ControllerState::Ready);
        assert_eq!(
            controller.history[0].validation,
            Some(ValidationOutcome::Failed)
        );
    }

    #[test]
    fn evidence_is_explicit_and_never_silently_assumed() {
        let (workflow, validation) = ready_plan(TaskKind::Inspect, None, vec![]);
        let mut controller = AdaptiveController::from_workflow(
            &workflow,
            &validation,
            ExecutionBudget::new(3, 2, 0).unwrap(),
        )
        .unwrap();
        controller.start_attempt().unwrap();
        controller
            .observe_attempt(AttemptOutcome::Ambiguous)
            .unwrap();
        assert_eq!(
            controller.state,
            ControllerState::NeedsEvidence(AdaptiveTrigger::Ambiguity)
        );
        controller
            .resolve_evidence(EvidenceResolution::StillUnknown)
            .unwrap();
        assert_eq!(
            controller.state,
            ControllerState::NeedsEvidence(AdaptiveTrigger::Ambiguity)
        );
        controller
            .resolve_evidence(EvidenceResolution::Resolved)
            .unwrap();
        assert_eq!(controller.state, ControllerState::Ready);
        assert_eq!(controller.retries_used, 1);
        assert_eq!(controller.current_profile, ProfileClass::Standard);
    }

    #[test]
    fn playbook_does_not_gain_unlisted_escalation_triggers() {
        let (workflow, validation) = ready_plan(TaskKind::Inspect, None, vec![]);
        let mut controller = AdaptiveController::from_workflow(
            &workflow,
            &validation,
            ExecutionBudget::new(2, 1, 0).unwrap(),
        )
        .unwrap();
        controller.start_attempt().unwrap();
        assert_eq!(
            controller.observe_attempt(AttemptOutcome::RequiredCapabilityUnknown),
            Err(AdaptiveError::TriggerNotAllowed)
        );
        assert_eq!(
            controller.state,
            ControllerState::Blocked(BlockReason::TriggerNotAllowed)
        );
        assert_eq!(controller.retries_used, 0);
    }

    #[test]
    fn unavailable_or_conflicting_evidence_blocks_without_retry() {
        let (workflow, validation) = ready_plan(
            TaskKind::Edit,
            Some(Archetype::FeatureImplementation),
            vec![],
        );
        let mut unavailable = AdaptiveController::from_workflow(
            &workflow,
            &validation,
            ExecutionBudget::new(3, 2, 0).unwrap(),
        )
        .unwrap();
        unavailable.start_attempt().unwrap();
        unavailable
            .observe_attempt(AttemptOutcome::RequiredCapabilityUnavailable)
            .unwrap();
        assert_eq!(
            unavailable.state,
            ControllerState::Blocked(BlockReason::RequiredCapabilityUnavailable)
        );
        assert_eq!(unavailable.retries_used, 0);

        let (security, validation) =
            ready_plan(TaskKind::Edit, None, vec![SafetyFact::SecuritySensitive]);
        let mut conflict = AdaptiveController::from_workflow(
            &security,
            &validation,
            ExecutionBudget::new(2, 1, 0).unwrap(),
        )
        .unwrap();
        conflict.start_attempt().unwrap();
        conflict
            .observe_attempt(AttemptOutcome::SafetyEvidenceConflict)
            .unwrap();
        assert_eq!(
            conflict.state,
            ControllerState::Blocked(BlockReason::SafetyEvidenceConflict)
        );
        assert_eq!(conflict.retries_used, 0);
    }

    #[test]
    fn exhausted_budget_is_terminal_and_no_hidden_retry_occurs() {
        let (workflow, validation) = ready_plan(TaskKind::Inspect, None, vec![]);
        let mut controller = AdaptiveController::from_workflow(
            &workflow,
            &validation,
            ExecutionBudget::new(2, 1, 0).unwrap(),
        )
        .unwrap();
        controller.start_attempt().unwrap();
        controller.observe_attempt(AttemptOutcome::Timeout).unwrap();
        controller.start_attempt().unwrap();
        assert_eq!(
            controller.observe_attempt(AttemptOutcome::RuntimeFailure),
            Err(AdaptiveError::AttemptBudgetExhausted)
        );
        assert_eq!(controller.state, ControllerState::Exhausted);
        assert_eq!(controller.attempts_started, 2);
        assert_eq!(controller.retries_used, 1);
        assert_eq!(controller.history.len(), 2);
    }

    #[test]
    fn invalid_budget_and_unready_workflow_fail_closed() {
        assert_eq!(
            ExecutionBudget::new(0, 0, 0),
            Err(AdaptiveError::InvalidBudget)
        );
        assert_eq!(
            ExecutionBudget::new(MAX_ATTEMPTS + 1, 0, 0),
            Err(AdaptiveError::InvalidBudget)
        );
        assert_eq!(
            ExecutionBudget::new(2, 2, 0),
            Err(AdaptiveError::InvalidBudget)
        );
        assert_eq!(
            ExecutionBudget::new(2, 1, MAX_DELEGATIONS + 1),
            Err(AdaptiveError::InvalidBudget)
        );

        let assessment = assess(&RoutingFacts {
            known_operations: vec![TaskKind::Edit],
            ..Default::default()
        });
        let workflow = plan_workflow(
            &assessment,
            None,
            &NativeSurface::verified_all(),
            &CapabilitySurface::default(),
            &ResourceCatalog::default(),
        );
        assert_eq!(workflow.status, PlanStatus::NeedsEvidence);
        let validation = ValidationRecipe {
            status: ValidationReadiness::Ready,
            checks: vec![],
        };
        assert_eq!(
            AdaptiveController::from_workflow(
                &workflow,
                &validation,
                ExecutionBudget::new(2, 1, 0).unwrap()
            ),
            Err(AdaptiveError::WorkflowNotReady)
        );
    }

    #[test]
    fn render_is_bounded_and_carries_no_execution_authority() {
        let (workflow, validation) = ready_plan(TaskKind::Inspect, None, vec![]);
        let controller = AdaptiveController::from_workflow(
            &workflow,
            &validation,
            ExecutionBudget::new(3, 2, 1).unwrap(),
        )
        .unwrap();
        let rendered = controller.render();
        for expected in [
            "Adaptive execution contract (no execution)",
            "Workflow: Inspection",
            "Floor: profile=Economy; reasoning=Medium",
            "delegations=1 (delegation not implemented)",
            "Allowed triggers:",
        ] {
            assert!(rendered.contains(expected), "missing {expected}");
        }
        for forbidden in [
            "/home/",
            "Bearer ",
            "api_key",
            "prompt",
            "source text",
            "gpt-",
            "execute ",
        ] {
            assert!(
                !rendered
                    .to_ascii_lowercase()
                    .contains(&forbidden.to_ascii_lowercase()),
                "render leaked {forbidden}"
            );
        }
    }

    #[test]
    fn validation_readiness_is_a_precondition() {
        let (workflow, _) = ready_plan(TaskKind::Inspect, None, vec![]);
        let validation = ValidationRecipe {
            status: ValidationReadiness::NeedsEvidence,
            checks: vec![],
        };
        assert_eq!(
            AdaptiveController::from_workflow(
                &workflow,
                &validation,
                ExecutionBudget::new(2, 1, 0).unwrap()
            ),
            Err(AdaptiveError::ValidationNotReady)
        );
    }

    #[test]
    fn profile_and_reasoning_never_drop_below_workflow_floor() {
        let (workflow, validation) = ready_plan(
            TaskKind::Edit,
            Some(Archetype::FeatureImplementation),
            vec![],
        );
        let mut controller = AdaptiveController::from_workflow(
            &workflow,
            &validation,
            ExecutionBudget::new(3, 2, 0).unwrap(),
        )
        .unwrap();
        controller.start_attempt().unwrap();
        controller
            .observe_attempt(AttemptOutcome::RuntimeFailure)
            .unwrap();
        assert_eq!(controller.floor_profile, ProfileClass::Standard);
        assert_eq!(controller.floor_reasoning, Reasoning::Medium);
        assert_eq!(controller.current_profile, ProfileClass::Strong);
        assert_eq!(controller.current_reasoning, Reasoning::High);
    }
}
