//! Fake Codex argv capture, entirely in memory; production LaunchPlan is unchanged.
use codex_smart_core::routing::Reasoning;
use codex_smart_core::routing::assessment::{RoutingFacts, SafetyFact, TaskKind, assess};
use codex_smart_core::routing::engine::{CapabilitySurface, decide};
use codex_smart_core::routing::reasoning::{
    ReasoningCompatibility, ReasoningDecision, Support, select_reasoning,
};
use codex_smart_core::routing::reasoning_args::{ArgPlanOutcome, plan_reasoning_args};
use std::ffi::OsString;

const SUPPORTED: ReasoningCompatibility = ReasoningCompatibility {
    cli: Support::Supported,
    medium: Support::Supported,
    high: Support::Supported,
};
fn decision(
    explicit: Option<Reasoning>,
    compatibility: ReasoningCompatibility,
) -> ReasoningDecision {
    let assessment = assess(&RoutingFacts {
        task_hints: vec![TaskKind::Edit],
        safety: vec![SafetyFact::SecuritySensitive],
        ..Default::default()
    });
    let router = decide(&assessment, &[], &CapabilitySurface::default());
    select_reasoning(&router.assessment, explicit, compatibility)
}
fn argv(values: &[&str]) -> Vec<OsString> {
    values.iter().map(OsString::from).collect()
}

#[test]
fn exact_synthetic_args_and_literal_payload() {
    for (explicit, effort, config) in [
        (None, Reasoning::High, "model_reasoning_effort=\"high\""),
        (
            Some(Reasoning::Medium),
            Reasoning::Medium,
            "model_reasoning_effort=\"medium\"",
        ),
    ] {
        for prefix in [
            vec![],
            vec!["exec"],
            vec!["e"],
            vec!["-c", "unrelated=1", "exec", "--config=other='literal'"],
        ] {
            let mut original = argv(&prefix);
            original.extend(argv(&[
                "--",
                "$(touch /tmp/never); `echo secret` --config model_reasoning_effort=low",
            ]));
            let plan = plan_reasoning_args(original.clone(), &decision(explicit, SUPPORTED));
            let mut expected = argv(&["--config", config]);
            expected.extend(original);
            assert_eq!(plan.outcome, ArgPlanOutcome::Injected(effort));
            assert_eq!(plan.args(), expected);
            assert!(!plan.summary().contains("secret"));
            assert!(!format!("{plan:?}").contains("literal"));
        }
    }
}

#[test]
fn existing_user_overrides_and_conflicts_are_preserved() {
    let cases = [
        (
            vec!["--config", "model_reasoning_effort=medium"],
            ArgPlanOutcome::UserOverride {
                effort: Some(Reasoning::Medium),
                status: Support::Supported,
            },
        ),
        (
            vec!["-c", "model_reasoning_effort=high"],
            ArgPlanOutcome::UserOverride {
                effort: Some(Reasoning::High),
                status: Support::Supported,
            },
        ),
        (
            vec!["--config=model_reasoning_effort='high'"],
            ArgPlanOutcome::UserOverride {
                effort: Some(Reasoning::High),
                status: Support::Supported,
            },
        ),
        (
            vec!["-cmodel_reasoning_effort=high"],
            ArgPlanOutcome::UserOverride {
                effort: Some(Reasoning::High),
                status: Support::Supported,
            },
        ),
        (
            vec!["-c=model_reasoning_effort=high"],
            ArgPlanOutcome::UserOverride {
                effort: Some(Reasoning::High),
                status: Support::Supported,
            },
        ),
        (
            vec![
                "--config",
                "unrelated=1",
                "exec",
                "-c",
                " model_reasoning_effort = \"medium\" ",
            ],
            ArgPlanOutcome::UserOverride {
                effort: Some(Reasoning::Medium),
                status: Support::Supported,
            },
        ),
        (
            vec![
                "-c",
                "model_reasoning_effort=medium",
                "exec",
                "--config",
                "model_reasoning_effort='medium'",
            ],
            ArgPlanOutcome::UserOverride {
                effort: Some(Reasoning::Medium),
                status: Support::Supported,
            },
        ),
        (
            vec![
                "-c",
                "model_reasoning_effort=medium",
                "--config",
                "model_reasoning_effort=high",
            ],
            ArgPlanOutcome::ConflictingUserOverrides,
        ),
        (
            vec![
                "-c",
                "model_reasoning_effort=high",
                "--config",
                "model_reasoning_effort=medium",
            ],
            ArgPlanOutcome::ConflictingUserOverrides,
        ),
        (
            vec!["--config", "model_reasoning_effort=xhigh"],
            ArgPlanOutcome::UserOverride {
                effort: None,
                status: Support::Unknown,
            },
        ),
        (
            vec!["--config", "model_reasoning_effort=1"],
            ArgPlanOutcome::AmbiguousArguments,
        ),
        (
            vec!["--config", "model_reasoning_effort=[\"high\"]"],
            ArgPlanOutcome::AmbiguousArguments,
        ),
        (
            vec!["--config", "model_reasoning_effort=\"high"],
            ArgPlanOutcome::AmbiguousArguments,
        ),
    ];
    for (values, expected) in cases {
        let original = argv(&values);
        let plan = plan_reasoning_args(original.clone(), &decision(None, SUPPORTED));
        assert_eq!(plan.outcome, expected, "{expected:?}");
        assert_eq!(plan.args(), original);
    }
    let compatibility = ReasoningCompatibility {
        medium: Support::Unsupported,
        ..SUPPORTED
    };
    let original = argv(&["--config", "model_reasoning_effort=medium"]);
    let plan = plan_reasoning_args(original.clone(), &decision(None, compatibility));
    assert_eq!(
        plan.outcome,
        ArgPlanOutcome::UserOverride {
            effort: Some(Reasoning::Medium),
            status: Support::Unsupported
        }
    );
    assert_eq!(plan.args(), original);
}

