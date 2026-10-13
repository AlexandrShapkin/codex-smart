use codex_smart_core::adaptive::{
    AdaptiveController, AdaptiveError, AttemptOutcome, ControllerState, ExecutionBudget,
    ValidationOutcome,
};
use codex_smart_core::adaptive_routing::{
    CompatibilityState, ModelCatalog, ModelDescriptor, ModelIdentity, ModelKey, ProviderKey,
    ReasoningCompatibility, ResolutionStatus, resolve_controller,
};
use codex_smart_core::playbook::{Archetype, ProfileClass};
use codex_smart_core::routing::Reasoning;
use codex_smart_core::routing::assessment::{
    RiskLevel, RoutingFacts, SafetyFact, TaskKind, assess,
};
use codex_smart_core::routing::engine::CapabilitySurface;
use codex_smart_core::workflow::{NativeSurface, ResourceCatalog, plan_workflow};
use std::env;
use std::process::ExitCode;

fn parse_task(value: &str) -> Option<TaskKind> {
    match value {
        "inspect" => Some(TaskKind::Inspect),
        "edit" => Some(TaskKind::Edit),
        "refactor" => Some(TaskKind::Refactor),
        _ => None,
    }
}
fn parse_risk(value: &str) -> Option<RiskLevel> {
    match value {
        "low" => Some(RiskLevel::Low),
        "medium" => Some(RiskLevel::Medium),
        "high" => Some(RiskLevel::High),
        _ => None,
    }
}
fn parse_archetype(value: &str) -> Option<Archetype> {
    match value {
        "inspection" => Some(Archetype::Inspection),
        "focused-bug-fix" => Some(Archetype::FocusedBugFix),
        "failing-test-repair" => Some(Archetype::FailingTestRepair),
        "feature-implementation" => Some(Archetype::FeatureImplementation),
        "api-change" => Some(Archetype::ApiChange),
        "refactor" => Some(Archetype::Refactor),
        "security-sensitive-change" => Some(Archetype::SecuritySensitiveChange),
        "ci-config-repair" => Some(Archetype::CiConfigRepair),
        "dependency-update" => Some(Archetype::DependencyUpdate),
        "documentation-change" => Some(Archetype::DocumentationChange),
        "release-preparation" => Some(Archetype::ReleasePreparation),
        _ => None,
    }
}
fn parse_safety(value: &str) -> Option<Vec<SafetyFact>> {
    if value == "none" {
        return Some(Vec::new());
    }
    value
        .split(',')
        .map(|item| match item {
            "security" => Some(SafetyFact::SecuritySensitive),
            "migration" => Some(SafetyFact::MigrationSensitive),
            "concurrency" => Some(SafetyFact::ConcurrencySensitive),
            _ => None,
        })
        .collect()
}
fn model(model: u16, profile: ProfileClass) -> ModelDescriptor {
    ModelDescriptor {
        identity: ModelIdentity {
            provider: ProviderKey(1),
            model: ModelKey(model),
        },
        profile,
        availability: CompatibilityState::Verified,
        reasoning: ReasoningCompatibility::VERIFIED,
    }
}
fn apply_event(controller: &mut AdaptiveController, event: &str) -> Result<(), AdaptiveError> {
    controller.start_attempt()?;
    match event {
        "runtime-failure" => controller.observe_attempt(AttemptOutcome::RuntimeFailure),
        "timeout" => controller.observe_attempt(AttemptOutcome::Timeout),
        "quality-failure" => {
            controller.observe_attempt(AttemptOutcome::Completed)?;
            controller.observe_validation(ValidationOutcome::Failed)
        }
        "quality-pass" => {
            controller.observe_attempt(AttemptOutcome::Completed)?;
            controller.observe_validation(ValidationOutcome::Passed)
        }
        _ => Err(AdaptiveError::InvalidState),
    }
}
fn state_name(state: ControllerState) -> &'static str {
    match state {
        ControllerState::Ready => "ready",
        ControllerState::Running => "running",
        ControllerState::AwaitingValidation => "awaiting-validation",
        ControllerState::NeedsEvidence(_) => "needs-evidence",
        ControllerState::Completed => "completed",
        ControllerState::Blocked(_) => "blocked",
        ControllerState::Exhausted => "exhausted",
    }
}
fn profile_name(profile: ProfileClass) -> &'static str {
    match profile {
        ProfileClass::Economy => "economy",
        ProfileClass::Standard => "standard",
        ProfileClass::Strong => "strong",
    }
}
fn reasoning_name(reasoning: Reasoning) -> &'static str {
    match reasoning {
        Reasoning::Medium => "medium",
        Reasoning::High => "high",
    }
}
fn usage() -> ExitCode {
    eprintln!(
        "usage: adaptive_benchmark_plan <task> <archetype> <risk> <safety|none> <max_attempts> <max_retries> <events|none>"
    );
    ExitCode::from(2)
}
fn main() -> ExitCode {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.len() != 7 {
        return usage();
    }
    let Some(task) = parse_task(&args[0]) else {
        return usage();
    };
    let Some(archetype) = parse_archetype(&args[1]) else {
        return usage();
    };
    let Some(risk) = parse_risk(&args[2]) else {
        return usage();
    };
    let Some(safety) = parse_safety(&args[3]) else {
        return usage();
    };
    let Ok(max_attempts) = args[4].parse::<u8>() else {
        return usage();
    };
    let Ok(max_retries) = args[5].parse::<u8>() else {
        return usage();
    };
    let events: Vec<&str> = if args[6] == "none" {
        Vec::new()
    } else {
        args[6].split(',').collect()
    };
    let assessment = assess(&RoutingFacts {
        task_hints: Vec::new(),
        risk_hint: Some(risk),
        known_operations: vec![task],
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
    let Some(validation) = workflow.validation_recipe(&native) else {
        eprintln!("validation recipe unavailable");
        return ExitCode::from(3);
    };
    let Ok(budget) = ExecutionBudget::new(max_attempts, max_retries, 0) else {
        eprintln!("invalid adaptive budget");
        return ExitCode::from(3);
    };
    let Ok(mut controller) = AdaptiveController::from_workflow(&workflow, &validation, budget)
    else {
        eprintln!("adaptive controller unavailable");
        return ExitCode::from(3);
    };
    for event in events {
        match apply_event(&mut controller, event) {
            Ok(()) => {}
            Err(AdaptiveError::AttemptBudgetExhausted | AdaptiveError::RetryBudgetExhausted)
                if controller.state == ControllerState::Exhausted => {}
            Err(error) => {
                eprintln!("invalid adaptive history: {error:?}");
                return ExitCode::from(3);
            }
        }
    }
    let catalog = ModelCatalog::new([
        model(10, ProfileClass::Economy),
        model(20, ProfileClass::Standard),
        model(30, ProfileClass::Strong),
    ]);
    let (profile, reasoning, model_key) = if controller.state == ControllerState::Ready {
        let resolution = resolve_controller(&controller, &catalog);
        if resolution.status != ResolutionStatus::Resolved {
            eprintln!("model resolution unavailable: {:?}", resolution.status);
            return ExitCode::from(3);
        }
        let target = resolution.target.expect("resolved target");
        (
            Some(profile_name(target.profile)),
            Some(reasoning_name(target.reasoning)),
            Some(target.identity.model.0),
        )
    } else {
        (None, None, None)
    };
    let profile_json = profile.map_or_else(|| "null".to_string(), |v| format!("\"{v}\""));
    let reasoning_json = reasoning.map_or_else(|| "null".to_string(), |v| format!("\"{v}\""));
    let model_json = model_key.map_or_else(|| "null".to_string(), |v| v.to_string());
    println!(
        "{{\"schema_version\":1,\"state\":\"{}\",\"profile\":{},\"reasoning\":{},\"model_key\":{},\"attempts_started\":{},\"retries_used\":{},\"delegations_used\":{}}}",
        state_name(controller.state),
        profile_json,
        reasoning_json,
        model_json,
        controller.attempts_started,
        controller.retries_used,
        controller.delegations_used,
    );
    ExitCode::SUCCESS
}
