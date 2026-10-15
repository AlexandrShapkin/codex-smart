//! Pure, offline structural policy. No trusted ingress, attestation or runtime adapter.
use crate::{
    playbook::{ProfileClass, ValidationObligation},
    routing::{
        Reasoning,
        assessment::{Ambiguity, TaskKind, TaskRiskAssessment},
    },
    version::Version,
    workflow::{ValidationReadiness, ValidationRecipe},
};

pub const SCHEMA_V1: u16 = 1;

pub const MAX_ARGS: usize = 32;
pub const MAX_ARG_BYTES: usize = 4096;
pub const MAX_PATH_BYTES: usize = 1024;
pub const MAX_LIFETIME_SECONDS: u64 = 300;
pub const MAX_RECIPE_CHECKS: usize = 16;

/// Typed lexical roles do not establish tool-specific argument semantics.
#[derive(Clone, PartialEq, Eq)]
pub enum Argument<'a> {
    Word(&'a str),
    Flag(&'a str),
    /// Relative to cwd; no absolute paths, dot components or platform ambiguity.
    Path(&'a str),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Budgets {
    pub wall_seconds: u64,
    pub cpu_seconds: u64,
    pub input_bytes: u64,
    pub output_bytes: u64,
    pub memory_bytes: u64,
    pub processes: u64,
}
impl Budgets {
    fn valid(self) -> bool {
        (1..=60).contains(&self.wall_seconds)
            && (1..=self.wall_seconds).contains(&self.cpu_seconds)
            && (1..=1_048_576).contains(&self.input_bytes)
            && (1..=1_048_576).contains(&self.output_bytes)
            && (1..=536_870_912).contains(&self.memory_bytes)
            && (1..=8).contains(&self.processes)
    }
}

/// Sensitive input: intentionally no Debug, Display, serialization or launch conversion.
/// Digests are opaque externally established identities, never hashes computed here.
#[derive(Clone, PartialEq, Eq)]
pub struct Specification<'a> {
    pub schema_version: u16,
    pub executable: &'a str,
    pub executable_pin: [u8; 32],
    pub version: Version,
    pub source_identity: [u8; 32],
    pub configuration_identity: [u8; 32],
    pub argv: &'a [Argument<'a>],
    pub scope: &'a str,
    pub cwd: &'a str,
    pub operation: ValidationObligation,
    pub budgets: Budgets,
    pub profile: ProfileClass,
    pub reasoning: Reasoning,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Provenance {
    CallerDeclared,
    /// An assumption supplied by a future external verifier, NOT authenticated here.
    ExternallyVerifiedAssumption,
}

/// A separate exact reviewed specification, not approval inferred from the candidate.
/// A caller can forge this entire structure; it never confers actual trust.
pub struct Approval<'a> {
    pub specification: &'a Specification<'a>,
    pub provenance: Provenance,
    pub observed_at: u64,
    pub expires_at: u64,
}

pub struct Input<'a> {
    pub specification: &'a Specification<'a>,
    pub approval: Option<Approval<'a>>,
    pub recipe: &'a ValidationRecipe,
    pub assessment: &'a TaskRiskAssessment,
    /// Current independent identity observation, separate from approval and candidate.
    pub current: &'a Specification<'a>,
    pub current_provenance: Provenance,
    pub current_observed_at: u64,
    pub current_expires_at: u64,
    /// External trusted clock assumptions; rollback against last observation is refused.
    pub now: u64,
    pub last_observed_time: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Reason {
    UnsupportedSchema,
    InvalidApprovalEvidence,
    InvalidCurrentEvidence,
    UnclearTask,
    InvalidCurrentFreshness,
    ArgumentLimit,
    UnsafeArgument,
    UnsafePath,
    OutsideScope,
    InvalidIdentity,
    InvalidBudgets,
    RiskFloor,
    RecipeNotReady,
    MissingObligation,
    MissingApproval,
    UnverifiedEvidence,
    ApprovalMismatch,
    CurrentMismatch,
    InvalidFreshness,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status {
    /// Only structural admissibility assuming all externally verified inputs are true.
    ConditionallyPolicyAdmissible,
    Refused(Reason),
}
impl Status {
    pub const fn admitted(self) -> bool {
        false
    }
    pub const fn attested(self) -> bool {
        false
    }
    pub const fn runtime_ready(self) -> bool {
        false
    }
    pub const fn execution_authorized(self) -> bool {
        false
    }
}

fn atom(s: &str) -> bool {
    !s.is_empty()
        && s.bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"_-".contains(&b))
}
fn path(s: &str, absolute: bool) -> bool {
    if s.len() > MAX_PATH_BYTES || s.starts_with('/') != absolute {
        return false;
    }
    let tail = if absolute { &s[1..] } else { s };
    !tail.is_empty()
        && tail.split('/').all(|part| {
            part != "."
                && part != ".."
                && !part.starts_with('-')
                && !part.is_empty()
                && part
                    .bytes()
                    .all(|b| b.is_ascii_alphanumeric() || b"_-.".contains(&b))
        })
}
fn contained(root: &str, child: &str) -> bool {
    child == root || child.strip_prefix(root).is_some_and(|s| s.starts_with('/'))
}

