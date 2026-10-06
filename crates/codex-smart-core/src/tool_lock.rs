//! Explicit entrypoint pins. Digest equality is not version or MCP attestation.
use crate::{
    capability::{Availability, Capability, Inventory},
    config::MAX_CONFIG_BYTES,
    version::Version,
};
use sha2::{Digest, Sha256};
use std::fmt;
use std::io::Read;
use std::path::Path;
use toml_edit::DocumentMut;

pub const MAX_VERIFY_BYTES: u64 = 256 * 1024 * 1024;
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LockError {
    Invalid,
    Missing,
    UnsafeArtifact,
    TooLarge,
    Changed,
    Io,
    Unsupported,
}
impl LockError {
    pub fn code(self) -> &'static str {
        match self {
            Self::Invalid => {
                "E_TOOL_LOCK: invalid marked schema/version/checksum/tool record (values omitted)"
            }
            Self::Missing => "E_TOOL_LOCK_MISSING: lock file not found",
            Self::UnsafeArtifact => {
                "E_TOOL_ARTIFACT: executable ownership, permissions or file type unsafe"
            }
            Self::TooLarge => "E_TOOL_SIZE: artifact verification byte budget exceeded",
            Self::Changed => "E_TOOL_CHANGED: artifact changed while hashing",
            Self::Io => "E_TOOL_IO: artifact could not be read",
            Self::Unsupported => "E_TOOL_PLATFORM: secure fingerprinting requires Linux openat2",
        }
    }
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Checksum([u8; 32]);
impl Checksum {
    pub fn parse(raw: &str) -> Option<Self> {
        if raw.len() != 64 || !raw.bytes().all(|b| b.is_ascii_hexdigit()) {
            return None;
        }
        let mut digest = [0; 32];
        for (i, byte) in digest.iter_mut().enumerate() {
            *byte = u8::from_str_radix(&raw[2 * i..2 * i + 2], 16).ok()?;
        }
        Some(Self(digest))
    }
}
impl fmt::Display for Checksum {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        for byte in self.0 {
            write!(f, "{byte:02x}")?;
        }
        Ok(())
    }
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Pin {
    pub capability: Capability,
    pub version: Version,
    pub checksum: Checksum,
}
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ToolLock {
    pub pins: Vec<Pin>,
}
impl ToolLock {
    pub fn parse(source: &str) -> Result<Self, LockError> {
        if source.len() > MAX_CONFIG_BYTES {
            return Err(LockError::Invalid);
        }
        let doc = source
            .parse::<DocumentMut>()
            .map_err(|_| LockError::Invalid)?;
        if doc.len() != 3
            || doc.get("kind").and_then(|v| v.as_str()) != Some("codex-smart-tools")
            || doc.get("schema_version").and_then(|v| v.as_integer()) != Some(1)
        {
            return Err(LockError::Invalid);
        }
        let tools = doc
            .get("tools")
            .and_then(|v| v.as_table())
            .ok_or(LockError::Invalid)?;
        // Codex is the only external executable owned by the launcher.
        if tools.len() != 1 {
            return Err(LockError::Invalid);
        }
        let mut pins = Vec::new();
        for (name, record) in tools {
            let capability = tool(name).ok_or(LockError::Invalid)?;
            let record = record.as_table().ok_or(LockError::Invalid)?;
            if record.len() != 2 {
                return Err(LockError::Invalid);
            }
            let version = record
                .get("version")
                .and_then(|v| v.as_str())
                .and_then(Version::parse)
                .ok_or(LockError::Invalid)?;
            let checksum = record
                .get("sha256")
                .and_then(|v| v.as_str())
                .and_then(Checksum::parse)
                .ok_or(LockError::Invalid)?;
            pins.push(Pin {
                capability,
                version,
                checksum,
            });
        }
        Ok(Self { pins })
    }
    pub fn pin(&self, capability: Capability) -> Option<&Pin> {
        self.pins.iter().find(|p| p.capability == capability)
    }
    pub fn report(&self, inventory: &Inventory, verify: bool) -> (String, bool) {
        let mut output = String::from("Tool lock (explicit artifact pins; no tools executed)\n");
        let mut artifact_ok = true;
        let mut remaining = MAX_VERIFY_BYTES;
        // Inventory order, not document order, determines the bounded verification order.
        for capability in Capability::ALL {
            let Some(pin) = self.pin(capability) else {
                continue;
            };
            let path = inventory
                .0
                .iter()
                .find(|e| e.capability == capability)
                .and_then(|e| e.executable.as_deref());
            let mut artifact = ArtifactEvidence::Deferred;
            let status = if !verify {
                "SHA-256: deferred".to_owned()
            } else if let Some(path) = path {
                match fingerprint(path, remaining) {
                    Ok((digest, bytes)) => {
                        remaining -= bytes;
                        if digest == pin.checksum {
                            artifact = ArtifactEvidence::Match;
                            "SHA-256 matches".to_owned()
                        } else {
                            artifact_ok = false;
                            artifact = ArtifactEvidence::Mismatch;
                            "SHA-256 mismatch".to_owned()
                        }
                    }
                    Err(error) => {
                        artifact_ok = false;
                        artifact = ArtifactEvidence::Rejected;
                        // Conservatively exhaust the budget: failures may follow partial reads.
                        remaining = 0;
                        error.code().to_owned()
                    }
                }
            } else {
                artifact_ok = false;
                artifact = ArtifactEvidence::Missing;
                "executable missing; SHA-256 not checked".to_owned()
            };
            let evidence =
                CapabilityEvidence::assess(capability, path.is_some(), Some(pin.version), artifact);
            output.push_str(&format!(
                "{}: declared version {}; {}; contract: {}; available: {:?}; runtime version: unknown; compatibility: {}; ready: {}\n",
                capability.name(),
                pin.version,
                status,
                evidence.execution_contract.name(),
                evidence.available,
                evidence.compatibility.name(),
                evidence.readiness.name(),
            ));
        }
        output.push_str("Runtime version/auth/MCP readiness: unverified; checksum does not authenticate a declaration or bind script/shim dependencies\n");
        (output, artifact_ok)
    }
}
pub fn tool(name: &str) -> Option<Capability> {
    (name == "codex").then_some(Capability::Codex)
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ArtifactEvidence {
    Deferred,
    Match,
    Mismatch,
    Missing,
    Rejected,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Compatibility {
    Unknown,
    ReferenceOnly,
    UnsupportedWrapper,
}
impl Compatibility {
    pub fn name(self) -> &'static str {
        match self {
            Self::Unknown => "unknown: runtime version/contract not validated",
            Self::ReferenceOnly => {
                "unknown: declared reference contract; runtime version not attested"
            }
            Self::UnsupportedWrapper => "incompatible: wrapper execution is unsupported",
        }
    }
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Readiness {
    Unknown,
    Unavailable,
    Blocked,
}
impl Readiness {
    pub fn name(self) -> &'static str {
        match self {
            Self::Unknown => "unknown: runtime/auth/transport not probed",
            Self::Unavailable => "no: executable unavailable",
            Self::Blocked => "no: artifact rejected or execution contract unsupported",
        }
    }
}
/// Available, declared-version, reference compatibility and readiness are independent.
/// This offline slice has no evidence source that can assert runtime readiness.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CapabilityEvidence {
    pub available: Availability,
    pub declared_version: Option<Version>,
    pub runtime_version: Option<Version>,
    pub execution_contract: Contract,
    pub compatibility: Compatibility,
    pub readiness: Readiness,
}
impl CapabilityEvidence {
    pub fn assess(
        capability: Capability,
        discovered: bool,
        declared_version: Option<Version>,
        artifact: ArtifactEvidence,
    ) -> Self {
        let available = if capability == Capability::Context7 {
            Availability::SessionUnknown
        } else if discovered {
            Availability::Discovered
        } else {
            Availability::NotFound
        };
        let execution_contract =
            declared_version.map_or(Contract::Unknown, |v| contract(capability, v));
        let compatibility = if capability == Capability::CodeGraphWrapper {
            Compatibility::UnsupportedWrapper
        } else if execution_contract != Contract::Unknown {
            Compatibility::ReferenceOnly
        } else {
            Compatibility::Unknown
        };
        let readiness = if available == Availability::NotFound {
            Readiness::Unavailable
        } else if compatibility == Compatibility::UnsupportedWrapper
            || matches!(
                artifact,
                ArtifactEvidence::Mismatch | ArtifactEvidence::Missing | ArtifactEvidence::Rejected
            )
        {
            Readiness::Blocked
        } else {
            Readiness::Unknown
        };
        Self {
            available,
            declared_version,
            runtime_version: None,
            execution_contract,
            compatibility,
            readiness,
        }
    }
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Contract {
    CodexArgv0160,
    SerenaCli17,
    Unknown,
}
impl Contract {
    pub fn name(self) -> &'static str {
        match self {
            Self::CodexArgv0160 => "codex argv 0.160 reference (not a runtime handshake)",
            Self::SerenaCli17 => "Serena CLI 1.7 reference (not MCP readiness)",
            Self::Unknown => "unknown",
        }
    }
}
pub fn contract(tool: Capability, version: Version) -> Contract {
    match (tool, version) {
        (
            Capability::Codex,
            Version {
                major: 0,
                minor: 160,
                patch: 0,
            },
        ) => Contract::CodexArgv0160,
        (
            Capability::Serena,
            Version {
                major: 1,
                minor: 7,
                patch: 0,
            },
        ) => Contract::SerenaCli17,
        _ => Contract::Unknown,
    }
}

