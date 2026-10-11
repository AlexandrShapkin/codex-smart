//! Pure Router v2 composition; neither discovery nor tool activation belongs here.
use super::assessment::{Ambiguity, RiskLevel, TaskKind, TaskRiskAssessment};
use crate::capability::Capability;
use crate::tool_lock::{CapabilityEvidence, Compatibility, Readiness};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum CapabilityNeed {
    StructuralImpact,
    SymbolNavigation,
    ExternalApiReference,
    RemoteRepository,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Backend {
    CodeGraph,
    Serena,
    Context7,
    GitHub,
    /// Represented for rejection, never a preferred backend.
    CodeGraphWrapper,
}
impl CapabilityNeed {
    fn backend(self) -> Backend {
        match self {
            Self::StructuralImpact => Backend::CodeGraph,
            Self::SymbolNavigation => Backend::Serena,
            Self::ExternalApiReference => Backend::Context7,
            Self::RemoteRepository => Backend::GitHub,
        }
    }
}

/// Ordered only for conservative duplicate normalization, not a readiness score.
/// Verified is a caller assertion of usable runtime/transport/auth/project evidence.
/// Discovery, reference contracts and entrypoint checksums cannot produce it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum CapabilityState {
    Verified,
    Unknown,
    Unavailable,
    Blocked,
}

/// One normalized immutable snapshot. Missing records mean Unknown.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct CapabilitySurface(BTreeMap<Backend, CapabilityState>);
impl CapabilitySurface {
    /// Future controlled integration (or stubs) supplies verified assertions here.
    /// Conflicting duplicates resolve to the most restrictive state.
    pub fn new(records: impl IntoIterator<Item = (Backend, CapabilityState)>) -> Self {
        let mut states = BTreeMap::new();
        for (backend, mut state) in records {
            if backend == Backend::CodeGraphWrapper {
                state = CapabilityState::Blocked;
            }
            states
                .entry(backend)
                .and_modify(|previous: &mut CapabilityState| *previous = (*previous).max(state))
                .or_insert(state);
        }
        Self(states)
    }

    /// Conservative projection of offline readiness; never fabricates Verified.
    /// Availability and reference compatibility remain diagnostic evidence, not proof.
    pub fn from_offline(
        records: impl IntoIterator<Item = (Capability, CapabilityEvidence)>,
    ) -> Self {
        Self::new(records.into_iter().filter_map(|(capability, evidence)| {
            let backend = match capability {
                Capability::CodeGraph => Backend::CodeGraph,
                Capability::Serena => Backend::Serena,
                Capability::Context7 => Backend::Context7,
                Capability::GitHub => Backend::GitHub,
                Capability::CodeGraphWrapper => Backend::CodeGraphWrapper,
                _ => return None,
            };
            let state = if evidence.compatibility == Compatibility::UnsupportedWrapper {
                CapabilityState::Blocked
            } else {
                match evidence.readiness {
                    Readiness::Unknown => CapabilityState::Unknown,
                    Readiness::Unavailable => CapabilityState::Unavailable,
                    Readiness::Blocked => CapabilityState::Blocked,
                }
            };
            Some((backend, state))
        }))
    }

