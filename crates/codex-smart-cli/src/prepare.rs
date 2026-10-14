//! One explicit preparation attempt; no discovery, configuration or model execution.
use crate::plan;
use codex_smart_core::{
    playbook::ContextObligation,
    preparation::{Limits, Request},
    preparation_supervision::State,
    preparation_wire::{Intent, PreparationRequest, VERSION},
    preparation_worker::{Outcome, WorkerPin, run_local_preparation},
    workflow::SelectionStatus,
};
use std::{ffi::OsString, path::Path, time::Duration};

pub const HELP: &str = "prepare --intent inspection --worker ABSOLUTE_PATH --worker-sha256 INDEPENDENT_SHA256 --worker-protocol 1 [--deadline-ms 1..250] [--cleanup-ms 1..250] [--task inspect] [--risk low|medium|high] [--safety none|security|migration|concurrency] [--file RELATIVE_PATH ...]\nOne supervised local acquisition attempt; public nominations only. Semantic sufficiency remains Unknown. No model or validation execution. Worker verification/spawn are outside the post-spawn deadline.";
const INVALID: &str =
    "E_PREPARE_ARGS: invalid, unsupported, missing or duplicate preparation option";

fn digest(value: &str) -> Result<[u8; 32], &'static str> {
    if value.len() != 64 || !value.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(INVALID);
    }
    let mut result = [0; 32];
    for (byte, pair) in result.iter_mut().zip(value.as_bytes().as_chunks::<2>().0) {
        *byte = u8::from_str_radix(std::str::from_utf8(pair).map_err(|_| INVALID)?, 16)
            .map_err(|_| INVALID)?;
    }
    Ok(result)
}
fn budget(value: &str) -> Result<Duration, &'static str> {
    if !value.bytes().all(|b| b.is_ascii_digit()) {
        return Err(INVALID);
    }
    value
        .parse::<u64>()
        .ok()
        .filter(|n| (1..=250).contains(n))
        .map(Duration::from_millis)
        .ok_or(INVALID)
}

pub fn execute(args: &[OsString], root: &Path) -> Result<(String, i32), &'static str> {
    // Existing plan bound plus five singleton runtime options. No input is echoed.
    if args.len() > 50
        || args.iter().map(|a| a.len()).sum::<usize>() > 20_480
        || !args.len().is_multiple_of(2)
    {
        return Err(INVALID);
    }
    let (mut executable, mut sha256, mut protocol, mut deadline, mut cleanup) =
        (None, None, None, None, None);
    let mut declarative = Vec::new();
    for pair in args.as_chunks::<2>().0 {
        let value = pair[1].to_str().ok_or(INVALID)?;
        match pair[0].to_str() {
            Some("--worker") if executable.is_none() => {
                let path = Path::new(value);
                if !path.is_absolute() || value.len() > 1024 || value.contains('\0') {
                    return Err(INVALID);
                }
                executable = Some(path.to_path_buf());
            }
            Some("--worker-sha256") if sha256.is_none() => sha256 = Some(digest(value)?),
            Some("--worker-protocol") if protocol.is_none() && value == "1" => {
                protocol = Some(VERSION)
            }
            Some("--deadline-ms") if deadline.is_none() => deadline = Some(budget(value)?),
            Some("--cleanup-ms") if cleanup.is_none() => cleanup = Some(budget(value)?),
            Some("--intent" | "--task" | "--risk" | "--safety" | "--file") => {
                declarative.extend_from_slice(pair)
            }
            _ => return Err(INVALID),
        }
    }
    let pin = WorkerPin {
        executable: executable.ok_or(INVALID)?,
        sha256: sha256.ok_or(INVALID)?,
        protocol: protocol.ok_or(INVALID)?,
    };
    let plan = plan::parse(&declarative)?;
    if plan.workflow.selection.status != SelectionStatus::Selected {
        return Err("E_PREPARE_PLAN: inspection selection requires compatible task evidence");
    }
    let deadline = deadline.unwrap_or(Duration::from_millis(250));
    let request = PreparationRequest {
        root: root.to_path_buf(),
        intent: Intent::Inspection,
        files: plan
            .files
            .into_iter()
            .map(|path| Request {
                path,
                obligation: ContextObligation::RelevantFiles,
            })
            .collect(),
        limits: Limits {
            elapsed: deadline,
            ..Limits::default()
        },
    };
    // Encoding applies the existing full scope/protocol bounds before artifact admission.
    request
        .encode()
        .map_err(|_| "E_PREPARE_SCOPE: invalid preparation scope")?;
    match run_local_preparation(
        &pin,
        &request,
        deadline,
        cleanup.unwrap_or(Duration::from_millis(250)),
    ) {
        Ok(outcome) => {
            let (summary, code) = render(&outcome);
            Ok((
                format!("Declarative inspection plan:\n{}{summary}", plan.summary),
                code,
            ))
        }
        Err(error) => Ok((
            format!(
                "Declarative inspection plan:\n{}Preparation refused: {error:?}\nSemantic context sufficiency: Unknown\nProduction admission: closed\n",
                plan.summary
            ),
            2,
        )),
    }
}

