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

#[cfg(target_os = "linux")]
mod supervised {
    use super::*;

    impl Fixture {
        fn stream(&self, body: &str) {
            fs::write(self.0.join("bin/codex"), format!("#!/bin/sh\nif [ \"$1\" = --version ]; then printf 'codex-cli 0.162.1\\n'; exit 0; fi\nif [ \"$1\" = debug ]; then printf '%s' \"$FAKE_CATALOG\"; exit 0; fi\nprintf '%s\\n' \"$@\" > \"$FAKE_ARGS\"\nprintf 'attempt\\n' >> \"$FAKE_CALLS\"\n{body}\n")).unwrap();
        }
        fn supervised(&self) -> Command {
            let mut command = self.command();
            command.args(["inspect", "--supervised-json", "--timeout-seconds", "1"]);
            command
        }
        fn one_call(&self) {
            assert_eq!(
                fs::read_to_string(self.0.join("calls")).unwrap(),
                "attempt\n"
            );
        }
    }
    const START: &str =
        "{\"type\":\"thread.started\",\"thread_id\":\"PRIVATE\"}\n{\"type\":\"turn.started\"}";
    fn stream_body(end: &str) -> String {
        format!(
            "printf '%s\\n' '{START}' '{{\"type\":\"item.completed\",\"item\":{{\"type\":\"agent_message\",\"text\":\"PRIVATE ANSWER\"}}}}' '{end}'\nprintf 'PRIVATE STDERR' >&2"
        )
    }
    fn report(output: &Output) -> serde_json::Value {
        assert!(!String::from_utf8_lossy(&output.stdout).contains("PRIVATE"));
        assert!(!stderr(output).contains("PRIVATE"));
        serde_json::from_slice(&output.stdout).unwrap()
    }