/// Streams only regular executable artifacts; no child process or file writes.
#[cfg(target_os = "linux")]
pub fn fingerprint(path: &Path, budget: u64) -> Result<(Checksum, u64), LockError> {
    use rustix::fs::{Mode, OFlags, ResolveFlags, openat2};
    use std::fs::File;
    use std::os::unix::fs::MetadataExt;
    let relative = path
        .strip_prefix("/")
        .map_err(|_| LockError::UnsafeArtifact)?;
    let root = File::open("/").map_err(|_| LockError::Io)?;
    let fd = openat2(
        &root,
        relative,
        OFlags::RDONLY | OFlags::NONBLOCK | OFlags::CLOEXEC,
        Mode::empty(),
        ResolveFlags::BENEATH | ResolveFlags::NO_SYMLINKS | ResolveFlags::NO_MAGICLINKS,
    )
    .map_err(|_| LockError::UnsafeArtifact)?;
    let mut file = File::from(fd);
    let before = file.metadata().map_err(|_| LockError::Io)?;
    if !before.is_file()
        || before.mode() & 0o022 != 0
        || before.mode() & 0o111 == 0
        || (before.uid() != 0 && before.uid() != rustix::process::geteuid().as_raw())
    {
        return Err(LockError::UnsafeArtifact);
    }
    let budget = budget.min(MAX_VERIFY_BYTES);
    if before.len() > budget {
        return Err(LockError::TooLarge);
    }
    let mut hasher = Sha256::new();
    let mut buffer = [0; 16_384];
    let mut count = 0u64;
    while count < before.len() {
        let limit = (before.len() - count).min(buffer.len() as u64) as usize;
        let size = file.read(&mut buffer[..limit]).map_err(|_| LockError::Io)?;
        if size == 0 {
            break;
        }
        count += size as u64;
        hasher.update(&buffer[..size]);
    }
    let after = file.metadata().map_err(|_| LockError::Io)?;
    if before.dev() != after.dev()
        || before.ino() != after.ino()
        || before.len() != after.len()
        || before.mode() != after.mode()
        || before.mtime() != after.mtime()
        || before.mtime_nsec() != after.mtime_nsec()
        || before.ctime() != after.ctime()
        || before.ctime_nsec() != after.ctime_nsec()
        || count != before.len()
    {
        return Err(LockError::Changed);
    }
    Ok((Checksum(hasher.finalize().into()), count))
}
#[cfg(not(target_os = "linux"))]
pub fn fingerprint(_path: &Path, _budget: u64) -> Result<(Checksum, u64), LockError> {
    Err(LockError::Unsupported)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn malformed_records_and_untrusted_commands_fail_without_reflection() {
        let prefix = "kind='codex-smart-tools'\nschema_version=1\n[tools.codex]\n";
        for body in [
            "version='SECRET'\nsha256='000'",
            "version='0.160.0'\nsha256='bad'",
            "version='0.160.0'\nsha256='000'\ncommand='evil'",
        ] {
            assert_eq!(
                ToolLock::parse(&format!("{prefix}{body}")),
                Err(LockError::Invalid)
            );
        }
        assert!(Checksum::parse(&"F".repeat(64)).is_some());
        assert_eq!(
            Checksum::parse(&"0".repeat(64)).unwrap().to_string(),
            "0".repeat(64)
        );
        assert_eq!(
            contract(Capability::Codex, Version::new(0, 160, 0)),
            Contract::CodexArgv0160
        );
        assert_eq!(
            contract(Capability::Codex, Version::new(0, 161, 0)),
            Contract::Unknown
        );
        assert_eq!(
            contract(Capability::Serena, Version::new(1, 7, 0)),
            Contract::SerenaCli17
        );
        assert_eq!(
            contract(Capability::CodeGraphWrapper, Version::new(1, 7, 0)),
            Contract::Unknown
        );
    }
    #[test]
    fn marked_lock_rejects_unknown_duplicate_fields_and_unowned_tools() {
        let valid = format!(
            "kind='codex-smart-tools'\nschema_version=1\n[tools.codex]\nversion='0.160.0'\nsha256='{}'\n",
            "0".repeat(64)
        );
        assert!(ToolLock::parse(&valid).is_ok());
        for source in [
            valid.replace("schema_version=1", "schema_version=2"),
            valid.replace("schema_version=1", "schema_version=1\ncommand='PRIVATE'"),
            valid.replace("version='0.160.0'", "version='0.160.0'\nversion='1.0.0'"),
            valid.replace("[tools.codex]", "[tools.serena]"),
            valid.replace("[tools.codex]", "[tools.context7]"),
            valid.replace("[tools.codex]", "[tools.code-graph-smart]"),
            valid.replace("version='0.160.0'", "version='0.160.0'\npath='/PRIVATE'"),
            format!(
                "{valid}[tools.git]\nversion='2.56.0'\nsha256='{}'",
                "0".repeat(64)
            ),
            "x".repeat(MAX_CONFIG_BYTES + 1),
        ] {
            assert_eq!(ToolLock::parse(&source), Err(LockError::Invalid));
        }
    }
    #[test]
    fn discovery_declaration_contract_and_artifact_never_imply_readiness() {
        for (capability, available, version, artifact, compatibility, readiness) in [
            (
                Capability::Codex,
                true,
                Some(Version::new(0, 160, 0)),
                ArtifactEvidence::Match,
                Compatibility::ReferenceOnly,
                Readiness::Unknown,
            ),
            (
                Capability::Codex,
                true,
                Some(Version::new(9, 0, 0)),
                ArtifactEvidence::Match,
                Compatibility::Unknown,
                Readiness::Unknown,
            ),
            (
                Capability::Codex,
                true,
                None,
                ArtifactEvidence::Deferred,
                Compatibility::Unknown,
                Readiness::Unknown,
            ),
            (
                Capability::Codex,
                true,
                Some(Version::new(0, 160, 0)),
                ArtifactEvidence::Mismatch,
                Compatibility::ReferenceOnly,
                Readiness::Blocked,
            ),
            (
                Capability::Codex,
                false,
                Some(Version::new(0, 160, 0)),
                ArtifactEvidence::Missing,
                Compatibility::ReferenceOnly,
                Readiness::Unavailable,
            ),
            (
                Capability::Serena,
                true,
                Some(Version::new(1, 7, 0)),
                ArtifactEvidence::Deferred,
                Compatibility::ReferenceOnly,
                Readiness::Unknown,
            ),
            (
                Capability::CodeGraphWrapper,
                true,
                None,
                ArtifactEvidence::Deferred,
                Compatibility::UnsupportedWrapper,
                Readiness::Blocked,
            ),
            (
                Capability::Context7,
                true,
                None,
                ArtifactEvidence::Deferred,
                Compatibility::Unknown,
                Readiness::Unknown,
            ),
        ] {
            let evidence = CapabilityEvidence::assess(capability, available, version, artifact);
            assert_eq!(evidence.runtime_version, None);
            assert_eq!(evidence.declared_version, version);
            assert_eq!(evidence.compatibility, compatibility);
            assert_eq!(evidence.readiness, readiness);
            if capability == Capability::Context7 {
                assert_eq!(evidence.available, Availability::SessionUnknown);
            }
        }
    }
    #[cfg(target_os = "linux")]
    #[test]
    fn fifo_and_magic_link_artifacts_are_rejected_without_blocking() {
        use std::fs::{self, File};
        use std::os::unix::fs::PermissionsExt;
        struct Cleanup(std::path::PathBuf);
        impl Drop for Cleanup {
            fn drop(&mut self) {
                let _ = fs::remove_dir_all(&self.0);
            }
        }
        let directory =
            std::env::temp_dir().join(format!("codex-smart-fifo-{}", std::process::id()));
        fs::create_dir(&directory).unwrap();
        let cleanup = Cleanup(directory);
        fs::set_permissions(&cleanup.0, fs::Permissions::from_mode(0o700)).unwrap();
        let dir = File::open(&cleanup.0).unwrap();
        rustix::fs::mkfifoat(&dir, "fifo", rustix::fs::Mode::from_raw_mode(0o700)).unwrap();
        assert_eq!(
            fingerprint(&cleanup.0.join("fifo"), MAX_VERIFY_BYTES),
            Err(LockError::UnsafeArtifact)
        );
        assert_eq!(
            fingerprint(Path::new("/proc/self/exe"), MAX_VERIFY_BYTES),
            Err(LockError::UnsafeArtifact)
        );
    }
}
