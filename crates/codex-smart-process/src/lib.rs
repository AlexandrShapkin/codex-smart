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
