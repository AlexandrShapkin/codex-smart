//! Explicit, offline migration of marked codex-smart TOML only.
use crate::config::{ConfigError, Layer, Origin, document, version};
use std::path::Path;

pub fn upgraded(source: &str) -> Result<String, ConfigError> {
    let mut doc = document(source)?;
    if version(&doc)? == 1 {
        Layer::parse(source, Origin::User)?;
        return Ok(source.to_owned());
    }
    if doc.contains_key("reasoning") && doc.contains_key("reasoning_effort") {
        return Err(ConfigError::InvalidValue);
    }
    if let Some((old_key, item)) = doc.as_table_mut().remove_entry("reasoning_effort") {
        let mut key = toml_edit::Key::new("reasoning");
        *key.leaf_decor_mut() = old_key.leaf_decor().clone();
        *key.dotted_decor_mut() = old_key.dotted_decor().clone();
        doc.as_table_mut().insert_formatted(&key, item);
    }
    let decor = doc["schema_version"]
        .as_value()
        .ok_or(ConfigError::Schema)?
        .decor()
        .clone();
    let mut schema = toml_edit::Value::from(1);
    *schema.decor_mut() = decor;
    doc["schema_version"] = toml_edit::Item::Value(schema);
    let output = doc.to_string();
    Layer::parse(&output, Origin::User)?;
    Ok(output)
}

#[cfg(target_os = "linux")]
mod linux {
    use super::*;
    use crate::config::MAX_CONFIG_BYTES;
    use rustix::fs::{self as sys, Mode, OFlags, ResolveFlags};
    use std::ffi::OsString;
    use std::fs::File;
    use std::io::{Read, Write};
    use std::os::unix::fs::MetadataExt;
    use std::path::Component;

