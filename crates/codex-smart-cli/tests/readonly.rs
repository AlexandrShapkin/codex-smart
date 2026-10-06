#![cfg(unix)]
use std::collections::BTreeMap;
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicUsize, Ordering};

static NEXT: AtomicUsize = AtomicUsize::new(0);
struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!(
            "codex-smart-readonly-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        fs::set_permissions(&path, fs::Permissions::from_mode(0o700)).unwrap();
        Self(path)
    }
    fn write(&self, name: &str, value: &str) {
        let path = self.0.join(name);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(path, value).unwrap();
    }
    fn tool(&self, name: &str) {
        self.write(
            &format!("bin/{name}"),
            "#!/bin/sh\nprintf touched > \"$HOME/side-effect\"\nexit 1\n",
        );
        fs::set_permissions(
            self.0.join("bin").join(name),
            fs::Permissions::from_mode(0o700),
        )
        .unwrap();
    }
    fn command(&self) -> Command {
        let mut command = Command::new(env!("CARGO_BIN_EXE_codex-smart"));
        command
            .env_clear()
            .env("PATH", self.0.join("bin"))
            .env("HOME", self.0.join("home"))
            .env("CODEX_HOME", self.0.join("home/.codex"))
            .current_dir(self.0.join("repo"));
        command
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
fn tree(path: &Path) -> BTreeMap<PathBuf, (Vec<u8>, std::time::SystemTime, u32)> {
    fn walk(
        root: &Path,
        path: &Path,
        output: &mut BTreeMap<PathBuf, (Vec<u8>, std::time::SystemTime, u32)>,
    ) {
        let meta = fs::symlink_metadata(path).unwrap();
        output.insert(
            path.strip_prefix(root).unwrap().to_owned(),
            (
                if meta.is_file() {
                    fs::read(path).unwrap()
                } else {
                    vec![]
                },
                meta.modified().unwrap(),
                meta.permissions().mode(),
            ),
        );
        if meta.is_dir() {
            for child in fs::read_dir(path).unwrap() {
                walk(root, &child.unwrap().path(), output);
            }
        }
    }
    let mut result = BTreeMap::new();
    walk(path, path, &mut result);
    result
}
#[test]
fn reported_legacy_mutations_and_hidden_installs_are_prevented() {
    let f = Fixture::new();
    f.write("repo/.git/info/exclude", "user-exclude\n");
    f.write("repo/.serena/memories/design.md", "tracked knowledge");
    f.write("repo/.code-graph/index", "original-index");
    f.write(
        "home/.codex/config.toml",
        "[mcp_servers.user]\ncommand = 'user-server'\n[plugins]\ncustom = true\n",
    );
    f.write("home/.codex/auth.json", "FAKE_SECRET_DO_NOT_PRINT");
    for tool in [
        "codex",
        "serena",
        "code-graph-smart",
        "code-graph-mcp",
        "gh",
        "npx",
        "rustc",
        "cargo",
        "git",
        "rg",
    ] {
        f.tool(tool);
    }
    let before = tree(&f.0);
    for args in [
        vec!["doctor"],
        vec!["capabilities"],
        vec!["explain"],
        vec!["explain", "--task", "architecture"],
        vec!["config"],
    ] {
        let output = f.command().args(args).output().unwrap();
        assert!(output.status.success(), "{:?}", output);
        assert!(!String::from_utf8_lossy(&output.stdout).contains("FAKE_SECRET"));
        assert!(output.stderr.is_empty());
        assert_eq!(tree(&f.0), before);
    }
}
#[test]
fn golden_explain_missing_capabilities() {
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    let output = f
        .command()
        .args(["explain", "--task", "architecture"])
        .output()
        .unwrap();
    assert!(output.status.success());
    assert_eq!(
        String::from_utf8(output.stdout).unwrap(),
        include_str!("../../../fixtures/explain-architecture.txt")
    );
}
#[test]
fn malformed_args_fail_without_reflecting_secret_input() {
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    for args in [
        vec!["explain", "--task", "FAKE_SECRET"],
        vec!["doctor", "FAKE_SECRET"],
        vec!["--version", "FAKE_SECRET"],
    ] {
        let output = f.command().args(args).output().unwrap();
        assert_eq!(output.status.code(), Some(2));
        assert!(output.stdout.is_empty());
        assert!(!String::from_utf8_lossy(&output.stderr).contains("FAKE_SECRET"));
    }
}
#[test]
fn path_hijacking_inside_repository_is_not_discovered() {
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.tool("codex");
    fs::create_dir(f.0.join("repo/bin")).unwrap();
    fs::copy(f.0.join("bin/codex"), f.0.join("repo/bin/codex")).unwrap();
    let output = f
        .command()
        .env("PATH", f.0.join("repo/bin"))
        .arg("doctor")
        .output()
        .unwrap();
    assert!(String::from_utf8_lossy(&output.stdout).contains("codex: not found on trusted PATH"));
    let output = f
        .command()
        .env("PATH", ".:bin")
        .arg("doctor")
        .output()
        .unwrap();
    assert!(String::from_utf8_lossy(&output.stdout).contains("codex: not found on trusted PATH"));
    fs::set_permissions(f.0.join("bin/codex"), fs::Permissions::from_mode(0o777)).unwrap();
    let output = f.command().arg("doctor").output().unwrap();
    assert!(String::from_utf8_lossy(&output.stdout).contains("codex: not found on trusted PATH"));
}

#[test]
fn dry_run_does_not_start_codex_or_expose_arguments() {
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.tool("codex");
    let before = tree(&f.0);
    let output = f
        .command()
        .args(["run", "--dry-run", "--", "exec", "FAKE_SECRET"])
        .output()
        .unwrap();
    assert!(output.status.success());
    let text = String::from_utf8(output.stdout).unwrap();
    assert!(text.contains("Arguments: 2 forwarded unchanged"));
    assert!(!text.contains("FAKE_SECRET"));
    assert_eq!(tree(&f.0), before);
}
#[test]
fn missing_codex_is_structured_error() {
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    let output = f.command().args(["run", "exec", "task"]).output().unwrap();
    assert_eq!(output.status.code(), Some(2));
    assert_eq!(
        String::from_utf8(output.stderr).unwrap(),
        "E_CODEX_MISSING: Codex not found on trusted PATH\n"
    );
}
#[test]
fn launch_preserves_argv_exit_status_and_non_utf8_without_shell_injection() {
    use std::os::unix::ffi::OsStringExt;
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.tool("codex");
    f.write(
        "bin/codex",
        "#!/bin/sh\nprintf '%s\\0' \"$@\" > \"$HOME/argv\"\nexit 37\n",
    );
    fs::create_dir_all(f.0.join("home")).unwrap();
    let dangerous = "$(touch injected); `touch injected`; a b \" c ";
    let non_utf8 = std::ffi::OsString::from_vec(vec![b'x', 0xff]);
    let output = f
        .command()
        .arg("run")
        .arg("--")
        .arg("exec")
        .arg(dangerous)
        .arg(&non_utf8)
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(37));
    let expected = [
        b"exec\0".as_slice(),
        dangerous.as_bytes(),
        &[0],
        &[b'x', 0xff, 0],
    ]
    .concat();
    assert_eq!(fs::read(f.0.join("home/argv")).unwrap(), expected);
    assert!(!f.0.join("repo/injected").exists());
    // Implicit passthrough and reserved-name escape use the same process path.
    for args in [
        vec!["exec", "--config", "model_reasoning_effort=high"],
        vec!["--", "doctor"],
    ] {
        let output = f.command().args(&args).output().unwrap();
        assert_eq!(output.status.code(), Some(37));
        let forwarded = if args[0] == "--" {
            &args[1..]
        } else {
            &args[..]
        };
        let expected: Vec<u8> = forwarded
            .iter()
            .flat_map(|a| a.bytes().chain([0]))
            .collect();
        assert_eq!(fs::read(f.0.join("home/argv")).unwrap(), expected);
    }
}

