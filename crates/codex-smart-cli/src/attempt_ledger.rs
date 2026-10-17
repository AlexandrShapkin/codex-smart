//! Private per-invocation crash receipts. No paths or provider payloads enter records.
use rustix::{
    fs::{Mode, OFlags, fstat, open, openat},
    process::geteuid,
};
use std::{
    fs::File,
    io::{Read, Write},
    path::{Component, Path},
};

const ERROR: &str = "E_INSPECT_LEDGER: private durable receipt unavailable";
const START: &[u8] = b"{\"schema\":1,\"type\":\"started\"}\n";
pub(crate) const LIMIT: usize = 2048;

pub struct Receipt {
    file: File,
    // Keep the validated inode, even if its pathname is renamed concurrently.
    _directory: File,
    terminal: bool,
}
impl Receipt {
    pub fn start(path: &Path) -> Result<Self, &'static str> {
        Self::create(path).map_err(|_| ERROR)
    }
    fn create(path: &Path) -> std::io::Result<Self> {
        let invalid = || std::io::Error::other("receipt refused");
        if path.as_os_str().is_empty() || path.components().count() > 256 {
            return Err(invalid());
        }
        let flags = OFlags::RDONLY | OFlags::DIRECTORY | OFlags::NOFOLLOW | OFlags::CLOEXEC;
        let mut directory = open(
            if path.is_absolute() { "/" } else { "." },
            flags,
            Mode::empty(),
        )?;
        for component in path.components() {
            match component {
                Component::Normal(name) => {
                    directory = openat(&directory, name, flags, Mode::empty())?
                }
                Component::RootDir | Component::CurDir => {}
                _ => return Err(invalid()),
            }
        }
        let stat = fstat(&directory)?;
        if stat.st_uid != geteuid().as_raw() || stat.st_mode & 0o7777 != 0o700 {
            return Err(invalid());
        }
        let mut random = [0u8; 16];
        File::open("/dev/urandom")?.read_exact(&mut random)?;
        let name = random
            .iter()
            .map(|v| format!("{v:02x}"))
            .collect::<String>()
            + ".jsonl";
        let fd = openat(
            &directory,
            name.as_str(),
            OFlags::WRONLY
                | OFlags::APPEND
                | OFlags::CREATE
                | OFlags::EXCL
                | OFlags::NOFOLLOW
                | OFlags::CLOEXEC,
            Mode::from_raw_mode(0o600),
        )?;
        let stat = fstat(&fd)?;
        if stat.st_uid != geteuid().as_raw() || stat.st_mode & 0o7777 != 0o600 || stat.st_nlink != 1
        {
            return Err(invalid());
        }
        let mut file = File::from(fd);
        let directory = File::from(directory);
        file.write_all(START)?;
        file.sync_all()?;
        directory.sync_all()?;
        Ok(Self {
            file,
            _directory: directory,
            terminal: false,
        })
    }
    pub fn finish(
        &mut self,
        report: &serde_json::Value,
        elapsed_ms: u64,
    ) -> Result<(), &'static str> {
        if self.terminal {
            return Err(ERROR);
        }
        // Set before writing: a partial write must never be retried as another terminal.
        self.terminal = true;
        let value = serde_json::json!({"schema":1,"type":"terminal","elapsed_ms":elapsed_ms,"report":report});
        let mut bytes = serde_json::to_vec(&value).map_err(|_| ERROR)?;
        bytes.push(b'\n');
        let mut evidence = START.to_vec();
        evidence.extend_from_slice(&bytes);
        if interpret(&evidence) != Recovery::Terminal {
            return Err(ERROR);
        }
        self.file
            .write_all(&bytes)
            .and_then(|_| self.file.sync_all())
            .map_err(|_| ERROR)
    }
}

#[derive(Debug, PartialEq, Eq)]
enum Recovery {
    Unfinished,
    Corrupt,
    Terminal,
}

#[derive(Debug)]
pub(crate) struct TerminalSummary {
    pub status: usize,
    pub elapsed_ms: u64,
    pub usage: [Option<u64>; 5],
}
pub(crate) const USAGE_KEYS: [&str; 5] = [
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "cache_write_input_tokens",
    "reasoning_output_tokens",
];
pub(crate) enum Summary {
    Unfinished,
    Corrupt,
    Terminal(TerminalSummary),
}
pub(crate) fn summarize(bytes: &[u8]) -> Summary {
    match parse(bytes) {
        Ok(Some(summary)) => Summary::Terminal(summary),
        Ok(None) => Summary::Unfinished,
        Err(()) => Summary::Corrupt,
    }
}
fn interpret(bytes: &[u8]) -> Recovery {
    match summarize(bytes) {
        Summary::Unfinished => Recovery::Unfinished,
        Summary::Corrupt => Recovery::Corrupt,
        Summary::Terminal(_) => Recovery::Terminal,
    }
}

