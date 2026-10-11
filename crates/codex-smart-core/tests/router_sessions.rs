//! In-memory E2E sessions across the public facts -> assessment -> decision -> explain API.
use codex_smart_core::routing::assessment::{RoutingFacts, TaskKind, assess};
use codex_smart_core::routing::engine::{
    Backend, CapabilityNeed, CapabilityState, CapabilitySurface, decide,
};

#[test]
fn stubbed_router_sessions() {
    let cases = [
        (
            "native",
            TaskKind::Inspect,
            None,
            CapabilityState::Unknown,
            "Inspect",
            "Low",
            "Clear",
            "{}",
            "{ExplicitTask}",
            "{NativeBaseline, NoExternalNeed}",
        ),
        (
            "verified structural",
            TaskKind::Edit,
            Some(CapabilityNeed::StructuralImpact),
            CapabilityState::Verified,
            "Edit",
            "Low",
            "Clear",
            "{CodeGraph}",
            "{ExplicitTask}",
            "{NativeBaseline, VerifiedCapabilitySelected(CodeGraph)}",
        ),
        (
            "unknown structural",
            TaskKind::Edit,
            Some(CapabilityNeed::StructuralImpact),
            CapabilityState::Unknown,
            "Edit",
            "Low",
            "Clear",
            "{}",
            "{ExplicitTask}",
            "{NativeBaseline, CapabilityUnknown(CodeGraph)}",
        ),
        (
            "blocked structural",
            TaskKind::Edit,
            Some(CapabilityNeed::StructuralImpact),
            CapabilityState::Blocked,
            "Edit",
            "Low",
            "Clear",
            "{}",
            "{ExplicitTask}",
            "{NativeBaseline, CapabilityBlocked(CodeGraph)}",
        ),
        (
            "ambiguous",
            TaskKind::Unknown,
            Some(CapabilityNeed::StructuralImpact),
            CapabilityState::Verified,
            "Unknown",
            "Medium",
            "Ambiguous",
            "{}",
            "{InsufficientTaskEvidence}",
            "{NativeBaseline, AmbiguousTask, CapabilityDeferredForAmbiguity(CodeGraph)}",
        ),
    ];
    for (
        name,
        task,
        need,
        state,
        task_text,
        risk,
        ambiguity,
        augmentations,
        assessment_reasons,
        reasons,
    ) in cases
    {
        let facts = RoutingFacts {
            task_hints: vec![task],
            ..Default::default()
        };
        let surface = CapabilitySurface::new([(Backend::CodeGraph, state)]);
        let needs: Vec<_> = need.into_iter().collect();
        let decision = decide(&assess(&facts), &needs, &surface);
        let expected = format!(
            "Router v2 decision (no activation)\nTask: {task_text}\nRisk: {risk}\nAmbiguity: {ambiguity}\nNative baseline: shell/git/search/build/test (subject to host availability)\nVerified augmentations: {augmentations}\nAssessment reasons: {assessment_reasons}\nDecision reasons: {reasons}\n"
        );
        assert_eq!(decision.render(), expected, "session: {name}");
        assert_eq!(decide(&assess(&facts), &needs, &surface).render(), expected);
    }
}