    fn error(error: rustix::io::Errno) -> ConfigError {
        match error {
            rustix::io::Errno::NOENT => ConfigError::Missing,
            rustix::io::Errno::LOOP | rustix::io::Errno::NOTDIR => ConfigError::UnsafePath,
            rustix::io::Errno::ACCESS | rustix::io::Errno::PERM => ConfigError::Permissions,
            rustix::io::Errno::NOSYS => ConfigError::Unsupported,
            rustix::io::Errno::EXIST => ConfigError::BackupExists,
            _ => ConfigError::Io,
        }
    }
    #[derive(Debug, Clone, PartialEq, Eq)]
    struct Identity {
        device: u64,
        inode: u64,
        length: u64,
        modified: (i64, i64),
        changed: (i64, i64),
        mode: u32,
        links: u64,
    }
    fn identity(meta: &std::fs::Metadata) -> Identity {
        Identity {
            device: meta.dev(),
            inode: meta.ino(),
            length: meta.len(),
            modified: (meta.mtime(), meta.mtime_nsec()),
            changed: (meta.ctime(), meta.ctime_nsec()),
            mode: meta.mode(),
            links: meta.nlink(),
        }
    }
    #[derive(Clone, PartialEq, Eq)]
    struct Content {
        bytes: Vec<u8>,
        identity: Identity,
    }
    struct Target {
        dir: File,
        name: OsString,
    }
    impl Target {
        fn open(path: &Path) -> Result<Self, ConfigError> {
            if path.components().any(|c| matches!(c, Component::ParentDir)) {
                return Err(ConfigError::UnsafePath);
            }
            let path = std::path::absolute(path).map_err(|_| ConfigError::Io)?;
            let name = path.file_name().ok_or(ConfigError::UnsafePath)?.to_owned();
            let parent = path
                .parent()
                .ok_or(ConfigError::UnsafePath)?
                .strip_prefix("/")
                .map_err(|_| ConfigError::UnsafePath)?;
            let root = File::open("/").map_err(|_| ConfigError::Io)?;
            let parent = if parent.as_os_str().is_empty() {
                Path::new(".")
            } else {
                parent
            };
            let dir = sys::openat2(
                &root,
                parent,
                OFlags::RDONLY | OFlags::DIRECTORY | OFlags::CLOEXEC,
                Mode::empty(),
                ResolveFlags::BENEATH | ResolveFlags::NO_SYMLINKS | ResolveFlags::NO_MAGICLINKS,
            )
            .map_err(error)?;
            Ok(Self {
                dir: File::from(dir),
                name,
            })
        }
        fn artifact(&self, suffix: &str) -> OsString {
            let mut name = self.name.clone();
            name.push(suffix);
            name
        }
        fn read(&self, name: &std::ffi::OsStr, private: bool) -> Result<Content, ConfigError> {
            let fd = sys::openat2(
                &self.dir,
                name,
                OFlags::RDONLY | OFlags::NONBLOCK | OFlags::CLOEXEC,
                Mode::empty(),
                ResolveFlags::BENEATH | ResolveFlags::NO_SYMLINKS | ResolveFlags::NO_MAGICLINKS,
            )
            .map_err(error)?;
            let mut file = File::from(fd);
            let meta = file.metadata().map_err(|_| ConfigError::Io)?;
            validate_file(&meta, private)?;
            if meta.len() > MAX_CONFIG_BYTES as u64 {
                return Err(ConfigError::TooLarge);
            }
            let mut bytes = Vec::new();
            (&mut file)
                .take(MAX_CONFIG_BYTES as u64 + 1)
                .read_to_end(&mut bytes)
                .map_err(|_| ConfigError::Io)?;
            if bytes.len() > MAX_CONFIG_BYTES {
                return Err(ConfigError::TooLarge);
            }
            let before = identity(&meta);
            if before != identity(&file.metadata().map_err(|_| ConfigError::Io)?) {
                return Err(ConfigError::Changed);
            }
            Ok(Content {
                bytes,
                identity: before,
            })
        }
        fn read_artifact(&self, suffix: &str) -> Result<Option<Content>, ConfigError> {
            match self.read(&self.artifact(suffix), true) {
                Ok(content) => Ok(Some(content)),
                Err(ConfigError::Missing) => Ok(None),
                Err(error) => Err(error),
            }
        }
        fn validate_parent(&self) -> Result<(), ConfigError> {
            let meta = self.dir.metadata().map_err(|_| ConfigError::Io)?;
            if meta.uid() != rustix::process::geteuid().as_raw() || meta.mode() & 0o022 != 0 {
                return Err(ConfigError::Permissions);
            }
            Ok(())
        }
        fn lock(&self) -> Result<File, ConfigError> {
            self.validate_parent()?;
            let flags = OFlags::RDWR | OFlags::NOFOLLOW | OFlags::NONBLOCK | OFlags::CLOEXEC;
            let created = sys::openat(
                &self.dir,
                ".codex-smart-migration.lock",
                flags | OFlags::CREATE | OFlags::EXCL,
                Mode::from_raw_mode(0o600),
            );
            let (fd, new) = match created {
                Ok(fd) => (fd, true),
                Err(rustix::io::Errno::EXIST) => (
                    sys::openat(
                        &self.dir,
                        ".codex-smart-migration.lock",
                        flags,
                        Mode::empty(),
                    )
                    .map_err(error)?,
                    false,
                ),
                Err(e) => return Err(error(e)),
            };
            let file = File::from(fd);
            if new {
                sys::fchmod(&file, Mode::from_raw_mode(0o600)).map_err(error)?;
            }
            validate_file(&file.metadata().map_err(|_| ConfigError::Io)?, true)?;
            sys::flock(&file, sys::FlockOperation::NonBlockingLockExclusive)
                .map_err(|_| ConfigError::Busy)?;
            Ok(file)
        }
    }
    fn validate_file(meta: &std::fs::Metadata, private: bool) -> Result<(), ConfigError> {
        if !meta.is_file() || meta.nlink() != 1 {
            return Err(ConfigError::UnsafePath);
        }
        if meta.uid() != rustix::process::geteuid().as_raw()
            || meta.mode() & if private { 0o077 } else { 0o022 } != 0
        {
            return Err(ConfigError::Permissions);
        }
        Ok(())
    }
    fn text(bytes: &[u8]) -> Result<&str, ConfigError> {
        std::str::from_utf8(bytes).map_err(|_| ConfigError::InvalidToml)
    }
    pub fn read_optional(path: &Path) -> Result<Option<String>, ConfigError> {
        let target = match Target::open(path) {
            Ok(t) => t,
            Err(ConfigError::Missing) => return Ok(None),
            Err(e) => return Err(e),
        };
        let source = match target.read(&target.name, false) {
            Ok(s) => s,
            Err(ConfigError::Missing) => return Ok(None),
            Err(e) => return Err(e),
        };
        Ok(Some(text(&source.bytes)?.to_owned()))
    }
    fn guard_mutation(path: &Path) -> Result<(), ConfigError> {
        let absolute = std::path::absolute(path).map_err(|_| ConfigError::Io)?;
        if absolute
            .components()
            .any(|c| matches!(c, Component::Normal(name) if name == ".codex"))
        {
            return Err(ConfigError::ProtectedStore);
        }
        let mut roots = Vec::new();
        if let Some(root) = std::env::var_os("CODEX_HOME").filter(|r| !r.is_empty()) {
            roots.push(std::path::PathBuf::from(root));
        }
        if let Some(home) = std::env::var_os("HOME") {
            roots.push(std::path::PathBuf::from(home).join(".codex"));
        }
        for root in roots {
            let root = std::path::absolute(root).map_err(|_| ConfigError::Io)?;
            let root = root.canonicalize().unwrap_or(root);
            if absolute.starts_with(root) {
                return Err(ConfigError::ProtectedStore);
            }
        }
        let name = absolute
            .file_name()
            .ok_or(ConfigError::UnsafePath)?
            .as_encoded_bytes();
        if name == b".codex-smart-migration.lock"
            || [
                b".codex-smart-backup".as_slice(),
                b".codex-smart-applied",
                b".codex-smart-stage",
            ]
            .iter()
            .any(|suffix| name.ends_with(suffix))
        {
            return Err(ConfigError::UnsafePath);
        }
        Ok(())
    }
    struct Recovery {
        backup: Content,
        receipt: Option<Content>,
        stage: Option<Content>,
    }
    enum Kind {
        Upgrade,
        Rollback(Box<Recovery>),
        Cleanup(Box<Recovery>),
        Noop,
    }
    pub struct MigrationPlan {
        target: Target,
        before: Content,
        after: Vec<u8>,
        kind: Kind,
        renamed_effort: bool,
    }
    impl MigrationPlan {
        pub fn prepare(path: &Path) -> Result<Self, ConfigError> {
            guard_mutation(path)?;
            let target = Target::open(path)?;
            target.validate_parent()?;
            let before = target.read(&target.name, true)?;
            let source = text(&before.bytes)?;
            let renamed_effort = document(source)?.contains_key("reasoning_effort");
            let after = upgraded(source)?.into_bytes();
            let kind = if before.bytes == after {
                Kind::Noop
            } else {
                Kind::Upgrade
            };
            Ok(Self {
                target,
                before,
                after,
                kind,
                renamed_effort,
            })
        }
        pub fn rollback(path: &Path) -> Result<Self, ConfigError> {
            guard_mutation(path)?;
            let target = Target::open(path)?;
            target.validate_parent()?;
            let before = target.read(&target.name, true)?;
            let backup = target.read_artifact(".codex-smart-backup")?;
            let receipt = target.read_artifact(".codex-smart-applied")?;
            let Some(backup) = backup else {
                if receipt.is_some() {
                    return Err(ConfigError::RecoveryRequired);
                }
                if version(&document(text(&before.bytes)?)?)? != 0 {
                    return Err(ConfigError::NoBackup);
                }
                return Ok(Self {
                    after: before.bytes.clone(),
                    before,
                    target,
                    kind: Kind::Noop,
                    renamed_effort: false,
                });
            };
            if version(&document(text(&backup.bytes)?)?)? != 0 {
                return Err(ConfigError::Changed);
            }
            let upgraded = upgraded(text(&backup.bytes)?)?.into_bytes();
            if receipt.as_ref().is_some_and(|r| r.bytes != upgraded) {
                return Err(ConfigError::Changed);
            }
            let stage = target.read_artifact(".codex-smart-stage")?;
            if stage
                .as_ref()
                .is_some_and(|stage| stage.bytes != upgraded && stage.bytes != backup.bytes)
            {
                return Err(ConfigError::RecoveryRequired);
            }
            let after = backup.bytes.clone();
            let cleanup = before.bytes == backup.bytes;
            if !cleanup && !receipt.as_ref().is_some_and(|r| before.bytes == r.bytes) {
                return Err(ConfigError::Changed);
            }
            let recovery = Box::new(Recovery {
                backup,
                receipt,
                stage,
            });
            let kind = if cleanup {
                Kind::Cleanup(recovery)
            } else {
                Kind::Rollback(recovery)
            };
            Ok(Self {
                target,
                before,
                after,
                kind,
                renamed_effort: false,
            })
        }
        pub fn preview(&self) -> String {
            match self.kind {
                Kind::Noop => "Configuration transaction: no changes\n".to_owned(),
                Kind::Cleanup(_) => "Configuration recovery cleanup: original already intact; remove verified transaction artifacts only\nDefault: dry-run; --apply required\n".to_owned(),
                Kind::Upgrade => format!("Configuration migration diff (unrelated fields/values omitted)\nschema_version: 0 -> 1\n{}Unknown fields and comments: preserved; parser may normalize formatting\nDefault: dry-run; --apply required\n", if self.renamed_effort { "reasoning_effort -> reasoning (value preserved)\n" } else { "" }),
                Kind::Rollback(_) => "Configuration rollback diff (unrelated values omitted)\nschema_version: 1 -> 0\nRestore exact private backup bytes; refuse intervening edits\nDefault: dry-run; --apply required\n".to_owned(),
            }
        }
        pub fn apply(&self) -> Result<(), ConfigError> {
            if matches!(self.kind, Kind::Noop) {
                return Ok(());
            }
            let _lock = self.target.lock()?;
            if self.target.read(&self.target.name, true)? != self.before {
                return Err(ConfigError::Changed);
            }
            let backup_name = self.target.artifact(".codex-smart-backup");
            let receipt_name = self.target.artifact(".codex-smart-applied");
            let stage_name = self.target.artifact(".codex-smart-stage");
            let mut pending = Pending {
                target: &self.target,
                names: Vec::new(),
            };
            match &self.kind {
                Kind::Upgrade => {
                    pending.write_new(&backup_name, &self.before.bytes)?;
                    pending.write_new(&receipt_name, &self.after)?;
                }
                Kind::Rollback(recovery) | Kind::Cleanup(recovery) => {
                    if self.target.read(&backup_name, true)? != recovery.backup
                        || self.target.read_artifact(".codex-smart-applied")? != recovery.receipt
                        || self.target.read_artifact(".codex-smart-stage")? != recovery.stage
                    {
                        return Err(ConfigError::Changed);
                    }
                    if recovery.stage.is_some() {
                        sys::unlinkat(&self.target.dir, &stage_name, sys::AtFlags::empty())
                            .map_err(error)?;
                    }
                    if matches!(self.kind, Kind::Cleanup(_)) {
                        // No primary-file replacement: the exact original is already present.
                        if recovery.receipt.is_some() {
                            sys::unlinkat(&self.target.dir, &receipt_name, sys::AtFlags::empty())
                                .map_err(error)?;
                        }
                        self.target
                            .dir
                            .sync_all()
                            .map_err(|_| ConfigError::RecoveryRequired)?;
                        sys::unlinkat(&self.target.dir, &backup_name, sys::AtFlags::empty())
                            .map_err(error)?;
                        self.target
                            .dir
                            .sync_all()
                            .map_err(|_| ConfigError::RecoveryRequired)?;
                        return Ok(());
                    }
                }
                Kind::Noop => unreachable!(),
            }
            pending.write_new(&stage_name, &self.after)?;
            self.target.dir.sync_all().map_err(|_| ConfigError::Io)?;
            if self.target.read(&self.target.name, true)? != self.before {
                return Err(ConfigError::Changed);
            }
            sys::renameat(
                &self.target.dir,
                &stage_name,
                &self.target.dir,
                &self.target.name,
            )
            .map_err(error)?;
            // Commit point: do not remove durable recovery data on subsequent errors.
            pending.names.clear();
            self.target
                .dir
                .sync_all()
                .map_err(|_| ConfigError::RecoveryRequired)?;
            if matches!(self.kind, Kind::Rollback(_)) {
                sys::unlinkat(&self.target.dir, &receipt_name, sys::AtFlags::empty())
                    .map_err(|_| ConfigError::RecoveryRequired)?;
                self.target
                    .dir
                    .sync_all()
                    .map_err(|_| ConfigError::RecoveryRequired)?;
                sys::unlinkat(&self.target.dir, &backup_name, sys::AtFlags::empty())
                    .map_err(|_| ConfigError::RecoveryRequired)?;
                self.target
                    .dir
                    .sync_all()
                    .map_err(|_| ConfigError::RecoveryRequired)?;
            }
            Ok(())
        }
    }
    struct Pending<'a> {
        target: &'a Target,
        names: Vec<OsString>,
    }
    impl Pending<'_> {
        fn write_new(&mut self, name: &std::ffi::OsStr, bytes: &[u8]) -> Result<(), ConfigError> {
            let fd = sys::openat(
                &self.target.dir,
                name,
                OFlags::WRONLY | OFlags::CREATE | OFlags::EXCL | OFlags::NOFOLLOW | OFlags::CLOEXEC,
                Mode::from_raw_mode(0o600),
            )
            .map_err(error)?;
            self.names.push(name.to_owned());
            let mut file = File::from(fd);
            sys::fchmod(&file, Mode::from_raw_mode(0o600)).map_err(error)?;
            file.write_all(bytes).map_err(|_| ConfigError::Io)?;
            file.sync_all().map_err(|_| ConfigError::Io)
        }
    }
    impl Drop for Pending<'_> {
        fn drop(&mut self) {
            for name in &self.names {
                let _ = sys::unlinkat(&self.target.dir, name, sys::AtFlags::empty());
            }
        }
    }
}
#[cfg(target_os = "linux")]
pub use linux::{MigrationPlan, read_optional};

