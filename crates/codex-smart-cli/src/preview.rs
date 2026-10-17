//! One-attempt preview. Explicit facts only; no capability verification or replay.
use codex_smart_core::routing::{
    Reasoning,
    assessment::{Ambiguity, RiskLevel, RoutingFacts, SafetyFact, TaskKind, assess},
    reasoning::{ReasoningCompatibility, select_reasoning},
    reasoning_args::{ArgPlanOutcome, plan_reasoning_args},
};
use std::ffi::OsString;

pub const HELP: &str = "Preview: codex-smart [--intent inspection] [--risk low|medium|high] [--safety security|migration|concurrency] [--reasoning medium|high] [--] [PROMPT]\nNo prompt opens interactive Codex; one PROMPT starts one Codex exec. Inspection intent adds native-first guidance. Explicit reasoning is forwarded with compatibility unknown. High risk refuses without verified Strong/High. Use run -- ARGS for exact Codex passthrough.";

pub fn arguments(mut input: Vec<OsString>) -> Result<Vec<OsString>, &'static str> {
    let mut facts = RoutingFacts::default();
    let mut effort = None;
    let mut inspection = false;
    let mut index = 0;
    while index < input.len() {
        if input[index] == "--" {
            index += 1;
            break;
        }
        let Some(option) = input[index].to_str() else {
            break;
        };
        if !option.starts_with('-') {
            break;
        }
        let value = input
            .get(index + 1)
            .and_then(|v| v.to_str())
            .ok_or("E_PREVIEW_ARGS: expected typed option value; use run -- for Codex options")?;
        match option {
            "--intent" if !inspection && value == "inspection" => {
                inspection = true;
                facts.task_hints.push(TaskKind::Inspect);
            }
            "--risk" if facts.risk_hint.is_none() => {
                facts.risk_hint = Some(match value {
                    "low" => RiskLevel::Low,
                    "medium" => RiskLevel::Medium,
                    "high" => RiskLevel::High,
                    _ => return Err("E_PREVIEW_ARGS: invalid risk"),
                })
            }
            "--safety" if facts.safety.is_empty() => facts.safety.push(match value {
                "security" => SafetyFact::SecuritySensitive,
                "migration" => SafetyFact::MigrationSensitive,
                "concurrency" => SafetyFact::ConcurrencySensitive,
                _ => return Err("E_PREVIEW_ARGS: invalid safety fact"),
            }),
            "--reasoning" if effort.is_none() => {
                effort = Some(
                    Reasoning::parse(value)
                        .ok_or("E_PREVIEW_ARGS: reasoning must be medium or high")?,
                )
            }
            _ => {
                return Err(
                    "E_PREVIEW_ARGS: unknown or duplicate option; use run -- for Codex options",
                );
            }
        }
        index += 2;
    }
    input.drain(..index);
    if input.len() > 1 {
        return Err("E_PREVIEW_ARGS: quote one task prompt; use run -- for Codex arguments");
    }
    let assessment = assess(&facts);
    let decision = select_reasoning(&assessment, effort, ReasoningCompatibility::default());
    if assessment.risk == RiskLevel::High {
        return Err(
            "E_PREVIEW_FLOOR: Strong/High required; model compatibility unknown; no launch",
        );
    }
    let native_guidance = inspection
        && assessment.task == TaskKind::Inspect
        && assessment.ambiguity == Ambiguity::Clear;
    if native_guidance && input.is_empty() {
        return Err("E_PREVIEW_ARGS: inspection optimization requires a task prompt");
    }
    let mut args = Vec::new();
    if let Some(effort) = effort {
        args.extend([
            OsString::from("--config"),
            OsString::from(match effort {
                Reasoning::Medium => "model_reasoning_effort=\"medium\"",
                Reasoning::High => "model_reasoning_effort=\"high\"",
            }),
        ]);
    }
    if let Some(prompt) = input.pop() {
        args.push("exec".into());
        args.push("--".into());
        // Explicit inspection intent accepts only this bounded instruction optimization.
        // It asserts no tool health, context sufficiency or model compatibility.
        let prompt = if native_guidance {
            let mut guided = OsString::from(
                "For this inspection, prefer targeted native file/search tools when available. Preserve required quality and verification; use other tools when needed.\n\n",
            );
            guided.push(prompt);
            guided
        } else {
            prompt
        };
        args.push(prompt);
    }
    let plan = plan_reasoning_args(args, &decision);
    match plan.outcome {
        ArgPlanOutcome::CompatibilityUnknown | ArgPlanOutcome::UserOverride { .. } => {}
        _ => return Err("E_PREVIEW_POLICY: unsupported argument plan; no launch"),
    }
    eprintln!(
        "Preview: {}; reasoning compatibility unknown; {}; one launch, no replay",
        if native_guidance {
            "accepted explicit inspection guidance"
        } else {
            "Codex defaults"
        },
        if effort.is_some() {
            "explicit user reasoning override"
        } else {
            "reasoning unchanged"
        }
    );
    Ok(plan.args().to_vec())
}