#[test]
fn default_launch_preserves_signal_termination() {
    use std::os::unix::process::ExitStatusExt;
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.tool("codex");
    f.write("bin/codex", "#!/bin/sh\nkill -TERM $$\n");
    let output = f.command().output().unwrap();
    assert_eq!(output.status.signal(), Some(15));
}
#[test]
fn changed_executable_is_rejected_after_planning() {
    use codex_smart_core::process::{LaunchError, LaunchPlan};
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.tool("codex");
    let path = f.0.join("bin");
    let plan = LaunchPlan::prepare(Some(path.as_os_str()), &f.0.join("repo"), vec![]).unwrap();
    fs::remove_file(path.join("codex")).unwrap();
    f.tool("codex");
    f.write("bin/codex", "#!/bin/sh\nexit 19\n");
    assert_eq!(plan.execute(), Err(LaunchError::ChangedExecutable));
}

#[test]
fn config_precedence_and_unknown_fields_are_read_only() {
    let f = Fixture::new();
    f.write("repo/.codex-smart.toml", "kind = 'codex-smart'\nschema_version = 1\ntask = 'refactor'\nreasoning = 'high'\n[extension]\nsecret = 'DO_NOT_PRINT'\n");
    f.write(
        "home/.config/codex-smart/config.toml",
        "kind = 'codex-smart'\nschema_version = 1\ntask = 'github'\n",
    );
    let before = tree(&f.0);
    let output = f
        .command()
        .args(["explain", "--task", "architecture", "--reasoning", "medium"])
        .output()
        .unwrap();
    assert!(output.status.success(), "{:?}", output);
    let text = String::from_utf8(output.stdout).unwrap();
    assert!(text.contains("Task: Architecture"));
    assert!(text.contains("Reasoning: Medium"));
    assert!(text.contains("task origin: Cli"));
    assert!(!text.contains("DO_NOT_PRINT"));
    assert_eq!(tree(&f.0), before);
    let output = f.command().arg("config").output().unwrap();
    assert!(output.status.success());
    let text = String::from_utf8(output.stdout).unwrap();
    assert!(text.contains("task: Refactor"));
    assert!(text.contains("task origin: Project"));
}
#[test]
fn malformed_or_malicious_project_config_fails_without_secret_output() {
    let f = Fixture::new();
    for text in [
        "kind = 'codex-smart'\nschema_version = 1\ncommand = 'FAKE_SECRET'\n",
        "kind = 'codex-smart'\nschema_version = 99\n",
        "kind = 'codex-smart'\nschema_version = 1\ncontext_limit = 1\n",
        "secret = 'FAKE_SECRET\n",
    ] {
        f.write("repo/.codex-smart.toml", text);
        let before = tree(&f.0);
        let output = f.command().arg("explain").output().unwrap();
        assert_eq!(output.status.code(), Some(2));
        assert!(!String::from_utf8_lossy(&output.stderr).contains("FAKE_SECRET"));
        assert_eq!(tree(&f.0), before);
    }
}
#[test]
fn migration_dry_run_apply_idempotency_and_rollback_preserve_unknown_data() {
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    let old = "# preserved comment\nkind = 'codex-smart'\nschema_version = 0\nreasoning_effort = 'high' # retain\n[extension]\nsecret = 'DO_NOT_PRINT'\n";
    f.write("home/smart.toml", old);
    let file = f.0.join("home/smart.toml");
    fs::set_permissions(&file, fs::Permissions::from_mode(0o600)).unwrap();
    let before = tree(&f.0);
    let output = f
        .command()
        .args(["config", "migrate", "--file"])
        .arg(&file)
        .output()
        .unwrap();
    assert!(output.status.success(), "{:?}", output);
    assert!(String::from_utf8_lossy(&output.stdout).contains("schema_version: 0 -> 1"));
    assert!(!String::from_utf8_lossy(&output.stdout).contains("DO_NOT_PRINT"));
    assert_eq!(tree(&f.0), before);
    let output = f
        .command()
        .args(["config", "migrate", "--file"])
        .arg(&file)
        .arg("--apply")
        .output()
        .unwrap();
    assert!(output.status.success(), "{:?}", output);
    let migrated = fs::read_to_string(&file).unwrap();
    assert!(migrated.contains("schema_version = 1"));
    assert!(migrated.contains("reasoning = 'high' # retain"));
    assert!(migrated.contains("secret = 'DO_NOT_PRINT'"));
    assert!(migrated.contains("# preserved comment"));
    assert_eq!(
        fs::metadata(&file).unwrap().permissions().mode() & 0o777,
        0o600
    );
    let applied = tree(&f.0);
    let output = f
        .command()
        .args(["config", "migrate", "--file"])
        .arg(&file)
        .arg("--apply")
        .output()
        .unwrap();
    assert!(output.status.success());
    assert_eq!(tree(&f.0), applied);
    let output = f
        .command()
        .args(["config", "rollback", "--file"])
        .arg(&file)
        .output()
        .unwrap();
    assert!(output.status.success(), "{:?}", output);
    assert_eq!(tree(&f.0), applied);
    let output = f
        .command()
        .args(["config", "rollback", "--file"])
        .arg(&file)
        .arg("--apply")
        .output()
        .unwrap();
    assert!(output.status.success(), "{:?}", output);
    assert_eq!(fs::read_to_string(&file).unwrap(), old);
}
#[test]
fn migration_rejects_symlinks_public_permissions_and_codex_config() {
    use std::os::unix::fs::symlink;
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.write(
        "home/original.toml",
        "kind = 'codex-smart'\nschema_version = 0\n",
    );
    symlink(f.0.join("home/original.toml"), f.0.join("home/link.toml")).unwrap();
    symlink(f.0.join("home"), f.0.join("redirect")).unwrap();
    f.write(
        "home/.codex/config.toml",
        "[mcp_servers.user]\ncommand = 'user'\n",
    );
    for file in [
        f.0.join("home/link.toml"),
        f.0.join("redirect/original.toml"),
        f.0.join("home/original.toml"),
        f.0.join("home/.codex/config.toml"),
    ] {
        let output = f
            .command()
            .args(["config", "migrate", "--file"])
            .arg(file)
            .arg("--apply")
            .output()
            .unwrap();
        assert_eq!(output.status.code(), Some(2));
    }
    assert_eq!(
        fs::read_to_string(f.0.join("home/original.toml")).unwrap(),
        "kind = 'codex-smart'\nschema_version = 0\n"
    );
    assert_eq!(
        fs::read_to_string(f.0.join("home/.codex/config.toml")).unwrap(),
        "[mcp_servers.user]\ncommand = 'user'\n"
    );
}

