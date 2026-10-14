//! Explicit declarative adapter. No discovery, configuration or runtime calls.
use codex_smart_core::{
    playbook::Archetype,
    preparation::{Limits, safe_nomination},
    routing::{
        assessment::{RiskLevel, RoutingFacts, SafetyFact, TaskKind, assess},
        engine::CapabilitySurface,
    },
    workflow::{NativeSurface, ResourceCatalog, plan_workflow},
};
use std::{collections::BTreeSet, ffi::OsString, path::Path};

pub const HELP: &str = "plan --intent inspection [--task inspect|edit|refactor|unknown] [--risk low|medium|high] [--safety none|security|migration|concurrency] [--file RELATIVE_PATH ...]";
const INVALID: &str = "E_PLAN_ARGS: invalid, unsupported or duplicate plan option";
const LIMIT: &str = "E_PLAN_LIMIT: plan input exceeds bounded limits";

/// Output contains only policy enums and counts; input values are never echoed.
pub fn preview(args: &[OsString]) -> Result<String, &'static str> {
    // Eight singleton option/value arguments and sixteen file option/value pairs.
    if args.len() > 40 || args.iter().map(|arg| arg.len()).sum::<usize>() > 18_432 {
        return Err(LIMIT);
    }
    if !args.len().is_multiple_of(2) {
        return Err(INVALID);
    }
    let mut intent = false;
    let mut task = None;
    let mut risk = None;
    let mut safety = None;
    let mut files = BTreeSet::new();
    for pair in args.as_chunks::<2>().0 {
        let value = pair[1].to_str().ok_or(INVALID)?;
        match pair[0].to_str() {
            Some("--intent") if !intent && value == "inspection" => intent = true,
            Some("--task") if task.is_none() => {
                task = Some(match value {
                    "inspect" => TaskKind::Inspect,
                    "edit" => TaskKind::Edit,
                    "refactor" => TaskKind::Refactor,
                    "unknown" => TaskKind::Unknown,
                    _ => return Err(INVALID),
                });
            }
            Some("--risk") if risk.is_none() => {
                risk = Some(match value {
                    "low" => RiskLevel::Low,
                    "medium" => RiskLevel::Medium,
                    "high" => RiskLevel::High,
                    _ => return Err(INVALID),
                });
            }
            Some("--safety") if safety.is_none() => {
                safety = Some(match value {
                    "none" => vec![],
                    "security" => vec![SafetyFact::SecuritySensitive],
                    "migration" => vec![SafetyFact::MigrationSensitive],
                    "concurrency" => vec![SafetyFact::ConcurrencySensitive],
                    _ => return Err(INVALID),
                });
            }
            Some("--file") => {
                let path = Path::new(value);
                if !safe_nomination(path) || !files.insert(path) {
                    return Err("E_PLAN_PATH: unsafe or duplicate declarative nomination");
                }
                if files.len() > Limits::default().files {
                    return Err(LIMIT);
                }
            }
            _ => return Err(INVALID),
        }
    }
    if !intent {
        return Err("E_PLAN_INTENT: explicit --intent inspection required");
    }
    let risk_declared = risk.is_some();
    let safety_declared = safety.is_some();
    let assessment = assess(&RoutingFacts {
        known_operations: if task == Some(TaskKind::Unknown) {
            vec![]
        } else {
            vec![TaskKind::Inspect]
        },
        task_hints: task.into_iter().collect(),
        risk_hint: risk,
        safety: safety.unwrap_or_default(),
    });
    // Declarations describe intent; they never establish capability verification.
    let native = NativeSurface::default();
    let workflow = plan_workflow(
        &assessment,
        Some(Archetype::Inspection),
        &native,
        &CapabilitySurface::default(),
        &ResourceCatalog::default(),
    );
    let validation = workflow.validation_recipe(&native);
    Ok(format!(
        "{}Assessment: {:?}; {:?}; {:?}\nRisk evidence: {}\nSafety evidence: {}\nNative evidence: Unknown\nExternal evidence: Unknown\nModel identity: Unknown\nNominated relevant files: {} (declarative; acquired=0; semantic coverage=Unknown)\nValidation recipe: {:?}\nExecution authority: none\n",
        workflow.render(),
        assessment.task,
        assessment.ambiguity,
        assessment.reasons,
        if risk_declared { "Declared" } else { "Unknown" },
        if safety_declared {
            "Declared"
        } else {
            "Unknown"
        },
        files.len(),
        validation,
    ))
}
