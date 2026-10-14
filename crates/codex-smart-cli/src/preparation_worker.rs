//! Dedicated deterministic worker. Ordinary CLI never calls this entrypoint.
fn main() -> std::process::ExitCode {
    if std::env::args_os().len() != 1
        || codex_smart_core::preparation_worker::worker_bootstrap().is_err()
        || codex_smart_core::preparation_wire::serve(
            std::io::stdin().lock(),
            std::io::stdout().lock(),
        )
        .is_err()
    {
        std::process::ExitCode::from(1)
    } else {
        std::process::ExitCode::SUCCESS
    }
}