#[test]
fn migration_detects_edits_and_does_not_overwrite_existing_recovery_artifacts() {
    use codex_smart_core::{config::ConfigError, migration::MigrationPlan};
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    let old = "kind='codex-smart'\nschema_version=0\n";
    f.write("home/smart.toml", old);
    let file = f.0.join("home/smart.toml");
    fs::set_permissions(&file, fs::Permissions::from_mode(0o600)).unwrap();
    let plan = MigrationPlan::prepare(&file).unwrap();
    fs::write(&file, format!("{old}# user edit\n")).unwrap();
    assert_eq!(plan.apply(), Err(ConfigError::Changed));
    assert!(fs::read_to_string(&file).unwrap().contains("# user edit"));
    fs::write(&file, old).unwrap();
    let backup = file.with_file_name("smart.toml.codex-smart-backup");
    fs::write(&backup, "existing backup").unwrap();
    assert_eq!(
        MigrationPlan::prepare(&file).unwrap().apply(),
        Err(ConfigError::BackupExists)
    );
    assert_eq!(fs::read_to_string(&backup).unwrap(), "existing backup");
    assert_eq!(fs::read_to_string(&file).unwrap(), old);
}
#[test]
fn failed_staging_preserves_original_and_removes_only_new_transaction_artifacts() {
    use codex_smart_core::{config::ConfigError, migration::MigrationPlan};
    use std::os::unix::fs::symlink;
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.write("home/smart.toml", "kind='codex-smart'\nschema_version=0\n");
    let file = f.0.join("home/smart.toml");
    fs::set_permissions(&file, fs::Permissions::from_mode(0o600)).unwrap();
    f.write("home/auth", "PRIVATE_AUTH_UNCHANGED");
    let stage = file.with_file_name("smart.toml.codex-smart-stage");
    symlink(f.0.join("home/auth"), &stage).unwrap();
    assert_eq!(
        MigrationPlan::prepare(&file).unwrap().apply(),
        Err(ConfigError::BackupExists)
    );
    assert_eq!(
        fs::read_to_string(&file).unwrap(),
        "kind='codex-smart'\nschema_version=0\n"
    );
    assert_eq!(
        fs::read_to_string(f.0.join("home/auth")).unwrap(),
        "PRIVATE_AUTH_UNCHANGED"
    );
    assert!(
        fs::symlink_metadata(&stage)
            .unwrap()
            .file_type()
            .is_symlink()
    );
    for suffix in [".codex-smart-backup", ".codex-smart-applied"] {
        assert!(!file.with_file_name(format!("smart.toml{suffix}")).exists());
    }
}
#[test]
fn rollback_refuses_intervening_edits_and_is_idempotent() {
    use codex_smart_core::{config::ConfigError, migration::MigrationPlan};
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.write("home/smart.toml", "kind='codex-smart'\nschema_version=0\n");
    let file = f.0.join("home/smart.toml");
    fs::set_permissions(&file, fs::Permissions::from_mode(0o600)).unwrap();
    MigrationPlan::prepare(&file).unwrap().apply().unwrap();
    let migrated = fs::read_to_string(&file).unwrap();
    fs::write(&file, format!("{migrated}# user edit\n")).unwrap();
    assert!(matches!(
        MigrationPlan::rollback(&file),
        Err(ConfigError::Changed)
    ));
    assert!(fs::read_to_string(&file).unwrap().contains("# user edit"));
    fs::write(&file, &migrated).unwrap();
    let plan = MigrationPlan::rollback(&file).unwrap();
    fs::write(
        file.with_file_name("smart.toml.codex-smart-backup"),
        "tampered backup",
    )
    .unwrap();
    assert_eq!(plan.apply(), Err(ConfigError::Changed));
    assert_eq!(fs::read_to_string(&file).unwrap(), migrated);
    fs::write(
        file.with_file_name("smart.toml.codex-smart-backup"),
        "kind='codex-smart'\nschema_version=0\n",
    )
    .unwrap();
    MigrationPlan::rollback(&file).unwrap().apply().unwrap();
    let restored = tree(&f.0);
    MigrationPlan::rollback(&file).unwrap().apply().unwrap();
    assert_eq!(tree(&f.0), restored);
}
#[test]
fn bounded_config_reads_reject_oversize_hardlinks_and_directories() {
    use codex_smart_core::{config::ConfigError, migration::read_optional};
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.write("home/large.toml", &"x".repeat(65_537));
    assert_eq!(
        read_optional(&f.0.join("home/large.toml")),
        Err(ConfigError::TooLarge)
    );
    f.write(
        "home/original.toml",
        "kind='codex-smart'\nschema_version=1\n",
    );
    fs::hard_link(
        f.0.join("home/original.toml"),
        f.0.join("home/hardlink.toml"),
    )
    .unwrap();
    assert_eq!(
        read_optional(&f.0.join("home/hardlink.toml")),
        Err(ConfigError::UnsafePath)
    );
    // A directory cannot be treated as a regular config input.
    assert_eq!(
        read_optional(&f.0.join("home")),
        Err(ConfigError::UnsafePath)
    );
}

