//! One explicit read-only Codex attempt. Bundled catalog support is identity-bound
//! to the selected executable, but freshness and provider availability stay unknown.
use codex_smart_core::{
    adaptive_routing::{
        CompatibilityState, ModelCatalog, ModelDescriptor, ModelIdentity, ModelKey, ProviderKey,
        ReasoningCompatibility as ModelReasoning, ResolutionStatus, resolve_model,
    },
    playbook::ProfileClass,
    process::LaunchPlan,
    routing::{
        Reasoning,
        assessment::{Ambiguity, RiskLevel, RoutingFacts, SafetyFact, TaskKind, assess},
        reasoning::{ReasoningCompatibility, Support, select_reasoning},
        reasoning_args::{ArgPlanOutcome, plan_reasoning_args},
    },
    workflow::{SelectionStatus, select_playbook},
};
use std::{ffi::OsString, path::Path};

pub const HELP: &str = "inspect [--risk low|medium|high] [--safety none|security|migration|concurrency] [--reasoning medium|high] [--model gpt-6-luna|gpt-6-sol|gpt-6-astra] [--] \"Read-only inspection task\"\nOne explicit codex exec -s read-only attempt. Low-risk only. Bundled catalog support is checked against the selected Codex 0.162.1 executable; freshness and account/provider availability remain unknown. A provider failure is returned without retry. No prompt inspection or savings claim.";
const ARGS: &str = "E_INSPECT_ARGS: expected one quoted task and supported, unique typed options";

#[derive(Clone, Copy)]
struct Candidate {
    name: &'static str,
    profile: ProfileClass,
    key: ModelKey,
}
const CANDIDATES: [Candidate; 3] = [
    Candidate {
        name: "gpt-6-luna",
        profile: ProfileClass::Economy,
        key: ModelKey(1),
    },
    Candidate {
        name: "gpt-6-sol",
        profile: ProfileClass::Standard,
        key: ModelKey(2),
    },
    Candidate {
        name: "gpt-6-astra",
        profile: ProfileClass::Strong,
        key: ModelKey(3),
    },
];

struct CatalogSnapshot {
    catalog: ModelCatalog,
    support: [Option<(bool, bool)>; 3],
}

fn support(model: &serde_json::Value, effort: &str) -> bool {
    model
        .get("supported_reasoning_levels")
        .and_then(serde_json::Value::as_array)
        .is_some_and(|levels| {
            levels.iter().any(|level| {
                level.get("effort").and_then(serde_json::Value::as_str) == Some(effort)
            })
        })
}

fn catalog(source: &[u8]) -> Result<CatalogSnapshot, &'static str> {
    let value: serde_json::Value =
        serde_json::from_slice(source).map_err(|_| "E_INSPECT_CATALOG: invalid bundled catalog")?;
    let models = value
        .get("models")
        .and_then(serde_json::Value::as_array)
        .ok_or("E_INSPECT_CATALOG: invalid bundled catalog")?;
    let mut states = [None; 3];
    let mut descriptors = Vec::new();
    for (index, candidate) in CANDIDATES.iter().enumerate() {
        let mut matches = models.iter().filter(|model| {
            model.get("slug").and_then(serde_json::Value::as_str) == Some(candidate.name)
        });
        let Some(model) = matches.next() else {
            continue;
        };
        if matches.next().is_some() {
            return Err("E_INSPECT_CATALOG: conflicting model entries");
        }
        if model
            .get("supported_in_api")
            .and_then(serde_json::Value::as_bool)
            != Some(true)
        {
            continue;
        }
        let medium = support(model, "medium");
        let high = support(model, "high");
        states[index] = Some((medium, high));
        descriptors.push(ModelDescriptor {
            identity: ModelIdentity {
                provider: ProviderKey(1),
                model: candidate.key,
            },
            profile: candidate.profile,
            availability: CompatibilityState::Unknown,
            reasoning: ModelReasoning {
                medium: if medium {
                    CompatibilityState::Verified
                } else {
                    CompatibilityState::Unsupported
                },
                high: if high {
                    CompatibilityState::Verified
                } else {
                    CompatibilityState::Unsupported
                },
            },
        });
    }
    Ok(CatalogSnapshot {
        catalog: ModelCatalog::new(descriptors),
        support: states,
    })
}

