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
        self.inspect_catalog_with(false)
    }
    /// Same catalog checks, with group cleanup for opt-in supervised probes too.
    pub fn inspect_catalog_supervised(&self) -> Result<Vec<u8>, LaunchError> {
        self.inspect_catalog_with(true)
    }
    fn inspect_catalog_with(&self, supervised: bool) -> Result<Vec<u8>, LaunchError> {
        let probe = |args: &[&str], limit: u64| {
            if supervised {
                #[cfg(target_os = "linux")]
                {
                    let args: Vec<_> = args.iter().map(OsString::from).collect();
                    let output = self.supervise_args(&args, Duration::from_secs(5), limit as usize);
                    return if output.outcome == ProcessOutcome::Success {
                        Ok(output.stdout)
                    } else {
                        Err(LaunchError::CatalogFailed)
                    };
                }
                #[cfg(not(target_os = "linux"))]
                return Err(LaunchError::CatalogFailed);
            }
            bounded_probe(&self.executable, args, limit)
        };
        if !self.unchanged() {
            return Err(LaunchError::ChangedExecutable);
        }
        self.verify_pin()?;
        let version = probe(&["--version"], 128)?;
        if version != b"codex-cli 0.162.1\n" {
            return Err(LaunchError::CatalogFailed);
        }
        if !self.unchanged() {
            return Err(LaunchError::ChangedExecutable);
        }
        let catalog = probe(&["debug", "models", "--bundled"], 2_000_000)?;
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
    /// Linux-only bounded private transport for an explicit noninteractive attempt.
    #[cfg(target_os = "linux")]
    pub fn supervise(self, timeout: Duration) -> SupervisedOutput {
        self.supervise_args(&self.args, timeout, MAX_SUPERVISED_OUTPUT)
    }
    #[cfg(target_os = "linux")]
    fn supervise_args(
        &self,
        args: &[OsString],
        timeout: Duration,
        limit: usize,
    ) -> SupervisedOutput {
        use rustix::{
            fs::{OFlags, fcntl_getfl, fcntl_setfl},
            process::{Pid, Signal, WaitId, WaitIdOptions, kill_process_group, waitid},
        };
        use std::os::unix::process::{CommandExt, ExitStatusExt};
        static SLOT: std::sync::Mutex<Option<std::process::Child>> = std::sync::Mutex::new(None);
        let unknown = || SupervisedOutput {
            outcome: ProcessOutcome::Unknown,
            stdout: Vec::new(),
        };
        let Ok(mut slot) = SLOT.try_lock() else {
            return unknown();
        };
        if let Some(child) = slot.as_mut() {
            if !matches!(child.try_wait(), Ok(Some(_))) {
                return unknown();
            }
            *slot = None;
        }
        if !self.unchanged() || self.verify_pin().is_err() {
            return unknown();
        }
        let Ok(signals) = codex_smart_process::InterruptGuard::install() else {
            return unknown();
        };
        let mut command = Command::new(&self.executable);
        command
            .args(args)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .process_group(0);
        codex_smart_process::stdio_only(&mut command);
        let Ok(child) = command.spawn() else {
            return unknown();
        };
        *slot = Some(child);
        let child = slot.as_mut().expect("owned child");
        let pid = Pid::from_raw(child.id() as i32).expect("child pid");
        let mut stdout = child.stdout.take().expect("piped stdout");
        let mut bytes = Vec::new();
        let mut eof = false;
        let mut outcome = ProcessOutcome::Unknown;
        let mut complete_transport = true;
        let deadline = Instant::now() + timeout;
        let configured = fcntl_getfl(&stdout)
            .and_then(|flags| fcntl_setfl(&stdout, flags | OFlags::NONBLOCK))
            .is_ok();
        if configured {
            loop {
                // Drain only a bounded chunk per tick so a noisy writer cannot starve the deadline.
                let mut buffer = [0; 8192];
                match stdout.read(&mut buffer) {
                    Ok(0) => eof = true,
                    Ok(n) if bytes.len() + n <= limit => bytes.extend_from_slice(&buffer[..n]),
                    Ok(_) => {
                        complete_transport = false;
                        break;
                    }
                    Err(e)
                        if e.kind() == std::io::ErrorKind::WouldBlock
                            || e.kind() == std::io::ErrorKind::Interrupted => {}
                    Err(_) => {
                        complete_transport = false;
                        break;
                    }
                }
                if signals.interrupted() {
                    outcome = ProcessOutcome::Interrupted;
                    break;
                }
                if Instant::now() >= deadline {
                    outcome = ProcessOutcome::Timeout;
                    break;
                }
                // NOWAIT keeps the leader's PID reserved until group cleanup, avoiding PID reuse.
                match waitid(
                    WaitId::Pid(pid),
                    WaitIdOptions::EXITED | WaitIdOptions::NOHANG | WaitIdOptions::NOWAIT,
                ) {
                    Ok(Some(_)) => break,
                    Ok(_) => {}
                    Err(_) => {
                        complete_transport = false;
                        break;
                    }
                }
                std::thread::sleep(Duration::from_millis(5));
            }
        }
        // Kill the entire original group before reaping its leader, even on success.
        // Escaped sessions cannot be confined by a process group; see public limits.
        let cleanup = kill_process_group(pid, Signal::KILL).is_ok();
        let cleanup_deadline = Instant::now() + Duration::from_secs(1);
        if configured && !eof {
            loop {
                let mut buffer = [0; 8192];
                match stdout.read(&mut buffer) {
                    Ok(0) => {
                        eof = true;
                        break;
                    }
                    Ok(n) if bytes.len() + n <= limit => bytes.extend_from_slice(&buffer[..n]),
                    Ok(_) => complete_transport = false,
                    Err(e)
                        if matches!(
                            e.kind(),
                            std::io::ErrorKind::WouldBlock | std::io::ErrorKind::Interrupted
                        ) => {}
                    Err(_) => break,
                }
                if Instant::now() >= cleanup_deadline {
                    break;
                }
                std::thread::sleep(Duration::from_millis(5));
            }
        }
        loop {
            match child.try_wait() {
                Ok(Some(status)) => {
                    if cleanup && configured && eof && complete_transport {
                        if outcome == ProcessOutcome::Unknown {
                            outcome = if status.signal().is_some() {
                                ProcessOutcome::Interrupted
                            } else if status.success() {
                                ProcessOutcome::Success
                            } else {
                                ProcessOutcome::Failure
                            };
                        }
                    } else {
                        outcome = ProcessOutcome::Unknown;
                    }
                    *slot = None;
                    break;
                }
                Ok(None) if Instant::now() < cleanup_deadline => {
                    std::thread::sleep(Duration::from_millis(5))
                }
                _ => {
                    outcome = ProcessOutcome::Unknown;
                    break;
                }
            }
        }
        SupervisedOutput {
            outcome,
            stdout: bytes,
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

/// Private bytes must never be rendered in diagnostics.
#[cfg(target_os = "linux")]
pub const MAX_SUPERVISED_OUTPUT: usize = 1_048_576;
#[cfg(target_os = "linux")]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ProcessOutcome {
    Success,
    Failure,
    Timeout,
    Interrupted,
    Unknown,
}
#[cfg(target_os = "linux")]
pub struct SupervisedOutput {
    pub outcome: ProcessOutcome,
    pub stdout: Vec<u8>,
}