#[test]
fn rollback_recovers_crash_before_commit_and_after_restore_without_losing_original() {
    use codex_smart_core::migration::{MigrationPlan, upgraded};
    for artifacts in [
        vec!["backup"],
        vec!["backup", "applied"],
        vec!["backup", "applied", "stage"],
    ] {
        let f = Fixture::new();
        f.write("repo/README", "fixture");
        let old = "kind='codex-smart'\nschema_version=0\n# preserve\n";
        f.write("home/smart.toml", old);
        let file = f.0.join("home/smart.toml");
        fs::set_permissions(&file, fs::Permissions::from_mode(0o600)).unwrap();
        let after = upgraded(old).unwrap();
        for artifact in artifacts {
            let path = file.with_file_name(format!("smart.toml.codex-smart-{artifact}"));
            fs::write(&path, if artifact == "backup" { old } else { &after }).unwrap();
            fs::set_permissions(&path, fs::Permissions::from_mode(0o600)).unwrap();
        }
        let before = tree(&f.0);
        let plan = MigrationPlan::rollback(&file).unwrap();
        assert!(plan.preview().contains("recovery cleanup"));
        assert_eq!(tree(&f.0), before);
        plan.apply().unwrap();
        assert_eq!(fs::read_to_string(&file).unwrap(), old);
        for artifact in ["backup", "applied", "stage"] {
            assert!(
                !file
                    .with_file_name(format!("smart.toml.codex-smart-{artifact}"))
                    .exists()
            );
        }
        MigrationPlan::prepare(&file).unwrap().apply().unwrap();
    }
}

