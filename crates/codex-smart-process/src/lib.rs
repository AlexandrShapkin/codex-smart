//! Linux child-only descriptor isolation for the explicitly supervised worker.
#![cfg(target_os = "linux")]
use std::{io, os::unix::process::CommandExt, process::Command};

/// Mark descriptors above stderr close-on-exec in the forked child only.
///
/// Install this as the final pre-exec hook: subsequent hooks must not introduce
/// inheritable descriptors. Unsupported kernels or syscall denial fail spawn.
/// The executable descriptor stays open for procfs resolution until exec commits.
pub fn stdio_only(command: &mut Command) {
    install(command, libc::CLOSE_RANGE_CLOEXEC as libc::c_ulong);
}

#[allow(unsafe_code)]
fn install(command: &mut Command, flags: libc::c_ulong) {
    // SAFETY: pre_exec forces std's fork path with a private child fd table.
    // std installs stdio before the hook. This captures only integer flags and performs one
    // syscall plus an allocation-free errno read: no locks, allocation, logging,
    // directory traversal or destructors after fork in a multithreaded caller.
    // CLOEXEC preserves the pinned executable and std's error pipe until exec;
    // close_range(3, UINT_MAX, 0) would prematurely destroy both. No UNSHARE is
    // needed for fork's already private table. No failure is ignored or retried.
    unsafe {
        command.pre_exec(move || {
            if libc::syscall(
                libc::SYS_close_range,
                3 as libc::c_ulong,
                u32::MAX as libc::c_ulong,
                flags,
            ) == 0
            {
                Ok(())
            } else {
                Err(io::Error::last_os_error())
            }
        });
    }
}

// Only one explicitly supervised launch may own these process-wide handlers.
static INTERRUPTED: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
static SIGNAL_OWNER: std::sync::Mutex<()> = std::sync::Mutex::new(());
extern "C" fn interrupt(_: libc::c_int) {
    INTERRUPTED.store(true, std::sync::atomic::Ordering::Relaxed);
}

pub struct InterruptGuard {
    old: [libc::sigaction; 2],
    _owner: std::sync::MutexGuard<'static, ()>,
}
impl InterruptGuard {
    #[allow(unsafe_code)]
    pub fn install() -> io::Result<Self> {
        let owner = SIGNAL_OWNER
            .try_lock()
            .map_err(|_| io::Error::other("signal owner busy"))?;
        INTERRUPTED.store(false, std::sync::atomic::Ordering::Relaxed);
        // SAFETY: initialized sigaction values; handler only sets a lock-free atomic.
        // Guard serializes installation and restores previous dispositions on drop.
        unsafe {
            let mut action: libc::sigaction = std::mem::zeroed();
            action.sa_sigaction = interrupt as *const () as usize;
            libc::sigemptyset(&mut action.sa_mask);
            let mut old: [libc::sigaction; 2] = std::mem::zeroed();
            if libc::sigaction(libc::SIGINT, &action, &mut old[0]) != 0 {
                return Err(io::Error::last_os_error());
            }
            if libc::sigaction(libc::SIGTERM, &action, &mut old[1]) != 0 {
                libc::sigaction(libc::SIGINT, &old[0], std::ptr::null_mut());
                return Err(io::Error::last_os_error());
            }
            Ok(Self { old, _owner: owner })
        }
    }
    pub fn interrupted(&self) -> bool {
        INTERRUPTED.load(std::sync::atomic::Ordering::Relaxed)
    }
}
impl Drop for InterruptGuard {
    #[allow(unsafe_code)]
    fn drop(&mut self) {
        // SAFETY: restore the exact dispositions retained by this exclusive guard.
        unsafe {
            libc::sigaction(libc::SIGINT, &self.old[0], std::ptr::null_mut());
            libc::sigaction(libc::SIGTERM, &self.old[1], std::ptr::null_mut());
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn syscall_failure_refuses_spawn() {
        let mut command = Command::new("/bin/true");
        // Bit 0 is undefined: exercise the exact hook's error path, without
        // changing parent descriptors or relying on an unsupported host kernel.
        install(&mut command, 1);
        assert_eq!(
            command.spawn().unwrap_err().raw_os_error(),
            Some(libc::EINVAL)
        );
    }

    #[test]
    fn exec_failure_preserves_spawn_error_transport() {
        let mut command = Command::new("/proc/self/fd/4294967295");
        stdio_only(&mut command);
        assert_eq!(
            command.spawn().unwrap_err().raw_os_error(),
            Some(libc::ENOENT)
        );
    }
}
