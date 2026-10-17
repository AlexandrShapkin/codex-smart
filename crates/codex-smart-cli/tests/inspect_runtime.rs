#![cfg(unix)]
use std::{
    fs,
    os::unix::{fs::PermissionsExt, process::ExitStatusExt},
    path::PathBuf,
    process::{Command, Output, Stdio},
    sync::atomic::{AtomicUsize, Ordering},
    time::{Duration, Instant},
};

static NEXT: AtomicUsize = AtomicUsize::new(0);
const CATALOG: &str = r#"{"models":[{"slug":"gpt-6-luna","supported_in_api":true,"supported_reasoning_levels":[{"effort":"medium"},{"effort":"high"}]},{"slug":"gpt-6-sol","supported_in_api":true,"supported_reasoning_levels":[{"effort":"medium"},{"effort":"high"}]},{"slug":"gpt-6-astra","supported_in_api":true,"supported_reasoning_levels":[{"effort":"medium"},{"effort":"high"}]}]}"#;

struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!(
            "codex-smart-inspect-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        fs::set_permissions(&path, fs::Permissions::from_mode(0o700)).unwrap();
        fs::create_dir(path.join("bin")).unwrap();
        fs::create_dir(path.join("repo")).unwrap();
        fs::create_dir(path.join("home")).unwrap();
        fs::set_permissions(path.join("bin"), fs::Permissions::from_mode(0o700)).unwrap();
        fs::write(path.join("bin/codex"), "#!/bin/sh\nif [ \"$1\" = --version ]; then printf '%s\\n' \"$FAKE_VERSION\"; exit 0; fi\nif [ \"$1\" = debug ]; then printf '%s\\n' \"$@\" > \"$FAKE_PROBE\"; printf '%s' \"$FAKE_CATALOG\"; exit \"$FAKE_CATALOG_EXIT\"; fi\nprintf '%s\\n' \"$@\" > \"$FAKE_ARGS\"\nprintf 'attempt\\n' >> \"$FAKE_CALLS\"\nexit \"$FAKE_EXIT\"\n").unwrap();
        fs::set_permissions(path.join("bin/codex"), fs::Permissions::from_mode(0o700)).unwrap();
        Self(path)
    }
    fn command(&self) -> Command {
        let mut command = Command::new(env!("CARGO_BIN_EXE_codex-smart"));
        command
            .env_clear()
            .env("PATH", self.0.join("bin"))
            .env("HOME", self.0.join("home"))
            .env("CODEX_HOME", self.0.join("home/.codex"))
            .env("FAKE_VERSION", "codex-cli 0.162.1")
            .env("FAKE_CATALOG", CATALOG)
            .env("FAKE_CATALOG_EXIT", "0")
            .env("FAKE_EXIT", "0")
            .env("FAKE_ARGS", self.0.join("args"))
            .env("FAKE_CALLS", self.0.join("calls"))
            .env("FAKE_PROBE", self.0.join("probe"))
            .current_dir(self.0.join("repo"));
        command
    }
    fn argv(&self) -> Vec<String> {
        fs::read_to_string(self.0.join("args"))
            .unwrap()
            .lines()
            .map(str::to_owned)
            .collect()
    }
    fn not_launched(&self) {
        assert!(!self.0.join("args").exists());
        assert!(!self.0.join("calls").exists());
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
fn stderr(output: &Output) -> String {
    String::from_utf8_lossy(&output.stderr).into_owned()
}

#[test]
fn low_risk_uses_one_read_only_codex_attempt_with_exact_argv() {
    let f = Fixture::new();
    let output = f
        .command()
        .args(["inspect", "Read-only inspection task"])
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(0));
    assert_eq!(
        f.argv(),
        [
            "--model",
            "gpt-6-luna",
            "--config",
            "model_reasoning_effort=\"medium\"",
            "exec",
            "-s",
            "read-only",
            "--",
            "Read-only inspection task"
        ]
    );
    assert!(stderr(&output).contains("availability unknown"));
    assert!(!stderr(&output).contains("Read-only inspection task"));
    assert_eq!(
        fs::read_to_string(f.0.join("probe")).unwrap(),
        "debug\nmodels\n--bundled\n"
    );
}

#[test]
fn explicit_stronger_model_and_effort_are_preserved() {
    let f = Fixture::new();
    let output = f
        .command()
        .args([
            "inspect",
            "--model",
            "gpt-6-sol",
            "--reasoning",
            "high",
            "--",
            "task",
        ])
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(0));
    assert_eq!(
        f.argv(),
        [
            "--model",
            "gpt-6-sol",
            "--config",
            "model_reasoning_effort=\"high\"",
            "exec",
            "-s",
            "read-only",
            "--",
            "task"
        ]
    );
}

