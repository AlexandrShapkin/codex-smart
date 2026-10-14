//! Pure supervision policy, driven by the separate explicit local worker adapter.
use std::time::Duration;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WorkerFact {
    Unknown,
    Denied,
    Verified,
}

/// Independently supplied facts; executable presence is insufficient.
#[derive(Debug, Clone, Copy)]
pub struct WorkerFacts {
    pub identity: WorkerFact,
    pub protocol: WorkerFact,
    pub containment: WorkerFact,
    pub termination: WorkerFact,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Refusal {
    UnknownWorker,
    DeniedWorker,
    RuntimeUnavailable,
    InvalidLimits,
}

fn check_facts(facts: WorkerFacts) -> Result<(), Refusal> {
    let facts = [
        facts.identity,
        facts.protocol,
        facts.containment,
        facts.termination,
    ];
    if facts.contains(&WorkerFact::Denied) {
        Err(Refusal::DeniedWorker)
    } else if facts.contains(&WorkerFact::Unknown) {
        Err(Refusal::UnknownWorker)
    } else {
        Ok(())
    }
}

/// Production admission remains closed even with caller-verified worker facts.
pub fn runtime_admission(facts: WorkerFacts) -> Result<(), Refusal> {
    check_facts(facts)?;
    Err(Refusal::RuntimeUnavailable)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum State {
    Running,
    Cancelling,
    Succeeded,
    Failed,
    TimedOut,
    CleanupUnknown,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    Poll,
    TerminateAndPollReap,
    Return,
}

/// One bounded observation, not a source payload. Output is cumulative wire bytes.
#[derive(Debug, Clone, Copy, Default)]
pub struct Observation {
    pub elapsed: Duration,
    pub output_bytes: usize,
    pub response_verified: bool,
    /// Adapter-observed protocol or pipe failure; never substitutes a fabricated byte count.
    pub transport_failed: bool,
    pub reaped_exit: Option<bool>,
}

/// Models one worker, no retries. The runtime adapter owns its monotonic clock,
/// nonblocking I/O, termination and reaping; this type performs none of those effects.
pub struct SupervisionPolicy {
    state: State,
    deadline: Duration,
    cleanup_end: Duration,
    output_limit: usize,
    previous: Observation,
    timed_out: bool,
}

impl SupervisionPolicy {
    pub fn new(
        facts: WorkerFacts,
        deadline: Duration,
        cleanup: Duration,
        output_limit: usize,
    ) -> Result<Self, Refusal> {
        check_facts(facts)?;
        if deadline.is_zero()
            || deadline > Duration::from_millis(250)
            || cleanup.is_zero()
            || cleanup > Duration::from_millis(250)
            || output_limit == 0
            || output_limit > 65536
        {
            return Err(Refusal::InvalidLimits);
        }
        Ok(Self {
            state: State::Running,
            deadline,
            cleanup_end: deadline + cleanup,
            output_limit,
            previous: Observation::default(),
            timed_out: false,
        })
    }

    pub fn state(&self) -> State {
        self.state
    }

    pub fn observe(&mut self, observation: Observation) -> Action {
        if !matches!(self.state, State::Running | State::Cancelling) {
            return Action::Return;
        }
        let invalid = observation.elapsed < self.previous.elapsed
            || observation.output_bytes < self.previous.output_bytes
            || observation.output_bytes > self.output_limit
            || observation.transport_failed;
        self.previous = observation;
        if self.state == State::Running {
            self.timed_out = observation.elapsed >= self.deadline;
            if invalid || self.timed_out {
                self.state = State::Cancelling;
            } else if let Some(success) = observation.reaped_exit {
                self.state = if success && observation.response_verified {
                    State::Succeeded
                } else {
                    State::Failed
                };
                return Action::Return;
            } else {
                return Action::Poll;
            }
        }
        if observation.reaped_exit.is_some() {
            self.state = if self.timed_out {
                State::TimedOut
            } else {
                State::Failed
            };
            Action::Return
        } else if observation.elapsed >= self.cleanup_end {
            self.state = State::CleanupUnknown;
            Action::Return
        } else {
            Action::TerminateAndPollReap
        }
    }
}
