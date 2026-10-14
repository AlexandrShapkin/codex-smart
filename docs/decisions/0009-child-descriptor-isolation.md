# ADR-0009: Child-only descriptor isolation for the supervised worker

Status: proposed for PR #91 owner review.

## Evidence

Ubuntu CI on `1681b7b49046da926d85ab6f71458b80b84dfd09` reports parent
fds 142 (flags 2048) and 145 (flags 1), neither close-on-exec. Both ordinary
worker tests fail with bootstrap exit 17. This establishes inheritance risk,
not the exact descriptor received by the child. Rust `Command` does not close
arbitrary inherited descriptors merely because the environment is cleared.
Rustix's directory iterator owns exactly the descriptor exempted by bootstrap.

## Decision

Install `close_range(3, UINT_MAX, CLOSE_RANGE_CLOEXEC)` as the final `pre_exec`
hook in the production supervised launcher. The syscall marks all extra child
fds close-on-exec. It does not close the pinned executable before `/proc/self/fd/N`
resolution, or destroy Rust's error-reporting pipe before a failed exec.
Stdio has already been duplicated to 0/1/2 when the hook runs.

Rust 1.98's Unix implementation declines posix_spawn when pre-exec closures exist
and uses fork; the child has a private descriptor table. No parent flag mutation,
parent-wide enumeration or concurrent-thread race is introduced. UNSHARE is
unnecessary in this forked child. The hook contains only a syscall and raw errno
conversion; no allocations, locks, logging, directory iteration or destructor
work. Linux 5.11 introduced this flag. ENOSYS, EINVAL, EPERM and other errors
propagate through Rust's spawn-error channel to Error::Spawn; no fallback or
worker execution follows. The existing post-spawn timing/ownership policy is
unchanged; spawn, including the hook, remains outside the runtime deadline.

Core and CLI keep unsafe_code=forbid. A small Linux-only process helper denies
unsafe by default, permitting it solely in the reviewed hook function. Its safe
API installs the fixed hook; only internal tests can request invalid flags.
Libc 0.2.189 has an exact pin, default features disabled and the existing registry
checksum; no new external package is introduced. Dependency provenance explicitly
recognizes this local helper and the new direct libc use.

## Verification and limits

Supervised startup with deliberate inheritable low/high fds must succeed while
parent flags stay unchanged. Direct startup must still return 17. Existing
identity, malformed-request, output/deadline and cleanup regressions remain.
Hook tests cover syscall refusal and failed-exec transport. Hermetic direct
protocol tests use child-only cleanup; direct descriptor-refusal tests remain
unsanitized. Exact-head Ubuntu acceptance remains a publication/review gate.
This does not add a hostile-code sandbox or production routing authority.

References: [Linux close_range manual](https://man7.org/linux/man-pages/man2/close_range.2.html),
[Rust 1.98 Unix process implementation](https://github.com/rust-lang/rust/blob/1.98.0/library/std/src/sys/process/unix/unix.rs).
