use codex_smart_core::preparation_supervision::*;
use std::time::Duration;

fn facts() -> WorkerFacts {
    WorkerFacts {
        identity: WorkerFact::Verified,
        protocol: WorkerFact::Verified,
        containment: WorkerFact::Verified,
        termination: WorkerFact::Verified,
    }
}
fn policy() -> SupervisionPolicy {
    SupervisionPolicy::new(
        facts(),
        Duration::from_millis(100),
        Duration::from_millis(50),
        64,
    )
    .unwrap()
}
fn observation(ms: u64) -> Observation {
    Observation {
        elapsed: Duration::from_millis(ms),
        ..Default::default()
    }
}

#[test]
fn admission_never_grants_runtime_authority() {
    assert_eq!(runtime_admission(facts()), Err(Refusal::RuntimeUnavailable));
    let mut mixed = facts();
    mixed.identity = WorkerFact::Unknown;
    mixed.termination = WorkerFact::Denied;
    assert_eq!(runtime_admission(mixed), Err(Refusal::DeniedWorker));
    for index in 0..4 {
        for (fact, refusal) in [
            (WorkerFact::Unknown, Refusal::UnknownWorker),
            (WorkerFact::Denied, Refusal::DeniedWorker),
        ] {
            let mut f = facts();
            match index {
                0 => f.identity = fact,
                1 => f.protocol = fact,
                2 => f.containment = fact,
                _ => f.termination = fact,
            }
            assert_eq!(runtime_admission(f), Err(refusal));
            assert!(
                matches!(SupervisionPolicy::new(f, Duration::from_millis(100), Duration::from_millis(50), 64), Err(e) if e == refusal)
            );
        }
    }
}
#[test]
fn limits_are_bounded() {
    for (deadline, cleanup, bytes) in [
        (0, 50, 64),
        (251, 50, 64),
        (100, 0, 64),
        (100, 251, 64),
        (100, 50, 0),
        (100, 50, 65537),
    ] {
        assert!(matches!(
            SupervisionPolicy::new(
                facts(),
                Duration::from_millis(deadline),
                Duration::from_millis(cleanup),
                bytes
            ),
            Err(Refusal::InvalidLimits)
        ));
    }
}
#[test]
fn timeout_requests_termination_and_retains_reap_uncertainty() {
    let mut p = policy();
    assert_eq!(p.observe(observation(99)), Action::Poll);
    assert_eq!(p.observe(observation(100)), Action::TerminateAndPollReap);
    assert_eq!(p.state(), State::Cancelling);
    assert_eq!(p.observe(observation(150)), Action::Return);
    assert_eq!(p.state(), State::CleanupUnknown);
    let mut late = observation(151);
    late.response_verified = true;
    late.reaped_exit = Some(true);
    assert_eq!(p.observe(late), Action::Return);
    assert_eq!(p.state(), State::CleanupUnknown);
}
#[test]
fn response_and_successful_reap_are_both_required_before_deadline() {
    for (time, response, exit, expected) in [
        (99, true, true, State::Succeeded),
        (99, false, true, State::Failed),
        (99, true, false, State::Failed),
        (100, true, true, State::TimedOut),
    ] {
        let mut p = policy();
        let mut o = observation(time);
        o.response_verified = response;
        o.reaped_exit = Some(exit);
        assert_eq!(p.observe(o), Action::Return);
        assert_eq!(p.state(), expected);
    }
    let mut p = policy();
    let mut response_only = observation(99);
    response_only.response_verified = true;
    assert_eq!(p.observe(response_only), Action::Poll);
    assert_eq!(p.observe(observation(100)), Action::TerminateAndPollReap);
    let mut o = observation(120);
    o.reaped_exit = Some(false);
    assert_eq!(p.observe(o), Action::Return);
    assert_eq!(p.state(), State::TimedOut);
}
#[test]
fn output_overflow_and_regressing_observations_fail_closed_deterministically() {
    for _ in 0..2 {
        for (first, second) in [(10, 9), (10, 11)] {
            let mut p = policy();
            let mut o = observation(first);
            o.output_bytes = 20;
            assert_eq!(p.observe(o), Action::Poll);
            o.elapsed = Duration::from_millis(second);
            o.output_bytes = if second == 9 { 20 } else { 19 };
            assert_eq!(p.observe(o), Action::TerminateAndPollReap);
            o.reaped_exit = Some(true);
            o.response_verified = true;
            assert_eq!(p.observe(o), Action::Return);
            assert_eq!(p.state(), State::Failed);
        }
        let mut p = policy();
        let mut o = observation(1);
        o.output_bytes = 65;
        assert_eq!(p.observe(o), Action::TerminateAndPollReap);
        assert_eq!(p.observe(observation(150)), Action::Return);
        assert_eq!(p.state(), State::CleanupUnknown);
    }
}

#[test]
fn real_transport_failure_cancels_without_fabricating_wire_bytes() {
    let mut p = policy();
    let mut o = observation(10);
    o.transport_failed = true;
    o.output_bytes = 3;
    assert_eq!(p.observe(o), Action::TerminateAndPollReap);
    o.elapsed = Duration::from_millis(11);
    o.transport_failed = false;
    o.response_verified = true;
    o.reaped_exit = Some(true);
    assert_eq!(p.observe(o), Action::Return);
    assert_eq!(p.state(), State::Failed);
}
