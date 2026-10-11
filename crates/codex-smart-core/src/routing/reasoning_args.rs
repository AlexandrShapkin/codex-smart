//! Bounded OS-argv planning only. Not connected to the production launch path.
use super::Reasoning;
use super::reasoning::{ReasoningDecision, Support};
use std::ffi::{OsStr, OsString};

const MAX_ARGS: usize = 256;
const MAX_ARG_BYTES: usize = 16_384;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ArgPlanOutcome {
    Injected(Reasoning),
    /// None means a valid forwarded string outside Medium/High; support stays Unknown.
    UserOverride {
        effort: Option<Reasoning>,
        status: Support,
    },
    ConflictingUserOverrides,
    AmbiguousArguments,
    UnsupportedInvocation,
    DeferredTargetOverride,
    CompatibilityUnknown,
    CompatibilityUnsupported,
    BoundsExceeded,
}

#[derive(Clone, PartialEq, Eq)]
pub struct ReasoningArgPlan {
    args: Vec<OsString>,
    pub outcome: ArgPlanOutcome,
}
impl ReasoningArgPlan {
    pub fn args(&self) -> &[OsString] {
        &self.args
    }
    pub fn summary(&self) -> String {
        format!(
            "Reasoning argv plan (not executed)\nOutcome: {:?}\nArguments: {}; values omitted\n",
            self.outcome,
            self.args.len()
        )
    }
}
impl std::fmt::Debug for ReasoningArgPlan {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str(&self.summary())
    }
}

#[derive(Default)]
struct Overrides {
    effort: Option<String>,
    conflict: bool,
    target_changed: bool,
}
impl Overrides {
    fn config(&mut self, value: &OsStr) -> Result<(), ArgPlanOutcome> {
        let value = value.to_str().ok_or(ArgPlanOutcome::AmbiguousArguments)?;
        if value.trim_start().starts_with('-') {
            return Err(ArgPlanOutcome::AmbiguousArguments);
        }
        let (key, raw) = value
            .split_once('=')
            .ok_or(ArgPlanOutcome::AmbiguousArguments)?;
        let key = key.trim();
        // No guessing quoted/table/ambiguous key syntax.
        if key.is_empty()
            || !key
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '.' || c == '-')
        {
            return Err(ArgPlanOutcome::AmbiguousArguments);
        }
        if key == "model_reasoning_effort" {
            let raw = raw.trim();
            let effort = match raw.parse::<toml_edit::Value>() {
                Ok(value) => value
                    .as_str()
                    .map(str::to_owned)
                    .ok_or(ArgPlanOutcome::AmbiguousArguments)?,
                // The pinned parser supports raw-string fallback. Restrict our accepted
                // fallback to plain identifiers rather than emulate every malformed TOML.
                Err(_)
                    if !raw.is_empty()
                        && raw
                            .chars()
                            .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-') =>
                {
                    raw.to_owned()
                }
                Err(_) => return Err(ArgPlanOutcome::AmbiguousArguments),
            };
            if let Some(previous) = &self.effort {
                self.conflict |= previous != &effort;
            } else {
                self.effort = Some(effort);
            }
        } else if matches!(
            key,
            "model"
                | "model_provider"
                | "model_catalog_json"
                | "profile"
                | "models"
                | "model_providers"
        ) || key.starts_with("models.")
            || key.starts_with("model_providers.")
            || key.starts_with("profiles.")
            || key.starts_with("model_reasoning_effort.")
        {
            self.target_changed = true;
        }
        Ok(())
    }
}

/// Supports reviewed interactive/exec option prefixes; payload starts after `--`.
/// Positional prompts/subcommands without that boundary and unknown option grammar
/// defer conservatively. Preserved argv never becomes a shell command.
fn inspect(args: &[OsString]) -> Result<Overrides, ArgPlanOutcome> {
    let mut overrides = Overrides::default();
    let mut index = 0;
    let mut exec_seen = false;
    while index < args.len() {
        let arg = args[index]
            .to_str()
            .ok_or(ArgPlanOutcome::AmbiguousArguments)?;
        if arg == "--" {
            break;
        }
        if matches!(arg, "exec" | "e") && !exec_seen {
            exec_seen = true;
            index += 1;
            continue;
        }
        let (kind, attached) = if matches!(arg, "--config" | "-c") {
            ("config", None)
        } else if matches!(arg, "--model" | "-m" | "--profile" | "-p") {
            ("target", None)
        } else if let Some(value) = arg.strip_prefix("--config=") {
            ("config", Some(value))
        } else if let Some(value) = arg.strip_prefix("-c").filter(|value| !value.is_empty()) {
            ("config", Some(value.strip_prefix('=').unwrap_or(value)))
        } else if arg.starts_with("--model=")
            || arg.starts_with("--profile=")
            || (arg.starts_with("-m") || arg.starts_with("-p")) && arg.len() > 2
        {
            (
                "target",
                Some(arg.split_once('=').map_or(&arg[2..], |(_, value)| value)),
            )
        } else {
            // Do not duplicate Codex's full clap grammar. Unknown flags may consume
            // values which look like our options; never inject on such a guess.
            return Err(ArgPlanOutcome::UnsupportedInvocation);
        };
        let value = if let Some(value) = attached {
            OsStr::new(value)
        } else {
            index += 1;
            args.get(index)
                .map(OsString::as_os_str)
                .ok_or(ArgPlanOutcome::AmbiguousArguments)?
        };
        if kind == "config" {
            overrides.config(value)?;
        } else {
            if value.is_empty() || value.to_str().is_some_and(|value| value.starts_with('-')) {
                return Err(ArgPlanOutcome::AmbiguousArguments);
            }
            overrides.target_changed = true;
        }
        index += 1;
    }
    Ok(overrides)
}

pub fn plan_reasoning_args(
    mut args: Vec<OsString>,
    decision: &ReasoningDecision,
) -> ReasoningArgPlan {
    if args.len() > MAX_ARGS {
        return ReasoningArgPlan {
            args,
            outcome: ArgPlanOutcome::BoundsExceeded,
        };
    }
    let total = args
        .iter()
        .try_fold(0_usize, |total, arg| total.checked_add(arg.len()));
    let outcome = if total.is_none_or(|total| total > MAX_ARG_BYTES) {
        ArgPlanOutcome::BoundsExceeded
    } else {
        match inspect(&args) {
            Err(outcome) => outcome,
            Ok(overrides) if overrides.conflict => ArgPlanOutcome::ConflictingUserOverrides,
            Ok(overrides) => {
                if let Some(effort) = overrides.effort {
                    let effort = Reasoning::parse(&effort);
                    let status = if overrides.target_changed {
                        Support::Unknown
                    } else {
                        effort.map_or(Support::Unknown, |effort| decision.support(effort))
                    };
                    ArgPlanOutcome::UserOverride { effort, status }
                } else if overrides.target_changed {
                    ArgPlanOutcome::DeferredTargetOverride
                } else {
                    match decision.support(decision.candidate) {
                        Support::Unknown => ArgPlanOutcome::CompatibilityUnknown,
                        Support::Unsupported => ArgPlanOutcome::CompatibilityUnsupported,
                        Support::Supported => {
                            let value = match decision.candidate {
                                Reasoning::Medium => "model_reasoning_effort=\"medium\"",
                                Reasoning::High => "model_reasoning_effort=\"high\"",
                            };
                            args.splice(0..0, [OsString::from("--config"), OsString::from(value)]);
                            ArgPlanOutcome::Injected(decision.candidate)
                        }
                    }
                }
            }
        }
    };
    ReasoningArgPlan { args, outcome }
}