#[test]
fn changed_target_unknown_compatibility_and_unsupported_shapes_defer() {
    for values in [
        vec!["--model", "unattested"],
        vec!["-m", "unattested"],
        vec!["--model=unattested"],
        vec!["-munattested"],
        vec!["--profile", "work"],
        vec!["-p", "work"],
        vec!["--profile=work"],
        vec!["-pwork"],
        vec!["-c", "model='unattested'"],
        vec!["-c", "model_provider='custom'"],
        vec!["-c", "models.new_thread.model='unattested'"],
        vec!["-c", "model_catalog_json='unread'"],
    ] {
        let original = argv(&values);
        let plan = plan_reasoning_args(original.clone(), &decision(None, SUPPORTED));
        assert_eq!(plan.outcome, ArgPlanOutcome::DeferredTargetOverride);
        assert_eq!(plan.args(), original);
    }
    for (values, expected) in [
        (vec!["--config"], ArgPlanOutcome::AmbiguousArguments),
        (
            vec!["-c", "--config=model_reasoning_effort=medium"],
            ArgPlanOutcome::AmbiguousArguments,
        ),
        (vec!["--model"], ArgPlanOutcome::AmbiguousArguments),
        (vec!["--profile="], ArgPlanOutcome::AmbiguousArguments),
        (
            vec!["--config", "model_reasoning_effort"],
            ArgPlanOutcome::AmbiguousArguments,
        ),
        (
            vec!["--config", "\"model_reasoning_effort\"='high'"],
            ArgPlanOutcome::AmbiguousArguments,
        ),
        (
            vec!["--unknown", "--config", "model_reasoning_effort=medium"],
            ArgPlanOutcome::UnsupportedInvocation,
        ),
        (
            vec!["exec", "plain positional prompt"],
            ArgPlanOutcome::UnsupportedInvocation,
        ),
        (
            vec!["resume", "--last"],
            ArgPlanOutcome::UnsupportedInvocation,
        ),
    ] {
        let original = argv(&values);
        let plan = plan_reasoning_args(original.clone(), &decision(None, SUPPORTED));
        assert_eq!(plan.outcome, expected);
        assert_eq!(plan.args(), original);
    }
    for (compatibility, expected) in [
        (
            ReasoningCompatibility::default(),
            ArgPlanOutcome::CompatibilityUnknown,
        ),
        (
            ReasoningCompatibility {
                high: Support::Unsupported,
                ..SUPPORTED
            },
            ArgPlanOutcome::CompatibilityUnsupported,
        ),
        (
            ReasoningCompatibility {
                cli: Support::Unknown,
                ..SUPPORTED
            },
            ArgPlanOutcome::CompatibilityUnknown,
        ),
    ] {
        let original = argv(&["exec", "--", "task"]);
        let plan = plan_reasoning_args(original.clone(), &decision(None, compatibility));
        assert_eq!(plan.outcome, expected);
        assert_eq!(plan.args(), original);
    }
    let original = argv(&["--model", "unattested", "-c", "model_reasoning_effort=high"]);
    let plan = plan_reasoning_args(original.clone(), &decision(None, SUPPORTED));
    assert_eq!(
        plan.outcome,
        ArgPlanOutcome::UserOverride {
            effort: Some(Reasoning::High),
            status: Support::Unknown
        }
    );
    assert_eq!(plan.args(), original);
}

#[test]
fn bounds_and_explanation_privacy() {
    for original in [
        vec![OsString::from("--"); 257],
        vec![OsString::from("x".repeat(16_385))],
    ] {
        let plan = plan_reasoning_args(original.clone(), &decision(None, SUPPORTED));
        assert_eq!(plan.outcome, ArgPlanOutcome::BoundsExceeded);
        assert_eq!(plan.args(), original);
    }
    let plan = plan_reasoning_args(
        argv(&["-c", "model_reasoning_effort='PRIVATE_EFFORT_TOKEN'"]),
        &decision(None, SUPPORTED),
    );
    assert!(!plan.summary().contains("PRIVATE"));
    assert!(!format!("{plan:?}").contains("PRIVATE"));
}

#[cfg(unix)]
#[test]
fn non_utf8_payload_and_unrelated_bytes_survive() {
    use std::os::unix::ffi::OsStringExt;
    let payload = OsString::from_vec(vec![b'p', 0xff, b';', b'$']);
    let original = vec![
        OsString::from("exec"),
        OsString::from("--"),
        payload.clone(),
    ];
    let plan = plan_reasoning_args(original.clone(), &decision(None, SUPPORTED));
    assert_eq!(plan.outcome, ArgPlanOutcome::Injected(Reasoning::High));
    assert_eq!(&plan.args()[2..], original);
    let original = vec![OsString::from("-c"), payload];
    let plan = plan_reasoning_args(original.clone(), &decision(None, SUPPORTED));
    assert_eq!(plan.outcome, ArgPlanOutcome::AmbiguousArguments);
    assert_eq!(plan.args(), original);
}
