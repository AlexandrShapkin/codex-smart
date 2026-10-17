//! Private JSONL transport. Only allowlisted aggregate fields reach stdout.
use codex_smart_core::process::LaunchPlan;
use std::path::Path;

#[cfg(not(target_os = "linux"))]
pub fn execute(_: LaunchPlan, _: Option<&Path>, _: u64) -> Result<i32, &'static str> {
    Err("E_INSPECT_PLATFORM: supervised inspection requires Linux")
}

#[cfg(target_os = "linux")]
pub fn execute(plan: LaunchPlan, answer: Option<&Path>, seconds: u64) -> Result<i32, &'static str> {
    use codex_smart_core::process::ProcessOutcome;
    use std::{fs::OpenOptions, io::Write, os::unix::fs::OpenOptionsExt, time::Duration};
    // Reserve before launching: existing files and symlinks refuse without any call.
    // Keep the opened inode; never pass a caller path to Codex or reopen it.
    let mut file = match answer {
        Some(path) => Some(
            OpenOptions::new()
                .write(true)
                .create_new(true)
                .mode(0o600)
                .open(path)
                .map_err(|_| "E_INSPECT_ANSWER: private exclusive-create failed; no launch")?,
        ),
        None => None,
    };
    let output = plan.supervise(Duration::from_secs(seconds));
    let parsed = parse(&output.stdout);
    let mut status = match output.outcome {
        ProcessOutcome::Timeout => "Timeout",
        ProcessOutcome::Interrupted => "Interrupted",
        ProcessOutcome::Success if parsed.valid && parsed.completed => "CompletedSuccess",
        ProcessOutcome::Success | ProcessOutcome::Failure if parsed.valid => "CompletedFailure",
        _ => "Unknown",
    };
    let mut answer_status = if file.is_some() {
        "Unavailable"
    } else {
        "NotRequested"
    };
    if matches!(status, "CompletedSuccess" | "CompletedFailure")
        && let (Some(file), Some(answer)) = (file.as_mut(), parsed.answer.as_ref())
    {
        if file
            .write_all(answer.as_bytes())
            .and_then(|_| file.sync_all())
            .is_ok()
        {
            answer_status = "Written";
        } else {
            answer_status = "WriteFailed";
            status = "Unknown";
        }
    }
    // A partial/invalid transport cannot establish authoritative usage.
    let usage = if parsed.valid {
        parsed.usage
    } else {
        [None; 5]
    };
    let report = serde_json::json!({
        "status": status,
        "usage": {"input_tokens": usage[0], "cached_input_tokens": usage[1], "output_tokens": usage[2], "cache_write_input_tokens": usage[3], "reasoning_output_tokens": usage[4]},
        "answer_file": answer_status,
    });
    println!("{report}");
    Ok(match status {
        "CompletedSuccess" => 0,
        "CompletedFailure" => 1,
        "Timeout" => 124,
        "Interrupted" => 130,
        _ => 2,
    })
}

#[cfg(target_os = "linux")]
#[derive(Default)]
struct Parsed {
    valid: bool,
    completed: bool,
    failed: bool,
    usage: [Option<u64>; 5],
    answer: Option<String>,
}

#[cfg(target_os = "linux")]
fn parse(bytes: &[u8]) -> Parsed {
    use serde_json::Value;
    let mut result = Parsed::default();
    // Require JSONL framing, start events and exactly one terminal event.
    if !bytes.ends_with(b"\n") {
        return result;
    }
    let mut thread = false;
    let mut turn = false;
    for line in bytes.split(|b| *b == b'\n').filter(|line| !line.is_empty()) {
        let Ok(value) = serde_json::from_slice::<Value>(line) else {
            return Parsed::default();
        };
        let Some(kind) = value.get("type").and_then(Value::as_str) else {
            return Parsed::default();
        };
        if result.completed || result.failed {
            return Parsed::default();
        }
        match kind {
            "thread.started" if !thread && !turn => thread = true,
            "turn.started" if thread && !turn => turn = true,
            "turn.completed" if turn => {
                result.completed = true;
                for (i, key) in [
                    "input_tokens",
                    "cached_input_tokens",
                    "output_tokens",
                    "cache_write_input_tokens",
                    "reasoning_output_tokens",
                ]
                .iter()
                .enumerate()
                {
                    result.usage[i] = value
                        .get("usage")
                        .and_then(|u| u.get(key))
                        .and_then(Value::as_u64);
                }
            }
            "turn.failed" if turn => result.failed = true,
            "item.started" | "item.updated" | "item.completed" if turn => {
                if kind == "item.completed" && value["item"]["type"] == "agent_message" {
                    let Some(text) = value["item"]["text"].as_str() else {
                        return Parsed::default();
                    };
                    result.answer = Some(text.to_owned());
                }
            }
            // Error payload is private. A turn.failed terminal is still required.
            "error" if thread => {}
            _ => return Parsed::default(),
        }
    }
    result.valid = thread && turn && (result.completed || result.failed);
    result
}