pub fn execute(args: &[OsString], repo: &Path) -> Result<i32, &'static str> {
    if args.len() > 11 || args.iter().map(|arg| arg.len()).sum::<usize>() > 16_384 {
        return Err(ARGS);
    }
    let mut risk = None;
    let mut safety = None;
    let mut reasoning = None;
    let mut model = None;
    let mut index = 0;
    while index < args.len() {
        if args[index] == "--" {
            index += 1;
            break;
        }
        let Some(option) = args[index].to_str() else {
            break;
        };
        if !option.starts_with('-') {
            break;
        }
        let value = args.get(index + 1).and_then(|v| v.to_str()).ok_or(ARGS)?;
        match option {
            "--risk" if risk.is_none() => {
                risk = Some(match value {
                    "low" => RiskLevel::Low,
                    "medium" => RiskLevel::Medium,
                    "high" => RiskLevel::High,
                    _ => return Err(ARGS),
                })
            }
            "--safety" if safety.is_none() => {
                safety = Some(match value {
                    "none" => None,
                    "security" => Some(SafetyFact::SecuritySensitive),
                    "migration" => Some(SafetyFact::MigrationSensitive),
                    "concurrency" => Some(SafetyFact::ConcurrencySensitive),
                    _ => return Err(ARGS),
                })
            }
            "--reasoning" if reasoning.is_none() => {
                reasoning = Some(Reasoning::parse(value).ok_or(ARGS)?)
            }
            "--model" if model.is_none() => {
                model = Some(
                    CANDIDATES
                        .iter()
                        .position(|candidate| candidate.name == value)
                        .ok_or(ARGS)?,
                )
            }
            _ => return Err(ARGS),
        }
        index += 2;
    }
    if args.len() != index + 1 || args[index].is_empty() {
        return Err(ARGS);
    }
    let assessment = assess(&RoutingFacts {
        task_hints: vec![TaskKind::Inspect],
        risk_hint: risk,
        safety: safety.flatten().into_iter().collect(),
        ..Default::default()
    });
    let selection = select_playbook(&assessment, None);
    if assessment.ambiguity != Ambiguity::Clear || selection.status != SelectionStatus::Selected {
        return Err("E_INSPECT_POLICY: inspection task evidence is not selectable");
    }
    if assessment.risk != RiskLevel::Low {
        return Err(
            "E_INSPECT_FLOOR: higher risk requires verified stronger model evidence; no launch",
        );
    }
    let required_profile = selection
        .profile
        .ok_or("E_INSPECT_POLICY: missing profile")?;
    let candidate = CANDIDATES[model.unwrap_or(0)];
    if candidate.profile < required_profile {
        return Err("E_INSPECT_FLOOR: model below policy floor");
    }
    let effort = reasoning.unwrap_or(
        selection
            .reasoning
            .ok_or("E_INSPECT_POLICY: missing reasoning")?,
    );
    let plan = LaunchPlan::prepare(std::env::var_os("PATH").as_deref(), repo, Vec::new())
        .map_err(|e| e.code())?;
    let snapshot = catalog(&plan.inspect_catalog().map_err(|e| e.code())?)?;
    let resolution = resolve_model(required_profile, effort, &snapshot.catalog);
    // The bundled catalog cannot prove account availability. Only this explicit
    // command permits one attempt with that fact still Unknown.
    if resolution.status != ResolutionStatus::NeedsEvidence {
        return Err("E_INSPECT_MODEL: model compatibility unavailable or unsupported; no launch");
    }
    let (medium, high) = snapshot.support[model.unwrap_or(0)]
        .ok_or("E_INSPECT_MODEL: selected model absent from bundled catalog; no launch")?;
    if !(match effort {
        Reasoning::Medium => medium,
        Reasoning::High => high,
    }) {
        return Err("E_INSPECT_MODEL: selected effort unsupported; no launch");
    }
    let decision = select_reasoning(
        &assessment,
        Some(effort),
        ReasoningCompatibility {
            cli: Support::Supported,
            medium: if medium {
                Support::Supported
            } else {
                Support::Unsupported
            },
            high: if high {
                Support::Supported
            } else {
                Support::Unsupported
            },
        },
    );
    let planned = plan_reasoning_args(vec![OsString::from("--"), args[index].clone()], &decision);
    if planned.outcome != ArgPlanOutcome::Injected(effort) {
        return Err("E_INSPECT_ARGS: reasoning argv could not be planned; no launch");
    }
    let mut argv = vec![OsString::from("--model"), OsString::from(candidate.name)];
    argv.extend_from_slice(&planned.args()[..2]);
    argv.extend([
        OsString::from("exec"),
        OsString::from("-s"),
        OsString::from("read-only"),
    ]);
    argv.extend_from_slice(&planned.args()[2..]);
    eprintln!(
        "Inspect: bundled model/effort syntax checked for Codex 0.162.1; catalog freshness and account/provider availability unknown; explicit single read-only attempt, no retry"
    );
    plan.with_args(argv)
        .with_closed_stdin()
        .execute()
        .map_err(|e| e.code())
}