#[test]
fn migration_respects_exclusive_lock_without_touching_source_or_backups() {
    use codex_smart_core::{config::ConfigError, migration::MigrationPlan};
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.write("home/smart.toml", "kind='codex-smart'\nschema_version=0\n");
    let file = f.0.join("home/smart.toml");
    fs::set_permissions(&file, fs::Permissions::from_mode(0o600)).unwrap();
    let lock = f.0.join("home/.codex-smart-migration.lock");
    fs::write(&lock, "").unwrap();
    fs::set_permissions(&lock, fs::Permissions::from_mode(0o600)).unwrap();
    let guard = fs::File::open(&lock).unwrap();
    guard.try_lock().unwrap();
    let before = tree(&f.0);
    let plan = MigrationPlan::prepare(&file).unwrap();
    assert_eq!(plan.apply(), Err(ConfigError::Busy));
    assert_eq!(tree(&f.0), before);
    guard.unlock().unwrap();
    drop(guard);
    plan.apply().unwrap();
}

#[test]
fn restrictive_umask_still_produces_private_readable_transaction_files() {
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.write("home/smart.toml", "kind='codex-smart'\nschema_version=0\n");
    let file = f.0.join("home/smart.toml");
    fs::set_permissions(&file, fs::Permissions::from_mode(0o600)).unwrap();
    let output = Command::new("/bin/sh")
        .args(["-c", "umask 777; exec \"$@\"", "fixture"])
        .arg(env!("CARGO_BIN_EXE_codex-smart"))
        .args(["config", "migrate", "--file"])
        .arg(&file)
        .arg("--apply")
        .env_clear()
        .env("HOME", f.0.join("home"))
        .current_dir(f.0.join("repo"))
        .output()
        .unwrap();
    assert!(output.status.success(), "{:?}", output);
    for path in [
        &file,
        &file.with_file_name("smart.toml.codex-smart-backup"),
        &file.with_file_name("smart.toml.codex-smart-applied"),
        &f.0.join("home/.codex-smart-migration.lock"),
    ] {
        assert_eq!(
            fs::metadata(path).unwrap().permissions().mode() & 0o777,
            0o600
        );
    }
}

