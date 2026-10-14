//! Explicit, bounded repository evidence acquisition; never grants launch authority.
use crate::playbook::{ContextObligation, builtin};
use crate::workflow::{NativeSurface, ValidationRecipe, WorkflowPlan};
use std::collections::BTreeSet;
use std::path::{Component, Path, PathBuf};
use std::time::{Duration, Instant};

/// Hard ceilings also constrain caller-supplied limits.
#[derive(Debug, Clone, Copy)]
pub struct Limits {
    pub files: usize,
    pub file_bytes: usize,
    pub total_bytes: usize,
    pub elapsed: Duration,
}
impl Default for Limits {
    fn default() -> Self {
        Self {
            files: 16,
            file_bytes: 8192,
            total_bytes: 32768,
            elapsed: Duration::from_millis(250),
        }
    }
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Request {
    pub path: PathBuf,
    pub obligation: ContextObligation,
}
/// Source text is deliberately excluded from Debug diagnostics.
#[derive(Clone, PartialEq, Eq)]
pub struct Snippet {
    pub request: Request,
    pub text: String,
    pub sha256: String,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Failure {
    InvalidLimits,
    MissingIntent,
    BlockedPlan,
    InvalidRequest,
    UnsafeOrMissingFile,
    FileLimit,
    ByteLimit,
    Deadline,
    InvalidText,
    UnsupportedPlatform,
}
/// Successful acquisition does not prove semantic sufficiency or validation success.
#[derive(Default)]
pub struct Preparation {
    pub snippets: Vec<Snippet>,
    pub unresolved: BTreeSet<ContextObligation>,
    pub validation: Option<ValidationRecipe>,
    pub failure: Option<Failure>,
}

impl Preparation {
    /// Inspect readiness and obligations without exposing paths or source payloads.
    pub fn summary(&self) -> String {
        format!(
            "files={}; bytes={}; failure={:?}; unresolved={:?}; validation={:?}",
            self.snippets.len(),
            self.snippets
                .iter()
                .map(|snippet| snippet.text.len())
                .sum::<usize>(),
            self.failure,
            self.unresolved,
            self.validation,
        )
    }
}

/// No recursive discovery: callers nominate task-relevant regular UTF-8 files.
/// All-or-nothing acquisition on error; validation readiness remains independent.
/// Deadline checks are cooperative, not a kernel I/O timeout. Use local trusted
/// filesystems; a future supervised runtime must enforce hard wall time externally.
pub fn prepare(
    root: &Path,
    plan: &WorkflowPlan,
    native: &NativeSurface,
    requests: &[Request],
    limits: Limits,
) -> Preparation {
    let started = Instant::now();
    let mut result = Preparation {
        validation: plan.validation_recipe(native),
        ..Default::default()
    };
    if plan.status == crate::workflow::PlanStatus::Blocked {
        result.failure = Some(Failure::BlockedPlan);
        return result;
    }
    let Some(archetype) = plan.selection.archetype else {
        result.failure = Some(Failure::MissingIntent);
        return result;
    };
    result.unresolved.extend(builtin(archetype).context);
    let acquired = acquire(root, requests, limits, started, &result.unresolved);
    match acquired {
        Ok(snippets) => {
            // File contents do not establish requirements, callers, repository state,
            // or even that selected files are semantically sufficient.
            result.snippets = snippets;
        }
        Err(failure) => result.failure = Some(failure),
    }
    result
}
fn acquire(
    root: &Path,
    requests: &[Request],
    limits: Limits,
    started: Instant,
    obligations: &BTreeSet<ContextObligation>,
) -> Result<Vec<Snippet>, Failure> {
    if limits.files == 0
        || limits.files > 16
        || limits.file_bytes == 0
        || limits.file_bytes > 8192
        || limits.total_bytes == 0
        || limits.total_bytes > 32768
        || limits.elapsed.is_zero()
        || limits.elapsed > Duration::from_millis(250)
    {
        return Err(Failure::InvalidLimits);
    }
    if root.as_os_str().len() > 1024 || root.components().count() > 32 {
        return Err(Failure::InvalidRequest);
    }
    if requests.len() > limits.files {
        return Err(Failure::FileLimit);
    }
    let mut ordered: Vec<_> = requests.iter().collect();
    ordered.sort_by(|a, b| a.path.cmp(&b.path).then(a.obligation.cmp(&b.obligation)));
    let mut seen = BTreeSet::new();
    for request in &ordered {
        if request.path.as_os_str().len() > 1024
            || request.path.as_os_str().is_empty()
            || request.path.components().count() > 16
            || request
                .path
                .components()
                .any(|c| !matches!(c, Component::Normal(_)))
            || !obligations.contains(&request.obligation)
            || !seen.insert(&request.path)
        {
            return Err(Failure::InvalidRequest);
        }
    }
    let mut snippets = Vec::new();
    let mut total = 0;
    for request in ordered {
        if started.elapsed() >= limits.elapsed {
            return Err(Failure::Deadline);
        }
        let bytes = read_file(
            root,
            &request.path,
            limits.file_bytes.min(limits.total_bytes - total),
        )?;
        total += bytes.len();
        if total > limits.total_bytes {
            return Err(Failure::ByteLimit);
        }
        if started.elapsed() >= limits.elapsed {
            return Err(Failure::Deadline);
        }
        if bytes.contains(&0) {
            return Err(Failure::InvalidText);
        }
        use sha2::{Digest, Sha256};
        let sha256 = Sha256::digest(&bytes)
            .iter()
            .map(|byte| format!("{byte:02x}"))
            .collect();
        let text = String::from_utf8(bytes).map_err(|_| Failure::InvalidText)?;
        snippets.push(Snippet {
            request: request.clone(),
            text,
            sha256,
        });
    }
    if started.elapsed() >= limits.elapsed {
        return Err(Failure::Deadline);
    }
    Ok(snippets)
}
#[cfg(target_os = "linux")]
fn read_file(root: &Path, path: &Path, limit: usize) -> Result<Vec<u8>, Failure> {
    use rustix::fs::{Mode, OFlags, ResolveFlags, openat2};
    use std::fs::File;
    use std::io::Read;
    use std::os::unix::fs::MetadataExt;
    let relative = root
        .strip_prefix("/")
        .map_err(|_| Failure::UnsafeOrMissingFile)?;
    if relative.as_os_str().is_empty()
        || relative
            .components()
            .any(|c| !matches!(c, Component::Normal(_)))
    {
        return Err(Failure::InvalidRequest);
    }
    let slash = File::open("/").map_err(|_| Failure::UnsafeOrMissingFile)?;
    let resolve = ResolveFlags::BENEATH | ResolveFlags::NO_SYMLINKS | ResolveFlags::NO_MAGICLINKS;
    let dir = openat2(
        &slash,
        relative,
        OFlags::RDONLY | OFlags::DIRECTORY | OFlags::CLOEXEC,
        Mode::empty(),
        resolve,
    )
    .map_err(|_| Failure::UnsafeOrMissingFile)?;
    let fd = openat2(
        &dir,
        path,
        OFlags::PATH | OFlags::CLOEXEC,
        Mode::empty(),
        resolve,
    )
    .map_err(|_| Failure::UnsafeOrMissingFile)?;
    let pinned = File::from(fd);
    let metadata = pinned
        .metadata()
        .map_err(|_| Failure::UnsafeOrMissingFile)?;
    if !metadata.is_file() || metadata.nlink() != 1 {
        return Err(Failure::UnsafeOrMissingFile);
    }
    use std::os::fd::AsRawFd;
    let proc_path = format!("/proc/self/fd/{}", pinned.as_raw_fd());
    let readable = rustix::fs::open(
        proc_path,
        OFlags::RDONLY | OFlags::NONBLOCK | OFlags::CLOEXEC,
        Mode::empty(),
    )
    .map_err(|_| Failure::UnsafeOrMissingFile)?;
    let mut file = File::from(readable);
    let before = file.metadata().map_err(|_| Failure::UnsafeOrMissingFile)?;
    if !before.is_file() || before.nlink() != 1 {
        return Err(Failure::UnsafeOrMissingFile);
    }
    if before.len() > limit as u64 {
        return Err(Failure::ByteLimit);
    }
    let mut bytes = Vec::new();
    (&mut file)
        .take(limit as u64 + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| Failure::UnsafeOrMissingFile)?;
    let after = file.metadata().map_err(|_| Failure::UnsafeOrMissingFile)?;
    if bytes.len() > limit {
        return Err(Failure::ByteLimit);
    }
    if before.len() != after.len()
        || before.mtime_nsec() != after.mtime_nsec()
        || before.mtime() != after.mtime()
        || before.ctime() != after.ctime()
        || before.ctime_nsec() != after.ctime_nsec()
        || bytes.len() as u64 != after.len()
    {
        return Err(Failure::UnsafeOrMissingFile);
    }
    Ok(bytes)
}
#[cfg(not(target_os = "linux"))]
fn read_file(_: &Path, _: &Path, _: usize) -> Result<Vec<u8>, Failure> {
    Err(Failure::UnsupportedPlatform)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn expired_budget_refuses_before_io() {
        let request = Request {
            path: "missing".into(),
            obligation: ContextObligation::RelevantFiles,
        };
        assert!(matches!(
            acquire(
                Path::new("/missing"),
                &[request],
                Limits::default(),
                Instant::now() - Duration::from_secs(1),
                &BTreeSet::from([ContextObligation::RelevantFiles])
            ),
            Err(Failure::Deadline)
        ));
    }
}
