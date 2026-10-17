//! Offline bounded observation of private receipts; never launches tools.
use std::ffi::OsString;
pub const HELP: &str = "Usage: codex-smart inspect-ledger --dir PRIVATE_DIRECTORY
Linux only; exactly one --dir is required. No tools or configuration are loaded.
Read-only bounded observation, NOT an atomic snapshot; consistency is unverified.
Limits: 256 path components, 1024 receipts, 2048 bytes each, 2097152 total bytes;
5 second cooperative deadline (blocking filesystem calls are not time bounded).
Only 32 lowercase hex digits followed by .jsonl are accepted. Directory mode 0700;
regular owned single-link files mode 0600; symlinks and unsafe entries refused.
Success prints one schema-1 JSON line: schema, snapshot_consistency
(unverified_non_atomic), observed_attempts, outcomes (successful, failure, timeout,
interrupted, unknown_terminal, unfinished, corrupt), usage (input_tokens,
cached_input_tokens, output_tokens, cache_write_input_tokens, reasoning_output_tokens),
elapsed_ms. Each counter has observed_sum (checked u64), missing_count (over ALL
observed attempts), incomplete_sum (missing_count != 0). No lifecycle/quality claims.
Any unsafe object, drift, I/O error, overflow or exceeded limit: exit 2, fixed error,
no JSON. Malformed bounded receipts count as corrupt. No repairs or receipt writes.";
#[cfg(target_os = "linux")]
const ERROR: &str = "E_INSPECT_LEDGER_READ: bounded private observation unavailable";
pub fn execute(args: &[OsString]) -> Result<i32, &'static str> {
    if args == [OsString::from("--help")] {
        println!("{HELP}");
        return Ok(0);
    }
    if args.len() != 2 || args[0] != "--dir" || args[1].is_empty() {
        return Err("E_INSPECT_LEDGER_ARGS: expected --dir PRIVATE_DIRECTORY");
    }
    #[cfg(target_os = "linux")]
    {
        let value = linux::scan(std::path::Path::new(&args[1])).map_err(|_| ERROR)?;
        use std::io::Write;
        writeln!(std::io::stdout().lock(), "{value}").map_err(|_| ERROR)?;
        Ok(0)
    }
    #[cfg(not(target_os = "linux"))]
    Err("E_INSPECT_LEDGER_PLATFORM: Linux required")
}
#[cfg(target_os = "linux")]
mod linux {
    use crate::attempt_ledger::{LIMIT, Summary, USAGE_KEYS, summarize};
    use rustix::{
        fs::{self, FileType, Mode, OFlags},
        process::geteuid,
    };
    use std::{
        fs::File,
        io::Read,
        path::{Component, Path},
        time::{Duration, Instant},
    };
    type Result<T> = std::result::Result<T, ()>;
    fn open_dir(path: &Path) -> Result<rustix::fd::OwnedFd> {
        if path.as_os_str().is_empty() || path.components().count() > 256 {
            return Err(());
        }
        let flags = OFlags::RDONLY | OFlags::DIRECTORY | OFlags::NOFOLLOW | OFlags::CLOEXEC;
        let mut fd = fs::open(
            if path.is_absolute() { "/" } else { "." },
            flags,
            Mode::empty(),
        )
        .map_err(|_| ())?;
        for part in path.components() {
            match part {
                Component::Normal(name) => {
                    fd = fs::openat(&fd, name, flags, Mode::empty()).map_err(|_| ())?
                }
                Component::RootDir | Component::CurDir => {}
                _ => return Err(()),
            }
        }
        let stat = fs::fstat(&fd).map_err(|_| ())?;
        if stat.st_uid != geteuid().as_raw() || stat.st_mode & 0o7777 != 0o700 {
            return Err(());
        }
        Ok(fd)
    }
    pub(super) fn identity(s: &fs::Stat) -> impl PartialEq + use<> {
        (
            s.st_dev,
            s.st_ino,
            s.st_mode,
            s.st_uid,
            s.st_gid,
            s.st_nlink,
            s.st_size,
            s.st_mtime,
            s.st_mtime_nsec,
            s.st_ctime,
            s.st_ctime_nsec,
        )
    }
    fn deadline(start: Instant) -> Result<()> {
        if start.elapsed() > Duration::from_secs(5) {
            Err(())
        } else {
            Ok(())
        }
    }
    pub fn scan(path: &Path) -> Result<serde_json::Value> {
        let start = Instant::now();
        let dir = open_dir(path)?;
        let before = fs::fstat(&dir).map_err(|_| ())?;
        let mut entries = fs::Dir::read_from(&dir).map_err(|_| ())?;
        let mut count = 0u64;
        let mut total = 0usize;
        let mut outcomes = [0u64; 7];
        let mut sums = [0u64; 6];
        let mut present = [0u64; 6];
        // Retain descriptors and metadata until final verification, bounded to 1024.
        let mut observed = Vec::new();
        for entry in &mut entries {
            deadline(start)?;
            let entry = entry.map_err(|_| ())?;
            let name = entry.file_name();
            let bytes = name.to_bytes();
            if bytes == b"." || bytes == b".." {
                continue;
            }
            if bytes.len() != 38
                || &bytes[32..] != b".jsonl"
                || !bytes[..32]
                    .iter()
                    .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(b))
            {
                return Err(());
            }
            count += 1;
            if count > 1024 {
                return Err(());
            }
            let fd = fs::openat(
                &dir,
                name,
                OFlags::RDONLY | OFlags::NOFOLLOW | OFlags::CLOEXEC | OFlags::NONBLOCK,
                Mode::empty(),
            )
            .map_err(|_| ())?;
            let stat = fs::fstat(&fd).map_err(|_| ())?;
            if FileType::from_raw_mode(stat.st_mode) != FileType::RegularFile
                || stat.st_uid != geteuid().as_raw()
                || stat.st_mode & 0o7777 != 0o600
                || stat.st_nlink != 1
                || stat.st_size < 0
                || stat.st_size > LIMIT as i64
            {
                return Err(());
            }
            total = total.checked_add(stat.st_size as usize).ok_or(())?;
            if total > 2_097_152 {
                return Err(());
            }
            if observed.iter().any(|(_, prior): &(File, fs::Stat)| {
                prior.st_dev == stat.st_dev && prior.st_ino == stat.st_ino
            }) {
                return Err(());
            }
            let mut file = File::from(fd);
            let mut data = Vec::with_capacity(LIMIT + 1);
            (&mut file)
                .take((LIMIT + 1) as u64)
                .read_to_end(&mut data)
                .map_err(|_| ())?;
            if data.len() != stat.st_size as usize
                || identity(&stat) != identity(&fs::fstat(&file).map_err(|_| ())?)
            {
                return Err(());
            }
            match summarize(&data) {
                Summary::Corrupt => outcomes[6] += 1,
                Summary::Unfinished => outcomes[5] += 1,
                Summary::Terminal(summary) => {
                    outcomes[summary.status] += 1;
                    for (i, value) in summary
                        .usage
                        .into_iter()
                        .chain([Some(summary.elapsed_ms)])
                        .enumerate()
                    {
                        if let Some(value) = value {
                            sums[i] = sums[i].checked_add(value).ok_or(())?;
                            present[i] += 1;
                        }
                    }
                }
            }
            observed.push((file, stat));
        }
        for (file, stat) in observed {
            deadline(start)?;
            if identity(&stat) != identity(&fs::fstat(&file).map_err(|_| ())?) {
                return Err(());
            }
        }
        // Re-resolve the supplied path to detect directory/path substitution.
        let current = open_dir(path)?;
        if identity(&before) != identity(&fs::fstat(&dir).map_err(|_| ())?)
            || identity(&before) != identity(&fs::fstat(&current).map_err(|_| ())?)
        {
            return Err(());
        }
        deadline(start)?;
        let counter = |i: usize| serde_json::json!({"observed_sum":sums[i], "missing_count":count-present[i], "incomplete_sum":present[i]!=count});
        let usage: serde_json::Map<String, serde_json::Value> = USAGE_KEYS
            .iter()
            .enumerate()
            .map(|(i, key)| ((*key).to_owned(), counter(i)))
            .collect();
        let outcomes: serde_json::Map<String, serde_json::Value> = [
            "successful",
            "failure",
            "timeout",
            "interrupted",
            "unknown_terminal",
            "unfinished",
            "corrupt",
        ]
        .iter()
        .enumerate()
        .map(|(i, key)| ((*key).to_owned(), outcomes[i].into()))
        .collect();
        Ok(
            serde_json::json!({"schema":1,"snapshot_consistency":"unverified_non_atomic","observed_attempts":count,"outcomes":outcomes,"usage":usage,"elapsed_ms":counter(5)}),
        )
    }
}

#[cfg(all(test, target_os = "linux"))]
mod tests {
    use super::linux::identity;
    use std::io::Write;
    #[test]
    fn metadata_detects_appended_bytes_on_held_inode() {
        let path = std::env::temp_dir().join(format!("ledger-drift-unit-{}", std::process::id()));
        let mut file = std::fs::OpenOptions::new()
            .read(true)
            .write(true)
            .create_new(true)
            .open(&path)
            .unwrap();
        let before = rustix::fs::fstat(&file).unwrap();
        file.write_all(b"stale appended bytes").unwrap();
        assert!(identity(&before) != identity(&rustix::fs::fstat(&file).unwrap()));
        std::fs::remove_file(path).unwrap();
    }
}
