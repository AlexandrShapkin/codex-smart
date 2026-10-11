//! Router v2 facts only: no collection, capability selection or reasoning policy.
use std::collections::BTreeSet;

/// Read-only investigation includes explanation, debugging and test inspection.
/// Edits include fixes and test changes; structural changes retain a distinct kind.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum TaskKind {
    Unknown,
    Inspect,
    Edit,
    Refactor,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum RiskLevel {
    Low,
    Medium,
    High,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Ambiguity {
    Clear,
    Ambiguous,
}

/// Caller-supplied semantic evidence, never inferred from arbitrary prompt text.
/// These safety facts impose High regardless of the task or explicit risk hint.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum SafetyFact {
    SecuritySensitive,
    MigrationSensitive,
    ConcurrencySensitive,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Reason {
    ExplicitTask,
    KnownOperation,
    ExplicitRisk,
    SecuritySensitive,
    MigrationSensitive,
    ConcurrencySensitive,
    StructuralChange,
    ConflictingTaskEvidence,
    InsufficientTaskEvidence,
}

/// Bounded facts collected outside policy. No size, language, inventory or text.
/// Multiple hints represent independent explicit sources, not priority layers.
/// Resolve configuration precedence before supplying them here.
#[derive(Debug, Default, Clone)]
pub struct RoutingFacts {
    pub task_hints: Vec<TaskKind>,
    pub risk_hint: Option<RiskLevel>,
    pub known_operations: Vec<TaskKind>,
    pub safety: Vec<SafetyFact>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TaskRiskAssessment {
    pub task: TaskKind,
    pub risk: RiskLevel,
    /// Ambiguous signals a need for more evidence; it does not execute escalation.
    pub ambiguity: Ambiguity,
    /// Stable enum ordering, with equivalent evidence deduplicated.
    pub reasons: BTreeSet<Reason>,
}

/// Pure assessment. Safety floors > explicit risk > structural/ambiguity floors.
/// Known explicit tasks survive missing facts; conflicting known tasks are unknown.
pub fn assess(input: &RoutingFacts) -> TaskRiskAssessment {
    let mut reasons = BTreeSet::new();
    let mut tasks = BTreeSet::new();
    for (values, reason) in [
        (&input.task_hints, Reason::ExplicitTask),
        (&input.known_operations, Reason::KnownOperation),
    ] {
        for task in values.iter().filter(|task| **task != TaskKind::Unknown) {
            tasks.insert(*task);
            reasons.insert(reason);
        }
    }
    let (task, ambiguity) = match tasks.len() {
        0 => {
            reasons.insert(Reason::InsufficientTaskEvidence);
            (TaskKind::Unknown, Ambiguity::Ambiguous)
        }
        1 => (*tasks.first().expect("one task"), Ambiguity::Clear),
        _ => {
            reasons.insert(Reason::ConflictingTaskEvidence);
            (TaskKind::Unknown, Ambiguity::Ambiguous)
        }
    };
    let mut risk = input.risk_hint.unwrap_or(RiskLevel::Low);
    if input.risk_hint.is_some() {
        reasons.insert(Reason::ExplicitRisk);
    }
    // Keep the structural floor even when conflicting evidence obscures task kind.
    if tasks.contains(&TaskKind::Refactor) {
        risk = risk.max(RiskLevel::Medium);
        reasons.insert(Reason::StructuralChange);
    }
    if ambiguity == Ambiguity::Ambiguous {
        risk = risk.max(RiskLevel::Medium);
    }
    for fact in &input.safety {
        risk = RiskLevel::High;
        reasons.insert(match fact {
            SafetyFact::SecuritySensitive => Reason::SecuritySensitive,
            SafetyFact::MigrationSensitive => Reason::MigrationSensitive,
            SafetyFact::ConcurrencySensitive => Reason::ConcurrencySensitive,
        });
    }
    TaskRiskAssessment {
        task,
        risk,
        ambiguity,
        reasons,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn facts(task: TaskKind) -> RoutingFacts {
        RoutingFacts {
            known_operations: vec![task],
            ..Default::default()
        }
    }

    #[test]
    fn task_risk_table() {
        let cases = [
            (
                facts(TaskKind::Inspect),
                TaskKind::Inspect,
                RiskLevel::Low,
                Ambiguity::Clear,
            ),
            (
                facts(TaskKind::Edit),
                TaskKind::Edit,
                RiskLevel::Low,
                Ambiguity::Clear,
            ),
            (
                facts(TaskKind::Refactor),
                TaskKind::Refactor,
                RiskLevel::Medium,
                Ambiguity::Clear,
            ),
            (
                RoutingFacts::default(),
                TaskKind::Unknown,
                RiskLevel::Medium,
                Ambiguity::Ambiguous,
            ),
            (
                facts(TaskKind::Unknown),
                TaskKind::Unknown,
                RiskLevel::Medium,
                Ambiguity::Ambiguous,
            ),
            (
                RoutingFacts {
                    task_hints: vec![TaskKind::Edit],
                    ..Default::default()
                },
                TaskKind::Edit,
                RiskLevel::Low,
                Ambiguity::Clear,
            ),
            (
                RoutingFacts {
                    task_hints: vec![TaskKind::Edit, TaskKind::Inspect],
                    ..Default::default()
                },
                TaskKind::Unknown,
                RiskLevel::Medium,
                Ambiguity::Ambiguous,
            ),
            (
                RoutingFacts {
                    task_hints: vec![TaskKind::Inspect],
                    ..facts(TaskKind::Edit)
                },
                TaskKind::Unknown,
                RiskLevel::Medium,
                Ambiguity::Ambiguous,
            ),
            (
                RoutingFacts {
                    risk_hint: Some(RiskLevel::High),
                    ..facts(TaskKind::Inspect)
                },
                TaskKind::Inspect,
                RiskLevel::High,
                Ambiguity::Clear,
            ),
        ];
        for (input, task, risk, ambiguity) in cases {
            let result = assess(&input);
            assert_eq!(
                (result.task, result.risk, result.ambiguity),
                (task, risk, ambiguity),
                "{input:?}"
            );
        }
    }

    const SAFETY: [SafetyFact; 3] = [
        SafetyFact::SecuritySensitive,
        SafetyFact::MigrationSensitive,
        SafetyFact::ConcurrencySensitive,
    ];

    #[test]
    fn mandatory_safety_floors_and_monotonicity() {
        for task in [
            TaskKind::Unknown,
            TaskKind::Inspect,
            TaskKind::Edit,
            TaskKind::Refactor,
        ] {
            for hint in [
                None,
                Some(RiskLevel::Low),
                Some(RiskLevel::Medium),
                Some(RiskLevel::High),
            ] {
                let input = RoutingFacts {
                    risk_hint: hint,
                    ..facts(task)
                };
                for (fact, reason) in SAFETY.into_iter().zip([
                    Reason::SecuritySensitive,
                    Reason::MigrationSensitive,
                    Reason::ConcurrencySensitive,
                ]) {
                    let result = assess(&RoutingFacts {
                        safety: vec![fact],
                        ..input.clone()
                    });
                    assert_eq!(result.risk, RiskLevel::High);
                    assert!(result.risk >= assess(&input).risk);
                    assert_eq!(result.task, assess(&input).task);
                    assert!(result.reasons.contains(&reason));
                }
            }
        }
    }

    #[test]
    fn equivalent_evidence_has_stable_output() {
        let input = RoutingFacts {
            task_hints: vec![TaskKind::Edit, TaskKind::Inspect],
            known_operations: vec![TaskKind::Refactor, TaskKind::Edit],
            safety: SAFETY.to_vec(),
            risk_hint: Some(RiskLevel::Low),
        };
        let expected = assess(&input);
        let mut reordered = input.clone();
        reordered.task_hints.reverse();
        reordered.known_operations.reverse();
        reordered.safety.reverse();
        assert_eq!(assess(&reordered), expected);
        reordered.task_hints.extend(input.task_hints);
        reordered.known_operations.extend(input.known_operations);
        reordered.safety.extend(input.safety);
        assert_eq!(assess(&reordered), expected);
        assert!(expected.reasons.contains(&Reason::ConflictingTaskEvidence));
    }

    #[test]
    fn conflict_remains_ambiguous_as_evidence_grows() {
        for task in [
            TaskKind::Unknown,
            TaskKind::Inspect,
            TaskKind::Edit,
            TaskKind::Refactor,
        ] {
            let input = RoutingFacts {
                task_hints: vec![TaskKind::Inspect, TaskKind::Edit],
                known_operations: vec![task],
                ..Default::default()
            };
            assert_eq!(assess(&input).ambiguity, Ambiguity::Ambiguous);
        }
    }

    #[test]
    fn cost_metadata_stays_outside_policy_boundary() {
        // External cost metadata cannot enter RoutingFacts or the pure function.
        let semantic = facts(TaskKind::Edit);
        let expected = assess(&semantic);
        for repository_bytes in [0_u64, 1, 1_000_000, u64::MAX] {
            let external = (repository_bytes, &semantic);
            assert_eq!(assess(external.1), expected);
        }
    }

    #[test]
    fn missing_optional_facts_and_reasons() {
        let input = RoutingFacts {
            task_hints: vec![TaskKind::Inspect, TaskKind::Unknown],
            ..Default::default()
        };
        assert_eq!(
            assess(&input).reasons,
            BTreeSet::from([Reason::ExplicitTask])
        );
        assert_eq!(assess(&input).ambiguity, Ambiguity::Clear);
        assert_eq!(
            assess(&RoutingFacts::default()).reasons,
            BTreeSet::from([Reason::InsufficientTaskEvidence])
        );
    }
}
