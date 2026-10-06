//! Offline evidence only. No subprocesses, recursive scans, auth reads or writes.
use crate::{
    VERSION,
    capability::{Availability, Capability, Inventory},
    config::MAX_CONFIG_BYTES,
    migration::read_optional,
    tool_lock::{ArtifactEvidence, CapabilityEvidence, MAX_VERIFY_BYTES, ToolLock, fingerprint},
};
use std::path::Path;
use toml_edit::DocumentMut;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CheckState {
    Pass,
    Warn,
    Fail,
    Unknown,
    NotChecked,
}
impl CheckState {
    pub fn name(self) -> &'static str {
        match self {
            Self::Pass => "PASS",
            Self::Warn => "WARN",
            Self::Fail => "FAIL",
            Self::Unknown => "UNKNOWN",
            Self::NotChecked => "NOT_CHECKED",
        }
    }
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DiagnosticCheck {
    pub id: &'static str,
    pub required: bool,
    pub state: CheckState,
    /// Allowlisted fact and explanation, never external values or paths.
    pub fact: &'static str,
    pub explanation: &'static str,
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CapabilityDiagnostic {
    pub capability: Capability,
    pub evidence: CapabilityEvidence,
    pub artifact: ArtifactEvidence,
}
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct DoctorReport {
    pub checks: Vec<DiagnosticCheck>,
    pub capabilities: Vec<CapabilityDiagnostic>,
}
impl DoctorReport {
    pub fn add(
        &mut self,
        id: &'static str,
        required: bool,
        state: CheckState,
        fact: &'static str,
        explanation: &'static str,
    ) {
        self.checks.push(DiagnosticCheck {
            id,
            required,
            state,
            fact,
            explanation,
        });
    }
    pub fn exit_code(&self) -> i32 {
        i32::from(
            self.checks
                .iter()
                .any(|c| c.required && c.state == CheckState::Fail),
        )
    }
    pub fn collect(
        repo: &Path,
        inventory: &Inventory,
        lock: Option<&ToolLock>,
        config: Result<(), &'static str>,
        codex_config: Option<&Path>,
    ) -> Self {
        let mut report = Self::default();
        match config {
            Ok(()) => report.add(
                "launcher_config",
                true,
                CheckState::Pass,
                "valid",
                "Configuration: marked schema 1 or built-in defaults; values omitted",
            ),
            Err(error) => report.add("launcher_config", true, CheckState::Fail, "rejected", error),
        }
        let found = inventory.found(Capability::Codex);
        report.add(
            "codex_executable",
            true,
            if found {
                CheckState::Pass
            } else {
                CheckState::Fail
            },
            if found { "discovered" } else { "absent" },
            "PATH metadata only; version/auth readiness unverified",
        );
        for entry in &inventory.0 {
            let pin = lock.and_then(|l| l.pin(entry.capability));
            let artifact = match pin {
                None => ArtifactEvidence::Deferred,
                Some(pin) => match entry.executable.as_deref() {
                    None => ArtifactEvidence::Missing,
                    Some(path) => match fingerprint(path, MAX_VERIFY_BYTES) {
                        Ok((sum, _)) if sum == pin.checksum => ArtifactEvidence::Match,
                        Ok(_) => ArtifactEvidence::Mismatch,
                        Err(_) => ArtifactEvidence::Rejected,
                    },
                },
            };
            if pin.is_some() {
                report.add(
                    "codex_artifact",
                    true,
                    if artifact == ArtifactEvidence::Match {
                        CheckState::Pass
                    } else {
                        CheckState::Fail
                    },
                    artifact_name(artifact),
                    "Explicit entrypoint digest only; declaration and dependencies not attested",
                );
            }
            report.capabilities.push(CapabilityDiagnostic {
                capability: entry.capability,
                artifact,
                evidence: CapabilityEvidence::assess(
                    entry.capability,
                    entry.executable.is_some(),
                    pin.map(|p| p.version),
                    artifact,
                ),
            });
        }
        directory_check(&mut report, "workspace_readable", repo, false);
        directory_check(&mut report, "workspace_writable", repo, true);
        let git = repo.join(".git");
        // Linked worktrees/submodules are deliberately not followed from untrusted gitdir files.
        let git_dir = std::fs::symlink_metadata(&git).is_ok_and(|m| m.is_dir());
        report.add(
            "git_repository",
            false,
            if git_dir {
                CheckState::Pass
            } else {
                CheckState::Unknown
            },
            if git_dir {
                "directory present"
            } else {
                "not established"
            },
            "Metadata only; gitdir indirection and parent repositories not followed",
        );
        directory_check(&mut report, "git_metadata_writable", &git, true);
        remote_check(&mut report, &git.join("config"));
        for id in [
            "network",
            "github_api",
            "github_auth",
            "git_remote_connectivity",
            "codex_auth",
            "mcp_handshake",
        ] {
            report.add(
                id,
                false,
                CheckState::NotChecked,
                "offline",
                "No subprocess, credentials, network or session probe",
            );
        }
        for (id, path) in [
            ("serena_project_marker", repo.join(".serena/project.yml")),
            ("codegraph_index_marker", repo.join(".code-graph/index")),
        ] {
            let fact = marker_status(&path);
            report.add(
                id,
                false,
                CheckState::Unknown,
                fact,
                "Conventional marker metadata only; format/freshness/project readiness unknown",
            );
        }
        report.add(
            "index_readiness",
            false,
            CheckState::Unknown,
            "unknown",
            "No index created, read recursively or freshness inferred",
        );
        match codex_config {
            None => report.add(
                "codex_config",
                false,
                CheckState::NotChecked,
                "not supplied",
                "Use --codex-config FILE for explicit single-file analysis; stores not discovered",
            ),
            Some(path) if path.extension().is_none_or(|ext| ext != "toml") => report.add(
                "codex_config",
                true,
                CheckState::Fail,
                "unsupported file kind",
                "Explicit configuration must be a .toml path; other files are not opened",
            ),
            Some(path) => match read_optional(path) {
                Ok(Some(source)) => analyze_codex_config(&mut report, &source, repo),
                Ok(None) => report.add(
                    "codex_config",
                    true,
                    CheckState::Fail,
                    "absent",
                    "Explicit configuration file missing",
                ),
                Err(error) => report.add(
                    "codex_config",
                    true,
                    CheckState::Fail,
                    "rejected",
                    error.code(),
                ),
            },
        }
        report.add(
            "effective_codex_config",
            false,
            CheckState::Unknown,
            "not resolved",
            "CLI/profile/managed/project precedence not evaluated; single-file facts only",
        );
        report
    }
    pub fn human(&self) -> String {
        let mut out = format!("codex-smart {VERSION} doctor (offline)\nChecks\n");
        for c in &self.checks {
            out.push_str(&format!("  {} {}: {}", c.state.name(), c.id, c.fact));
            if matches!(c.state, CheckState::Warn | CheckState::Fail) {
                out.push_str(&format!("; {}", c.explanation));
            }
            out.push('\n');
        }
        out.push_str("Access checks are hints, not mutation proof; full effective Codex config is unknown.\n");
        out.push_str("Capabilities (discovery != compatibility != readiness)\n");
        for c in &self.capabilities {
            out.push_str(&format!("  {}: {}; declared version {}; artifact: {}; runtime version: unknown; compatibility: {}; contract: {}; ready: {}\n",c.capability.name(),availability_name(c.evidence.available),c.evidence.declared_version.map_or_else(||"unknown".into(),|v|v.to_string()),artifact_name(c.artifact),c.evidence.compatibility.name(),c.evidence.execution_contract.name(),c.evidence.readiness.name()));
        }
        let required = self.checks.iter().filter(|c| c.required).count();
        let pass = self
            .checks
            .iter()
            .filter(|c| c.required && c.state == CheckState::Pass)
            .count();
        out.push_str(&format!("Summary: required {pass}/{required} pass; exit {}; mutations: none; network: not used\n",self.exit_code()));
        out
    }
    /// Schema 1 uses the same typed checks/evidence as human output. Only allowlisted
    /// text, booleans and strict numeric versions can reach this encoder.
    pub fn json(&self) -> String {
        let checks = self
            .checks
            .iter()
            .map(|c| {
                format!(
                    "{{\"id\":{},\"required\":{},\"state\":{},\"fact\":{},\"explanation\":{}}}",
                    quote(c.id),
                    c.required,
                    quote(c.state.name()),
                    quote(c.fact),
                    quote(c.explanation)
                )
            })
            .collect::<Vec<_>>()
            .join(",");
        let caps=self.capabilities.iter().map(|c|format!("{{\"id\":{},\"discovered\":{},\"declared_version\":{},\"runtime_version\":null,\"artifact\":{},\"compatibility\":{},\"execution_contract\":{},\"readiness\":{}}}",quote(c.capability.name()),match c.evidence.available {Availability::Discovered=>"true",Availability::NotFound=>"false",Availability::SessionUnknown=>"null"},c.evidence.declared_version.map_or_else(||"null".into(),|v|quote(&v.to_string())),quote(artifact_name(c.artifact)),quote(c.evidence.compatibility.name()),quote(c.evidence.execution_contract.name()),quote(c.evidence.readiness.name()))).collect::<Vec<_>>().join(",");
        format!(
            "{{\"schema_version\":1,\"mode\":\"offline\",\"version\":{},\"checks\":[{}],\"capabilities\":[{}],\"exit_code\":{},\"mutations\":false,\"network_used\":false}}\n",
            quote(VERSION),
            checks,
            caps,
            self.exit_code()
        )
    }
}
fn quote(s: &str) -> String {
    let mut out = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            c if c.is_control() => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}
fn availability_name(a: Availability) -> &'static str {
    match a {
        Availability::Discovered => "found: PATH metadata only",
        Availability::NotFound => "not found on trusted PATH",
        Availability::SessionUnknown => "unknown: session integration not probed",
    }
}
fn artifact_name(a: ArtifactEvidence) -> &'static str {
    match a {
        ArtifactEvidence::Deferred => "not checked",
        ArtifactEvidence::Match => "SHA-256 matches",
        ArtifactEvidence::Mismatch => "SHA-256 mismatch",
        ArtifactEvidence::Missing => "executable missing",
        ArtifactEvidence::Rejected => "unsafe, oversized or changed artifact rejected",
    }
}
fn directory_check(report: &mut DoctorReport, id: &'static str, path: &Path, write: bool) {
    let meta = std::fs::symlink_metadata(path);
    let (state, fact) = match meta {
        Ok(m) if m.is_dir() => directory_access(path, write),
        _ => (
            CheckState::Unknown,
            "directory unavailable or symlink refused",
        ),
    };
    report.add(id,false,state,fact,"Metadata/effective access hint only; mount/sandbox/ACL/races may still deny writes; no mutation proof");
}
#[cfg(target_os = "linux")]
fn directory_access(path: &Path, write: bool) -> (CheckState, &'static str) {
    use rustix::fs::{Access, AtFlags, Mode, OFlags, ResolveFlags, accessat, openat2};
    use std::fs::File;
    use std::os::unix::fs::MetadataExt;
    let opened = (|| {
        let root = File::open("/").ok()?;
        let relative = path.strip_prefix("/").ok()?;
        let fd = openat2(
            &root,
            relative,
            OFlags::RDONLY | OFlags::DIRECTORY | OFlags::CLOEXEC,
            Mode::empty(),
            ResolveFlags::BENEATH | ResolveFlags::NO_SYMLINKS | ResolveFlags::NO_MAGICLINKS,
        )
        .ok()?;
        Some(File::from(fd))
    })();
    let Some(dir) = opened else {
        return (CheckState::Unknown, "directory unsafe or inaccessible");
    };
    let Ok(m) = dir.metadata() else {
        return (CheckState::Unknown, "metadata unavailable");
    };
    if write && m.mode() & 0o222 == 0 {
        return (CheckState::Warn, "apparently read-only: no write mode bits");
    }
    match accessat(
        &dir,
        ".",
        if write {
            Access::WRITE_OK | Access::EXEC_OK
        } else {
            Access::READ_OK | Access::EXEC_OK
        },
        AtFlags::EACCESS,
    ) {
        Ok(()) => (
            CheckState::Pass,
            if write {
                "apparently writable"
            } else {
                "apparently readable"
            },
        ),
        Err(_) => (CheckState::Warn, "effective access denied or unsupported"),
    }
}
#[cfg(not(target_os = "linux"))]
fn directory_access(_path: &Path, _write: bool) -> (CheckState, &'static str) {
    (CheckState::Unknown, "access adapter unavailable")
}
#[cfg(target_os = "linux")]
fn marker_status(path: &Path) -> &'static str {
    use rustix::fs::{Mode, OFlags, ResolveFlags, openat2};
    use std::fs::File;
    let Ok(root) = File::open("/") else {
        return "unknown";
    };
    let Ok(relative) = path.strip_prefix("/") else {
        return "unknown";
    };
    match openat2(
        &root,
        relative,
        OFlags::PATH | OFlags::CLOEXEC,
        Mode::empty(),
        ResolveFlags::BENEATH | ResolveFlags::NO_SYMLINKS | ResolveFlags::NO_MAGICLINKS,
    ) {
        Ok(fd) => {
            if File::from(fd).metadata().is_ok_and(|m| m.is_file()) {
                "present"
            } else {
                "unknown"
            }
        }
        Err(rustix::io::Errno::NOENT) => "absent",
        _ => "unknown",
    }
}
#[cfg(not(target_os = "linux"))]
fn marker_status(_path: &Path) -> &'static str {
    "unknown"
}
fn remote_check(report: &mut DoctorReport, path: &Path) {
    let source = match read_optional(path) {
        Ok(Some(s)) => s,
        _ => {
            report.add(
                "git_origin",
                false,
                CheckState::Unknown,
                "not established",
                "Config absent/unsafe/unreadable; includes and Git config precedence not resolved",
            );
            return;
        }
    };
    let mut origin = false;
    let mut url = None;
    let mut ambiguous = false;
    for line in source.lines() {
        let line = line.trim();
        if line.starts_with('[') {
            origin = line == "[remote \"origin\"]";
            if line.starts_with("[include") {
                ambiguous = true;
            }
        } else if origin
            && let Some((key, value)) = line.split_once('=')
            && key.trim() == "url"
        {
            if url.is_some() {
                ambiguous = true;
            }
            url = Some(value.trim());
        }
    }
    let fact = if ambiguous {
        "unknown: includes or multiple URLs"
    } else {
        match url {
            Some(v) if v.starts_with("https://") => "origin configured: https",
            Some(v) if v.starts_with("ssh://") || v.contains('@') => "origin configured: ssh-like",
            Some(_) => "origin configured: transport unknown",
            None => "origin not found in local config",
        }
    };
    report.add("git_origin",false,if ambiguous {CheckState::Unknown} else {CheckState::Pass},fact,"Bounded local config syntax hint; URLs/credentials omitted; rewrites/includes/global config not resolved");
}
fn analyze_codex_config(report: &mut DoctorReport, source: &str, repo: &Path) {
    let parsed = if source.len() > MAX_CONFIG_BYTES {
        None
    } else {
        source.parse::<DocumentMut>().ok()
    };
    let Some(doc) = parsed else {
        report.add(
            "codex_config",
            true,
            CheckState::Fail,
            "invalid",
            "TOML/size invalid; values omitted",
        );
        return;
    };
    let typed = doc
        .get("default_permissions")
        .is_none_or(|v| v.as_str().is_some())
        && doc.get("sandbox_mode").is_none_or(|v| {
            matches!(
                v.as_str(),
                Some("read-only" | "workspace-write" | "danger-full-access")
            )
        })
        && doc.get("approval_policy").is_none_or(|v| {
            matches!(
                v.as_str(),
                Some("untrusted" | "on-failure" | "on-request" | "never")
            )
        })
        && [
            "permissions",
            "sandbox_workspace_write",
            "profiles",
            "projects",
            "mcp_servers",
        ]
        .iter()
        .all(|k| doc.get(k).is_none_or(|v| v.as_table().is_some()));
    let typed = typed
        && doc
            .get("mcp_servers")
            .and_then(|v| v.as_table())
            .is_none_or(|servers| {
                servers.len() <= 32
                    && servers.iter().all(|(_, record)| {
                        record.as_table().is_some_and(|t| {
                            t.get("enabled").is_none_or(|v| v.as_bool().is_some())
                                && t.get("required").is_none_or(|v| v.as_bool().is_some())
                                && ["command", "url"]
                                    .iter()
                                    .all(|k| t.get(k).is_none_or(|v| v.as_str().is_some()))
                                && !(t.contains_key("command") && t.contains_key("url"))
                                && t.get("args").is_none_or(|v| {
                                    v.as_array()
                                        .is_some_and(|a| a.iter().all(|v| v.as_str().is_some()))
                                })
                        })
                    })
            });
    report.add(
        "codex_config",
        true,
        if typed {
            CheckState::Pass
        } else {
            CheckState::Fail
        },
        if typed {
            "readable and parseable"
        } else {
            "invalid selected field types"
        },
        "Allowlisted subset only; unknown fields inert; not full upstream schema validation",
    );
    if !typed {
        return;
    }
    let conflict = doc.contains_key("default_permissions")
        && (doc.contains_key("sandbox_mode") || doc.contains_key("sandbox_workspace_write"));
    report.add(
        "codex_permission_mechanism",
        true,
        if conflict {
            CheckState::Fail
        } else {
            CheckState::Pass
        },
        if conflict {
            "conflicting profile and legacy settings"
        } else if doc.contains_key("default_permissions") {
            "named profile selected"
        } else if doc.contains_key("sandbox_mode") || doc.contains_key("sandbox_workspace_write") {
            "legacy sandbox selected"
        } else {
            "unspecified"
        },
        "Single-file selection; active CLI/profile/managed overrides unknown",
    );
    if let Some(name) = doc.get("default_permissions").and_then(|v| v.as_str()) {
        let known = name.starts_with(':')
            || doc
                .get("permissions")
                .and_then(|v| v.as_table())
                .is_some_and(|t| t.contains_key(name));
        report.add(
            "codex_permission_profile",
            false,
            if known {
                CheckState::Unknown
            } else {
                CheckState::Warn
            },
            if known {
                "selector present"
            } else {
                "selected definition absent in file"
            },
            "Profile contents and cross-layer definition not validated; selector value omitted",
        );
    }
    let trust = doc
        .get("projects")
        .and_then(|v| v.as_table())
        .and_then(|t| repo.to_str().and_then(|p| t.get(p)))
        .and_then(|v| v.as_table())
        .and_then(|t| t.get("trust_level"))
        .and_then(|v| v.as_str());
    report.add(
        "codex_project_trust",
        false,
        CheckState::Unknown,
        match trust {
            Some("trusted") => "declared trusted",
            Some("untrusted") => "declared untrusted",
            Some(_) => "invalid declaration",
            None => "not declared for exact cwd",
        },
        "Declaration only; project layers/ancestor selection/runtime trust not resolved",
    );
    let Some(servers) = doc.get("mcp_servers").and_then(|v| v.as_table()) else {
        report.add(
            "mcp_configuration",
            false,
            CheckState::Unknown,
            "absent in supplied file",
            "Session/plugins/other config layers not inspected",
        );
        return;
    };
    if servers.len() > 32 {
        report.add(
            "mcp_configuration",
            true,
            CheckState::Fail,
            "too many definitions",
            "At most 32 definitions analyzed; no commands executed",
        );
        return;
    }
    // Only names of supported capability families are mapped; arbitrary names never echoed.
    for (id, needle) in [
        ("serena_configuration", "serena"),
        ("codegraph_configuration", "codegraph"),
        ("context7_configuration", "context7"),
    ] {
        let mut matches = 0;
        let mut enabled = None;
        let mut transport = "unknown";
        let mut unsafe_command = false;
        let mut invalid = false;
        for (name, record) in servers {
            let normalized = name.to_ascii_lowercase().replace(['-', '_'], "");
            if !normalized.contains(needle) {
                continue;
            }
            matches += 1;
            let Some(table) = record.as_table() else {
                invalid = true;
                continue;
            };
            enabled = Some(
                table
                    .get("enabled")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(true),
            );
            if table.get("enabled").is_some_and(|v| v.as_bool().is_none()) {
                invalid = true;
            }
            let command = table.get("command").and_then(|v| v.as_str());
            let url = table.get("url").and_then(|v| v.as_str());
            invalid |= table.get("command").is_some_and(|v| v.as_str().is_none())
                || table.get("url").is_some_and(|v| v.as_str().is_none())
                || (command.is_some() && url.is_some());
            transport = if command.is_some() {
                "stdio declared"
            } else if url.is_some() {
                "HTTP URL declared; exact transport unknown"
            } else {
                "unknown"
            };
            if let Some(command) = command {
                let basename = Path::new(command)
                    .file_name()
                    .and_then(|v| v.to_str())
                    .unwrap_or("");
                unsafe_command |= matches!(
                    basename,
                    "npx" | "npm" | "uvx" | "uv" | "sh" | "bash" | "code-graph-smart"
                );
            }
            if table.get("args").is_some_and(|v| {
                v.as_array()
                    .is_none_or(|a| a.iter().any(|v| v.as_str().is_none()))
            }) {
                invalid = true;
            }
        }
        report.add(id,false,if invalid || matches>1 {CheckState::Warn} else {CheckState::Unknown},if invalid {"invalid selected definition"} else if matches>1 {"duplicate capability aliases"} else {match enabled {Some(true)=>"configured; enabled",Some(false)=>"configured; disabled",None=>"not identified in supplied file"}},"Name-based mapping only; aliases/plugin sessions may differ; no runtime readiness inferred");
        if matches > 0 {
            report.add(
                match id {
                    "serena_configuration" => "serena_transport",
                    "codegraph_configuration" => "codegraph_transport",
                    _ => "context7_transport",
                },
                false,
                if unsafe_command {
                    CheckState::Warn
                } else {
                    CheckState::Unknown
                },
                transport,
                if unsafe_command {
                    "Unsafe/unpinned installer or shell command; execution probe refused"
                } else {
                    "Artifact/version/compatibility/probe safety unknown; handshake not checked"
                },
            );
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn optional_unknown_warn_and_fail_do_not_determine_exit_status() {
        let mut report = DoctorReport::default();
        for state in [
            CheckState::Unknown,
            CheckState::NotChecked,
            CheckState::Warn,
            CheckState::Fail,
        ] {
            report.add("optional", false, state, "fixture", "fixture");
        }
        report.add("required", true, CheckState::Pass, "valid", "fixture");
        assert_eq!(report.exit_code(), 0);
        report.add("required", true, CheckState::Fail, "invalid", "fixture");
        assert_eq!(report.exit_code(), 1);
    }
    #[test]
    fn json_allowlist_encoder_escapes_controls_and_quotes() {
        assert_eq!(quote("\"\\\n\t\0"), "\"\\\"\\\\\\u000a\\u0009\\u0000\"");
    }
    #[test]
    fn permission_conflict_profile_and_types_have_stable_assessments() {
        let mut report = DoctorReport::default();
        analyze_codex_config(
            &mut report,
            "default_permissions=':workspace'\n[sandbox_workspace_write]\nnetwork_access=true",
            Path::new("/fixture"),
        );
        assert!(
            report
                .checks
                .iter()
                .any(|c| c.id == "codex_permission_mechanism" && c.state == CheckState::Fail)
        );
        let mut report = DoctorReport::default();
        analyze_codex_config(&mut report, "sandbox_mode=42", Path::new("/fixture"));
        assert_eq!(report.exit_code(), 1);
    }
}
