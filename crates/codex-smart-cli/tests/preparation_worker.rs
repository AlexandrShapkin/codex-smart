#![cfg(target_os = "linux")]
use codex_smart_core::{
    playbook::ContextObligation,
    preparation::{Failure, Limits, Request},
    preparation_supervision::State,
    preparation_wire::{Intent, PreparationRequest, VERSION, serve},
    preparation_worker::{Error, WorkerPin, run_local_preparation},
};
use sha2::{Digest, Sha256};
use std::{
    fs,
    io::{Read, Write},
    os::{fd::AsFd, unix::fs::PermissionsExt},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    time::{Duration, Instant},
};
static TEST_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

// Failure-only parent evidence: numeric IDs and kernel flags, never descriptor
// targets, paths, environment values or raw procfs text. Drop the listing before
// inspecting flags so its transient descriptor cannot masquerade as inheritance.
fn descriptor_snapshot() -> Vec<(i32, Option<u32>)> {
    let Ok(entries) = fs::read_dir("/proc/self/fd") else {
        return Vec::new();
    };
    let mut ids: Vec<i32> = entries
        .filter_map(Result::ok)
        .filter_map(|entry| entry.file_name().to_str()?.parse().ok())
        .collect();
    ids.sort_unstable();
    ids.into_iter()
        .filter_map(|id| {
            let info = fs::read_to_string(format!("/proc/self/fdinfo/{id}")).ok()?;
            let flags = info
                .lines()
                .find_map(|line| u32::from_str_radix(line.strip_prefix("flags:")?.trim(), 8).ok());
            Some((id, flags))
        })
        .collect()
}

struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let p = PathBuf::from(format!("/tmp/cs-worker-{}", std::process::id()));
        fs::create_dir(&p).unwrap();
        fs::write(p.join("a.rs"), "fn public_source() {}\n").unwrap();
        Self(p)
    }
    fn request(&self) -> PreparationRequest {
        PreparationRequest {
            root: self.0.clone(),
            intent: Intent::Inspection,
            files: vec![Request {
                path: "a.rs".into(),
                obligation: ContextObligation::RelevantFiles,
            }],
            limits: Limits::default(),
        }
    }
    fn pin(&self, path: &Path) -> WorkerPin {
        // Test-only receipt from controlled fixture. Production must use an independent pin.
        WorkerPin {
            executable: path.into(),
            sha256: Sha256::digest(fs::read(path).unwrap()).into(),
            protocol: VERSION,
        }
    }
    fn fake(&self, name: &str, behavior: &str) -> WorkerPin {
        let source = self.0.join(format!("{name}.rs"));
        let exe = self.0.join(name);
        fs::write(
            &source,
            format!("use std::io::{{Read,Write}}; fn main() {{ {behavior} }}"),
        )
        .unwrap();
        let result = Command::new("rustc")
            .arg("--edition=2024")
            .arg("-Awarnings")
            // Fixture setup is outside supervision. Bound codegen and linker
            // parallelism without changing any worker's post-spawn deadline.
            .arg("-C")
            .arg("codegen-units=1")
            .arg("-C")
            .arg("link-arg=-Wl,--threads=1")
            .arg(&source)
            .arg("-o")
            .arg(&exe)
            .output()
            .unwrap();
        if !result.status.success() {
            let stderr = String::from_utf8_lossy(&result.stderr);
            let errors: Vec<_> = stderr
                .lines()
                .filter(|line| {
                    line.starts_with("error:")
                        || line.contains("os error")
                        || line.contains("No space left")
                        || line.contains("Resource temporarily unavailable")
                        || line.contains("LLVM ERROR")
                        || line.contains("what():")
                        || line.contains("collect2:")
                })
                .collect();
            panic!(
                "fixture compilation failed ({name}, {:?}): {}",
                result.status.code(),
                errors.join("; ")
            );
        }
        self.pin(&exe)
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.0).unwrap();
    }
}
fn children() -> Vec<u32> {
    let mut children = Vec::new();
    for task in fs::read_dir("/proc/self/task").unwrap() {
        if let Ok(text) = fs::read_to_string(task.unwrap().path().join("children")) {
            children.extend(text.split_whitespace().map(|s| s.parse::<u32>().unwrap()));
        }
    }
    children.sort_unstable();
    children
}