    #[test]
    fn ledger_private_receipts_and_concurrent_invocations() {
        let f = Fixture::new();
        f.stream(&stream_body(r#"{"type":"turn.completed"}"#));
        let dir = f.0.join("ledger");
        fs::create_dir(&dir).unwrap();
        fs::set_permissions(&dir, fs::Permissions::from_mode(0o700)).unwrap();
        let mut children = Vec::new();
        for _ in 0..4 {
            children.push(
                f.supervised()
                    .arg("--attempt-ledger-dir")
                    .arg(&dir)
                    .arg("PRIVATE PROMPT")
                    .stdout(Stdio::piped())
                    .stderr(Stdio::piped())
                    .spawn()
                    .unwrap(),
            );
        }
        for child in children {
            assert_eq!(
                report(&child.wait_with_output().unwrap())["status"],
                "CompletedSuccess"
            );
        }
        let entries: Vec<_> = fs::read_dir(&dir).unwrap().collect();
        assert_eq!(entries.len(), 4);
        for entry in entries {
            let path = entry.unwrap().path();
            assert_eq!(
                fs::metadata(&path).unwrap().permissions().mode() & 0o7777,
                0o600
            );
            let text = fs::read_to_string(path).unwrap();
            assert!(!text.contains("PRIVATE"));
            let records: Vec<serde_json::Value> = text
                .lines()
                .map(|line| serde_json::from_str(line).unwrap())
                .collect();
            assert_eq!(records.len(), 2);
            assert_eq!(records[0], serde_json::json!({"schema":1,"type":"started"}));
            assert_eq!(
                records[1]["report"]["usage"]["input_tokens"],
                serde_json::Value::Null
            );
        }
    }

    #[test]
    fn ledger_refuses_unsafe_paths_without_model_launch() {
        use std::os::unix::fs::symlink;
        for case in 0..4 {
            let f = Fixture::new();
            let dir = f.0.join("ledger");
            fs::create_dir(&dir).unwrap();
            fs::set_permissions(
                &dir,
                fs::Permissions::from_mode(if case == 0 { 0o755 } else { 0o700 }),
            )
            .unwrap();
            symlink(&dir, f.0.join("link")).unwrap();
            let path = match case {
                1 => f.0.join("link"),
                2 => f.0.join("link/../ledger"),
                3 => f.0.join("missing"),
                _ => dir,
            };
            let output = f
                .supervised()
                .arg("--attempt-ledger-dir")
                .arg(path)
                .arg("PRIVATE")
                .output()
                .unwrap();
            assert_eq!(output.status.code(), Some(2));
            assert!(output.stdout.is_empty());
            assert!(stderr(&output).contains("E_INSPECT_LEDGER"));
            f.not_launched();
        }
        let f = Fixture::new();
        let output = f
            .command()
            .args(["inspect", "--attempt-ledger-dir", "/tmp", "task"])
            .output()
            .unwrap();
        assert_eq!(output.status.code(), Some(2));
        f.not_launched();
    }

    #[test]
    fn ledger_retains_failure_and_timeout() {
        for (body, status) in [
            (stream_body(r#"{"type":"turn.failed"}"#), "CompletedFailure"),
            ("while :; do :; done".to_owned(), "Timeout"),
        ] {
            let f = Fixture::new();
            f.stream(&body);
            let output = f
                .supervised()
                .arg("--attempt-ledger-dir")
                .arg(&f.0)
                .arg("task")
                .output()
                .unwrap();
            assert_eq!(report(&output)["status"], status);
            let path = fs::read_dir(&f.0)
                .unwrap()
                .map(|e| e.unwrap().path())
                .find(|p| p.extension().is_some_and(|e| e == "jsonl"))
                .unwrap();
            let text = fs::read_to_string(path).unwrap();
            let terminal: serde_json::Value =
                serde_json::from_str(text.lines().nth(1).unwrap()).unwrap();
            assert_eq!(terminal["report"]["status"], status);
            f.one_call();
        }
    }

    #[test]
    fn supervised_success_usage_private_answer_and_exact_argv() {
        let f = Fixture::new();
        f.stream(&stream_body(r#"{"type":"turn.completed","usage":{"input_tokens":12,"cached_input_tokens":0,"output_tokens":7,"cache_write_input_tokens":null,"reasoning_output_tokens":null}}"#));
        let answer = f.0.join("answer");
        let output = f
            .supervised()
            .arg("--answer-file")
            .arg(&answer)
            .arg("PRIVATE TASK")
            .output()
            .unwrap();
        let value = report(&output);
        assert!(output.status.success());
        assert_eq!(value["status"], "CompletedSuccess");
        assert_eq!(
            value["usage"],
            serde_json::json!({"input_tokens":12,"cached_input_tokens":0,"output_tokens":7,"cache_write_input_tokens":null,"reasoning_output_tokens":null})
        );
        assert_eq!(value["answer_file"], "Written");
        assert_eq!(fs::read_to_string(&answer).unwrap(), "PRIVATE ANSWER");
        assert_eq!(
            fs::metadata(answer).unwrap().permissions().mode() & 0o777,
            0o600
        );
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
                "--json",
                "--ephemeral",
                "--",
                "PRIVATE TASK"
            ]
        );
        f.one_call();
    }

    #[test]
    fn supervised_missing_usage_is_null_and_failed_turn_is_explicit() {
        for (terminal, exit, expected) in [
            (r#"{"type":"turn.completed"}"#, 0, "CompletedSuccess"),
            (
                r#"{"type":"turn.failed","error":{"message":"PRIVATE ERROR"}}"#,
                1,
                "CompletedFailure",
            ),
        ] {
            let f = Fixture::new();
            f.stream(&format!("{}\nexit {exit}", stream_body(terminal)));
            let output = f.supervised().arg("task").output().unwrap();
            let value = report(&output);
            assert_eq!(value["status"], expected);
            assert_eq!(
                value["usage"],
                serde_json::json!({"input_tokens":null,"cached_input_tokens":null,"output_tokens":null,"cache_write_input_tokens":null,"reasoning_output_tokens":null})
            );
            f.one_call();
        }
    }

    #[test]
    fn supervised_invalid_incomplete_oversize_and_abnormal_streams_never_replay() {
        for body in [
            "printf 'PRIVATE INVALID\\n'".to_owned(),
            format!("printf '%s\\n' '{START}'"),
            format!("printf '%s\\n' '{START}'; printf '{{\"type\":\"turn.completed\"}}'"),
            "exec /usr/bin/head -c 1048577 /dev/zero".to_owned(),
            "exit 3".to_owned(),
            "kill -TERM $$".to_owned(),
        ] {
            let f = Fixture::new();
            f.stream(&body);
            let output = f.supervised().arg("task").output().unwrap();
            let value = report(&output);
            let expected = if body == "kill -TERM $$" {
                "Interrupted"
            } else {
                "Unknown"
            };
            assert_eq!(value["status"], expected);
            assert!(!output.status.success());
            f.one_call();
        }
    }

    #[test]
    fn supervised_answer_refuses_existing_file_and_symlink_without_call() {
        use std::os::unix::fs::symlink;
        let f = Fixture::new();
        let target = f.0.join("target");
        fs::write(&target, "original").unwrap();
        let link = f.0.join("link");
        symlink(&target, &link).unwrap();
        for path in [&target, &link] {
            let output = f
                .supervised()
                .arg("--answer-file")
                .arg(path)
                .arg("PRIVATE TASK")
                .output()
                .unwrap();
            assert_eq!(output.status.code(), Some(2));
            assert!(output.stdout.is_empty());
            assert!(!stderr(&output).contains("PRIVATE"));
            f.not_launched();
            assert_eq!(fs::read_to_string(&target).unwrap(), "original");
        }
    }

    #[test]
    fn supervised_timeout_kills_descendants_and_closes_stdin() {
        let f = Fixture::new();
        f.stream("if read -r line; then printf 'PRIVATE INPUT'; exit 4; fi\n/usr/bin/sleep 30 &\nprintf '%s' $! > \"$FAKE_CALLS.pid\"\nwait");
        let started = Instant::now();
        let output = f.supervised().arg("task").output().unwrap();
        assert_eq!(report(&output)["status"], "Timeout");
        assert_eq!(output.status.code(), Some(124));
        assert!(started.elapsed() < Duration::from_secs(4));
        f.one_call();
        let pid = fs::read_to_string(f.0.join("calls.pid")).unwrap();
        // A killed descendant may remain a zombie until the host's init reaps it.
        if let Ok(stat) = fs::read_to_string(format!("/proc/{pid}/stat")) {
            assert_eq!(stat.split_whitespace().nth(2), Some("Z"));
        }
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn supervised_parent_interrupt_reports_and_reaps_without_replay() {
        use rustix::process::{Pid, Signal, kill_process};
        let f = Fixture::new();
        f.stream("exec /usr/bin/sleep 30");
        let child = f
            .supervised()
            .arg("--attempt-ledger-dir")
            .arg(&f.0)
            .arg("task")
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        let deadline = Instant::now() + Duration::from_secs(3);
        while !f.0.join("calls").exists() {
            assert!(Instant::now() < deadline);
            std::thread::sleep(Duration::from_millis(10));
        }
        kill_process(Pid::from_raw(child.id() as i32).unwrap(), Signal::INT).unwrap();
        let output = child.wait_with_output().unwrap();
        assert_eq!(report(&output)["status"], "Interrupted");
        f.one_call();
        let path = fs::read_dir(&f.0)
            .unwrap()
            .map(|e| e.unwrap().path())
            .find(|p| p.extension().is_some_and(|e| e == "jsonl"))
            .unwrap();
        let text = fs::read_to_string(path).unwrap();
        assert!(text.contains("Interrupted"));
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn supervised_spawn_failure_is_unknown_without_replay() {
        use std::os::unix::fs::symlink;
        let f = Fixture::new();
        let interpreter = f.0.join("shell");
        symlink("/bin/sh", &interpreter).unwrap();
        fs::write(f.0.join("bin/codex"), format!("#!{}\nif [ \"$1\" = --version ]; then printf 'codex-cli 0.162.1\\n'; exit 0; fi\nif [ \"$1\" = debug ]; then printf '%s' \"$FAKE_CATALOG\"; /bin/rm -- \"$FAKE_INTERPRETER\"; exit 0; fi\nprintf attempt >> \"$FAKE_CALLS\"\n", interpreter.display())).unwrap();
        let output = f
            .supervised()
            .env("FAKE_INTERPRETER", interpreter)
            .arg("task")
            .output()
            .unwrap();
        assert_eq!(report(&output)["status"], "Unknown");
        assert_eq!(output.status.code(), Some(2));
        f.not_launched();
    }

    #[test]
    fn supervised_protocol_and_usage_fail_closed_without_private_leaks() {
        for terminal in [
            r#"{"type":"turn.completed","usage":{"input_tokens":9}}"#,
            r#"{"type":"turn.completed","usage":{"input_tokens":-1,"cached_input_tokens":"PRIVATE","output_tokens":null,"cache_write_input_tokens":null,"reasoning_output_tokens":null}}"#,
            "{\"type\":\"turn.completed\"}\n{\"type\":\"turn.completed\"}",
            "{\"type\":\"turn.completed\"}\nPRIVATE TRAILING",
        ] {
            let f = Fixture::new();
            f.stream(&stream_body(terminal));
            let output = f.supervised().arg("task").output().unwrap();
            let value = report(&output);
            if terminal.contains("9") {
                assert_eq!(value["status"], "CompletedSuccess");
                assert_eq!(value["usage"]["input_tokens"], 9);
                assert!(value["usage"]["cached_input_tokens"].is_null());
                assert!(value["usage"]["output_tokens"].is_null());
            } else if terminal.contains("-1") {
                assert_eq!(value["status"], "CompletedSuccess");
                assert_eq!(
                    value["usage"],
                    serde_json::json!({"input_tokens":null,"cached_input_tokens":null,"output_tokens":null,"cache_write_input_tokens":null,"reasoning_output_tokens":null})
                );
            } else {
                assert_eq!(value["status"], "Unknown");
            }
            f.one_call();
        }
    }

    #[test]
    fn supervised_only_options_refuse_in_default_inspect_and_run_stays_passthrough() {
        let f = Fixture::new();
        for options in [
            vec!["--answer-file", "PRIVATE", "task"],
            vec!["--timeout-seconds", "1", "task"],
            vec!["--supervised-json", "--timeout-seconds", "0", "task"],
            vec!["--supervised-json", "--supervised-json", "task"],
        ] {
            let output = f.command().arg("inspect").args(options).output().unwrap();
            assert_eq!(output.status.code(), Some(2));
            assert!(!stderr(&output).contains("PRIVATE"));
            f.not_launched();
        }
        let output = f
            .command()
            .args([
                "run",
                "--",
                "inspect",
                "--supervised-json",
                "--answer-file",
                "PRIVATE",
            ])
            .output()
            .unwrap();
        assert!(output.status.success());
        assert_eq!(
            f.argv(),
            ["inspect", "--supervised-json", "--answer-file", "PRIVATE"]
        );
    }

    #[test]
    fn supervised_nonzero_completed_stream_is_failure_and_all_native_usage_is_preserved() {
        let f = Fixture::new();
        f.stream(&format!("{}\nexit 5", stream_body(r#"{"type":"turn.completed","usage":{"cache_write_input_tokens":4,"reasoning_output_tokens":2}}"#)));
        let output = f.supervised().arg("task").output().unwrap();
        let value = report(&output);
        assert_eq!(value["status"], "CompletedFailure");
        assert_eq!(value["usage"]["cache_write_input_tokens"], 4);
        assert_eq!(value["usage"]["reasoning_output_tokens"], 2);
        assert!(value["usage"]["input_tokens"].is_null());
        f.one_call();
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn supervised_cleanup_uncertainty_is_unknown() {
        use rustix::process::{Pid, Signal, kill_process};
        let f = Fixture::new();
        f.stream("/usr/bin/setsid /bin/sh -c 'printf %s $$ > \"$FAKE_CALLS.pid\"; exec /usr/bin/sleep 30' &\nwait");
        let output = f.supervised().arg("task").output().unwrap();
        // Explicit fixture cleanup of the deliberately escaped test process.
        let pid = fs::read_to_string(f.0.join("calls.pid"))
            .unwrap()
            .parse::<i32>()
            .unwrap();
        kill_process(Pid::from_raw(pid).unwrap(), Signal::KILL).unwrap();
        assert_eq!(report(&output)["status"], "Unknown");
        f.one_call();
    }

    #[test]
    fn supervised_null_stdin_does_not_wait_for_inherited_open_pipe() {
        let f = Fixture::new();
        f.stream(&format!(
            "if read -r line; then printf PRIVATE; exit 4; fi\n{}",
            stream_body(r#"{"type":"turn.completed"}"#)
        ));
        let mut child = f
            .supervised()
            .arg("task")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        let inherited_writer = child.stdin.take().unwrap();
        let deadline = Instant::now() + Duration::from_secs(3);
        loop {
            if child.try_wait().unwrap().is_some() {
                break;
            }
            assert!(Instant::now() < deadline);
            std::thread::sleep(Duration::from_millis(10));
        }
        let output = child.wait_with_output().unwrap();
        drop(inherited_writer);
        assert_eq!(report(&output)["status"], "CompletedSuccess");
        f.one_call();
    }

    #[test]
    fn supervised_normal_exit_cleans_lingering_descendants_and_keeps_last_answer() {
        let f = Fixture::new();
        f.stream(&format!("printf '%s\\n' '{START}' '{{\"type\":\"item.completed\",\"item\":{{\"type\":\"agent_message\",\"text\":\"PRIVATE FIRST\"}}}}' '{{\"type\":\"item.completed\",\"item\":{{\"type\":\"agent_message\",\"text\":\"PRIVATE LAST\"}}}}' '{{\"type\":\"turn.completed\"}}'\n/usr/bin/sleep 30 &\nprintf '%s' $! > \"$FAKE_CALLS.pid\"\nexit 0"));
        let answer = f.0.join("answer");
        let started = Instant::now();
        let output = f
            .supervised()
            .arg("--answer-file")
            .arg(&answer)
            .arg("task")
            .output()
            .unwrap();
        assert_eq!(report(&output)["status"], "CompletedSuccess");
        assert!(started.elapsed() < Duration::from_secs(3));
        assert_eq!(fs::read_to_string(answer).unwrap(), "PRIVATE LAST");
        let pid = fs::read_to_string(f.0.join("calls.pid")).unwrap();
        if let Ok(stat) = fs::read_to_string(format!("/proc/{pid}/stat")) {
            assert_eq!(stat.split_whitespace().nth(2), Some("Z"));
        }
        f.one_call();
    }

    #[test]
    fn supervised_catalog_probes_clean_up_their_descendants() {
        let f = Fixture::new();
        f.stream(&stream_body(r#"{"type":"turn.completed"}"#));
        let path = f.0.join("bin/codex");
        let script = fs::read_to_string(&path).unwrap()
        .replace("then printf 'codex-cli", "then /usr/bin/sleep 30 &\nprintf '%s' $! > \"$FAKE_CALLS.version.pid\"\nprintf 'codex-cli")
        .replace("then printf '%s' \"$FAKE_CATALOG\"", "then /usr/bin/sleep 30 &\nprintf '%s' $! > \"$FAKE_CALLS.catalog.pid\"\nprintf '%s' \"$FAKE_CATALOG\"");
        fs::write(path, script).unwrap();
        let output = f.supervised().arg("task").output().unwrap();
        assert_eq!(report(&output)["status"], "CompletedSuccess");
        for suffix in ["version", "catalog"] {
            let pid = fs::read_to_string(f.0.join(format!("calls.{suffix}.pid"))).unwrap();
            if let Ok(stat) = fs::read_to_string(format!("/proc/{pid}/stat")) {
                assert_eq!(stat.split_whitespace().nth(2), Some("Z"));
            }
        }
        f.one_call();
    }
}
