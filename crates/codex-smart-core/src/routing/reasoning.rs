//! Pure effort selection. Configuration precedence and compatibility collection are external.
use super::Reasoning;
use super::assessment::{Ambiguity, RiskLevel, TaskRiskAssessment};
use std::collections::BTreeSet;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Support {
    Supported,
    Unsupported,
    Unknown,
}
impl Support {
    fn combine(self, other: Self) -> Self {
        match (self, other) {
            (Self::Unsupported, _) | (_, Self::Unsupported) => Self::Unsupported,
            (Self::Unknown, _) | (_, Self::Unknown) => Self::Unknown,
            _ => Self::Supported,
        }
    }
}

/// Normalized evidence for the effective target, not an inferred model catalog.
/// CLI Supported asserts the reviewed 0.160 config argv contract applies to the target.
/// A declared version/reference contract/checksum alone cannot establish it.
/// Medium/High support are separate assertions about the effective model.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ReasoningCompatibility {
    pub cli: Support,
    pub medium: Support,
    pub high: Support,
}
impl Default for ReasoningCompatibility {
    fn default() -> Self {
        Self {
            cli: Support::Unknown,
            medium: Support::Unknown,
            high: Support::Unknown,
        }
    }
}
impl ReasoningCompatibility {
    pub fn support(self, effort: Reasoning) -> Support {
        self.cli.combine(match effort {
            Reasoning::Medium => self.medium,
            Reasoning::High => self.high,
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ReasoningOrigin {
    Explicit,
    Policy,
    Default,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ReasoningReason {
    ExplicitOverride,
    HighRisk,
    Ambiguity,
    MediumDefault,
    CompatibilitySupported,
    CompatibilityUnknown,
    CompatibilityUnsupported,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ReasoningDecision {
    pub candidate: Reasoning,
    pub origin: ReasoningOrigin,
    pub status: Support,
    pub reasons: BTreeSet<ReasoningReason>,
    // Retained so the argv adapter can validate a different forwarded user effort.
    compatibility: ReasoningCompatibility,
}
impl ReasoningDecision {
    pub fn accepted(&self) -> Option<Reasoning> {
        (self.support(self.candidate) == Support::Supported).then_some(self.candidate)
    }
    pub(super) fn support(&self, effort: Reasoning) -> Support {
        self.compatibility.support(effort)
    }
    pub fn render(&self) -> String {
        format!(
            "Reasoning decision (no activation)\nCandidate: {:?}\nAccepted: {:?}\nOrigin: {:?}\nCompatibility: {:?}\nReasons: {:?}\n",
            self.candidate,
            self.accepted(),
            self.origin,
            self.status,
            self.reasons
        )
    }
}

pub fn select_reasoning(
    assessment: &TaskRiskAssessment,
    explicit: Option<Reasoning>,
    compatibility: ReasoningCompatibility,
) -> ReasoningDecision {
    let mut reasons = BTreeSet::new();
    let (candidate, origin) = if let Some(effort) = explicit {
        reasons.insert(ReasoningReason::ExplicitOverride);
        (effort, ReasoningOrigin::Explicit)
    } else {
        if assessment.risk == RiskLevel::High {
            reasons.insert(ReasoningReason::HighRisk);
        }
        if assessment.ambiguity == Ambiguity::Ambiguous {
            reasons.insert(ReasoningReason::Ambiguity);
        }
        if reasons.is_empty() {
            reasons.insert(ReasoningReason::MediumDefault);
            (Reasoning::Medium, ReasoningOrigin::Default)
        } else {
            (Reasoning::High, ReasoningOrigin::Policy)
        }
    };
    let status = compatibility.support(candidate);
    reasons.insert(match status {
        Support::Supported => ReasoningReason::CompatibilitySupported,
        Support::Unknown => ReasoningReason::CompatibilityUnknown,
        Support::Unsupported => ReasoningReason::CompatibilityUnsupported,
    });
    ReasoningDecision {
        candidate,
        origin,
        status,
        reasons,
        compatibility,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::routing::assessment::{RoutingFacts, TaskKind, assess};

    fn input(risk: RiskLevel, ambiguity: Ambiguity) -> TaskRiskAssessment {
        let mut assessment = assess(&RoutingFacts {
            task_hints: vec![TaskKind::Edit],
            ..Default::default()
        });
        assessment.risk = risk;
        assessment.ambiguity = ambiguity;
        assessment
    }
    const SUPPORTED: ReasoningCompatibility = ReasoningCompatibility {
        cli: Support::Supported,
        medium: Support::Supported,
        high: Support::Supported,
    };

    #[test]
    fn policy_and_override_matrix() {
        for risk in [RiskLevel::Low, RiskLevel::Medium, RiskLevel::High] {
            for ambiguity in [Ambiguity::Clear, Ambiguity::Ambiguous] {
                for explicit in [None, Some(Reasoning::Medium), Some(Reasoning::High)] {
                    let decision = select_reasoning(&input(risk, ambiguity), explicit, SUPPORTED);
                    let expected = explicit.unwrap_or(
                        if risk == RiskLevel::High || ambiguity == Ambiguity::Ambiguous {
                            Reasoning::High
                        } else {
                            Reasoning::Medium
                        },
                    );
                    assert_eq!(decision.candidate, expected);
                    assert_eq!(decision.accepted(), Some(expected));
                    assert_eq!(
                        decision.origin,
                        if explicit.is_some() {
                            ReasoningOrigin::Explicit
                        } else if expected == Reasoning::High {
                            ReasoningOrigin::Policy
                        } else {
                            ReasoningOrigin::Default
                        }
                    );
                }
            }
        }
    }

    #[test]
    fn cli_and_model_support_are_independent_and_never_substitute() {
        for effort in [Reasoning::Medium, Reasoning::High] {
            for cli in [Support::Supported, Support::Unsupported, Support::Unknown] {
                for model in [Support::Supported, Support::Unsupported, Support::Unknown] {
                    let compatibility = ReasoningCompatibility {
                        cli,
                        medium: model,
                        high: model,
                    };
                    let decision = select_reasoning(
                        &input(RiskLevel::High, Ambiguity::Clear),
                        Some(effort),
                        compatibility,
                    );
                    let expected = match (cli, model) {
                        (Support::Unsupported, _) | (_, Support::Unsupported) => {
                            Support::Unsupported
                        }
                        (Support::Supported, Support::Supported) => Support::Supported,
                        _ => Support::Unknown,
                    };
                    assert_eq!(decision.candidate, effort);
                    assert_eq!(decision.status, expected);
                    assert_eq!(
                        decision.accepted(),
                        (expected == Support::Supported).then_some(effort)
                    );
                }
            }
        }
        let compatibility = ReasoningCompatibility {
            high: Support::Unsupported,
            ..SUPPORTED
        };
        assert_eq!(
            select_reasoning(
                &input(RiskLevel::High, Ambiguity::Clear),
                None,
                compatibility
            )
            .status,
            Support::Unsupported
        );
        assert_eq!(
            select_reasoning(
                &input(RiskLevel::High, Ambiguity::Clear),
                Some(Reasoning::Medium),
                compatibility
            )
            .accepted(),
            Some(Reasoning::Medium)
        );
    }

    #[test]
    fn refactor_is_risk_based_and_external_size_is_irrelevant() {
        let facts = RoutingFacts {
            task_hints: vec![TaskKind::Unknown, TaskKind::Refactor, TaskKind::Refactor],
            ..Default::default()
        };
        let expected = select_reasoning(&assess(&facts), None, SUPPORTED);
        assert_eq!(expected.candidate, Reasoning::Medium);
        for repository_bytes in [0_u64, 1, u64::MAX] {
            let external = (repository_bytes, &facts);
            let actual = select_reasoning(&assess(external.1), None, SUPPORTED);
            assert_eq!(actual, expected);
            assert_eq!(actual.render(), expected.render());
        }
        let mut reordered = facts;
        reordered.task_hints.reverse();
        assert_eq!(
            select_reasoning(&assess(&reordered), None, SUPPORTED),
            expected
        );
        assert_eq!(Reasoning::parse("xhigh"), None);
    }

    #[test]
    fn typed_reasons_and_render_are_stable() {
        let mut assessment = input(RiskLevel::High, Ambiguity::Ambiguous);
        let expected = select_reasoning(&assessment, None, SUPPORTED);
        assert_eq!(
            expected.reasons,
            BTreeSet::from([
                ReasoningReason::HighRisk,
                ReasoningReason::Ambiguity,
                ReasoningReason::CompatibilitySupported,
            ])
        );
        assert_eq!(
            expected.render(),
            "Reasoning decision (no activation)\nCandidate: High\nAccepted: Some(High)\nOrigin: Policy\nCompatibility: Supported\nReasons: {HighRisk, Ambiguity, CompatibilitySupported}\n"
        );
        // Assessment reason ordering is not a second risk source of truth.
        assessment.reasons.clear();
        assert_eq!(select_reasoning(&assessment, None, SUPPORTED), expected);
    }
}