#[cfg(not(target_os = "linux"))]
pub fn read_optional(_path: &Path) -> Result<Option<String>, ConfigError> {
    Err(ConfigError::Unsupported)
}
#[cfg(not(target_os = "linux"))]
pub struct MigrationPlan;
#[cfg(not(target_os = "linux"))]
impl MigrationPlan {
    pub fn prepare(_path: &Path) -> Result<Self, ConfigError> {
        Err(ConfigError::Unsupported)
    }
    pub fn rollback(_path: &Path) -> Result<Self, ConfigError> {
        Err(ConfigError::Unsupported)
    }
    pub fn preview(&self) -> String {
        String::new()
    }
    pub fn apply(&self) -> Result<(), ConfigError> {
        Err(ConfigError::Unsupported)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn preserves_comments_attached_to_renamed_key() {
        let before = "kind='codex-smart'\nschema_version=0 # schema comment\n# reasoning explanation\nreasoning_effort='high' # value comment\n";
        let after = upgraded(before).unwrap();
        assert!(after.contains("# reasoning explanation"));
        assert!(after.contains("# schema comment"));
        assert!(after.contains("# value comment"));
    }
    #[test]
    fn preserves_unknown_tables_and_rejects_conflicting_rename() {
        let original = "kind='codex-smart'\nschema_version=0\nreasoning_effort='high' # retained\n[unknown]\nopaque={ nested=['x','y'] }\n";
        let result = upgraded(original).unwrap();
        assert_eq!(
            document(&result)
                .unwrap()
                .get("reasoning")
                .and_then(|v| v.as_str()),
            Some("high")
        );
        assert!(result.contains("'high' # retained"));
        assert!(result.contains("opaque={ nested=['x','y'] }"));
        assert_eq!(upgraded(&result).unwrap(), result);
        assert_eq!(
            upgraded(
                "kind='codex-smart'\nschema_version=0\nreasoning='medium'\nreasoning_effort='high'"
            ),
            Err(ConfigError::InvalidValue)
        );
    }
}