fn attempt(
    pin: &WorkerPin,
    r: &PreparationRequest,
    deadline: u64,
) -> codex_smart_core::preparation_worker::Outcome {
    let result = run_local_preparation(
        pin,
        r,
        Duration::from_millis(deadline),
        Duration::from_millis(80),
    )
    .unwrap();
    // Scheduler allowance; no claim of real-time OS scheduling. Runtime excludes hash/spawn.
    assert!(
        result.elapsed < Duration::from_millis(deadline + 80 + 100),
        "parent exceeded post-spawn ceiling: {:?}",
        result.elapsed
    );
    result
}
#[test]
fn actual_worker_and_adversarial_workers_are_bounded_and_reaped() {
    let _test_lock = TEST_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let f = Fixture::new();
    let baseline = children();
    let request = f.request();
    let worker_path = f.0.join("worker");
    // Cargo hardlinks build outputs; deployment fixture must be an isolated single-link copy.
    fs::copy(
        env!("CARGO_BIN_EXE_codex-smart-preparation-worker"),
        &worker_path,
    )
    .unwrap();
    let worker = f.pin(&worker_path);
    let descriptors = descriptor_snapshot();
    let result = attempt(&worker, &request, 250);
    assert_eq!(
        result.state,
        State::Succeeded,
        "worker exit code: {:?}; parent fd count: {}; numeric fd/flags: {:?}",
        result.worker_exit_code,
        descriptors.len(),
        descriptors
    );
    let prepared = result.preparation.unwrap();
    assert_eq!(prepared.failure, None);
    assert_eq!(prepared.snippets[0].text, "fn public_source() {}\n");
    assert!(!prepared.unresolved.is_empty());
    assert!(!prepared.summary().contains("public_source"));
    let mut expected = Vec::new();
    serve(request.encode().unwrap().as_slice(), &mut expected).unwrap();
    let valid = format!("{:?}", expected);
    let consume = "let mut input = Vec::new(); std::io::stdin().read_to_end(&mut input).unwrap();";
    for (name, body, state, deadline) in [
        (
            "timeout",
            "loop { std::hint::spin_loop(); }".to_string(),
            State::TimedOut,
            30,
        ),
        (
            "no-read",
            "std::thread::sleep(std::time::Duration::from_secs(10));".to_string(),
            State::TimedOut,
            30,
        ),
        (
            "late",
            format!(
                "{consume} std::thread::sleep(std::time::Duration::from_millis(100)); std::io::stdout().write_all(&{valid}).unwrap();"
            ),
            State::TimedOut,
            30,
        ),
        (
            "exit",
            format!(
                "{consume} std::io::stdout().write_all(&{valid}).unwrap(); std::process::exit(7);"
            ),
            State::Failed,
            250,
        ),
        (
            "bad",
            format!("{consume} std::io::stdout().write_all(b\"invalid\\xff\").unwrap();"),
            State::Failed,
            250,
        ),
        (
            "flood",
            "loop { if std::io::stdout().write_all(&[42;4096]).is_err() { break; } }".to_string(),
            State::Failed,
            250,
        ),
        (
            "stderr",
            format!(
                "{consume} std::io::stderr().write_all(b\"unexpected\").unwrap(); std::io::stdout().write_all(&{valid}).unwrap();"
            ),
            State::Failed,
            250,
        ),
        (
            "unsolicited",
            format!(
                "{consume} std::io::stdout().write_all(&{valid}).unwrap(); std::io::stdout().write_all(b\"extra\").unwrap();"
            ),
            State::Failed,
            250,
        ),
        (
            "partial",
            format!(
                "{consume} std::io::stdout().write_all(&{:?}).unwrap();",
                &expected[..expected.len() - 1]
            ),
            State::Failed,
            250,
        ),
        (
            "mismatch",
            {
                let mut b = expected.clone();
                b[12] ^= 1;
                format!("{consume} std::io::stdout().write_all(&{b:?}).unwrap();")
            },
            State::Failed,
            250,
        ),
        (
            "env",
            format!(
                "{consume} assert_eq!(std::env::vars_os().count(),0); assert_eq!(std::env::args_os().count(),1); assert_eq!(std::env::current_dir().unwrap(), std::path::Path::new(\"/\")); std::io::stdout().write_all(&{valid}).unwrap();"
            ),
            State::Succeeded,
            250,
        ),
    ] {
        let pin = f.fake(name, &body);
        let mut flooded_input = f.request();
        flooded_input.files = (0..16)
            .map(|n| Request {
                path: format!("{}-{n}", "x".repeat(1000)).into(),
                obligation: ContextObligation::RelevantFiles,
            })
            .collect();
        let nominated = if name == "no-read" {
            &flooded_input
        } else {
            &request
        };
        assert!(flooded_input.encode().unwrap().len() > 8192);
        let result = attempt(&pin, nominated, deadline);
        assert_eq!(result.state, state, "{name}");
        if state != State::Succeeded {
            assert!(result.preparation.is_none());
        }
        assert_eq!(children(), baseline, "leaked child: {name}");
    }
    // Kernel descriptor reads reject special files and links without blocking.
    std::os::unix::fs::symlink("a.rs", f.0.join("link")).unwrap();
    fs::hard_link(f.0.join("a.rs"), f.0.join("hard")).unwrap();
    rustix::fs::mkfifoat(
        rustix::fs::CWD,
        f.0.join("fifo"),
        rustix::fs::Mode::RUSR | rustix::fs::Mode::WUSR,
    )
    .unwrap();
    for name in ["link", "hard", "fifo"] {
        let mut r = f.request();
        r.files[0].path = name.into();
        let result = attempt(&worker, &r, 250);
        assert_eq!(result.state, State::Succeeded);
        assert_eq!(
            result.preparation.unwrap().failure,
            Some(Failure::UnsafeOrMissingFile)
        );
    }
    // Request text stays data even when it contains executable-looking instructions.
    let marker = f.0.join("executed");
    let bait = format!(
        "codex exec; ssh example; validation; touch {}",
        marker.display()
    );
    fs::write(f.0.join("bait.txt"), &bait).unwrap();
    let mut r = f.request();
    r.files[0].path = "bait.txt".into();
    assert_eq!(
        attempt(&worker, &r, 250).preparation.unwrap().snippets[0].text,
        bait
    );
    assert!(!marker.exists());
    // Real worker refuses a descriptor deliberately made inheritable by the caller.
    let leaked = fs::File::open(f.0.join("bait.txt")).unwrap();
    rustix::io::fcntl_setfd(&leaked, rustix::io::FdFlags::empty()).unwrap();
    let refusal = attempt(&worker, &r, 250);
    assert_eq!(refusal.state, State::Failed);
    assert_eq!(refusal.worker_exit_code, Some(17));
    drop(leaked);
    for path in [
        "../a.rs",
        ".env",
        ".aws/credentials",
        ".ssh/id_rsa",
        "auth.json",
    ] {
        let mut r = f.request();
        r.files[0].path = path.into();
        assert!(matches!(
            run_local_preparation(
                &worker,
                &r,
                Duration::from_millis(250),
                Duration::from_millis(80)
            ),
            Err(Error::Protocol)
        ));
    }
    // While a caller owns the one process-wide slot, concurrent attempts refuse.
    let slow = f.fake(
        "busy",
        "std::thread::sleep(std::time::Duration::from_secs(10));",
    );
    std::thread::scope(|scope| {
        let handle = scope.spawn(|| attempt(&slow, &request, 200));
        let wait_start = Instant::now();
        while children() == baseline && wait_start.elapsed() < Duration::from_secs(3) {
            std::thread::sleep(Duration::from_millis(1));
        }
        assert_ne!(children(), baseline);
        assert!(matches!(
            run_local_preparation(
                &worker,
                &request,
                Duration::from_millis(250),
                Duration::from_millis(80)
            ),
            Err(Error::Busy)
        ));
        assert_eq!(handle.join().unwrap().state, State::TimedOut);
    });
    let mut bad_pin = f.pin(&worker.executable);
    bad_pin.sha256[0] ^= 1;
    assert!(matches!(
        run_local_preparation(
            &bad_pin,
            &request,
            Duration::from_millis(250),
            Duration::from_millis(80)
        ),
        Err(Error::Identity)
    ));
    let alias = f.0.join("worker-link");
    std::os::unix::fs::symlink(&worker.executable, &alias).unwrap();
    bad_pin = f.pin(&alias);
    assert!(matches!(
        run_local_preparation(
            &bad_pin,
            &request,
            Duration::from_millis(250),
            Duration::from_millis(80)
        ),
        Err(Error::Identity)
    ));
    let writable = f.0.join("writable");
    fs::copy(&worker.executable, &writable).unwrap();
    fs::set_permissions(&writable, fs::Permissions::from_mode(0o777)).unwrap();
    bad_pin = f.pin(&writable);
    assert!(matches!(
        run_local_preparation(
            &bad_pin,
            &request,
            Duration::from_millis(250),
            Duration::from_millis(80)
        ),
        Err(Error::Identity)
    ));
    bad_pin = f.pin(&worker.executable);
    bad_pin.protocol = 99;
    assert!(matches!(
        run_local_preparation(
            &bad_pin,
            &request,
            Duration::from_millis(250),
            Duration::from_millis(80)
        ),
        Err(Error::Protocol)
    ));
    assert_eq!(children(), baseline);
}
struct TestChild(std::process::Child);
impl Drop for TestChild {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let cleanup = Instant::now();
        while cleanup.elapsed() < Duration::from_millis(100) {
            if matches!(self.0.try_wait(), Ok(Some(_))) {
                return;
            }
            std::thread::sleep(Duration::from_millis(1));
        }
    }
}
fn test_nonblocking(fd: impl AsFd) {
    rustix::fs::fcntl_setfl(
        &fd,
        rustix::fs::fcntl_getfl(&fd).unwrap() | rustix::fs::OFlags::NONBLOCK,
    )
    .unwrap();
}
fn worker_command() -> Command {
    let mut command = Command::new(env!("CARGO_BIN_EXE_codex-smart-preparation-worker"));
    command.env_clear().current_dir("/");
    command
}
fn assert_direct_exit(mut command: Command, bytes: &[u8], expected_code: u8) {
    let descriptors = descriptor_snapshot();
    let mut child = TestChild(
        command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap(),
    );
    let started = Instant::now();
    let mut input = child.0.stdin.take();
    let mut output = child.0.stdout.take().unwrap();
    let mut errors = child.0.stderr.take().unwrap();
    test_nonblocking(input.as_ref().unwrap());
    test_nonblocking(&output);
    test_nonblocking(&errors);
    let mut sent = 0;
    let mut eof = [false; 2];
    let mut exit = None;
    while started.elapsed() < Duration::from_secs(1) {
        if let Some(pipe) = input.as_mut() {
            match pipe.write(&bytes[sent..]) {
                Ok(n) => sent += n,
                Err(e)
                    if matches!(
                        e.kind(),
                        std::io::ErrorKind::WouldBlock | std::io::ErrorKind::Interrupted
                    ) => {}
                Err(e) if e.kind() == std::io::ErrorKind::BrokenPipe => input = None,
                Err(_) => panic!("test input failure"),
            }
            if sent == bytes.len() {
                input = None;
            }
        }
        for (i, pipe) in [&mut output as &mut dyn Read, &mut errors as &mut dyn Read]
            .into_iter()
            .enumerate()
        {
            let mut buf = [0; 64];
            match pipe.read(&mut buf) {
                Ok(0) => eof[i] = true,
                Ok(_) => panic!("worker logged/output an invalid request"),
                Err(e)
                    if matches!(
                        e.kind(),
                        std::io::ErrorKind::WouldBlock | std::io::ErrorKind::Interrupted
                    ) => {}
                Err(_) => panic!("test output failure"),
            }
        }
        if exit.is_none() {
            exit = child.0.try_wait().unwrap();
        }
        if let Some(status) = exit
            && eof.iter().all(|x| *x)
        {
            assert_eq!(
                status.code(),
                Some(i32::from(expected_code)),
                "parent fd count: {}; numeric fd/flags: {:?}",
                descriptors.len(),
                descriptors
            );
            return;
        }
        std::thread::sleep(Duration::from_millis(1));
    }
    panic!("invalid request worker failed to return within test deadline");
}
#[test]
fn bootstrap_refuses_inherited_proc_directory() {
    let _test_lock = TEST_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let baseline = children();
    // Even a descriptor whose target names the iterator directory is inherited.
    let leaked = fs::File::open("/proc/self/fd").unwrap();
    rustix::io::fcntl_setfd(&leaked, rustix::io::FdFlags::empty()).unwrap();
    assert_direct_exit(worker_command(), &[], 17);
    drop(leaked);
    assert_eq!(children(), baseline);
}
#[test]
fn bootstrap_refuses_inherited_own_proc_directory_after_exec() {
    let _test_lock = TEST_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let f = Fixture::new();
    let baseline = children();
    // Controlled adversarial executable: retain its own proc directory across
    // exec, so its target has exactly the spelling the old bootstrap exempted.
    // Linux F_SETFD=2; the unsafe FFI lives only in compiled fixture source.
    let helper = f.fake(
        "proc-exec",
        &format!(
            "use std::os::{{fd::AsRawFd,unix::process::CommandExt}}; \
         unsafe extern \"C\" {{ fn fcntl(fd:i32,cmd:i32,...)->i32; }} \
         let directory=std::fs::File::open(\"/proc/self/fd\").unwrap(); \
         assert_eq!(unsafe {{fcntl(directory.as_raw_fd(),2,0_i32)}},0); \
         let _=std::process::Command::new({:?}).env_clear().exec(); \
         std::process::exit(99);",
            env!("CARGO_BIN_EXE_codex-smart-preparation-worker")
        ),
    );
    let mut command = Command::new(&helper.executable);
    command.env_clear();
    assert_direct_exit(command, &[], 17);
    assert_eq!(children(), baseline);
}
#[test]
fn bootstrap_environment_and_arguments_have_payload_free_refusal_codes() {
    let _test_lock = TEST_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let baseline = children();
    let mut command = worker_command();
    command.env("CS_PUBLIC_BOOTSTRAP_FIXTURE", "public-fixture-value");
    assert_direct_exit(command, &[], 11);
    let mut command = worker_command();
    command.arg("unsupported-fixture-argument");
    assert_direct_exit(command, &[], 2);
    assert_eq!(children(), baseline);
}
#[test]
fn worker_rejects_bounded_bad_requests_without_logging() {
    let _test_lock = TEST_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let baseline = children();
    let mut malformed = vec![
        vec![],
        b"CSPREQ\0\x02\0\0\0\0".to_vec(),
        vec![0xff; 18433],
        b"CSPREQ\0\x01\xff\xff\xff\xff".to_vec(),
    ];
    // Valid-size envelope containing invalid UTF-8 or excessive nomination count.
    let request = PreparationRequest {
        root: "/tmp".into(),
        intent: Intent::Inspection,
        files: vec![],
        limits: Limits::default(),
    };
    let wire = request.encode().unwrap();
    let mut utf8 = wire.clone();
    utf8[17] = 255;
    malformed.push(utf8);
    let mut count = wire.clone();
    count[37..41].copy_from_slice(&17_u32.to_be_bytes());
    malformed.push(count);
    let mut trailing = wire.clone();
    trailing.push(0);
    malformed.push(trailing);
    for bytes in malformed {
        assert!(PreparationRequest::decode(&bytes).is_err());
        assert_direct_exit(worker_command(), &bytes, 4);
        assert_eq!(children(), baseline);
    }
}