fn render(outcome: &Outcome) -> (String, i32) {
    let summary = outcome
        .preparation
        .as_ref()
        .map(|p| p.summary())
        .unwrap_or_else(|| "acquisition unavailable".into());
    let code = if outcome.state == State::Succeeded
        && outcome
            .preparation
            .as_ref()
            .is_some_and(|p| p.failure.is_none())
    {
        0
    } else {
        2
    };
    (
        format!(
            "Preparation state: {:?}\nWorker exit: {:?}\nAcquisition: {summary}\nSemantic context sufficiency: Unknown\nProduction admission: closed\n",
            outcome.state, outcome.worker_exit_code
        ),
        code,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn missing_malformed_and_excessive_authority_inputs_refuse_before_admission() {
        for args in [
            vec!["--intent", "inspection"],
            vec!["--intent", "inspection", "--worker", "/PRIVATE"],
            vec!["--worker", "PRIVATE"],
            vec!["--worker-sha256", "PRIVATE"],
            vec!["--worker-protocol", "2"],
            vec!["--deadline-ms", "251"],
            vec!["--cleanup-ms", "PRIVATE"],
            vec!["--intent"],
        ] {
            let args: Vec<_> = args.into_iter().map(OsString::from).collect();
            let error = execute(&args, Path::new("/tmp")).err().unwrap();
            assert!(!error.contains("PRIVATE"));
        }
        let excessive = vec![OsString::from("PRIVATE"); 52];
        assert!(execute(&excessive, Path::new("/tmp")).is_err());
        let oversized = vec![
            OsString::from("--worker"),
            OsString::from("x".repeat(20_481)),
        ];
        assert!(execute(&oversized, Path::new("/tmp")).is_err());
    }

    #[test]
    fn cleanup_uncertainty_and_private_payload_are_retained_without_disclosure() {
        use codex_smart_core::preparation::{Preparation, Snippet};
        let outcome = Outcome {
            state: State::CleanupUnknown,
            preparation: Some(Preparation {
                snippets: vec![Snippet {
                    request: Request {
                        path: "PRIVATE_PATH".into(),
                        obligation: ContextObligation::RelevantFiles,
                    },
                    text: "PRIVATE_SOURCE".into(),
                    sha256: "PRIVATE_DIGEST".into(),
                }],
                ..Default::default()
            }),
            elapsed: Duration::from_millis(500),
            worker_exit_code: None,
        };
        let (text, code) = render(&outcome);
        assert_eq!(code, 2);
        assert!(text.contains("CleanupUnknown"));
        assert!(text.contains("Semantic context sufficiency: Unknown"));
        assert!(!text.contains("PRIVATE"));
    }
}
