//! Dedicated deterministic worker. Ordinary CLI never calls this entrypoint.
fn main() -> std::process::ExitCode {
    // Stable payload-free refusal codes for worker/parent fault isolation.
    if std::env::args_os().len() != 1 {
        return std::process::ExitCode::from(2);
    }
    if let Err(refusal) = codex_smart_core::preparation_worker::worker_bootstrap() {
        return std::process::ExitCode::from(refusal.exit_code());
    }
    if codex_smart_core::preparation_wire::serve(std::io::stdin().lock(), std::io::stdout().lock())
        .is_err()
    {
        return std::process::ExitCode::from(4);
    }
    std::process::ExitCode::SUCCESS
}