// Internal interpretation only; never discovers paths, scans, launches or replays.
fn parse(bytes: &[u8]) -> Result<Option<TerminalSummary>, ()> {
    if bytes.len() > LIMIT || !bytes.starts_with(START) {
        return Err(());
    }
    let tail = &bytes[START.len()..];
    if tail.is_empty() {
        return Ok(None);
    }
    if !tail.ends_with(b"\n") {
        return Err(());
    }
    let Ok(value) = serde_json::from_slice::<serde_json::Value>(&tail[..tail.len() - 1]) else {
        return Err(());
    };
    // Canonical encoding also rejects duplicate keys, whitespace and extra records.
    if serde_json::to_vec(&value).ok().as_deref() != Some(&tail[..tail.len() - 1]) {
        return Err(());
    }
    let Some(object) = value.as_object() else {
        return Err(());
    };
    if object.len() != 4
        || value["schema"] != 1
        || value["type"] != "terminal"
        || value["elapsed_ms"].as_u64().is_none()
    {
        return Err(());
    }
    let report = &value["report"];
    if report.as_object().map(|v| v.len()) != Some(3)
        || !matches!(
            report["status"].as_str(),
            Some("CompletedSuccess" | "CompletedFailure" | "Timeout" | "Interrupted" | "Unknown")
        )
        || !matches!(
            report["answer_file"].as_str(),
            Some("NotRequested" | "Written" | "Unavailable" | "WriteFailed")
        )
    {
        return Err(());
    }
    let Some(usage) = report["usage"].as_object() else {
        return Err(());
    };
    if usage.len() != 5
        || USAGE_KEYS.iter().any(|key| {
            !usage
                .get(*key)
                .is_some_and(|v| v.is_null() || v.as_u64().is_some())
        })
    {
        return Err(());
    }
    Ok(Some(TerminalSummary {
        status: match report["status"].as_str().unwrap() {
            "CompletedSuccess" => 0,
            "CompletedFailure" => 1,
            "Timeout" => 2,
            "Interrupted" => 3,
            _ => 4,
        },
        elapsed_ms: value["elapsed_ms"].as_u64().unwrap(),
        usage: USAGE_KEYS.map(|key| usage[key].as_u64()),
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn report() -> serde_json::Value {
        serde_json::json!({"status":"CompletedSuccess","answer_file":"NotRequested","usage":{"input_tokens":null,"cached_input_tokens":null,"output_tokens":null,"cache_write_input_tokens":null,"reasoning_output_tokens":null}})
    }
    #[test]
    fn durable_start_survives_drop_and_directory_rename() {
        use std::os::unix::fs::PermissionsExt;
        let dir = std::env::temp_dir().join(format!("receipt-unit-{}", std::process::id()));
        std::fs::create_dir(&dir).unwrap();
        std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o700)).unwrap();
        let mut receipt = Receipt::start(&dir).unwrap();
        let name = std::fs::read_dir(&dir)
            .unwrap()
            .next()
            .unwrap()
            .unwrap()
            .file_name();
        let bytes = std::fs::read(dir.join(&name)).unwrap();
        assert_eq!(interpret(&bytes), Recovery::Unfinished);
        let moved = dir.with_extension("moved");
        std::fs::rename(&dir, &moved).unwrap();
        // A replaced pathname cannot redirect writes away from the held inode.
        std::fs::create_dir(&dir).unwrap();
        receipt.finish(&report(), u64::MAX).unwrap();
        assert!(receipt.finish(&report(), 0).is_err());
        drop(receipt);
        assert_eq!(
            interpret(&std::fs::read(moved.join(name)).unwrap()),
            Recovery::Terminal
        );
        assert_eq!(std::fs::read_dir(&dir).unwrap().count(), 0);
        std::fs::remove_dir(&dir).unwrap();
        std::fs::remove_dir_all(&moved).unwrap();
    }
    #[test]
    fn terminal_parser_rejects_duplicates_and_invalid_fields() {
        let value =
            serde_json::json!({"schema":1,"type":"terminal","elapsed_ms":1,"report":report()});
        let mut bytes = START.to_vec();
        bytes.extend(serde_json::to_vec(&value).unwrap());
        bytes.push(b'\n');
        assert_eq!(interpret(&bytes), Recovery::Terminal);
        let valid = bytes.clone();
        bytes.extend_from_slice(&valid[START.len()..]);
        assert_eq!(interpret(&bytes), Recovery::Corrupt);
        for replacement in ["\"schema\":2", "\"schema\":1,\"schema\":1"] {
            let text =
                String::from_utf8(valid.clone())
                    .unwrap()
                    .replacen("\"schema\":1", replacement, 2);
            assert_eq!(interpret(text.as_bytes()), Recovery::Corrupt);
        }
        for key in ["status", "usage", "answer_file"] {
            let mut value = value.clone();
            value["report"].as_object_mut().unwrap().remove(key);
            let mut bytes = START.to_vec();
            bytes.extend(serde_json::to_vec(&value).unwrap());
            bytes.push(b'\n');
            assert_eq!(interpret(&bytes), Recovery::Corrupt);
        }
    }
    #[test]
    fn terminal_io_failure_never_retries() {
        let mut receipt = Receipt {
            file: std::fs::OpenOptions::new()
                .write(true)
                .open("/dev/full")
                .unwrap(),
            _directory: File::open("/").unwrap(),
            terminal: false,
        };
        assert!(receipt.finish(&report(), 1).is_err());
        assert!(receipt.terminal);
        assert!(receipt.finish(&report(), 1).is_err());
    }
    #[test]
    fn crash_and_corrupt_evidence_never_complete() {
        assert_eq!(interpret(START), Recovery::Unfinished);
        for bytes in [
            b"".as_slice(),
            b"{}\n",
            b"{\"schema\":2,\"type\":\"started\"}\n",
        ] {
            assert_eq!(interpret(bytes), Recovery::Corrupt);
        }
        let mut bytes = START.to_vec();
        bytes.extend_from_slice(b"{\"schema\":1");
        assert_eq!(interpret(&bytes), Recovery::Corrupt);
        assert_eq!(interpret(&vec![b'x'; LIMIT + 1]), Recovery::Corrupt);
    }
}
