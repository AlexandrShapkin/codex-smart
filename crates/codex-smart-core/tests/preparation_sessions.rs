#![cfg(target_os = "linux")]
use codex_smart_core::{
    playbook::ContextObligation,
    preparation::*,
    routing::{
        assessment::{RoutingFacts, TaskKind, assess},
        engine::CapabilitySurface,
    },
    workflow::{NativeSurface, ResourceCatalog, plan_workflow},
};
use std::{
    fs,
    path::PathBuf,
    sync::atomic::{AtomicUsize, Ordering},
};
static ID: AtomicUsize = AtomicUsize::new(0);
struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let path = PathBuf::from(format!(
            "/tmp/preparation-{}-{}",
            std::process::id(),
            ID.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        fs::write(path.join("a.rs"), "fn a() {}\n").unwrap();
        fs::write(path.join("b.rs"), "fn b() {}\n").unwrap();
        Self(path)
    }
    fn run(&self, paths: &[&str], limits: Limits) -> Preparation {
        let assessment = assess(&RoutingFacts {
            known_operations: vec![TaskKind::Inspect],
            ..Default::default()
        });
        let native = NativeSurface::default();
        let plan = plan_workflow(
            &assessment,
            None,
            &native,
            &CapabilitySurface::default(),
            &ResourceCatalog::default(),
        );
        let requests: Vec<_> = paths
            .iter()
            .map(|p| Request {
                path: p.into(),
                obligation: ContextObligation::RelevantFiles,
            })
            .collect();
        prepare(&self.0, &plan, &native, &requests, limits)
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.0).unwrap();
    }
}
#[test]
fn deterministic_context_preserves_unknown_validation_and_obligations() {
    let f = Fixture::new();
    let a = f.run(&["b.rs", "a.rs"], Limits::default());
    let b = f.run(&["a.rs", "b.rs"], Limits::default());
    assert!(a.failure.is_none());
    assert!(!a.summary().contains("fn a"));
    assert!(!a.summary().contains("a.rs"));
    assert!(a.snippets == b.snippets);
    assert_eq!(a.snippets[0].text, "fn a() {}\n");
    assert_eq!(a.snippets[0].sha256.len(), 64);
    assert!(a.unresolved.contains(&ContextObligation::RepositoryState));
    assert_eq!(
        a.validation.unwrap().status,
        codex_smart_core::workflow::ValidationReadiness::NeedsEvidence
    );
}
#[test]
fn limits_and_incomplete_evidence_discard_partial_context() {
    let f = Fixture::new();
    for (paths, limits, failure) in [
        (
            vec!["a.rs", "b.rs"],
            Limits {
                files: 1,
                ..Limits::default()
            },
            Failure::FileLimit,
        ),
        (
            vec!["a.rs"],
            Limits {
                file_bytes: 1,
                ..Limits::default()
            },
            Failure::ByteLimit,
        ),
        (
            vec!["a.rs", "b.rs"],
            Limits {
                total_bytes: 12,
                ..Limits::default()
            },
            Failure::ByteLimit,
        ),
        (
            vec!["a.rs", "missing"],
            Limits::default(),
            Failure::UnsafeOrMissingFile,
        ),
        (vec!["../a.rs"], Limits::default(), Failure::InvalidRequest),
        (
            vec!["a.rs", "a.rs"],
            Limits::default(),
            Failure::InvalidRequest,
        ),
        (
            vec!["a.rs"],
            Limits {
                files: 17,
                ..Limits::default()
            },
            Failure::InvalidLimits,
        ),
    ] {
        let result = f.run(&paths, limits);
        assert_eq!(result.failure, Some(failure));
        assert!(result.snippets.is_empty());
    }
}
#[test]
fn unsafe_files_and_binary_text_are_refused() {
    let f = Fixture::new();
    std::os::unix::fs::symlink("a.rs", f.0.join("link")).unwrap();
    fs::hard_link(f.0.join("a.rs"), f.0.join("hard")).unwrap();
    fs::write(f.0.join("binary"), [0, 255]).unwrap();
    rustix::fs::mkfifoat(
        rustix::fs::CWD,
        f.0.join("fifo"),
        rustix::fs::Mode::RUSR | rustix::fs::Mode::WUSR,
    )
    .unwrap();
    for path in ["link", "hard", "fifo", "/etc/passwd"] {
        assert!(f.run(&[path], Limits::default()).failure.is_some());
    }
    assert_eq!(
        f.run(&["binary"], Limits::default()).failure,
        Some(Failure::InvalidText)
    );
}

#[test]
fn unknown_intent_blocked_plan_and_irrelevant_requests_do_not_acquire() {
    let f = Fixture::new();
    let native = NativeSurface::default();
    let unknown = assess(&RoutingFacts::default());
    let mut plan = plan_workflow(
        &unknown,
        None,
        &native,
        &CapabilitySurface::default(),
        &ResourceCatalog::default(),
    );
    assert_eq!(
        prepare(&f.0, &plan, &native, &[], Limits::default()).failure,
        Some(Failure::MissingIntent)
    );
    plan.status = codex_smart_core::workflow::PlanStatus::Blocked;
    assert_eq!(
        prepare(&f.0, &plan, &native, &[], Limits::default()).failure,
        Some(Failure::BlockedPlan)
    );
    let inspection = assess(&RoutingFacts {
        known_operations: vec![TaskKind::Inspect],
        ..Default::default()
    });
    let plan = plan_workflow(
        &inspection,
        None,
        &native,
        &CapabilitySurface::default(),
        &ResourceCatalog::default(),
    );
    let request = Request {
        path: "a.rs".into(),
        obligation: ContextObligation::ReleaseState,
    };
    assert_eq!(
        prepare(&f.0, &plan, &native, &[request], Limits::default()).failure,
        Some(Failure::InvalidRequest)
    );
    assert!(!f.run(&[], Limits::default()).unresolved.is_empty());
}
