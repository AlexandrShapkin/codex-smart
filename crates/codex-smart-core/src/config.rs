//! Bounded typed configuration. Unknown fields are inert and preserved by migrations.
use crate::capability::Inventory;
use crate::routing::{Reasoning, Task, decide};
use toml_edit::DocumentMut;

pub const SCHEMA_VERSION: i64 = 1;
pub const MAX_CONFIG_BYTES: usize = 65_536;
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConfigError {
    Missing,
    ProtectedStore,
    Io,
    UnsafePath,
    Permissions,
    TooLarge,
    InvalidToml,
    WrongKind,
    Schema,
    NeedsMigration,
    InvalidValue,
    ForbiddenProjectField,
    Busy,
    Changed,
    BackupExists,
    NoBackup,
    RecoveryRequired,
    Unsupported,
}
impl ConfigError {
    pub fn code(self) -> &'static str {
        match self {
            Self::Missing => "E_CONFIG_MISSING: configuration file not found",
            Self::ProtectedStore => {
                "E_CONFIG_PROTECTED: Codex config/auth/plugin stores cannot be migration targets"
            }
            Self::Io => "E_CONFIG_IO: configuration I/O failed",
            Self::UnsafePath => "E_CONFIG_PATH: unsafe path, symlink or non-regular file",
            Self::Permissions => {
                "E_CONFIG_PERMISSIONS: configuration ownership or permissions unsafe"
            }
            Self::TooLarge => "E_CONFIG_SIZE: configuration exceeds 64 KiB",
            Self::InvalidToml => "E_CONFIG_TOML: invalid TOML (contents omitted)",
            Self::WrongKind => "E_CONFIG_KIND: expected codex-smart configuration marker",
            Self::Schema => "E_CONFIG_SCHEMA: unsupported schema version",
            Self::NeedsMigration => "E_CONFIG_MIGRATION: schema 0 requires explicit migration",
            Self::InvalidValue => "E_CONFIG_VALUE: invalid typed configuration value",
            Self::ForbiddenProjectField => {
                "E_CONFIG_PROJECT: executable or safety overrides forbidden in project config"
            }
            Self::Busy => "E_CONFIG_BUSY: another migration holds the lock",
            Self::Changed => "E_CONFIG_CHANGED: file changed since planning; refusing overwrite",
            Self::BackupExists => {
                "E_CONFIG_BACKUP: backup/staging artifacts already exist; inspect recovery state"
            }
            Self::NoBackup => "E_CONFIG_BACKUP_MISSING: no rollback backup",
            Self::RecoveryRequired => {
                "E_CONFIG_RECOVERY: transaction may be committed; retain backup and inspect before retry"
            }
            Self::Unsupported => "E_CONFIG_PLATFORM: secure config access requires Linux openat2",
        }
    }
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Origin {
    BuiltIn,
    User,
    Project,
    Cli,
}
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Layer {
    pub task: Option<Task>,
    pub reasoning: Option<Reasoning>,
    pub context_limit: Option<usize>,
}
impl Layer {
    pub fn parse(source: &str, origin: Origin) -> Result<Self, ConfigError> {
        let doc = document(source)?;
        if version(&doc)? != SCHEMA_VERSION {
            return Err(ConfigError::NeedsMigration);
        }
        if origin == Origin::Project
            && [
                "command",
                "codex_path",
                "shell",
                "mcp_servers",
                "plugins",
                "auth",
                "sandbox",
                "approval_policy",
                "policy_script",
            ]
            .iter()
            .any(|key| doc.contains_key(key))
        {
            return Err(ConfigError::ForbiddenProjectField);
        }
        let task = doc
            .get("task")
            .map(|v| {
                v.as_str()
                    .and_then(Task::parse)
                    .ok_or(ConfigError::InvalidValue)
            })
            .transpose()?;
        let reasoning = doc
            .get("reasoning")
            .map(|v| {
                v.as_str()
                    .and_then(Reasoning::parse)
                    .ok_or(ConfigError::InvalidValue)
            })
            .transpose()?;
        let context_limit = doc
            .get("context_limit")
            .map(|v| {
                v.as_integer()
                    .and_then(|n| usize::try_from(n).ok())
                    .filter(|n| (1024..=65_536).contains(n))
                    .ok_or(ConfigError::InvalidValue)
            })
            .transpose()?;
        Ok(Self {
            task,
            reasoning,
            context_limit,
        })
    }
}
pub(crate) fn document(source: &str) -> Result<DocumentMut, ConfigError> {
    if source.len() > MAX_CONFIG_BYTES {
        return Err(ConfigError::TooLarge);
    }
    let doc = source
        .parse::<DocumentMut>()
        .map_err(|_| ConfigError::InvalidToml)?;
    if doc.get("kind").and_then(|v| v.as_str()) != Some("codex-smart") {
        return Err(ConfigError::WrongKind);
    }
    version(&doc)?;
    Ok(doc)
}
pub(crate) fn version(doc: &DocumentMut) -> Result<i64, ConfigError> {
    match doc.get("schema_version").and_then(|v| v.as_integer()) {
        Some(v @ (0 | 1)) => Ok(v),
        _ => Err(ConfigError::Schema),
    }
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Resolved {
    pub task: Task,
    pub reasoning: Reasoning,
    pub context_limit: usize,
    pub task_origin: Origin,
    pub reasoning_origin: Origin,
    pub context_origin: Origin,
}
pub fn resolve(user: &Layer, project: &Layer, cli: &Layer) -> Resolved {
    let mut result = Resolved {
        task: Task::Local,
        reasoning: Reasoning::Medium,
        context_limit: 8192,
        task_origin: Origin::BuiltIn,
        reasoning_origin: Origin::BuiltIn,
        context_origin: Origin::BuiltIn,
    };
    let mut effort = None;
    for (layer, origin) in [
        (user, Origin::User),
        (project, Origin::Project),
        (cli, Origin::Cli),
    ] {
        if let Some(value) = layer.task {
            result.task = value;
            result.task_origin = origin;
        }
        if let Some(value) = layer.reasoning {
            effort = Some(value);
            result.reasoning_origin = origin;
        }
        if let Some(value) = layer.context_limit {
            result.context_limit = value;
            result.context_origin = origin;
        }
    }
    result.reasoning =
        effort.unwrap_or_else(|| decide(result.task, &Inventory::default()).reasoning);
    result
}
impl Resolved {
    pub fn render(&self) -> String {
        format!(
            "Configuration schema: 1\ntask: {:?}\nreasoning: {:?}\ncontext_limit: {} bytes per retrieval response (escalate rather than skip evidence)\ntask origin: {:?}\nreasoning origin: {:?}\ncontext origin: {:?}\nUnknown fields: preserved/inert; values not displayed\nCodex config/auth/MCP/plugins: untouched\n",
            self.task,
            self.reasoning,
            self.context_limit,
            self.task_origin,
            self.reasoning_origin,
            self.context_origin
        )
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn defaults_and_each_layer_precedence() {
        let user = Layer {
            task: Some(Task::GitHub),
            reasoning: Some(Reasoning::High),
            context_limit: Some(4096),
        };
        let project = Layer {
            task: Some(Task::Refactor),
            context_limit: Some(16384),
            ..Layer::default()
        };
        let cli = Layer {
            task: Some(Task::Local),
            reasoning: Some(Reasoning::Medium),
            ..Layer::default()
        };
        let resolved = resolve(&user, &project, &cli);
        assert_eq!(resolved.task, Task::Local);
        assert_eq!(resolved.task_origin, Origin::Cli);
        assert_eq!(resolved.reasoning, Reasoning::Medium);
        assert_eq!(resolved.context_limit, 16384);
        assert_eq!(resolved.context_origin, Origin::Project);
        let implicit = resolve(
            &Layer::default(),
            &Layer::default(),
            &Layer {
                task: Some(Task::Security),
                ..Layer::default()
            },
        );
        assert_eq!(implicit.reasoning, Reasoning::High);
    }
    #[test]
    fn strict_types_schema_marker_and_legacy() {
        assert_eq!(
            Layer::parse("kind='codex-smart'\nschema_version=0", Origin::User),
            Err(ConfigError::NeedsMigration)
        );
        assert_eq!(
            Layer::parse("kind='other'\nschema_version=1", Origin::User),
            Err(ConfigError::WrongKind)
        );
        for invalid in [
            "task=42",
            "reasoning='low'",
            "context_limit=-1",
            "context_limit=65537",
            "schema_version=true",
        ] {
            assert!(
                Layer::parse(
                    &format!("kind='codex-smart'\nschema_version=1\n{invalid}"),
                    Origin::User
                )
                .is_err()
            );
        }
        assert_eq!(
            Layer::parse(
                "kind='codex-smart'\nschema_version=1\n[extensions]\nprivate='inert'",
                Origin::Project
            ),
            Ok(Layer::default())
        );
    }
}
