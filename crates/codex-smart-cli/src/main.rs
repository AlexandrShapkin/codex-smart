use codex_smart_core::{
    VERSION,
    capability::{Capability, Inventory},
    config::{self, ConfigError, Layer, Origin, Resolved},
    migration::{MigrationPlan, read_optional},
    process::LaunchPlan,
    routing::{Reasoning, Task, decide},
    tool_lock::{LockError, ToolLock},
};
use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

fn cwd() -> Result<PathBuf, &'static str> {
    std::env::current_dir().map_err(|_| "E_CWD: cannot resolve current directory")
}
fn read_layer(path: &Path, origin: Origin) -> Result<Layer, ConfigError> {
    read_optional(path)?.map_or(Ok(Layer::default()), |source| Layer::parse(&source, origin))
}
fn configuration(cli: &Layer) -> Result<Resolved, &'static str> {
    let user_path =
        if let Some(root) = std::env::var_os("XDG_CONFIG_HOME").filter(|v| !v.is_empty()) {
            Some(PathBuf::from(root).join("codex-smart/config.toml"))
        } else {
            std::env::var_os("HOME")
                .map(|root| PathBuf::from(root).join(".config/codex-smart/config.toml"))
        };
    if user_path.as_ref().is_some_and(|p| !p.is_absolute()) {
        return Err(ConfigError::UnsafePath.code());
    }
    let user = match user_path {
        Some(path) => read_layer(&path, Origin::User),
        None => Ok(Layer::default()),
    }
    .map_err(|e| e.code())?;
    let project =
        read_layer(&cwd()?.join(".codex-smart.toml"), Origin::Project).map_err(|e| e.code())?;
    Ok(config::resolve(&user, &project, cli))
}
fn explain_overrides(args: &[OsString]) -> Result<Layer, &'static str> {
    if !args.len().is_multiple_of(2) {
        return Err("E_ARGS: explain options require values");
    }
    let mut layer = Layer::default();
    for pair in args.as_chunks::<2>().0 {
        let value = pair[1].to_str().ok_or("E_ARGS: invalid option value")?;
        match pair[0].to_str() {
            Some("--task") if layer.task.is_none() => {
                layer.task = Some(Task::parse(value).ok_or("E_TASK: invalid task hint")?)
            }
            Some("--reasoning") if layer.reasoning.is_none() => {
                layer.reasoning =
                    Some(Reasoning::parse(value).ok_or("E_REASONING: expected medium or high")?)
            }
            Some("--context-limit") if layer.context_limit.is_none() => {
                layer.context_limit = Some(
                    value
                        .parse::<usize>()
                        .ok()
                        .filter(|n| (1024..=65_536).contains(n))
                        .ok_or("E_CONTEXT: expected 1024..65536 bytes")?,
                )
            }
            _ => return Err("E_ARGS: unknown or duplicate explain option"),
        }
    }
    Ok(layer)
}
fn config_command(args: &[OsString]) -> Result<(), &'static str> {
    if args.is_empty() || args == [OsString::from("show")] {
        print!("{}", configuration(&Layer::default())?.render());
        return Ok(());
    }
    if !(args.len() == 3 || args.len() == 4) || args[1] != "--file" {
        return Err(
            "E_ARGS: config [show | validate --file FILE | migrate/rollback --file FILE [--apply|--dry-run]]",
        );
    }
    let path = Path::new(&args[2]);
    match args[0].to_str() {
        Some("validate") if args.len() == 3 => {
            let source = read_optional(path)
                .map_err(|e| e.code())?
                .ok_or(ConfigError::Missing.code())?;
            Layer::parse(&source, Origin::User).map_err(|e| e.code())?;
            println!("Configuration valid: codex-smart schema 1; unknown values omitted");
        }
        Some(command @ ("migrate" | "rollback")) => {
            let apply = args.get(3).is_some_and(|v| v == "--apply");
            if args.len() == 4 && !apply && args[3] != "--dry-run" {
                return Err("E_ARGS: expected --apply or --dry-run");
            }
            let plan = if command == "migrate" {
                MigrationPlan::prepare(path)
            } else {
                MigrationPlan::rollback(path)
            }
            .map_err(|e| e.code())?;
            print!("{}", plan.preview());
            if apply {
                // Make the safe diff visible before any attempted mutation.
                use std::io::Write;
                std::io::stdout()
                    .flush()
                    .map_err(|_| "E_OUTPUT: could not show transaction diff")?;
                plan.apply().map_err(|e| e.code())?;
                println!("Transaction completed");
            }
        }
        _ => return Err("E_ARGS: invalid config command"),
    }
    Ok(())
}
fn read_tool_lock(path: &Path) -> Result<ToolLock, &'static str> {
    let source = read_optional(path)
        .map_err(|e| e.code())?
        .ok_or(LockError::Missing.code())?;
    ToolLock::parse(&source).map_err(|e| e.code())
}
fn diagnostic_options(
    args: &[OsString],
) -> Result<(Option<ToolLock>, Vec<OsString>), &'static str> {
    let mut lock = None;
    let mut remaining = Vec::new();
    let mut index = 0;
    while index < args.len() {
        if args[index] == "--tool-lock" {
            if lock.is_some() || index + 1 == args.len() {
                return Err("E_ARGS: --tool-lock requires one file and may not be repeated");
            }
            lock = Some(read_tool_lock(Path::new(&args[index + 1]))?);
            index += 2;
        } else {
            remaining.push(args[index].clone());
            index += 1;
        }
    }
    Ok((lock, remaining))
}
fn launch(mut args: Vec<OsString>, explicit_run: bool) -> Result<i32, &'static str> {
    let mut dry_run = false;
    let mut lock = None;
    if explicit_run {
        loop {
            if args.first().is_some_and(|a| a == "--dry-run") {
                if dry_run {
                    return Err("E_ARGS: --dry-run may not be repeated");
                }
                dry_run = true;
                args.remove(0);
            } else if args.first().is_some_and(|a| a == "--tool-lock") {
                if lock.is_some() || args.len() < 2 {
                    return Err("E_ARGS: --tool-lock requires one file and may not be repeated");
                }
                lock = Some(read_tool_lock(Path::new(&args[1]))?);
                args.drain(..2);
            } else {
                break;
            }
        }
    }
    if args.first().is_some_and(|a| a == "--") {
        args.remove(0);
    }
    let mut plan = LaunchPlan::prepare(std::env::var_os("PATH").as_deref(), &cwd()?, args)
        .map_err(|e| e.code())?;
    if let Some(lock) = lock {
        let pin = lock
            .pin(Capability::Codex)
            .ok_or("E_CODEX_PIN: tool lock must include a Codex pin")?;
        plan = plan.require_pin(pin).map_err(|e| e.code())?;
    }
    if dry_run {
        print!("{}", plan.summary());
        Ok(0)
    } else {
        plan.execute().map_err(|e| e.code())
    }
}
fn execute(mut args: Vec<OsString>) -> Result<i32, &'static str> {
    let command = args.first().and_then(|a| a.to_str());
    match command {
        Some("--version" | "-V" | "version") if args.len() == 1 => {
            println!("codex-smart {VERSION}")
        }
        Some("--help" | "-h" | "help") if args.len() == 1 => println!(
            "codex-smart {VERSION}\nCommands: run [--tool-lock FILE] [--dry-run] [--] [codex args...], doctor/capabilities [--tool-lock FILE], explain [--tool-lock FILE] [--task KIND] [--reasoning medium|high] [--context-limit BYTES], config [show|validate|migrate|rollback], version\nOther arguments pass through to Codex. Use -- to pass a reserved command name. Config transactions default to dry-run; use --file FILE and explicit --apply. Tool pins are explicit; versions/health remain unverified."
        ),
        Some("doctor" | "capabilities") => {
            let (lock, remaining) = diagnostic_options(&args[1..])?;
            if !remaining.is_empty() {
                return Err("E_ARGS: diagnostics do not accept extra arguments");
            }
            let inventory = Inventory::discover(std::env::var_os("PATH").as_deref(), &cwd()?);
            println!("codex-smart {VERSION}\n{}", inventory.render());
            let mut artifact_ok = true;
            if let Some(lock) = lock {
                let (report, verified) = lock.report(&inventory, command == Some("doctor"));
                print!("{report}");
                artifact_ok = verified;
            }
            if command == Some("doctor") {
                match configuration(&Layer::default()) {
                    Ok(resolved) => print!("{}", resolved.render()),
                    Err(error) => {
                        println!("Configuration: {error}");
                        return Ok(1);
                    }
                }
            }
            if !artifact_ok {
                return Ok(1);
            }
        }
        Some("explain" | "--explain") => {
            let (lock, remaining) = diagnostic_options(&args[1..])?;
            let resolved = configuration(&explain_overrides(&remaining)?)?;
            let inventory = Inventory::discover(std::env::var_os("PATH").as_deref(), &cwd()?);
            let mut decision = decide(resolved.task, &inventory);
            decision.reasoning = resolved.reasoning;
            print!(
                "{}{}{}",
                resolved.render(),
                inventory.render(),
                decision.render()
            );
            if let Some(lock) = lock {
                print!("{}", lock.report(&inventory, false).0);
            }
        }
        Some("config") => config_command(&args[1..])?,
        Some("run") => {
            args.remove(0);
            return launch(args, true);
        }
        Some("--version" | "-V" | "version" | "--help" | "-h" | "help") => {
            return Err("E_ARGS: unexpected arguments");
        }
        _ => return launch(args, false),
    }
    Ok(0)
}
fn main() -> ExitCode {
    match execute(std::env::args_os().skip(1).collect()) {
        Ok(code) => ExitCode::from(u8::try_from(code).unwrap_or(1)),
        Err(error) => {
            eprintln!("{error}");
            ExitCode::from(2)
        }
    }
}