#[test]
fn golden_doctor_reports_missing_capabilities_without_probing() {
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    let output = f.command().arg("doctor").output().unwrap();
    assert!(output.status.success());
    assert_eq!(
        String::from_utf8(output.stdout).unwrap(),
        include_str!("../../../fixtures/doctor-empty-path.txt")
    );
}
#[test]
fn doctor_reports_invalid_config_and_returns_degraded_exit_code() {
    let f = Fixture::new();
    f.write("repo/.codex-smart.toml", "private='FAKE_SECRET\n");
    let before = tree(&f.0);
    let output = f.command().arg("doctor").output().unwrap();
    assert_eq!(output.status.code(), Some(1));
    let text = String::from_utf8(output.stdout).unwrap();
    assert!(text.contains("Configuration: E_CONFIG_TOML"));
    assert!(!text.contains("FAKE_SECRET"));
    assert!(output.stderr.is_empty());
    assert_eq!(tree(&f.0), before);
}

#[test]
fn marked_file_in_codex_home_is_never_migrated() {
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    for name in [
        "home/.codex/config.toml",
        "repo/.codex/config.toml",
        "custom/config.toml",
    ] {
        f.write(
            name,
            "kind='codex-smart'\nschema_version=0\n[mcp_servers.user]\ncommand='user'\n",
        );
        let file = f.0.join(name);
        fs::set_permissions(&file, fs::Permissions::from_mode(0o600)).unwrap();
        let before = tree(&f.0);
        let output = f
            .command()
            .env("CODEX_HOME", f.0.join("custom"))
            .args(["config", "migrate", "--file"])
            .arg(&file)
            .arg("--apply")
            .output()
            .unwrap();
        assert_eq!(output.status.code(), Some(2));
        assert_eq!(tree(&f.0), before);
    }
}

#[test]
fn rollback_refuses_orphan_staging_without_backup() {
    use codex_smart_core::{config::ConfigError, migration::MigrationPlan};
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.write("home/smart.toml", "kind='codex-smart'\nschema_version=0\n");
    let file = f.0.join("home/smart.toml");
    fs::set_permissions(&file, fs::Permissions::from_mode(0o600)).unwrap();
    let stage = file.with_file_name("smart.toml.codex-smart-stage");
    fs::write(&stage, "unrecognized interrupted state").unwrap();
    fs::set_permissions(&stage, fs::Permissions::from_mode(0o600)).unwrap();
    let before = tree(&f.0);
    assert!(matches!(
        MigrationPlan::rollback(&file),
        Err(ConfigError::RecoveryRequired)
    ));
    assert_eq!(tree(&f.0), before);
}

#[test]
fn tool_lock_verification_is_read_only_and_does_not_claim_runtime_version() {
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.tool("codex");
    f.write(
        "repo/tools.toml",
        include_str!("../../../fixtures/tools-codex.toml"),
    );
    let file = f.0.join("repo/tools.toml");
    let before = tree(&f.0);
    let output = f
        .command()
        .arg("doctor")
        .arg("--tool-lock")
        .arg(&file)
        .output()
        .unwrap();
    assert!(output.status.success(), "{:?}", output);
    let text = String::from_utf8(output.stdout).unwrap();
    assert!(text.contains("codex: declared version 0.160.0; SHA-256 matches"));
    assert!(text.contains("Runtime version/auth/MCP readiness: unverified"));
    assert!(text.contains("runtime version: unknown; compatibility: unknown:"));
    assert!(text.contains("ready: unknown:"));
    assert_eq!(tree(&f.0), before);
}
#[test]
fn pin_mismatch_prevents_launch_and_unknown_contract_remains_explicit() {
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.tool("codex");
    f.write("repo/tools.toml", &format!("kind='codex-smart-tools'\nschema_version=1\n[tools.codex]\nversion='9.0.0'\nsha256='{}'\n", "0".repeat(64)));
    let file = f.0.join("repo/tools.toml");
    let before = tree(&f.0);
    let output = f
        .command()
        .args(["run", "--tool-lock"])
        .arg(&file)
        .args(["--", "exec", "FAKE_SECRET"])
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&output.stderr).contains("E_CODEX_PIN"));
    assert!(!String::from_utf8_lossy(&output.stderr).contains("FAKE_SECRET"));
    assert_eq!(tree(&f.0), before);
    let output = f
        .command()
        .args(["explain", "--tool-lock"])
        .arg(&file)
        .output()
        .unwrap();
    assert!(output.status.success(), "{:?}", output);
    let text = String::from_utf8(output.stdout).unwrap();
    assert!(text.contains("contract: unknown"));
    assert!(text.contains("SHA-256: deferred"));
    assert_eq!(tree(&f.0), before);
}
#[test]
fn matching_codex_pin_preserves_passthrough_exit_and_dry_run() {
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.tool("codex");
    f.write("bin/codex", "#!/bin/sh\nexit 37\n");
    f.write("repo/tools.toml", "kind='codex-smart-tools'\nschema_version=1\n[tools.codex]\nversion='0.160.0'\nsha256='707a93d29a0084fcd4b3a053bbc1caa8cac8d2e03de02907fa20d2878a932074'\n");
    let file = f.0.join("repo/tools.toml");
    let before = tree(&f.0);
    let output = f
        .command()
        .args(["run", "--tool-lock"])
        .arg(&file)
        .args(["--dry-run", "--", "exec"])
        .output()
        .unwrap();
    assert!(output.status.success(), "{:?}", output);
    assert_eq!(tree(&f.0), before);
    let output = f
        .command()
        .args(["run", "--tool-lock"])
        .arg(&file)
        .args(["--", "exec"])
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(37));
}