    pub fn state(&self, backend: Backend) -> CapabilityState {
        if backend == Backend::CodeGraphWrapper {
            CapabilityState::Blocked
        } else {
            self.0
                .get(&backend)
                .copied()
                .unwrap_or(CapabilityState::Unknown)
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum DecisionReason {
    NativeBaseline,
    NoExternalNeed,
    AmbiguousTask,
    AdditionalSafetyEvidenceRequired,
    VerifiedCapabilitySelected(Backend),
    CapabilityUnknown(Backend),
    CapabilityUnavailable(Backend),
    CapabilityBlocked(Backend),
    CapabilityDeferredForAmbiguity(Backend),
}

/// Native shell/git/search/build/test is inherent in every decision, subject to host
/// availability. Augmentations supplement it; this output grants no execution authority.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RouterDecision {
    pub assessment: TaskRiskAssessment,
    pub augmentations: BTreeSet<Backend>,
    pub reasons: BTreeSet<DecisionReason>,
}

pub fn decide(
    assessment: &TaskRiskAssessment,
    needs: &[CapabilityNeed],
    surface: &CapabilitySurface,
) -> RouterDecision {
    let mut reasons = BTreeSet::from([DecisionReason::NativeBaseline]);
    let mut augmentations = BTreeSet::new();
    if needs.is_empty() {
        reasons.insert(DecisionReason::NoExternalNeed);
    }
    let ambiguous =
        assessment.ambiguity == Ambiguity::Ambiguous || assessment.task == TaskKind::Unknown;
    if ambiguous {
        reasons.insert(DecisionReason::AmbiguousTask);
    }
    if assessment.risk == RiskLevel::High {
        reasons.insert(DecisionReason::AdditionalSafetyEvidenceRequired);
    }
    // Deduplicate needs before consulting the snapshot. No discovery or retries.
    let requested: BTreeSet<_> = needs.iter().map(|need| need.backend()).collect();
    for backend in requested {
        let reason = match surface.state(backend) {
            CapabilityState::Blocked => DecisionReason::CapabilityBlocked(backend),
            CapabilityState::Unavailable => DecisionReason::CapabilityUnavailable(backend),
            CapabilityState::Unknown => DecisionReason::CapabilityUnknown(backend),
            CapabilityState::Verified if ambiguous => {
                DecisionReason::CapabilityDeferredForAmbiguity(backend)
            }
            CapabilityState::Verified => {
                augmentations.insert(backend);
                DecisionReason::VerifiedCapabilitySelected(backend)
            }
        };
        reasons.insert(reason);
    }
    RouterDecision {
        assessment: assessment.clone(),
        augmentations,
        reasons,
    }
}

impl RouterDecision {
    /// Enum-only explanation: no paths, configuration values or arbitrary tool output.
    pub fn render(&self) -> String {
        format!(
            "Router v2 decision (no activation)\nTask: {:?}\nRisk: {:?}\nAmbiguity: {:?}\nNative baseline: shell/git/search/build/test (subject to host availability)\nVerified augmentations: {:?}\nAssessment reasons: {:?}\nDecision reasons: {:?}\n",
            self.assessment.task,
            self.assessment.risk,
            self.assessment.ambiguity,
            self.augmentations,
            self.assessment.reasons,
            self.reasons
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::routing::assessment::{RoutingFacts, assess};
    use crate::tool_lock::ArtifactEvidence;

    const MAPPINGS: [(CapabilityNeed, Backend); 4] = [
        (CapabilityNeed::StructuralImpact, Backend::CodeGraph),
        (CapabilityNeed::SymbolNavigation, Backend::Serena),
        (CapabilityNeed::ExternalApiReference, Backend::Context7),
        (CapabilityNeed::RemoteRepository, Backend::GitHub),
    ];
    fn assessment(task: TaskKind) -> TaskRiskAssessment {
        assess(&RoutingFacts {
            task_hints: vec![task],
            ..Default::default()
        })
    }

    #[test]
    fn decision_matrix() {
        for task in [
            TaskKind::Inspect,
            TaskKind::Edit,
            TaskKind::Refactor,
            TaskKind::Unknown,
        ] {
            for (need, backend) in MAPPINGS {
                for state in [
                    CapabilityState::Verified,
                    CapabilityState::Unknown,
                    CapabilityState::Unavailable,
                    CapabilityState::Blocked,
                ] {
                    let input = assessment(task);
                    let decision =
                        decide(&input, &[need], &CapabilitySurface::new([(backend, state)]));
                    let selected = state == CapabilityState::Verified && task != TaskKind::Unknown;
                    assert_eq!(
                        decision.augmentations.contains(&backend),
                        selected,
                        "{task:?}/{need:?}/{state:?}"
                    );
                    assert_eq!(decision.augmentations.len(), usize::from(selected));
                    assert!(decision.reasons.contains(&DecisionReason::NativeBaseline));
                    let expected = match state {
                        CapabilityState::Verified if selected => {
                            DecisionReason::VerifiedCapabilitySelected(backend)
                        }
                        CapabilityState::Verified => {
                            DecisionReason::CapabilityDeferredForAmbiguity(backend)
                        }
                        CapabilityState::Unknown => DecisionReason::CapabilityUnknown(backend),
                        CapabilityState::Unavailable => {
                            DecisionReason::CapabilityUnavailable(backend)
                        }
                        CapabilityState::Blocked => DecisionReason::CapabilityBlocked(backend),
                    };
                    assert!(decision.reasons.contains(&expected));
                    assert_eq!(decision.assessment, input);
                }
            }
        }
    }

    #[test]
    fn native_first_and_risk_does_not_select_tools() {
        let surface = CapabilitySurface::new(
            MAPPINGS.map(|(_, backend)| (backend, CapabilityState::Verified)),
        );
        for risk in [RiskLevel::Low, RiskLevel::Medium, RiskLevel::High] {
            let mut input = assessment(TaskKind::Edit);
            input.risk = risk;
            let decision = decide(&input, &[], &surface);
            assert!(decision.augmentations.is_empty());
            assert!(decision.reasons.contains(&DecisionReason::NoExternalNeed));
            assert_eq!(
                decision
                    .reasons
                    .contains(&DecisionReason::AdditionalSafetyEvidenceRequired),
                risk == RiskLevel::High
            );
        }
        let decision = decide(
            &assessment(TaskKind::Refactor),
            &[CapabilityNeed::StructuralImpact],
            &surface,
        );
        assert_eq!(decision.augmentations, BTreeSet::from([Backend::CodeGraph]));
    }

    #[test]
    fn ordering_duplicates_and_conflicts_are_conservative() {
        let records = MAPPINGS.map(|(_, backend)| (backend, CapabilityState::Verified));
        let needs = MAPPINGS.map(|(need, _)| need);
        let input = assessment(TaskKind::Edit);
        let expected = decide(&input, &needs, &CapabilitySurface::new(records));
        let mut reversed_records = records.to_vec();
        reversed_records.reverse();
        reversed_records.extend(records);
        let mut reversed_needs = needs.to_vec();
        reversed_needs.reverse();
        reversed_needs.extend(needs);
        let actual = decide(
            &input,
            &reversed_needs,
            &CapabilitySurface::new(reversed_records),
        );
        assert_eq!(actual, expected);
        assert_eq!(actual.render(), expected.render());
        assert_eq!(actual.augmentations.len(), 4);
        for state in [
            CapabilityState::Unknown,
            CapabilityState::Unavailable,
            CapabilityState::Blocked,
        ] {
            for pair in [
                [CapabilityState::Verified, state],
                [state, CapabilityState::Verified],
            ] {
                let surface = CapabilitySurface::new(pair.map(|state| (Backend::CodeGraph, state)));
                assert_eq!(surface.state(Backend::CodeGraph), state);
                assert!(
                    decide(&input, &[CapabilityNeed::StructuralImpact], &surface)
                        .augmentations
                        .is_empty()
                );
            }
        }
    }

    #[test]
    fn offline_discovery_reference_and_checksum_never_verify() {
        for capability in [
            Capability::CodeGraph,
            Capability::Serena,
            Capability::Context7,
            Capability::GitHub,
            Capability::CodeGraphWrapper,
        ] {
            for discovered in [false, true] {
                for artifact in [
                    ArtifactEvidence::Deferred,
                    ArtifactEvidence::Match,
                    ArtifactEvidence::Mismatch,
                    ArtifactEvidence::Missing,
                    ArtifactEvidence::Rejected,
                ] {
                    let evidence = CapabilityEvidence::assess(
                        capability,
                        discovered,
                        Some(crate::version::Version::new(1, 7, 0)),
                        artifact,
                    );
                    let surface = CapabilitySurface::from_offline([(capability, evidence)]);
                    let backend = match capability {
                        Capability::CodeGraph => Backend::CodeGraph,
                        Capability::Serena => Backend::Serena,
                        Capability::Context7 => Backend::Context7,
                        Capability::GitHub => Backend::GitHub,
                        Capability::CodeGraphWrapper => Backend::CodeGraphWrapper,
                        _ => unreachable!(),
                    };
                    let expected = if backend == Backend::CodeGraphWrapper {
                        CapabilityState::Blocked
                    } else {
                        match evidence.readiness {
                            Readiness::Unknown => CapabilityState::Unknown,
                            Readiness::Unavailable => CapabilityState::Unavailable,
                            Readiness::Blocked => CapabilityState::Blocked,
                        }
                    };
                    assert_eq!(surface.state(backend), expected);
                    let decision = decide(
                        &assessment(TaskKind::Refactor),
                        &MAPPINGS.map(|(need, _)| need),
                        &surface,
                    );
                    assert!(decision.augmentations.is_empty());
                }
            }
        }
    }

    #[test]
    fn wrapper_is_blocked_even_with_fabricated_verified_assertion() {
        let surface =
            CapabilitySurface::new([(Backend::CodeGraphWrapper, CapabilityState::Verified)]);
        assert_eq!(
            surface.state(Backend::CodeGraphWrapper),
            CapabilityState::Blocked
        );
        let decision = decide(
            &assessment(TaskKind::Edit),
            &[CapabilityNeed::StructuralImpact],
            &surface,
        );
        assert!(decision.augmentations.is_empty());
        assert!(
            decision
                .reasons
                .contains(&DecisionReason::CapabilityUnknown(Backend::CodeGraph))
        );
        // Rejected wrapper evidence cannot contaminate separately verified direct use.
        let direct = CapabilitySurface::new([
            (Backend::CodeGraphWrapper, CapabilityState::Verified),
            (Backend::CodeGraph, CapabilityState::Verified),
        ]);
        assert_eq!(
            decide(
                &assessment(TaskKind::Edit),
                &[CapabilityNeed::StructuralImpact],
                &direct,
            )
            .augmentations,
            BTreeSet::from([Backend::CodeGraph])
        );
    }

    #[test]
    fn ambiguity_and_external_cost_metadata_cannot_enable_backend() {
        let mut input = assessment(TaskKind::Edit);
        input.ambiguity = Ambiguity::Ambiguous;
        let surface = CapabilitySurface::new([(Backend::CodeGraph, CapabilityState::Verified)]);
        let expected = decide(&input, &[CapabilityNeed::StructuralImpact], &surface);
        assert!(expected.augmentations.is_empty());
        for repository_bytes in [0_u64, 1, u64::MAX] {
            let external = (repository_bytes, &input);
            assert_eq!(
                decide(external.1, &[CapabilityNeed::StructuralImpact], &surface),
                expected
            );
        }
    }
}
