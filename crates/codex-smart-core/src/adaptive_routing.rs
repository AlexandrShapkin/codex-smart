//! Replaceable model/profile compatibility routing for adaptive execution.
//!
//! Product policy names capability classes, not commercial model names. Callers provide
//! a verified catalog of opaque provider/model handles. This module is pure: it performs
//! no discovery, network access, authentication, configuration mutation or execution.

use crate::adaptive::AdaptiveController;
use crate::playbook::ProfileClass;
use crate::routing::Reasoning;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct ProviderKey(pub u16);

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct ModelKey(pub u16);

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct ModelIdentity {
    pub provider: ProviderKey,
    pub model: ModelKey,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum CompatibilityState {
    Verified,
    Unknown,
    Unsupported,
    Unavailable,
    Blocked,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ReasoningCompatibility {
    pub medium: CompatibilityState,
    pub high: CompatibilityState,
}

impl ReasoningCompatibility {
    pub const VERIFIED: Self = Self {
        medium: CompatibilityState::Verified,
        high: CompatibilityState::Verified,
    };

    pub fn state(self, reasoning: Reasoning) -> CompatibilityState {
        match reasoning {
            Reasoning::Medium => self.medium,
            Reasoning::High => self.high,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ModelDescriptor {
    pub identity: ModelIdentity,
    /// Capability class. A higher class may satisfy a lower requested class, but never
    /// the reverse.
    pub profile: ProfileClass,
    /// Provider/model identity and runtime availability must be verified separately
    /// from profile semantics.
    pub availability: CompatibilityState,
    pub reasoning: ReasoningCompatibility,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ModelCatalog {
    entries: Vec<ModelDescriptor>,
}

impl ModelCatalog {
    pub fn new(entries: impl IntoIterator<Item = ModelDescriptor>) -> Self {
        Self {
            entries: entries.into_iter().collect(),
        }
    }

    pub fn entries(&self) -> &[ModelDescriptor] {
        &self.entries
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ResolutionReason {
    ExactProfile,
    HigherProfileFallback,
    UnknownCompatibility,
    UnsupportedReasoning,
    ModelUnavailable,
    ModelBlocked,
    NoCompatibleCandidate,
    ConflictingDescriptor,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ResolutionStatus {
    Resolved,
    NeedsEvidence,
    Unavailable,
    Blocked,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ExecutionTarget {
    pub identity: ModelIdentity,
    pub profile: ProfileClass,
    pub reasoning: Reasoning,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ModelResolution {
    pub status: ResolutionStatus,
    pub requested_profile: ProfileClass,
    pub requested_reasoning: Reasoning,
    pub target: Option<ExecutionTarget>,
    pub reasons: BTreeSet<ResolutionReason>,
}

fn combined_state(descriptor: ModelDescriptor, reasoning: Reasoning) -> CompatibilityState {
    let effort = descriptor.reasoning.state(reasoning);
    match (descriptor.availability, effort) {
        (CompatibilityState::Blocked, _) | (_, CompatibilityState::Blocked) => {
            CompatibilityState::Blocked
        }
        (CompatibilityState::Unavailable, _) | (_, CompatibilityState::Unavailable) => {
            CompatibilityState::Unavailable
        }
        (CompatibilityState::Unsupported, _) | (_, CompatibilityState::Unsupported) => {
            CompatibilityState::Unsupported
        }
        (CompatibilityState::Unknown, _) | (_, CompatibilityState::Unknown) => {
            CompatibilityState::Unknown
        }
        (CompatibilityState::Verified, CompatibilityState::Verified) => {
            CompatibilityState::Verified
        }
    }
}

fn catalog_conflicts(catalog: &ModelCatalog) -> bool {
    let mut seen = BTreeMap::new();
    for descriptor in catalog.entries() {
        if let Some(previous) = seen.insert(descriptor.identity, *descriptor)
            && previous != *descriptor
        {
            return true;
        }
    }
    false
}

/// Resolve the minimally sufficient verified model capability for a requested adaptive
/// profile/reasoning pair.
///
/// Catalog ordering is irrelevant. Unknown compatibility never becomes ready. A verified
/// higher capability class may safely satisfy a lower requested class when no lower
/// verified candidate exists; a lower class can never satisfy a stronger request.
pub fn resolve_model(
    requested_profile: ProfileClass,
    requested_reasoning: Reasoning,
    catalog: &ModelCatalog,
) -> ModelResolution {
    let mut reasons = BTreeSet::new();
    if catalog_conflicts(catalog) {
        reasons.insert(ResolutionReason::ConflictingDescriptor);
        return ModelResolution {
            status: ResolutionStatus::Blocked,
            requested_profile,
            requested_reasoning,
            target: None,
            reasons,
        };
    }

    let mut verified = Vec::new();
    let mut unknown = false;
    let mut unavailable = false;
    let mut blocked = false;
    let mut unsupported = false;

    for descriptor in catalog
        .entries()
        .iter()
        .copied()
        .filter(|descriptor| descriptor.profile >= requested_profile)
    {
        match combined_state(descriptor, requested_reasoning) {
            CompatibilityState::Verified => verified.push(descriptor),
            CompatibilityState::Unknown => unknown = true,
            CompatibilityState::Unsupported => unsupported = true,
            CompatibilityState::Unavailable => unavailable = true,
            CompatibilityState::Blocked => blocked = true,
        }
    }

    verified.sort_by_key(|descriptor| (descriptor.profile, descriptor.identity));
    if let Some(descriptor) = verified.first().copied() {
        reasons.insert(if descriptor.profile == requested_profile {
            ResolutionReason::ExactProfile
        } else {
            ResolutionReason::HigherProfileFallback
        });
        if descriptor.profile > requested_profile {
            for skipped in catalog.entries().iter().copied().filter(|candidate| {
                candidate.profile >= requested_profile && candidate.profile < descriptor.profile
            }) {
                match combined_state(skipped, requested_reasoning) {
                    CompatibilityState::Verified => {}
                    CompatibilityState::Unknown => {
                        reasons.insert(ResolutionReason::UnknownCompatibility);
                    }
                    CompatibilityState::Unsupported => {
                        reasons.insert(ResolutionReason::UnsupportedReasoning);
                    }
                    CompatibilityState::Unavailable => {
                        reasons.insert(ResolutionReason::ModelUnavailable);
                    }
                    CompatibilityState::Blocked => {
                        reasons.insert(ResolutionReason::ModelBlocked);
                    }
                }
            }
        }
        return ModelResolution {
            status: ResolutionStatus::Resolved,
            requested_profile,
            requested_reasoning,
            target: Some(ExecutionTarget {
                identity: descriptor.identity,
                profile: descriptor.profile,
                reasoning: requested_reasoning,
            }),
            reasons,
        };
    }

    if unknown {
        reasons.insert(ResolutionReason::UnknownCompatibility);
        return ModelResolution {
            status: ResolutionStatus::NeedsEvidence,
            requested_profile,
            requested_reasoning,
            target: None,
            reasons,
        };
    }
    if blocked {
        reasons.insert(ResolutionReason::ModelBlocked);
        return ModelResolution {
            status: ResolutionStatus::Blocked,
            requested_profile,
            requested_reasoning,
            target: None,
            reasons,
        };
    }
    if unavailable {
        reasons.insert(ResolutionReason::ModelUnavailable);
        return ModelResolution {
            status: ResolutionStatus::Unavailable,
            requested_profile,
            requested_reasoning,
            target: None,
            reasons,
        };
    }
    if unsupported {
        reasons.insert(ResolutionReason::UnsupportedReasoning);
    } else {
        reasons.insert(ResolutionReason::NoCompatibleCandidate);
    }
    ModelResolution {
        status: ResolutionStatus::Unavailable,
        requested_profile,
        requested_reasoning,
        target: None,
        reasons,
    }
}

/// Resolve the controller's current monotonic profile/reasoning request. Re-running this
/// after a #43 state transition is the progressive-routing mechanism: the controller
/// owns escalation; this resolver only maps the current capability requirement.
pub fn resolve_controller(
    controller: &AdaptiveController,
    catalog: &ModelCatalog,
) -> ModelResolution {
    resolve_model(
        controller.current_profile,
        controller.current_reasoning,
        catalog,
    )
}

impl ModelResolution {
    /// Opaque-ID explanation only: no provider/model names, prompts, source, credentials,
    /// configuration or tool output are carried by the policy layer.
    pub fn render(&self) -> String {
        format!(
            "Adaptive model resolution (no execution)\nStatus: {:?}\nRequested: profile={:?}; reasoning={:?}\nTarget: {:?}\nReasons: {:?}\n",
            self.status,
            self.requested_profile,
            self.requested_reasoning,
            self.target,
            self.reasons,
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::adaptive::{AdaptiveController, AttemptOutcome, ExecutionBudget, ValidationOutcome};
    use crate::playbook::Archetype;
    use crate::routing::assessment::{RoutingFacts, SafetyFact, TaskKind, assess};
    use crate::routing::engine::CapabilitySurface;
    use crate::workflow::{NativeSurface, ResourceCatalog, plan_workflow};

    const ECONOMY: ModelDescriptor = ModelDescriptor {
        identity: ModelIdentity {
            provider: ProviderKey(1),
            model: ModelKey(10),
        },
        profile: ProfileClass::Economy,
        availability: CompatibilityState::Verified,
        reasoning: ReasoningCompatibility::VERIFIED,
    };
    const STANDARD: ModelDescriptor = ModelDescriptor {
        identity: ModelIdentity {
            provider: ProviderKey(1),
            model: ModelKey(20),
        },
        profile: ProfileClass::Standard,
        availability: CompatibilityState::Verified,
        reasoning: ReasoningCompatibility::VERIFIED,
    };
    const STRONG: ModelDescriptor = ModelDescriptor {
        identity: ModelIdentity {
            provider: ProviderKey(1),
            model: ModelKey(30),
        },
        profile: ProfileClass::Strong,
        availability: CompatibilityState::Verified,
        reasoning: ReasoningCompatibility::VERIFIED,
    };

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
    fn exact_profile_is_preferred_and_catalog_order_does_not_matter() {
        let first = resolve_model(
            ProfileClass::Standard,
            Reasoning::Medium,
            &ModelCatalog::new([STRONG, ECONOMY, STANDARD]),
        );
        let second = resolve_model(
            ProfileClass::Standard,
            Reasoning::Medium,
            &ModelCatalog::new([STANDARD, STRONG, ECONOMY]),
        );
        assert_eq!(first, second);
        assert_eq!(first.status, ResolutionStatus::Resolved);
        assert_eq!(first.target.unwrap().identity, STANDARD.identity);
        assert!(first.reasons.contains(&ResolutionReason::ExactProfile));
    }

    #[test]
    fn higher_verified_profile_is_safe_fallback_but_lower_never_is() {
        let higher = resolve_model(
            ProfileClass::Standard,
            Reasoning::Medium,
            &ModelCatalog::new([ECONOMY, STRONG]),
        );
        assert_eq!(higher.status, ResolutionStatus::Resolved);
        assert_eq!(higher.target.unwrap().identity, STRONG.identity);
        assert!(
            higher
                .reasons
                .contains(&ResolutionReason::HigherProfileFallback)
        );

        let lower_only = resolve_model(
            ProfileClass::Strong,
            Reasoning::High,
            &ModelCatalog::new([ECONOMY, STANDARD]),
        );
        assert_eq!(lower_only.status, ResolutionStatus::Unavailable);
        assert!(lower_only.target.is_none());
        assert!(
            lower_only
                .reasons
                .contains(&ResolutionReason::NoCompatibleCandidate)
        );
    }

    #[test]
    fn unknown_compatibility_needs_evidence_and_never_becomes_ready() {
        let unknown = ModelDescriptor {
            availability: CompatibilityState::Unknown,
            ..STANDARD
        };
        let resolution = resolve_model(
            ProfileClass::Standard,
            Reasoning::Medium,
            &ModelCatalog::new([unknown]),
        );
        assert_eq!(resolution.status, ResolutionStatus::NeedsEvidence);
        assert!(resolution.target.is_none());
        assert!(
            resolution
                .reasons
                .contains(&ResolutionReason::UnknownCompatibility)
        );
    }

    #[test]
    fn verified_higher_candidate_can_bypass_unknown_lower_without_quality_loss() {
        let unknown = ModelDescriptor {
            availability: CompatibilityState::Unknown,
            ..STANDARD
        };
        let resolution = resolve_model(
            ProfileClass::Standard,
            Reasoning::Medium,
            &ModelCatalog::new([unknown, STRONG]),
        );
        assert_eq!(resolution.status, ResolutionStatus::Resolved);
        assert_eq!(resolution.target.unwrap().identity, STRONG.identity);
        assert!(
            resolution
                .reasons
                .contains(&ResolutionReason::HigherProfileFallback)
        );
    }

    #[test]
    fn reasoning_compatibility_is_verified_per_model() {
        let medium_only = ModelDescriptor {
            reasoning: ReasoningCompatibility {
                medium: CompatibilityState::Verified,
                high: CompatibilityState::Unsupported,
            },
            ..STRONG
        };
        let high = resolve_model(
            ProfileClass::Strong,
            Reasoning::High,
            &ModelCatalog::new([medium_only]),
        );
        assert_eq!(high.status, ResolutionStatus::Unavailable);
        assert!(
            high.reasons
                .contains(&ResolutionReason::UnsupportedReasoning)
        );

        let medium = resolve_model(
            ProfileClass::Strong,
            Reasoning::Medium,
            &ModelCatalog::new([medium_only]),
        );
        assert_eq!(medium.status, ResolutionStatus::Resolved);
    }

    #[test]
    fn conflicting_duplicate_identity_blocks_catalog() {
        let conflict = ModelDescriptor {
            profile: ProfileClass::Strong,
            ..STANDARD
        };
        let resolution = resolve_model(
            ProfileClass::Standard,
            Reasoning::Medium,
            &ModelCatalog::new([STANDARD, conflict]),
        );
        assert_eq!(resolution.status, ResolutionStatus::Blocked);
        assert!(resolution.target.is_none());
        assert!(
            resolution
                .reasons
                .contains(&ResolutionReason::ConflictingDescriptor)
        );
    }

    #[test]
    fn adaptive_escalation_re_resolves_to_progressively_stronger_targets() {
        let mut controller = controller(TaskKind::Inspect, None, vec![]);
        let catalog = ModelCatalog::new([ECONOMY, STANDARD, STRONG]);

        let first = resolve_controller(&controller, &catalog);
        assert_eq!(first.target.unwrap().identity, ECONOMY.identity);

        controller.start_attempt().unwrap();
        controller
            .observe_attempt(AttemptOutcome::RuntimeFailure)
            .unwrap();
        let second = resolve_controller(&controller, &catalog);
        assert_eq!(second.target.unwrap().identity, STANDARD.identity);

        controller.start_attempt().unwrap();
        controller
            .observe_attempt(AttemptOutcome::Completed)
            .unwrap();
        controller
            .observe_validation(ValidationOutcome::Failed)
            .unwrap();
        let third = resolve_controller(&controller, &catalog);
        let target = third.target.unwrap();
        assert_eq!(target.identity, STRONG.identity);
        assert_eq!(target.reasoning, Reasoning::High);
    }

    #[test]
    fn high_risk_controller_never_resolves_to_lower_profiles() {
        let controller = controller(TaskKind::Edit, None, vec![SafetyFact::SecuritySensitive]);
        let resolution =
            resolve_controller(&controller, &ModelCatalog::new([ECONOMY, STANDARD, STRONG]));
        let target = resolution.target.unwrap();
        assert_eq!(target.profile, ProfileClass::Strong);
        assert_eq!(target.reasoning, Reasoning::High);
        assert_eq!(target.identity, STRONG.identity);
    }

    #[test]
    fn opaque_render_never_contains_commercial_model_or_provider_names() {
        let resolution = resolve_model(
            ProfileClass::Economy,
            Reasoning::Medium,
            &ModelCatalog::new([ECONOMY]),
        );
        let rendered = resolution.render();
        assert!(rendered.contains("ProviderKey(1)"));
        for forbidden in [
            "gpt-",
            "openai",
            "anthropic",
            "gemini",
            "Bearer ",
            "api_key",
            "/home/",
            "prompt",
        ] {
            assert!(
                !rendered
                    .to_ascii_lowercase()
                    .contains(&forbidden.to_ascii_lowercase()),
                "render leaked {forbidden}"
            );
        }
    }
}
