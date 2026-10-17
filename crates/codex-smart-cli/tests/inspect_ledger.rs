#![cfg(target_os = "linux")]
use serde_json::{Value, json};
use std::{
    fs,
    os::unix::fs::{PermissionsExt, symlink},
    path::PathBuf,
    process::{Command, Output},
    sync::atomic::{AtomicUsize, Ordering},
};
static NEXT: AtomicUsize = AtomicUsize::new(0);
const START: &[u8] = b"{\"schema\":1,\"type\":\"started\"}\n";
const KEYS: [&str; 5] = [
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "cache_write_input_tokens",
    "reasoning_output_tokens",
];
struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!(
            "ledger-reader-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        fs::set_permissions(&path, fs::Permissions::from_mode(0o700)).unwrap();
        Self(path)
    }
    fn file(&self, n: usize, bytes: &[u8]) -> PathBuf {
        let path = self.0.join(format!("{n:032x}.jsonl"));
        fs::write(&path, bytes).unwrap();
        fs::set_permissions(&path, fs::Permissions::from_mode(0o600)).unwrap();
        path
    }
    fn command(&self) -> Command {
        let mut cmd = Command::new(env!("CARGO_BIN_EXE_codex-smart"));
        cmd.env_clear()
            .env("PATH", "/nonexistent")
            .env("HOME", "/nonexistent")
            .current_dir(&self.0)
            .arg("inspect-ledger");
        cmd
    }
    fn scan(&self) -> Output {
        self.command().arg("--dir").arg(&self.0).output().unwrap()
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
fn terminal(status: &str, usage: [Option<u64>; 5], elapsed: u64) -> Vec<u8> {
    let usage: serde_json::Map<String, Value> = KEYS
        .iter()
        .zip(usage)
        .map(|(k, v)| (k.to_string(), json!(v)))
        .collect();
    let mut bytes = START.to_vec();
    bytes.extend(serde_json::to_vec(&json!({"schema":1,"type":"terminal","elapsed_ms":elapsed,"report":{"status":status,"answer_file":"NotRequested","usage":usage}})).unwrap());
    bytes.push(b'\n');
    bytes
}
fn refused(out: Output) {
    assert_eq!(out.status.code(), Some(2));
    assert!(out.stdout.is_empty());
    assert_eq!(
        out.stderr,
        b"E_INSPECT_LEDGER_READ: bounded private observation unavailable\n"
    );
}
#[test]
fn outcome_mix_missing_denominator_and_no_content_changes() {
    let f = Fixture::new();
    let mut originals = Vec::new();
    for (i, status) in [
        "CompletedSuccess",
        "CompletedFailure",
        "Timeout",
        "Interrupted",
        "Unknown",
    ]
    .iter()
    .enumerate()
    {
        let usage = std::array::from_fn(|j| if j <= i { Some((j + 1) as u64) } else { None });
        let bytes = terminal(status, usage, 10);
        let path = f.file(i, &bytes);
        originals.push((path, bytes));
    }
    f.file(5, START);
    f.file(6, b"");
    let out = f.scan();
    assert!(out.status.success(), "{:?}", out.stderr);
    assert!(out.stderr.is_empty());
    assert_eq!(out.stdout.iter().filter(|b| **b == b'\n').count(), 1);
    let v: Value = serde_json::from_slice(&out.stdout).unwrap();
    assert_eq!(v["observed_attempts"], 7);
    assert_eq!(v["snapshot_consistency"], "unverified_non_atomic");
    for key in [
        "successful",
        "failure",
        "timeout",
        "interrupted",
        "unknown_terminal",
        "unfinished",
        "corrupt",
    ] {
        assert_eq!(v["outcomes"][key], 1);
    }
    for (i, key) in KEYS.iter().enumerate() {
        assert_eq!(v["usage"][key]["missing_count"], i + 2);
        assert_eq!(v["usage"][key]["observed_sum"], (5 - i) * (i + 1));
        assert_eq!(v["usage"][key]["incomplete_sum"], true);
    }
    assert_eq!(
        v["elapsed_ms"],
        json!({"observed_sum":50,"missing_count":2,"incomplete_sum":true})
    );
    for (path, bytes) in originals {
        assert_eq!(fs::read(path).unwrap(), bytes);
    }
    assert_eq!(fs::read_dir(&f.0).unwrap().count(), 7);
}
#[test]
fn malformed_never_success() {
    let f = Fixture::new();
    let valid = terminal("CompletedSuccess", [Some(1); 5], 1);
    let mut duplicate = valid.clone();
    duplicate.extend(&valid[START.len()..]);
    f.file(0, &duplicate);
    f.file(1, &valid[..valid.len() - 1]);
    f.file(
        2,
        &String::from_utf8(valid.clone())
            .unwrap()
            .replace("\"schema\":1", "\"schema\":2")
            .into_bytes(),
    );
    f.file(
        3,
        &String::from_utf8(valid)
            .unwrap()
            .replace("\"elapsed_ms\":1", "\"elapsed_ms\":1,\"elapsed_ms\":1")
            .into_bytes(),
    );
    let out = f.scan();
    assert!(out.status.success());
    let v: Value = serde_json::from_slice(&out.stdout).unwrap();
    assert_eq!(v["outcomes"]["corrupt"], 4);
    assert_eq!(v["outcomes"]["successful"], 0);
    assert_eq!(v["elapsed_ms"]["missing_count"], 4);
}
#[test]
fn unsafe_files_and_limits_fail_without_partial_output() {
    for case in 0..8 {
        let f = Fixture::new();
        let path = f.file(0, START);
        match case {
            0 => fs::set_permissions(&f.0, fs::Permissions::from_mode(0o755)).unwrap(),
            1 => fs::set_permissions(&path, fs::Permissions::from_mode(0o644)).unwrap(),
            2 => {
                fs::remove_file(&path).unwrap();
                symlink("/dev/zero", &path).unwrap();
            }
            3 => {
                fs::hard_link(&path, f.0.join(format!("{:032x}.jsonl", 1))).unwrap();
            }
            4 => {
                fs::remove_file(&path).unwrap();
                fs::create_dir(&path).unwrap();
            }
            5 => {
                f.file(0, &vec![b'x'; 2049]);
            }
            6 => {
                for n in 1..1025 {
                    f.file(n, START);
                }
            }
            _ => {
                fs::write(f.0.join("unrecognized-private-name"), b"secret").unwrap();
            }
        }
        refused(f.scan());
    }
}
#[test]
fn fifo_is_refused_without_reading_and_symlink_components_refused() {
    let f = Fixture::new();
    let path = f.0.join(format!("{:032x}.jsonl", 0));
    rustix::fs::mknodat(
        rustix::fs::CWD,
        &path,
        rustix::fs::FileType::Fifo,
        rustix::fs::Mode::from_raw_mode(0o600),
        0,
    )
    .unwrap();
    refused(f.scan());
    fs::remove_file(path).unwrap();
    let parent = Fixture::new();
    symlink(&f.0, parent.0.join("link")).unwrap();
    refused(
        f.command()
            .arg("--dir")
            .arg(parent.0.join("link"))
            .output()
            .unwrap(),
    );
    refused(
        f.command()
            .arg("--dir")
            .arg(parent.0.join("link/."))
            .output()
            .unwrap(),
    );
}
#[test]
fn cli_help_empty_and_overflow() {
    let f = Fixture::new();
    for args in [
        vec![],
        vec!["--dir"],
        vec!["--dir", ".", "--dir", "."],
        vec!["--json"],
        vec!["--help", "--dir", "."],
    ] {
        let out = f.command().args(args).output().unwrap();
        assert_eq!(out.status.code(), Some(2));
        assert!(out.stdout.is_empty());
        assert_eq!(
            out.stderr,
            b"E_INSPECT_LEDGER_ARGS: expected --dir PRIVATE_DIRECTORY\n"
        );
    }
    assert!(f.command().arg("--help").output().unwrap().status.success());
    let out = f.scan();
    assert!(out.status.success());
    let v: Value = serde_json::from_slice(&out.stdout).unwrap();
    assert_eq!(v["observed_attempts"], 0);
    assert_eq!(v["usage"][KEYS[0]]["incomplete_sum"], false);
    f.file(
        0,
        &terminal("CompletedSuccess", [Some(u64::MAX); 5], u64::MAX),
    );
    let out = f.scan();
    assert!(out.status.success());
    f.file(1, &terminal("CompletedSuccess", [Some(1); 5], 1));
    refused(f.scan());
}
