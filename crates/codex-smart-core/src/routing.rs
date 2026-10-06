use crate::capability::{Capability, Inventory};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum Task {
    #[default]
    Local,
    Architecture,
    Refactor,
    ExternalApi,
    GitHub,
    Migration,
    Security,
}
impl Task {
    pub fn parse(value: &str) -> Option<Self> {
        Some(match value {
            "local" => Self::Local,
            "architecture" => Self::Architecture,
            "refactor" => Self::Refactor,
            "external-api" => Self::ExternalApi,
            "github" => Self::GitHub,
            "migration" => Self::Migration,
            "security" => Self::Security,
            _ => return None,
        })
    }
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Reasoning {
    Medium,
    High,
}
impl Reasoning {
    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "medium" => Some(Self::Medium),
            "high" => Some(Self::High),
            _ => None,
        }
    }
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Decision {
    pub task: Task,
    pub reasoning: Reasoning,
    pub preferred: Option<Capability>,
    pub discovered: bool,
}
pub fn decide(task: Task, inventory: &Inventory) -> Decision {
    let preferred = match task {
        Task::Architecture => Some(Capability::CodeGraph),
        Task::Refactor => Some(Capability::Serena),
        Task::ExternalApi => Some(Capability::Context7),
        Task::GitHub => Some(Capability::GitHub),
        _ => None,
    };
    Decision {
        task,
        reasoning: match task {
            Task::Architecture | Task::Refactor | Task::Migration | Task::Security => {
                Reasoning::High
            }
            _ => Reasoning::Medium,
        },
        preferred,
        discovered: preferred.is_some_and(|cap| inventory.found(cap)),
    }
}
impl Decision {
    pub fn render(&self) -> String {
        let capability = self.preferred.map_or("none", Capability::name);
        let confidence = if self.preferred.is_none() {
            "medium: explicit hint only"
        } else if self.discovered {
            "limited: executable present; integration unverified"
        } else {
            "low: preferred capability unavailable or unknown"
        };
        format!(
            "Routing preview (does not enable tools or alter Codex config)\nTask: {:?}\nReasoning: {:?}\nTool surface: native shell/git/search/build/tests, subject to host availability\nPreferred capability: {}\nReason: resolved task hint; native first; high effort for structural or safety risk\nFallback: native targeted evidence; escalate when evidence is insufficient; never skip verification\nConfidence: {}\nOverhead: bounded PATH metadata and configuration reads; no repository scan, indexing, subprocesses or network; latency unmeasured\n",
            self.task, self.reasoning, capability, confidence
        )
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use crate::capability::Entry;
    #[test]
    fn missing_graph_keeps_high_and_explicit_fallback() {
        let decision = decide(Task::Architecture, &Inventory::default());
        assert_eq!(decision.reasoning, Reasoning::High);
        assert!(!decision.discovered);
        assert!(decision.render().contains("low:"));
        assert!(decision.render().contains("never skip verification"));
    }
    #[test]
    fn presence_is_not_health_or_mcp_readiness() {
        let inventory = Inventory(vec![Entry {
            capability: Capability::Serena,
            executable: Some("/trusted/serena".into()),
        }]);
        assert!(
            decide(Task::Refactor, &inventory)
                .render()
                .contains("integration unverified")
        );
    }
    #[test]
    fn no_unconditional_lean_or_size_based_reasoning() {
        assert_eq!(
            decide(Task::Local, &Inventory::default()).reasoning,
            Reasoning::Medium
        );
        for task in [
            Task::Architecture,
            Task::Refactor,
            Task::Security,
            Task::Migration,
        ] {
            assert_eq!(
                decide(task, &Inventory::default()).reasoning,
                Reasoning::High
            );
        }
        assert_eq!(Task::parse("unrecognized"), None);
    }
}
