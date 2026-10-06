use crate::tool_lock::{ArtifactEvidence, CapabilityEvidence};
use std::ffi::OsStr;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Capability {
    Codex,
    Rust,
    Cargo,
    Git,
    Search,
    GitHub,
    CodeGraph,
    CodeGraphWrapper,
    Serena,
    Context7,
}
impl Capability {
    pub const ALL: [Self; 10] = [
        Self::Codex,
        Self::Rust,
        Self::Cargo,
        Self::Git,
        Self::Search,
        Self::GitHub,
        Self::CodeGraph,
        Self::CodeGraphWrapper,
        Self::Serena,
        Self::Context7,
    ];
    pub fn name(self) -> &'static str {
        match self {
            Self::Codex => "codex",
            Self::Rust => "rustc",
            Self::Cargo => "cargo",
            Self::Git => "git",
            Self::Search => "rg",
            Self::GitHub => "gh",
            Self::CodeGraph => "code-graph-mcp",
            Self::CodeGraphWrapper => "code-graph-smart",
            Self::Serena => "serena",
            Self::Context7 => "context7 (session integration)",
        }
    }
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub capability: Capability,
    pub executable: Option<PathBuf>,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Availability {
    Discovered,
    NotFound,
    SessionUnknown,
}
impl Entry {
    pub fn evidence(&self) -> CapabilityEvidence {
        CapabilityEvidence::assess(
            self.capability,
            self.availability() == Availability::Discovered,
            None,
            ArtifactEvidence::Deferred,
        )
    }
    pub fn availability(&self) -> Availability {
        if self.capability == Capability::Context7 {
            Availability::SessionUnknown
        } else if self.executable.is_some() {
            Availability::Discovered
        } else {
            Availability::NotFound
        }
    }
}
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Inventory(pub Vec<Entry>);
impl Inventory {
    pub fn discover(path: Option<&OsStr>, repo: &Path) -> Self {
        Self(
            Capability::ALL
                .into_iter()
                .map(|capability| Entry {
                    capability,
                    executable: if capability == Capability::Context7 {
                        None
                    } else {
                        find_executable(path, capability.name(), repo)
                    },
                })
                .collect(),
        )
    }
    pub fn found(&self, capability: Capability) -> bool {
        self.0
            .iter()
            .any(|e| e.capability == capability && e.availability() == Availability::Discovered)
    }
    pub fn render(&self) -> String {
        let mut output = String::from("Capability inventory (offline; no tools executed)\n");
        for entry in &self.0 {
            // Paths and tool output are deliberately omitted from public diagnostics.
            let status = match entry.availability() {
                Availability::SessionUnknown => "unknown: session integration not probed",
                Availability::Discovered if entry.capability == Capability::CodeGraphWrapper => {
                    "found: version/health/auth unverified; execution unsupported (wrapper may install dependencies)"
                }
                Availability::Discovered => "found: version/health/auth unverified",
                Availability::NotFound => "not found on trusted PATH",
            };
            let evidence = entry.evidence();
            output.push_str(&format!(
                "{}: {}; compatibility: {}; contract: {}; ready: {}\n",
                entry.capability.name(),
                status,
                evidence.compatibility.name(),
                evidence.execution_contract.name(),
                evidence.readiness.name()
            ));
        }
        output.push_str("MCP readiness, tool compatibility and index health: not probed\n");
        output
    }
}
/// Reject relative/current/repository paths and writable-by-other Unix executables.
/// Canonicalization supports normal rustup/system symlinks, but is not an ownership proof.
pub fn find_executable(path: Option<&OsStr>, name: &str, repo: &Path) -> Option<PathBuf> {
    let repo = repo.canonicalize().ok()?;
    let path = path?;
    if path.len() > 16_384 {
        return None;
    }
    for dir in std::env::split_paths(path).take(64) {
        if !dir.is_absolute() {
            continue;
        }
        let Ok(dir) = dir.canonicalize() else {
            continue;
        };
        if dir.starts_with(&repo) || !safe_permissions(&dir, false) {
            continue;
        }
        let candidate = dir.join(name);
        let Ok(candidate) = candidate.canonicalize() else {
            continue;
        };
        if candidate.starts_with(&repo) || !safe_permissions(&candidate, true) {
            continue;
        }
        return Some(candidate);
    }
    None
}
fn safe_permissions(path: &Path, executable: bool) -> bool {
    let Ok(meta) = path.metadata() else {
        return false;
    };
    if executable && !meta.is_file() {
        return false;
    }
    if !executable && !meta.is_dir() {
        return false;
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mode = meta.permissions().mode();
        if mode & 0o022 != 0 {
            return false;
        }
        if executable && mode & 0o111 == 0 {
            return false;
        }
    }
    #[cfg(not(unix))]
    {
        if executable {
            return false;
        }
    }
    true
}