#[test]
fn fingerprint_rejects_unsafe_artifacts_and_enforces_exact_read_budget() {
    use codex_smart_core::tool_lock::{Checksum, LockError, MAX_VERIFY_BYTES, fingerprint};
    use std::os::unix::fs::symlink;
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.tool("codex");
    let file = f.0.join("bin/codex");
    let before = tree(&f.0);
    let (digest, size) = fingerprint(&file, MAX_VERIFY_BYTES).unwrap();
    assert_eq!(
        digest,
        Checksum::parse("ff6f57a4d9e2f1c8a885cfdd6cdd5dac1b1c6ce0a3029ef9891bff686951276c")
            .unwrap()
    );
    assert_eq!(fingerprint(&file, size).unwrap(), (digest, size));
    assert_eq!(fingerprint(&file, size - 1), Err(LockError::TooLarge));
    assert_eq!(
        fingerprint(Path::new("relative"), size),
        Err(LockError::UnsafeArtifact)
    );
    assert_eq!(
        fingerprint(&f.0.join("bin"), size),
        Err(LockError::UnsafeArtifact)
    );
    assert_eq!(tree(&f.0), before);
    let link = f.0.join("link");
    symlink(&file, &link).unwrap();
    assert_eq!(fingerprint(&link, size), Err(LockError::UnsafeArtifact));
    for mode in [0o600, 0o777] {
        fs::set_permissions(&file, fs::Permissions::from_mode(mode)).unwrap();
        assert_eq!(fingerprint(&file, size), Err(LockError::UnsafeArtifact));
    }
    fs::set_permissions(&file, fs::Permissions::from_mode(0o700)).unwrap();
    fs::OpenOptions::new()
        .write(true)
        .open(&file)
        .unwrap()
        .set_len(MAX_VERIFY_BYTES + 1)
        .unwrap();
    let before = fs::metadata(&file).unwrap();
    assert_eq!(fingerprint(&file, u64::MAX), Err(LockError::TooLarge));
    let after = fs::metadata(&file).unwrap();
    assert_eq!(before.len(), after.len());
    assert_eq!(before.modified().unwrap(), after.modified().unwrap());
}

#[test]
fn tool_lock_parser_and_file_errors_are_read_only_and_private() {
    use std::os::unix::fs::symlink;
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.tool("codex");
    let valid = include_str!("../../../fixtures/tools-codex.toml");
    for source in [
        valid.replace("schema_version = 1", "schema_version = 99"),
        valid.replace("[tools.codex]", "[tools.code-graph-smart]"),
        valid.replace("version = \"0.160.0\"", "version = \"PRIVATE_VALUE\""),
        valid.replace(
            "schema_version = 1",
            "schema_version = 1\ncommand = 'PRIVATE_VALUE'",
        ),
        "x".repeat(65_537),
    ] {
        f.write("repo/tools.toml", &source);
        let before = tree(&f.0);
        let output = f
            .command()
            .args(["doctor", "--tool-lock", "tools.toml"])
            .output()
            .unwrap();
        assert_eq!(output.status.code(), Some(2));
        assert!(!String::from_utf8_lossy(&output.stderr).contains("PRIVATE_VALUE"));
        assert!(output.stdout.is_empty());
        assert_eq!(tree(&f.0), before);
    }
    f.write("repo/tools.toml", valid);
    symlink(f.0.join("repo/tools.toml"), f.0.join("repo/link.toml")).unwrap();
    for args in [
        vec!["doctor", "--tool-lock", "link.toml"],
        vec!["doctor", "--tool-lock", "missing.toml"],
        vec!["doctor", "--tool-lock"],
        vec!["run", "--dry-run", "--dry-run"],
        vec![
            "doctor",
            "--tool-lock",
            "tools.toml",
            "--tool-lock",
            "tools.toml",
        ],
        vec![
            "run",
            "--tool-lock",
            "tools.toml",
            "--tool-lock",
            "tools.toml",
        ],
    ] {
        let before = tree(&f.0);
        let output = f.command().args(args).output().unwrap();
        assert_eq!(output.status.code(), Some(2));
        assert_eq!(tree(&f.0), before);
    }
}

