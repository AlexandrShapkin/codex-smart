//! Opt-in inspection join, not an evidence authenticator or execution adapter.
use crate::{
    routing::assessment::TaskRiskAssessment,
    validation_policy::{self, Approval, Input, Provenance, Reason, Specification, Status},
    workflow::{NativeSurface, WorkflowPlan},
};

/// Separately supplied current identity/time assumptions. No host observation occurs.
/// Intentionally lacks Debug and serialization, as do candidate and approval inputs.
pub struct CurrentAssumptions<'a> {
    pub specification: &'a Specification<'a>,
    pub provenance: Provenance,
    pub observed_at: u64,
    pub expires_at: u64,
    pub now: u64,
    pub last_observed_time: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Readiness {
    NeedsEvidence,
    Blocked,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EvidenceProvenance {
    Unknown,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Finding {
    MissingWorkflowRecipe,
    MissingCurrentAssumptions,
    Policy(Status),
}
/// Fixed-size, enum-only diagnostic; contains no candidate or authority handle.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Inspection {
    pub readiness: Readiness,
    pub provenance: EvidenceProvenance,
    pub finding: Finding,
}
impl WorkflowPlan {
    /// Explicit pure inspection of one candidate against this plan's validation recipe.
    /// Supplied approval/current provenance remains an unauthenticated assumption.
    /// Even a positive structural assessment requires independent host evidence;
    /// this API cannot issue admission, argv, health, validation success or authority.
    pub fn inspect_validation(
        &self,
        native: &NativeSurface,
        assessment: &TaskRiskAssessment,
        candidate: &Specification<'_>,
        approval: Option<Approval<'_>>,
        current: Option<CurrentAssumptions<'_>>,
    ) -> Inspection {
        // Retain the selected workflow risk floor when caller facts are weaker.
        let mut assessment = assessment.clone();
        assessment.risk = assessment.risk.max(self.selection.effective_risk);
        let finding = match (self.validation_recipe(native), current) {
            (None, _) => Finding::MissingWorkflowRecipe,
            (_, None) => Finding::MissingCurrentAssumptions,
            (Some(recipe), Some(current)) => Finding::Policy(validation_policy::evaluate(&Input {
                specification: candidate,
                approval,
                recipe: &recipe,
                assessment: &assessment,
                current: current.specification,
                current_provenance: current.provenance,
                current_observed_at: current.observed_at,
                current_expires_at: current.expires_at,
                now: current.now,
                last_observed_time: current.last_observed_time,
            })),
        };
        let readiness = match finding {
            Finding::Policy(Status::Refused(reason)) => match reason {
                Reason::MissingApproval | Reason::UnverifiedEvidence | Reason::RecipeNotReady => {
                    Readiness::NeedsEvidence
                }
                _ => Readiness::Blocked,
            },
            _ => Readiness::NeedsEvidence,
        };
        Inspection {
            readiness,
            provenance: EvidenceProvenance::Unknown,
            finding,
        }
    }
}
