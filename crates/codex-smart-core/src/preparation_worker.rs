//! Explicit Linux process boundary. Production admission and ordinary CLI stay closed.
use crate::preparation::Preparation;
use crate::preparation_supervision::State;
use crate::preparation_wire::{PreparationRequest, VERSION};
use std::{path::PathBuf, time::Duration};

/// Pin must originate in independent trusted build/review evidence, never discovery.
/// This is authority to execute that exact artifact, not a general sandbox for it.
pub struct WorkerPin {
    pub executable: PathBuf,
    pub sha256: [u8; 32],
    pub protocol: u8,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Error {
    Unsupported,
    Identity,
    Protocol,
    Busy,
    Spawn,
    Limits,
}
pub struct Outcome {
    pub state: State,
    pub preparation: Option<Preparation>,
    /// Parent monotonic elapsed after successful spawn; excludes verification/spawn.
    pub elapsed: Duration,
    /// Payload-free observed worker exit code, if reaping completed.
    pub worker_exit_code: Option<i32>,
}
/// Explicit opt-in, one attempt, no retry; serializes all callers in this process.
pub fn run_local_preparation(
    pin: &WorkerPin,
    request: &PreparationRequest,
    deadline: Duration,
    cleanup: Duration,
) -> Result<Outcome, Error> {
    if pin.protocol != VERSION {
        return Err(Error::Protocol);
    }
    let encoded = request.encode().map_err(|_| Error::Protocol)?;
    #[cfg(target_os = "linux")]
    {
        linux::run(pin, request, encoded, deadline, cleanup)
    }
    #[cfg(not(target_os = "linux"))]
    {
        let _ = (pin, request, encoded, deadline, cleanup);
        Err(Error::Unsupported)
    }
}
/// Applied only by the dedicated worker, never by a read-only CLI command.
pub fn worker_bootstrap() -> Result<(), Error> {
    #[cfg(target_os = "linux")]
    {
        linux::bootstrap()
    }
    #[cfg(not(target_os = "linux"))]
    {
        Err(Error::Unsupported)
    }
}
#[cfg(target_os = "linux")]
mod linux {
    use super::*;
    use crate::{
        preparation_supervision::{
            Action, Observation, SupervisionPolicy, WorkerFact, WorkerFacts,
        },
        preparation_wire::{MAX_RESPONSE, verify_response},
    };
    use rustix::fs::{Mode, OFlags, ResolveFlags, fcntl_getfl, fcntl_setfl, openat2};
    use sha2::{Digest, Sha256};
    use std::{
        fs::File,
        io::{Read, Write},
        os::{
            fd::{AsFd, AsRawFd},
            unix::fs::MetadataExt,
        },
        process::{Child, Command, Stdio},
        sync::Mutex,
        time::Instant,
    };

