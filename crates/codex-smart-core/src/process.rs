//! Explicit process launching. No shell, profile edits, installs or tool probes.
use crate::capability::Capability;
use crate::capability::find_executable;
use crate::tool_lock::{Checksum, MAX_VERIFY_BYTES, Pin, fingerprint};
use std::ffi::{OsStr, OsString};
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

fn bounded_probe(executable: &Path, args: &[&str], limit: u64) -> Result<Vec<u8>, LaunchError> {
    let mut child = Command::new(executable)
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| LaunchError::CatalogFailed)?;
    let stdout = child.stdout.take().ok_or(LaunchError::CatalogFailed)?;
    let (tx, rx) = std::sync::mpsc::sync_channel(1);
    std::thread::spawn(move || {
        let mut bytes = Vec::new();
        let result = stdout
            .take(limit + 1)
            .read_to_end(&mut bytes)
            .map(|_| bytes);
        let _ = tx.send(result);
    });
    let deadline = Instant::now() + Duration::from_secs(5);
    let remaining = deadline.saturating_duration_since(Instant::now());
    let bytes = match rx.recv_timeout(remaining) {
        Ok(Ok(bytes)) if bytes.len() as u64 <= limit => bytes,
        _ => {
            let _ = child.kill();
            let _ = child.wait();
            return Err(LaunchError::CatalogFailed);
        }
    };
    loop {
        match child.try_wait() {
            Ok(Some(status)) if status.success() => return Ok(bytes),
            Ok(Some(_)) | Err(_) => return Err(LaunchError::CatalogFailed),
            Ok(None) if Instant::now() < deadline => std::thread::sleep(Duration::from_millis(10)),
            Ok(None) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(LaunchError::CatalogFailed);
            }
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LaunchError {
    MissingCodex,
    ChangedExecutable,
    SpawnFailed,
    PinMismatch,
    CatalogFailed,
}
impl LaunchError {
    pub fn code(self) -> &'static str {
        match self {
            Self::MissingCodex => "E_CODEX_MISSING: Codex not found on trusted PATH",
            Self::ChangedExecutable => "E_CODEX_CHANGED: executable changed after planning",
            Self::SpawnFailed => "E_CODEX_SPAWN: could not execute Codex",
            Self::PinMismatch => "E_CODEX_PIN: required Codex artifact pin could not be verified",
            Self::CatalogFailed => "E_CODEX_CATALOG: trusted Codex model catalog could not be read",
        }
    }
}
#[derive(Debug)]
pub struct LaunchPlan {
    executable: PathBuf,
    args: Vec<OsString>,
    metadata: std::fs::Metadata,
    checksum: Option<Checksum>,
    closed_stdin: bool,
}
impl LaunchPlan {
    /// Attach reviewed argv to the same executable identity inspected earlier.
    pub fn with_args(mut self, args: Vec<OsString>) -> Self {
        self.args = args;
        self
    }
    /// Explicit noninteractive attempts must not append or wait for inherited stdin.
    pub fn with_closed_stdin(mut self) -> Self {
        self.closed_stdin = true;
        self
    }
    /// Explicit opt-in runtime inspection only. The catalog describes syntax and
    /// supported effort; it does not establish account/provider availability.
    /// Discard stderr and catalog bodies: both may contain private runtime data.
    pub fn inspect_catalog(&self) -> Result<Vec<u8>, LaunchError> {
        if !self.unchanged() {
            return Err(LaunchError::ChangedExecutable);
        }
        self.verify_pin()?;
        let version = bounded_probe(&self.executable, &["--version"], 128)?;
        if version != b"codex-cli 0.162.1\n" {
            return Err(LaunchError::CatalogFailed);
        }
        if !self.unchanged() {
            return Err(LaunchError::ChangedExecutable);
        }
        let catalog = bounded_probe(
            &self.executable,
            &["debug", "models", "--bundled"],
            2_000_000,
        )?;
        if !self.unchanged() {
            return Err(LaunchError::ChangedExecutable);
        }
        self.verify_pin()?;
        Ok(catalog)
    }
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
            checksum: None,
            closed_stdin: false,
        })
    }
    pub fn require_pin(mut self, pin: &Pin) -> Result<Self, LaunchError> {
        if pin.capability != Capability::Codex {
            return Err(LaunchError::PinMismatch);
        }
        self.checksum = Some(pin.checksum);
        self.verify_pin()?;
        Ok(self)
    }
    fn verify_pin(&self) -> Result<(), LaunchError> {
        if let Some(checksum) = self.checksum {
            let (actual, _) = fingerprint(&self.executable, MAX_VERIFY_BYTES)
                .map_err(|_| LaunchError::PinMismatch)?;
            if actual != checksum || !self.unchanged() {
                return Err(LaunchError::PinMismatch);
            }
        }
        Ok(())
    }
    pub fn summary(&self) -> String {
        format!(
            "Launch dry-run\nExecutable: trusted absolute Codex path (not executed)\nArguments: {} forwarded unchanged; values omitted for privacy\nArtifact pin: {}\nShell: none\nCodex config/auth/MCP/plugins: no launcher edits\nRouting: passthrough; no profile or reasoning override injected\n",
            self.args.len(),
            if self.checksum.is_some() {
                "required SHA-256 matched; runtime version/readiness unverified"
            } else {
                "none required"
            }
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
        self.verify_pin()?;
        let mut command = Command::new(&self.executable);
        command.args(&self.args);
        if self.closed_stdin {
            command.stdin(Stdio::null());
        }
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