#[test]
fn unknown_stale_incompatible_and_unavailable_catalogs_refuse_without_attempt() {
    let cases = [
        (r#"{"models":[]}"#, "codex-cli 0.162.1", "E_INSPECT_MODEL"),
        (
            r#"{"models":[{"slug":"gpt-6-luna","supported_in_api":true,"supported_reasoning_levels":[{"effort":"high"}]}]}"#,
            "codex-cli 0.162.1",
            "E_INSPECT_MODEL",
        ),
        (
            r#"{"models":[{"slug":"gpt-6-luna","supported_in_api":false,"supported_reasoning_levels":[{"effort":"medium"}]}]}"#,
            "codex-cli 0.162.1",
            "E_INSPECT_MODEL",
        ),
        ("invalid", "codex-cli 0.162.1", "E_INSPECT_CATALOG"),
        (CATALOG, "codex-cli 0.161.0", "E_CODEX_CATALOG"),
    ];
    for (catalog, version, expected) in cases {
        let f = Fixture::new();
        let output = f
            .command()
            .env("FAKE_CATALOG", catalog)
            .env("FAKE_VERSION", version)
            .args(["inspect", "private prompt"])
            .output()
            .unwrap();
        assert_eq!(output.status.code(), Some(2));
        assert!(stderr(&output).contains(expected));
        assert!(!stderr(&output).contains("private prompt"));
        f.not_launched();
    }
}

#[test]
fn higher_risk_and_safety_refuse_before_catalog_probe() {
    for options in [
        vec!["--risk", "medium"],
        vec!["--risk", "high"],
        vec!["--safety", "security"],
        vec!["--safety", "migration"],
        vec!["--safety", "concurrency"],
    ] {
        let f = Fixture::new();
        let mut command = f.command();
        let output = command
            .arg("inspect")
            .args(options)
            .arg("private prompt")
            .output()
            .unwrap();
        assert_eq!(output.status.code(), Some(2));
        assert!(stderr(&output).contains("E_INSPECT_FLOOR"));
        assert!(!stderr(&output).contains("private prompt"));
        f.not_launched();
    }
}

#[test]
fn provider_failure_and_catalog_failure_propagate_without_replay() {
    let f = Fixture::new();
    let output = f
        .command()
        .env("FAKE_EXIT", "17")
        .args(["inspect", "task"])
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(17));
    assert_eq!(fs::read_to_string(f.0.join("calls")).unwrap(), "attempt\n");
    let f = Fixture::new();
    let output = f
        .command()
        .env("FAKE_CATALOG_EXIT", "7")
        .args(["inspect", "task"])
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
    assert!(stderr(&output).contains("E_CODEX_CATALOG"));
    f.not_launched();
}

#[test]
fn malformed_options_and_private_values_never_appear_in_errors() {
    let f = Fixture::new();
    let output = f
        .command()
        .args(["inspect", "--model", "PRIVATE_SECRET", "task"])
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
    assert!(!stderr(&output).contains("PRIVATE_SECRET"));
    f.not_launched();
}

#[test]
fn inspect_closes_inherited_stdin_without_waiting_for_input() {
    let f = Fixture::new();
    fs::write(
        f.0.join("bin/codex"),
        "#!/bin/sh\nif [ \"$1\" = --version ]; then printf 'codex-cli 0.162.1\\n'; exit 0; fi\nif [ \"$1\" = debug ]; then printf '%s' \"$FAKE_CATALOG\"; exit 0; fi\nif IFS= read -r line; then exit 41; fi\nprintf 'attempt\\n' >> \"$FAKE_CALLS\"\nexit 0\n",
    )
    .unwrap();
    let mut child = f
        .command()
        .args(["inspect", "task"])
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .unwrap();
    // Keep the pipe writer open, replicating an interactive remote parent.
    let _still_open = child.stdin.take().unwrap();
    let deadline = Instant::now() + Duration::from_secs(3);
    let status = loop {
        if let Some(status) = child.try_wait().unwrap() {
            break status;
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            panic!("inspect waited on inherited stdin");
        }
        std::thread::sleep(Duration::from_millis(20));
    };
    assert!(status.success());
    assert_eq!(fs::read_to_string(f.0.join("calls")).unwrap(), "attempt\n");
}

#[test]
fn catalog_probe_timeout_and_oversized_output_fail_closed() {
    for mode in ["timeout", "oversized"] {
        let f = Fixture::new();
        let script = if mode == "timeout" {
            "#!/bin/sh\nif [ \"$1\" = --version ]; then exec /usr/bin/sleep 20; fi\nexit 0\n"
        } else {
            "#!/bin/sh\nif [ \"$1\" = --version ]; then printf 'codex-cli 0.162.1\\n'; exit 0; fi\nif [ \"$1\" = debug ]; then exec /usr/bin/head -c 2000100 /dev/zero; fi\nexit 0\n"
        };
        fs::write(f.0.join("bin/codex"), script).unwrap();
        let started = Instant::now();
        let output = f.command().args(["inspect", "task"]).output().unwrap();
        assert_eq!(output.status.code(), Some(2), "{mode}");
        assert!(stderr(&output).contains("E_CODEX_CATALOG"), "{mode}");
        assert!(started.elapsed() < Duration::from_secs(9), "{mode}");
        f.not_launched();
    }
}

#[test]
fn inspect_exec_signal_is_propagated_without_replay() {
    let f = Fixture::new();
    fs::write(
        f.0.join("bin/codex"),
        "#!/bin/sh\nif [ \"$1\" = --version ]; then printf 'codex-cli 0.162.1\\n'; exit 0; fi\nif [ \"$1\" = debug ]; then printf '%s' \"$FAKE_CATALOG\"; exit 0; fi\nprintf 'attempt\\n' >> \"$FAKE_CALLS\"\nkill -TERM $$\n",
    )
    .unwrap();
    let output = f.command().args(["inspect", "task"]).output().unwrap();
    assert_eq!(output.status.signal(), Some(15));
    assert_eq!(fs::read_to_string(f.0.join("calls")).unwrap(), "attempt\n");
}