#[test]
fn doctor_pin_failures_degrade_and_unsafe_wrappers_never_execute() {
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.tool("code-graph-smart");
    f.tool("npx");
    f.write(
        "repo/tools.toml",
        include_str!("../../../fixtures/tools-codex.toml"),
    );
    let before = tree(&f.0);
    let output = f
        .command()
        .args(["doctor", "--tool-lock", "tools.toml"])
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(1));
    let text = String::from_utf8(output.stdout).unwrap();
    assert!(text.contains("executable missing"));
    assert!(text.contains("ready: no: executable unavailable"));
    assert!(text.contains("execution unsupported (wrapper may install dependencies)"));
    assert_eq!(tree(&f.0), before);
    f.tool("codex");
    f.write("bin/codex", "#!/bin/sh\nexit 37\n");
    let before = tree(&f.0);
    let output = f
        .command()
        .args(["doctor", "--tool-lock", "tools.toml"])
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(1));
    assert!(String::from_utf8_lossy(&output.stdout).contains("SHA-256 mismatch"));
    assert_eq!(tree(&f.0), before);
    for name in ["explain", "capabilities"] {
        let output = f
            .command()
            .args([name, "--tool-lock", "tools.toml"])
            .output()
            .unwrap();
        assert!(output.status.success());
        assert!(String::from_utf8_lossy(&output.stdout).contains("SHA-256: deferred"));
        assert_eq!(tree(&f.0), before);
    }
}

#[test]
fn pinned_plan_rejects_replacement_before_execution() {
    use codex_smart_core::{
        capability::Capability,
        process::{LaunchError, LaunchPlan},
        tool_lock::ToolLock,
    };
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.tool("codex");
    let path = f.0.join("bin");
    let lock = ToolLock::parse(include_str!("../../../fixtures/tools-codex.toml")).unwrap();
    let plan = LaunchPlan::prepare(Some(path.as_os_str()), &f.0.join("repo"), vec![])
        .unwrap()
        .require_pin(lock.pin(Capability::Codex).unwrap())
        .unwrap();
    fs::write(path.join("codex"), "#!/bin/sh\nexit 37\n").unwrap();
    assert_eq!(plan.execute(), Err(LaunchError::ChangedExecutable));
    assert!(!f.0.join("home/side-effect").exists());
}

#[test]
fn pinned_launch_preserves_argument_bytes_and_wrapper_option_boundary() {
    use std::os::unix::ffi::OsStringExt;
    let f = Fixture::new();
    f.write("repo/README", "fixture");
    f.tool("codex");
    f.write(
        "bin/codex",
        "#!/bin/sh\nprintf \"%s\\0\" \"$@\" > \"$HOME/argv\"\nexit 37\n",
    );
    fs::create_dir_all(f.0.join("home")).unwrap();
    f.write("repo/tools.toml", "kind='codex-smart-tools'\nschema_version=1\n[tools.codex]\nversion='9.0.0'\nsha256='4f5ef69c8043b22a9a6e28ac44df31d3687cb0fabf771782bba376d49e8d68c5'\n");
    let non_utf8 = std::ffi::OsString::from_vec(vec![b'x', 0xff]);
    let dangerous = "$(touch injected); `touch injected`";
    let output = f
        .command()
        .args([
            "run",
            "--tool-lock",
            "tools.toml",
            "--",
            "exec",
            "--tool-lock",
            "not-a-lock",
        ])
        .arg(&non_utf8)
        .arg(dangerous)
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(37));
    let expected = [
        b"exec\0--tool-lock\0not-a-lock\0".as_slice(),
        &[b'x', 0xff, 0],
        dangerous.as_bytes(),
        &[0],
    ]
    .concat();
    assert_eq!(fs::read(f.0.join("home/argv")).unwrap(), expected);
    assert!(!f.0.join("repo/injected").exists());
    let before = tree(&f.0);
    let output = f
        .command()
        .args([
            "run",
            "--dry-run",
            "--tool-lock",
            "tools.toml",
            "--",
            "exec",
        ])
        .output()
        .unwrap();
    assert!(output.status.success());
    assert!(
        String::from_utf8_lossy(&output.stdout)
            .contains("required SHA-256 matched; runtime version/readiness unverified")
    );
    assert_eq!(tree(&f.0), before);
}