    // Process-lifetime ownership. An unreaped child stays here even after caller return.
    // No subsequent call can spawn until try_wait proves that exact child reaped.
    struct Slot {
        child: Option<Child>,
        // Retain at most one verified regular-file descriptor across caller return.
        // Filesystem-specific close/release belongs to the next pre-spawn admission,
        // never to the deadline-controlled loop or its return path.
        executable: Option<File>,
    }
    static SLOT: Mutex<Slot> = Mutex::new(Slot {
        child: None,
        executable: None,
    });
    struct Running<'a>(&'a mut Option<Child>);
    impl Drop for Running<'_> {
        fn drop(&mut self) {
            if let Some(child) = self.0.as_mut() {
                let _ = child.kill();
                if matches!(child.try_wait(), Ok(Some(_))) {
                    *self.0 = None;
                }
            }
        }
    }
    const POLL: Duration = Duration::from_millis(1);
    fn host() -> Result<(), Error> {
        let slash = File::open("/").map_err(|_| Error::Unsupported)?;
        openat2(
            &slash,
            "proc/self/fd",
            OFlags::RDONLY | OFlags::DIRECTORY | OFlags::CLOEXEC,
            Mode::empty(),
            ResolveFlags::BENEATH | ResolveFlags::NO_MAGICLINKS,
        )
        .map_err(|_| Error::Unsupported)?;
        let fd = rustix::fs::open(
            "/proc/self/exe",
            OFlags::RDONLY | OFlags::CLOEXEC,
            Mode::empty(),
        )
        .map_err(|_| Error::Unsupported)?;
        if !File::from(fd)
            .metadata()
            .map_err(|_| Error::Unsupported)?
            .is_file()
        {
            return Err(Error::Unsupported);
        }
        Ok(())
    }
    pub(super) fn bootstrap() -> Result<(), Error> {
        if std::env::vars_os().next().is_some() {
            return Err(Error::Unsupported);
        }
        host()?;
        // Refuse leaked inherited descriptors before consuming any request/source.
        let listing = format!("/proc/{}/fd", std::process::id());
        for entry in std::fs::read_dir("/proc/self/fd").map_err(|_| Error::Unsupported)? {
            let entry = entry.map_err(|_| Error::Unsupported)?;
            let n = entry
                .file_name()
                .to_str()
                .and_then(|s| s.parse::<u32>().ok())
                .ok_or(Error::Unsupported)?;
            if n > 2
                && std::fs::read_link(entry.path()).map_err(|_| Error::Unsupported)?
                    != std::path::Path::new(&listing)
            {
                return Err(Error::Unsupported);
            }
        }
        rustix::thread::set_no_new_privs(true).map_err(|_| Error::Unsupported)?;
        use rustix::process::{Resource, Rlimit, setrlimit};
        for (resource, n) in [
            (Resource::Core, 0),
            (Resource::Cpu, 1),
            (Resource::As, 128 * 1024 * 1024),
            (Resource::Nproc, 0),
            (Resource::Nofile, 32),
        ] {
            setrlimit(
                resource,
                Rlimit {
                    current: Some(n),
                    maximum: Some(n),
                },
            )
            .map_err(|_| Error::Unsupported)?;
        }
        Ok(())
    }
    fn verified_file(pin: &WorkerPin) -> Result<File, Error> {
        use std::path::Component;
        if !pin.executable.is_absolute()
            || pin.executable.as_os_str().len() > 4096
            || !pin
                .executable
                .components()
                .all(|c| matches!(c, Component::RootDir | Component::Normal(_)))
        {
            return Err(Error::Identity);
        }
        let slash = File::open("/").map_err(|_| Error::Identity)?;
        let relative = pin
            .executable
            .strip_prefix("/")
            .map_err(|_| Error::Identity)?;
        let fd = openat2(
            &slash,
            relative,
            OFlags::PATH | OFlags::CLOEXEC,
            Mode::empty(),
            ResolveFlags::BENEATH | ResolveFlags::NO_SYMLINKS | ResolveFlags::NO_MAGICLINKS,
        )
        .map_err(|_| Error::Identity)?;
        let pinned = File::from(fd);
        let before = pinned.metadata().map_err(|_| Error::Identity)?;
        if !before.is_file()
            || before.nlink() != 1
            || before.len() > 64 * 1024 * 1024
            || before.mode() & 0o7022 != 0
            || before.mode() & 0o100 == 0
            || (before.uid() != 0 && before.uid() != rustix::process::geteuid().as_raw())
        {
            return Err(Error::Identity);
        }
        let readable = rustix::fs::open(
            format!("/proc/self/fd/{}", pinned.as_raw_fd()),
            OFlags::RDONLY | OFlags::NONBLOCK | OFlags::CLOEXEC,
            Mode::empty(),
        )
        .map_err(|_| Error::Unsupported)?;
        let mut file = File::from(readable);
        let mut hash = Sha256::new();
        let mut buf = [0; 8192];
        let mut count = 0;
        let mut elf = false;
        loop {
            let n = file.read(&mut buf).map_err(|_| Error::Identity)?;
            if n == 0 {
                break;
            }
            if count == 0 {
                elf = n >= 4 && &buf[..4] == b"\x7fELF";
            }
            count += n;
            if count > 64 * 1024 * 1024 {
                return Err(Error::Identity);
            }
            hash.update(&buf[..n]);
        }
        let after = file.metadata().map_err(|_| Error::Identity)?;
        if !elf
            || hash.finalize().as_slice() != pin.sha256
            || count as u64 != before.len()
            || before.dev() != after.dev()
            || before.ino() != after.ino()
            || before.mode() != after.mode()
            || before.uid() != after.uid()
            || before.nlink() != after.nlink()
            || before.len() != after.len()
            || before.mtime() != after.mtime()
            || before.mtime_nsec() != after.mtime_nsec()
            || before.ctime() != after.ctime()
            || before.ctime_nsec() != after.ctime_nsec()
        {
            return Err(Error::Identity);
        }
        // Verify procfs descriptor resolution while keeping the hashed fd alive through spawn.
        let proc = format!("/proc/self/fd/{}", file.as_raw_fd());
        let m = std::fs::metadata(proc).map_err(|_| Error::Unsupported)?;
        if m.dev() != after.dev() || m.ino() != after.ino() {
            return Err(Error::Unsupported);
        }
        Ok(file)
    }
    /// Local-only admission derives identity from the independent receipt and host
    /// primitives. No caller-provided WorkerFacts can open this gate.
    fn admit_pinned_local_worker(pin: &WorkerPin) -> Result<File, Error> {
        host()?;
        verified_file(pin)
    }
    fn nonblocking(fd: impl AsFd) -> std::io::Result<()> {
        fcntl_setfl(&fd, fcntl_getfl(&fd)? | OFlags::NONBLOCK)?;
        Ok(())
    }
    // Exactly one syscall per pipe per tick: floods cannot monopolize the clock.
    fn read_tick(
        pipe: &mut impl Read,
        bytes: &mut Vec<u8>,
        count: &mut usize,
        eof: &mut bool,
        bad: &mut bool,
        retain: bool,
    ) {
        if *eof {
            return;
        }
        let mut buf = [0; 4096];
        match pipe.read(&mut buf) {
            Ok(0) => *eof = true,
            Ok(n) => {
                *count = count.saturating_add(n);
                if retain && bytes.len() + n <= MAX_RESPONSE {
                    bytes.extend_from_slice(&buf[..n]);
                } else {
                    *bad = true;
                }
            }
            Err(e)
                if matches!(
                    e.kind(),
                    std::io::ErrorKind::WouldBlock | std::io::ErrorKind::Interrupted
                ) => {}
            Err(_) => *bad = true,
        }
    }
    pub(super) fn run(
        pin: &WorkerPin,
        request: &PreparationRequest,
        encoded: Vec<u8>,
        deadline: Duration,
        cleanup: Duration,
    ) -> Result<Outcome, Error> {
        if deadline.is_zero()
            || deadline > Duration::from_millis(250)
            || cleanup.is_zero()
            || cleanup > Duration::from_millis(250)
        {
            return Err(Error::Limits);
        }
        let mut slot = SLOT.try_lock().map_err(|_| Error::Busy)?;
        if let Some(child) = slot.child.as_mut() {
            match child.try_wait() {
                Ok(Some(_)) => slot.child = None,
                _ => {
                    let _ = child.kill();
                    return Err(Error::Busy);
                }
            }
        }
        slot.executable = None;
        let executable = admit_pinned_local_worker(pin)?;
        // These facts apply only to this constrained local adapter. No claim of hostile
        // binary containment: the independently authorized pin is a trust boundary.
        let facts = WorkerFacts {
            identity: WorkerFact::Verified,
            protocol: WorkerFact::Verified,
            containment: WorkerFact::Verified,
            termination: WorkerFact::Verified,
        };
        let mut policy = SupervisionPolicy::new(facts, deadline, cleanup, MAX_RESPONSE)
            .map_err(|_| Error::Limits)?;

        let executable_path = format!("/proc/self/fd/{}", executable.as_raw_fd());
        slot.executable = Some(executable);
        let child = Command::new(executable_path)
            .env_clear()
            .current_dir("/")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|_| Error::Spawn)?;
        let started = Instant::now();
        slot.child = Some(child);
        let running = Running(&mut slot.child);
        let child = running.0.as_mut().expect("owned child");
        // From this point every error/panic goes through nonblocking cleanup.
        let mut input = child.stdin.take();
        let mut output = child.stdout.take().expect("piped stdout");
        let mut errors = child.stderr.take().expect("piped stderr");
        let mut bad = nonblocking(input.as_ref().expect("piped stdin")).is_err()
            || nonblocking(&output).is_err()
            || nonblocking(&errors).is_err();
        let mut sent = 0;
        let mut bytes = Vec::new();
        let mut count = 0;
        let mut stdout_eof = false;
        let mut stderr_eof = false;
        let mut reaped = None;
        let mut worker_exit_code = None;
        let mut preparation = None;
        loop {
            // Never touch potentially blocking pipes if nonblocking setup failed.
            if !bad && policy.state() == State::Running && started.elapsed() < deadline {
                if let Some(pipe) = input.as_mut() {
                    match pipe.write(&encoded[sent..]) {
                        Ok(0) => bad = true,
                        Ok(n) => sent += n,
                        Err(e)
                            if matches!(
                                e.kind(),
                                std::io::ErrorKind::WouldBlock | std::io::ErrorKind::Interrupted
                            ) => {}
                        Err(_) => bad = true,
                    }
                    if sent == encoded.len() {
                        input = None;
                    }
                }
                read_tick(
                    &mut output,
                    &mut bytes,
                    &mut count,
                    &mut stdout_eof,
                    &mut bad,
                    true,
                );
                read_tick(
                    &mut errors,
                    &mut Vec::new(),
                    &mut count,
                    &mut stderr_eof,
                    &mut bad,
                    false,
                );
            }
            if reaped.is_none() {
                match child.try_wait() {
                    Ok(Some(s)) => {
                        worker_exit_code = s.code();
                        reaped = Some(s.success());
                    }
                    Ok(None) => {}
                    Err(_) => bad = true,
                }
            }
            let complete = stdout_eof && stderr_eof && sent == encoded.len();
            if complete && preparation.is_none() && !bad {
                match verify_response(&bytes, request, &encoded) {
                    Ok(p) => preparation = Some(p),
                    Err(_) => bad = true,
                }
            }
            let action = policy.observe(Observation {
                elapsed: started.elapsed(),
                output_bytes: count,
                transport_failed: bad,
                response_verified: preparation.is_some() && !bad,
                reaped_exit: if bad || complete || policy.state() != State::Running {
                    reaped
                } else {
                    None
                },
            });
            match action {
                Action::Poll => {}
                Action::TerminateAndPollReap => {
                    input = None;
                    let _ = child.kill();
                }
                Action::Return => {
                    let state = policy.state();
                    if reaped.is_some() {
                        *running.0 = None;
                    }
                    return Ok(Outcome {
                        state,
                        preparation: if state == State::Succeeded {
                            preparation
                        } else {
                            None
                        },
                        elapsed: started.elapsed(),
                        worker_exit_code,
                    });
                }
            }
            std::thread::sleep(POLL);
        }
    }
}