/// Deterministic first refusal, bounded traversal, no filesystem/clock/process access.
/// This neither validates command success nor authenticates any supplied evidence.
pub fn evaluate(input: &Input<'_>) -> Status {
    match check(input) {
        Ok(()) => Status::ConditionallyPolicyAdmissible,
        Err(reason) => Status::Refused(reason),
    }
}
fn validate_specification(spec: &Specification<'_>) -> Result<(), Reason> {
    if spec.schema_version != SCHEMA_V1 {
        return Err(Reason::UnsupportedSchema);
    }
    if spec.argv.len() > MAX_ARGS {
        return Err(Reason::ArgumentLimit);
    }
    let mut bytes = 0usize;
    for arg in spec.argv {
        let raw = match arg {
            Argument::Word(s) | Argument::Flag(s) | Argument::Path(s) => s,
        };
        bytes = bytes.saturating_add(raw.len());
        if bytes > MAX_ARG_BYTES {
            return Err(Reason::ArgumentLimit);
        }
        let safe = match arg {
            Argument::Word(s) => atom(s) && !s.starts_with('-'),
            Argument::Flag(s) => s
                .strip_prefix("--")
                .is_some_and(|tail| atom(tail) && !tail.starts_with('-')),
            Argument::Path(s) => path(s, false),
        };
        if !safe {
            return Err(Reason::UnsafeArgument);
        }
    }
    if !path(spec.executable, true) || !path(spec.scope, true) || !path(spec.cwd, true) {
        return Err(Reason::UnsafePath);
    }
    if !contained(spec.scope, spec.cwd) {
        return Err(Reason::OutsideScope);
    }
    if [
        spec.executable_pin,
        spec.source_identity,
        spec.configuration_identity,
    ]
    .contains(&[0; 32])
    {
        return Err(Reason::InvalidIdentity);
    }
    if !spec.budgets.valid() {
        return Err(Reason::InvalidBudgets);
    }
    Ok(())
}

fn fresh(observed: u64, expires: u64, now: u64) -> bool {
    observed > 0
        && observed <= now
        && now < expires
        && expires
            .checked_sub(observed)
            .is_some_and(|life| life <= MAX_LIFETIME_SECONDS)
}

fn check(input: &Input<'_>) -> Result<(), Reason> {
    let spec = input.specification;
    validate_specification(spec)?;
    validate_specification(input.current).map_err(|_| Reason::InvalidCurrentEvidence)?;
    if let Some(approval) = &input.approval {
        validate_specification(approval.specification)
            .map_err(|_| Reason::InvalidApprovalEvidence)?;
    }
    if input.assessment.ambiguity == Ambiguity::Ambiguous
        || input.assessment.task == TaskKind::Unknown
    {
        return Err(Reason::UnclearTask);
    }
    if input.assessment.risk == crate::routing::assessment::RiskLevel::High
        && (spec.profile != ProfileClass::Strong || spec.reasoning != Reasoning::High)
    {
        return Err(Reason::RiskFloor);
    }
    if input.recipe.status != ValidationReadiness::Ready
        || input.recipe.checks.len() > MAX_RECIPE_CHECKS
        || input
            .recipe
            .checks
            .iter()
            .any(|c| c.readiness != ValidationReadiness::Ready)
    {
        return Err(Reason::RecipeNotReady);
    }
    if !input
        .recipe
        .checks
        .iter()
        .any(|c| c.obligation == spec.operation && c.readiness == ValidationReadiness::Ready)
    {
        return Err(Reason::MissingObligation);
    }
    let approval = input.approval.as_ref().ok_or(Reason::MissingApproval)?;
    if approval.provenance != Provenance::ExternallyVerifiedAssumption
        || input.current_provenance != Provenance::ExternallyVerifiedAssumption
    {
        return Err(Reason::UnverifiedEvidence);
    }
    // All three specifications have bounded structure before any deep comparison.
    if approval.specification != spec {
        return Err(Reason::ApprovalMismatch);
    }
    if input.current != spec {
        return Err(Reason::CurrentMismatch);
    }
    if input.now < input.last_observed_time
        || !fresh(approval.observed_at, approval.expires_at, input.now)
    {
        return Err(Reason::InvalidFreshness);
    }
    if !fresh(
        input.current_observed_at,
        input.current_expires_at,
        input.now,
    ) {
        return Err(Reason::InvalidCurrentFreshness);
    }
    Ok(())
}
