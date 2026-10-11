//! Finite evidence/verification planning. Codex owns how obligations are satisfied.
use super::assessment::{Ambiguity, Reason, RiskLevel, TaskKind};
use super::engine::{Backend, DecisionReason, RouterDecision};
use super::reasoning::{ReasoningDecision, Support};
use std::collections::BTreeSet;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum RouteMode {
    Proceed,
    ProceedWithFallback,
    NeedsEvidence,
    Blocked,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Obligation {
    ImpactAnalysis,
    RelevantTests,
    BuildOrStaticValidation,
    SymbolReferences,
    AdditionalVerification,
    SecurityReview,
    MigrationRollbackValidation,
    ConcurrencyReview,
    ExternalReferenceValidation,
    LocalRepositoryEvidence,
    RemoteStateValidation,
    ReasoningCompatibilityValidation,
}

/// A caller assertion about a prerequisite, not a tool-presence flag.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EvidenceState {
    Satisfied,
    Unknown,
    /// Cannot be satisfied under the current contract; no rescue backend is guessed.
    Unavailable,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RepositoryRequirement {
    LocalHistory,
    CurrentRemoteState,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ReasoningApplication {
    /// Candidate is advisory; existing launch is not applying synthetic settings.
    Passthrough,
    RequiredSyntheticOverride,
    /// Compatibility of the user's own effort (not the automatic candidate).
    UserOwned(Support),
}

/// Already collected prerequisites, independent of capability readiness.
/// Verification entries explicitly gate proceeding; absent entries do not certify
/// obligations completed. Context insufficiency never removes an obligation.
#[derive(Debug, Clone)]
pub struct PlanEvidence {
    pub native_fallback: EvidenceState,
    pub external_reference: EvidenceState,
    pub repository_requirement: RepositoryRequirement,
    pub remote_state: EvidenceState,
    pub verification: Vec<(Obligation, EvidenceState)>,
    pub context_sufficient: bool,
    pub reasoning_application: ReasoningApplication,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum PlanReason {
    Router(DecisionReason),
    RequiredVerificationPreserved,
    NativeFallbackSelected,
    NativeFallbackUnknown,
    NativeFallbackUnavailable,
    MissingEvidence(Obligation),
    UnavailableEvidence(Obligation),
    ContextInsufficient,
    ReasoningCompatibilityUnknown,
    ReasoningCompatibilityUnsupported,
    UserOwnedReasoning,
    MoreEvidenceRequired,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RoutingPlan {
    pub mode: RouteMode,
    /// True means the plan offers native evidence as a replacement path, not execution.
    pub native_fallback: bool,
    pub obligations: BTreeSet<Obligation>,
    pub reasons: BTreeSet<PlanReason>,
    pub reasoning_status: Support,
}
impl RoutingPlan {
    fn require_evidence(&mut self, obligation: Obligation, state: EvidenceState) {
        self.obligations.insert(obligation);
        match state {
            EvidenceState::Satisfied => {}
            EvidenceState::Unknown => {
                self.mode = self.mode.max(RouteMode::NeedsEvidence);
                self.reasons.insert(PlanReason::MissingEvidence(obligation));
            }
            EvidenceState::Unavailable => {
                self.mode = RouteMode::Blocked;
                self.reasons
                    .insert(PlanReason::UnavailableEvidence(obligation));
            }
        }
    }
    pub fn render(&self) -> String {
        format!(
            "Routing plan (no execution)\nMode: {:?}\nNative baseline: shell/git/search/build/test (subject to host availability)\nNative fallback: {}\nRequired obligations: {:?}\nReasons: {:?}\nEvidence escalation required: {}\nReasoning compatibility: {:?}\n",
            self.mode,
            self.native_fallback,
            self.obligations,
            self.reasons,
            self.mode >= RouteMode::NeedsEvidence,
            self.reasoning_status
        )
    }
}

pub fn plan_fallback(
    router: &RouterDecision,
    reasoning: &ReasoningDecision,
    evidence: &PlanEvidence,
) -> RoutingPlan {
    let assessment = &router.assessment;
    let ambiguous =
        assessment.ambiguity == Ambiguity::Ambiguous || assessment.task == TaskKind::Unknown;
    let mut plan = RoutingPlan {
        mode: RouteMode::Proceed,
        native_fallback: false,
        obligations: BTreeSet::new(),
        reasons: router
            .reasons
            .iter()
            .copied()
            .map(PlanReason::Router)
            .collect(),
        reasoning_status: match evidence.reasoning_application {
            ReasoningApplication::UserOwned(status) => status,
            _ => reasoning.status,
        },
    };
    if matches!(assessment.task, TaskKind::Edit | TaskKind::Refactor) || ambiguous {
        plan.obligations.extend([
            Obligation::RelevantTests,
            Obligation::BuildOrStaticValidation,
        ]);
    }
    if assessment.task == TaskKind::Refactor || ambiguous {
        plan.obligations.insert(Obligation::ImpactAnalysis);
    }
    if ambiguous {
        plan.mode = RouteMode::NeedsEvidence;
        plan.reasons
            .insert(PlanReason::Router(DecisionReason::AmbiguousTask));
    }
    if assessment.risk == RiskLevel::High {
        plan.obligations.insert(Obligation::AdditionalVerification);
    }
    for (reason, obligation) in [
        (Reason::SecuritySensitive, Obligation::SecurityReview),
        (
            Reason::MigrationSensitive,
            Obligation::MigrationRollbackValidation,
        ),
        (Reason::ConcurrencySensitive, Obligation::ConcurrencyReview),
    ] {
        if assessment.reasons.contains(&reason) {
            plan.obligations.insert(obligation);
        }
    }
    // Requests and their degraded status are already normalized by #10.
    // Backend-to-obligation mapping does not select or rediscover a capability.
    for reason in &router.reasons {
        let (backend, degraded) = match reason {
            DecisionReason::VerifiedCapabilitySelected(backend) => (*backend, false),
            DecisionReason::CapabilityUnknown(backend)
            | DecisionReason::CapabilityUnavailable(backend)
            | DecisionReason::CapabilityBlocked(backend)
            | DecisionReason::CapabilityDeferredForAmbiguity(backend) => (*backend, true),
            _ => continue,
        };
        match backend {
            Backend::CodeGraph => {
                plan.obligations.insert(Obligation::ImpactAnalysis);
            }
            Backend::Serena => {
                plan.obligations.insert(Obligation::SymbolReferences);
            }
            Backend::Context7 => plan.require_evidence(
                Obligation::ExternalReferenceValidation,
                evidence.external_reference,
            ),
            Backend::GitHub => match evidence.repository_requirement {
                RepositoryRequirement::LocalHistory => {
                    plan.obligations.insert(Obligation::LocalRepositoryEvidence);
                }
                RepositoryRequirement::CurrentRemoteState => {
                    plan.require_evidence(Obligation::RemoteStateValidation, evidence.remote_state)
                }
            },
            Backend::CodeGraphWrapper => {
                // Even a malformed external decision cannot offer the unsafe wrapper.
                plan.mode = RouteMode::Blocked;
                plan.obligations.insert(Obligation::ImpactAnalysis);
                plan.reasons
                    .insert(PlanReason::Router(DecisionReason::CapabilityBlocked(
                        Backend::CodeGraphWrapper,
                    )));
            }
        }
        if degraded && backend != Backend::CodeGraphWrapper {
            match evidence.native_fallback {
                EvidenceState::Satisfied => {
                    plan.native_fallback = true;
                    plan.mode = plan.mode.max(RouteMode::ProceedWithFallback);
                    plan.reasons.insert(PlanReason::NativeFallbackSelected);
                }
                EvidenceState::Unknown => {
                    plan.mode = plan.mode.max(RouteMode::NeedsEvidence);
                    plan.reasons.insert(PlanReason::NativeFallbackUnknown);
                }
                EvidenceState::Unavailable => {
                    plan.mode = RouteMode::Blocked;
                    plan.reasons.insert(PlanReason::NativeFallbackUnavailable);
                }
            }
        }
    }
    if matches!(
        evidence.reasoning_application,
        ReasoningApplication::UserOwned(_)
    ) {
        plan.reasons.insert(PlanReason::UserOwnedReasoning);
    }
    let reasoning_required = evidence.reasoning_application != ReasoningApplication::Passthrough;
    if reasoning_required {
        plan.obligations
            .insert(Obligation::ReasoningCompatibilityValidation);
    }
    match plan.reasoning_status {
        Support::Supported => {}
        Support::Unknown => {
            plan.reasons
                .insert(PlanReason::ReasoningCompatibilityUnknown);
            if reasoning_required {
                plan.require_evidence(
                    Obligation::ReasoningCompatibilityValidation,
                    EvidenceState::Unknown,
                );
            }
        }
        Support::Unsupported => {
            plan.reasons
                .insert(PlanReason::ReasoningCompatibilityUnsupported);
            if reasoning_required {
                plan.require_evidence(
                    Obligation::ReasoningCompatibilityValidation,
                    EvidenceState::Unavailable,
                );
            }
        }
    }
    for (obligation, state) in &evidence.verification {
        plan.require_evidence(*obligation, *state);
    }
    if !evidence.context_sufficient {
        plan.mode = plan.mode.max(RouteMode::NeedsEvidence);
        plan.reasons.insert(PlanReason::ContextInsufficient);
    }
    if !plan.obligations.is_empty() {
        plan.reasons
            .insert(PlanReason::RequiredVerificationPreserved);
    }
    if plan.mode >= RouteMode::NeedsEvidence {
        plan.reasons.insert(PlanReason::MoreEvidenceRequired);
    }
    plan
}

#[cfg(test)]
mod tests {
    use super::*;

    fn empty_plan() -> RoutingPlan {
        RoutingPlan {
            mode: RouteMode::Proceed,
            native_fallback: false,
            obligations: BTreeSet::new(),
            reasons: BTreeSet::new(),
            reasoning_status: Support::Supported,
        }
    }

    #[test]
    fn prerequisite_failure_cannot_be_erased_by_satisfied_duplicate() {
        for (state, mode) in [
            (EvidenceState::Unknown, RouteMode::NeedsEvidence),
            (EvidenceState::Unavailable, RouteMode::Blocked),
        ] {
            for states in [
                [state, EvidenceState::Satisfied],
                [EvidenceState::Satisfied, state],
            ] {
                let mut plan = empty_plan();
                for value in states {
                    plan.require_evidence(Obligation::RelevantTests, value);
                }
                assert_eq!(plan.mode, mode);
                assert_eq!(
                    plan.obligations,
                    BTreeSet::from([Obligation::RelevantTests])
                );
            }
        }
    }

    #[test]
    fn blocked_prerequisite_has_precedence_over_missing_evidence() {
        let mut plan = empty_plan();
        plan.require_evidence(Obligation::ImpactAnalysis, EvidenceState::Unavailable);
        plan.require_evidence(Obligation::RelevantTests, EvidenceState::Unknown);
        assert_eq!(plan.mode, RouteMode::Blocked);
        assert_eq!(plan.obligations.len(), 2);
        assert!(
            plan.reasons
                .contains(&PlanReason::MissingEvidence(Obligation::RelevantTests))
        );
        assert!(
            plan.reasons
                .contains(&PlanReason::UnavailableEvidence(Obligation::ImpactAnalysis))
        );
    }
}
