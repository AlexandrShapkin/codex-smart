//! Explicit process launching. No shell, profile edits, installs or tool probes.
use crate::capability::find_executable;
use std::ffi::{OsStr, OsString};
use std::path::{Path, PathBuf};
use std::process::Command;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LaunchError {
    MissingCodex,
    ChangedExecutable,
    SpawnFailed,
}
impl LaunchError {
    pub fn code(self) -> &'static str {
        match self {
            Self::MissingCodex => "E_CODEX_MISSING: Codex not found on trusted PATH",
            Self::ChangedExecutable => "E_CODEX_CHANGED: executable changed after planning",
            Self::SpawnFailed => "E_CODEX_SPAWN: could not execute Codex",
        }
    }
}
#[derive(Debug)]
pub struct LaunchPlan {
    executable: PathBuf,
    args: Vec<OsString>,
    metadata: std::fs::Metadata,
}
impl LaunchPlan {
    pub fn prepare(
        path: Option<&OsStr>,
        repo: &Path,
        args: Vec<OsString>,
    ) -> Result<Self, LaunchError> {
        let executable = find_executable(path, "codex", repo).ok_or(LaunchError::MissingCodex)?;
        let metadata = executable
            .metadata()
            .map_err(|_| LaunchError::MissingCodex)?;
        Ok(Self {
            executable,
            args,
            metadata,
        })
    }
    pub fn summary(&self) -> String {
        format!(
            "Launch dry-run\nExecutable: trusted absolute Codex path (not executed)\nArguments: {} forwarded unchanged; values omitted for privacy\nShell: none\nCodex config/auth/MCP/plugins: no launcher edits\nRouting: passthrough; no profile or reasoning override injected\n",
            self.args.len()
        )
    }
    fn unchanged(&self) -> bool {
        let Ok(now) = self.executable.metadata() else {
            return false;
        };
        #[cfg(unix)]
        {
            use std::os::unix::fs::MetadataExt;
            now.dev() == self.metadata.dev()
                && now.ino() == self.metadata.ino()
                && now.mode() == self.metadata.mode()
                && now.len() == self.metadata.len()
                && now.mtime() == self.metadata.mtime()
                && now.mtime_nsec() == self.metadata.mtime_nsec()
                && now.ctime() == self.metadata.ctime()
                && now.ctime_nsec() == self.metadata.ctime_nsec()
        }
        #[cfg(not(unix))]
        {
            now.len() == self.metadata.len() && now.modified().ok() == self.metadata.modified().ok()
        }
    }
    /// Unix replaces the launcher, preserving terminal, exit status and signals.
    /// A metadata recheck narrows but does not eliminate pathname execution TOCTOU.
    pub fn execute(self) -> Result<i32, LaunchError> {
        if !self.unchanged() {
            return Err(LaunchError::ChangedExecutable);
        }
        let mut command = Command::new(&self.executable);
        command.args(&self.args);
        #[cfg(unix)]
        {
            use std::os::unix::process::CommandExt;
            let _error = command.exec();
            Err(LaunchError::SpawnFailed)
        }
        #[cfg(not(unix))]
        {
            let status = command.status().map_err(|_| LaunchError::SpawnFailed)?;
            Ok(status.code().unwrap_or(1))
        }
    }
}
