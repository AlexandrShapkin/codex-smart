//! Versioned workflow-playbook semantics.
//!
//! This module defines bounded, typed contracts only. It does not select a playbook,
//! prepare resources, execute tools, change Codex settings, or resolve provider/model
//! names. Selection and preparation are separate reviewed stages.

use crate::routing::Reasoning;
use crate::routing::assessment::{RiskLevel, SafetyFact, TaskKind};
use crate::routing::engine::CapabilityNeed;
use std::collections::BTreeSet;

pub const PLAYBOOK_SCHEMA_VERSION: u16 = 1;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Archetype {
    Inspection,
    FocusedBugFix,
    FailingTestRepair,
    FeatureImplementation,
    ApiChange,
    Refactor,
    SecuritySensitiveChange,
    CiConfigRepair,
    DependencyUpdate,
    DocumentationChange,
    ReleasePreparation,
}

impl Archetype {
    pub const ALL: [Self; 11] = [
        Self::Inspection,
        Self::FocusedBugFix,
        Self::FailingTestRepair,
        Self::FeatureImplementation,
        Self::ApiChange,
        Self::Refactor,
        Self::SecuritySensitiveChange,
        Self::CiConfigRepair,
        Self::DependencyUpdate,
        Self::DocumentationChange,
        Self::ReleasePreparation,
    ];

    pub const fn slug(self) -> &'static str {
        match self {
            Self::Inspection => "inspection",
            Self::FocusedBugFix => "focused-bug-fix",
            Self::FailingTestRepair => "failing-test-repair",
            Self::FeatureImplementation => "feature-implementation",
            Self::ApiChange => "api-change",
            Self::Refactor => "refactor",
            Self::SecuritySensitiveChange => "security-sensitive-change",
            Self::CiConfigRepair => "ci-config-repair",
            Self::DependencyUpdate => "dependency-update",
            Self::DocumentationChange => "documentation-change",
            Self::ReleasePreparation => "release-preparation",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ProfileClass {
    Economy,
    Standard,
    Strong,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum AmbiguityPolicy {
    /// The playbook can gather bounded read-only evidence before a later planner decides.
    BoundedEvidence,
    /// Ambiguity must remain an explicit evidence gate.
    NeedsEvidence,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum NativeCapability {
    ReadFiles,
    Search,
    Git,
    Edit,
    Build,
    Tests,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ContextObligation {
    TaskDefinition,
    Requirements,
    RelevantFiles,
    RepositoryState,
    FailureEvidence,
    ExistingTests,
    Callers,
    ImpactSurface,
    SymbolReferences,
    PublicContract,
    ExternalReference,
    SecurityBoundary,
    CiConfiguration,
    DependencyMetadata,
    DocumentationSourceOfTruth,
    ReleaseState,
    ValidationHistory,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum PreparationAttribute {
    Identity,
    Version,
    Scope,
    Owner,
    Validity,
    Invalidation,
    Privacy,
    Cleanup,
}

pub const COMPLETE_PREPARED_STATE_CONTRACT: &[PreparationAttribute] = &[
    PreparationAttribute::Identity,
    PreparationAttribute::Version,
    PreparationAttribute::Scope,
    PreparationAttribute::Owner,
    PreparationAttribute::Validity,
    PreparationAttribute::Invalidation,
    PreparationAttribute::Privacy,
    PreparationAttribute::Cleanup,
];

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ValidationObligation {
    ReadOnlyInvariant,
    RelevantTests,
    BuildOrStaticCheck,
    CallerCompatibility,
    ImpactReview,
    SecurityReview,
    CiConfigurationCheck,
    DependencyValidation,
    DocumentationCheck,
    ReleaseRehearsal,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum EscalationTrigger {
    Ambiguity,
    MissingRequiredContext,
    RequiredCapabilityUnknown,
    RequiredCapabilityUnavailable,
    ValidationFailure,
    SafetyEvidenceConflict,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum CleanupObligation {
    TemporaryWorkspace,
    GeneratedArtifacts,
    PreparedResources,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum FallbackPolicy {
    /// Native evidence is the first fallback; unresolved obligations remain NeedsEvidence.
    NativeThenNeedsEvidence,
    /// Native evidence is attempted first, but missing required verification must block.
    NativeThenBlock,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Applicability {
    pub task_kinds: &'static [TaskKind],
    pub risk_floor: RiskLevel,
    pub risk_ceiling: RiskLevel,
    pub ambiguity: AmbiguityPolicy,
    /// Required semantic safety facts. An empty slice means none are required.
    pub safety_facts: &'static [SafetyFact],
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ExecutionFloor {
    pub profile: ProfileClass,
    pub reasoning: Reasoning,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PlaybookContract {
    pub schema_version: u16,
    pub archetype: Archetype,
    pub applicability: Applicability,
    /// Native capabilities are semantic requirements only; host readiness is external.
    pub required_native: &'static [NativeCapability],
    /// External capability needs are optional augmentations, never hidden prerequisites.
    pub optional_external: &'static [CapabilityNeed],
    pub context: &'static [ContextObligation],
    /// Empty means no reusable prepared state is required by this archetype.
    pub prepared_state: &'static [PreparationAttribute],
    pub execution_floor: ExecutionFloor,
    pub validation: &'static [ValidationObligation],
    pub escalation: &'static [EscalationTrigger],
    pub cleanup: &'static [CleanupObligation],
    pub fallback: FallbackPolicy,
}

impl PlaybookContract {
    pub fn id(self) -> String {
        format!("{}-v{}", self.archetype.slug(), self.schema_version)
    }

    /// Enum-only explanation. It contains no model/provider names, paths, prompt text,
    /// repository source, credentials, dynamic tool output, or execution authority.
    pub fn render(self) -> String {
        format!(
            "Playbook contract (no selection or execution)\nID: {}\nArchetype: {:?}\nApplicability: task={:?}; risk={:?}..={:?}; ambiguity={:?}; safety={:?}\nNative requirements: {:?}\nOptional external needs: {:?}\nContext obligations: {:?}\nPrepared-state contract: {:?}\nExecution floor: profile={:?}; reasoning={:?}\nValidation: {:?}\nEscalation triggers: {:?}\nCleanup: {:?}\nFallback: {:?}\n",
            self.id(),
            self.archetype,
            self.applicability.task_kinds,
            self.applicability.risk_floor,
            self.applicability.risk_ceiling,
            self.applicability.ambiguity,
            self.applicability.safety_facts,
            self.required_native,
            self.optional_external,
            self.context,
            self.prepared_state,
            self.execution_floor.profile,
            self.execution_floor.reasoning,
            self.validation,
            self.escalation,
            self.cleanup,
            self.fallback,
        )
    }
}

const INSPECT_TASKS: &[TaskKind] = &[TaskKind::Inspect];
const EDIT_TASKS: &[TaskKind] = &[TaskKind::Edit];
const EDIT_REFACTOR_TASKS: &[TaskKind] = &[TaskKind::Edit, TaskKind::Refactor];
const REFACTOR_TASKS: &[TaskKind] = &[TaskKind::Refactor];
const INSPECT_EDIT_TASKS: &[TaskKind] = &[TaskKind::Inspect, TaskKind::Edit];

const READ_SEARCH_GIT: &[NativeCapability] = &[
    NativeCapability::ReadFiles,
    NativeCapability::Search,
    NativeCapability::Git,
];
const EDIT_BUILD_TEST: &[NativeCapability] = &[
    NativeCapability::ReadFiles,
    NativeCapability::Search,
    NativeCapability::Edit,
    NativeCapability::Build,
    NativeCapability::Tests,
];
const EDIT_TEST: &[NativeCapability] = &[
    NativeCapability::ReadFiles,
    NativeCapability::Search,
    NativeCapability::Edit,
    NativeCapability::Tests,
];

const CORE_ESCALATION: &[EscalationTrigger] = &[
    EscalationTrigger::Ambiguity,
    EscalationTrigger::MissingRequiredContext,
    EscalationTrigger::ValidationFailure,
];
const CAPABILITY_ESCALATION: &[EscalationTrigger] = &[
    EscalationTrigger::Ambiguity,
    EscalationTrigger::MissingRequiredContext,
    EscalationTrigger::RequiredCapabilityUnknown,
    EscalationTrigger::RequiredCapabilityUnavailable,
    EscalationTrigger::ValidationFailure,
];
const SAFETY_ESCALATION: &[EscalationTrigger] = &[
    EscalationTrigger::Ambiguity,
    EscalationTrigger::MissingRequiredContext,
    EscalationTrigger::RequiredCapabilityUnknown,
    EscalationTrigger::RequiredCapabilityUnavailable,
    EscalationTrigger::ValidationFailure,
    EscalationTrigger::SafetyEvidenceConflict,
];

const TEMP_CLEANUP: &[CleanupObligation] = &[
    CleanupObligation::TemporaryWorkspace,
    CleanupObligation::GeneratedArtifacts,
];
const PREPARED_CLEANUP: &[CleanupObligation] = &[
    CleanupObligation::TemporaryWorkspace,
    CleanupObligation::GeneratedArtifacts,
    CleanupObligation::PreparedResources,
];

const SECURITY_FACT: &[SafetyFact] = &[SafetyFact::SecuritySensitive];

const STRUCTURAL: &[CapabilityNeed] = &[CapabilityNeed::StructuralImpact];
const SYMBOLS: &[CapabilityNeed] = &[CapabilityNeed::SymbolNavigation];
const EXTERNAL: &[CapabilityNeed] = &[CapabilityNeed::ExternalApiReference];
const REMOTE: &[CapabilityNeed] = &[CapabilityNeed::RemoteRepository];
const STRUCTURAL_SYMBOLS: &[CapabilityNeed] = &[
    CapabilityNeed::StructuralImpact,
    CapabilityNeed::SymbolNavigation,
];
const EXTERNAL_REMOTE: &[CapabilityNeed] = &[
    CapabilityNeed::ExternalApiReference,
    CapabilityNeed::RemoteRepository,
];
const NONE_EXTERNAL: &[CapabilityNeed] = &[];

const INSPECTION_CONTEXT: &[ContextObligation] = &[
    ContextObligation::TaskDefinition,
    ContextObligation::RelevantFiles,
    ContextObligation::RepositoryState,
];
const BUG_CONTEXT: &[ContextObligation] = &[
    ContextObligation::TaskDefinition,
    ContextObligation::FailureEvidence,
    ContextObligation::RelevantFiles,
    ContextObligation::ExistingTests,
    ContextObligation::Callers,
];
const FEATURE_CONTEXT: &[ContextObligation] = &[
    ContextObligation::Requirements,
    ContextObligation::RelevantFiles,
    ContextObligation::ExistingTests,
    ContextObligation::Callers,
];
const API_CONTEXT: &[ContextObligation] = &[
    ContextObligation::Requirements,
    ContextObligation::PublicContract,
    ContextObligation::Callers,
    ContextObligation::ExistingTests,
    ContextObligation::ExternalReference,
];
const REFACTOR_CONTEXT: &[ContextObligation] = &[
    ContextObligation::TaskDefinition,
    ContextObligation::RelevantFiles,
    ContextObligation::ImpactSurface,
    ContextObligation::SymbolReferences,
    ContextObligation::ExistingTests,
];
const SECURITY_CONTEXT: &[ContextObligation] = &[
    ContextObligation::Requirements,
    ContextObligation::SecurityBoundary,
    ContextObligation::ImpactSurface,
    ContextObligation::RelevantFiles,
    ContextObligation::ExistingTests,
];
const CI_CONTEXT: &[ContextObligation] = &[
    ContextObligation::TaskDefinition,
    ContextObligation::FailureEvidence,
    ContextObligation::CiConfiguration,
    ContextObligation::RelevantFiles,
];
const DEPENDENCY_CONTEXT: &[ContextObligation] = &[
    ContextObligation::Requirements,
    ContextObligation::DependencyMetadata,
    ContextObligation::ExternalReference,
    ContextObligation::ExistingTests,
];
const DOC_CONTEXT: &[ContextObligation] = &[
    ContextObligation::Requirements,
    ContextObligation::RelevantFiles,
    ContextObligation::DocumentationSourceOfTruth,
];
const RELEASE_CONTEXT: &[ContextObligation] = &[
    ContextObligation::Requirements,
    ContextObligation::ReleaseState,
    ContextObligation::CiConfiguration,
    ContextObligation::ValidationHistory,
    ContextObligation::DependencyMetadata,
];

const READ_ONLY_VALIDATION: &[ValidationObligation] = &[ValidationObligation::ReadOnlyInvariant];
const CODE_VALIDATION: &[ValidationObligation] = &[
    ValidationObligation::RelevantTests,
    ValidationObligation::BuildOrStaticCheck,
];
const API_VALIDATION: &[ValidationObligation] = &[
    ValidationObligation::RelevantTests,
    ValidationObligation::BuildOrStaticCheck,
    ValidationObligation::CallerCompatibility,
];
const REFACTOR_VALIDATION: &[ValidationObligation] = &[
    ValidationObligation::RelevantTests,
    ValidationObligation::BuildOrStaticCheck,
    ValidationObligation::ImpactReview,
];
const SECURITY_VALIDATION: &[ValidationObligation] = &[
    ValidationObligation::RelevantTests,
    ValidationObligation::BuildOrStaticCheck,
    ValidationObligation::ImpactReview,
    ValidationObligation::SecurityReview,
];
const CI_VALIDATION: &[ValidationObligation] = &[
    ValidationObligation::CiConfigurationCheck,
    ValidationObligation::BuildOrStaticCheck,
    ValidationObligation::RelevantTests,
];
const DEPENDENCY_VALIDATION: &[ValidationObligation] = &[
    ValidationObligation::DependencyValidation,
    ValidationObligation::BuildOrStaticCheck,
    ValidationObligation::RelevantTests,
];
const DOC_VALIDATION: &[ValidationObligation] = &[ValidationObligation::DocumentationCheck];
const RELEASE_VALIDATION: &[ValidationObligation] = &[
    ValidationObligation::BuildOrStaticCheck,
    ValidationObligation::RelevantTests,
    ValidationObligation::SecurityReview,
    ValidationObligation::ReleaseRehearsal,
];

const NO_PREPARATION: &[PreparationAttribute] = &[];

pub const BUILTIN_PLAYBOOKS: &[PlaybookContract] = &[
    PlaybookContract {
        schema_version: PLAYBOOK_SCHEMA_VERSION,
        archetype: Archetype::Inspection,
        applicability: Applicability {
            task_kinds: INSPECT_TASKS,
            risk_floor: RiskLevel::Low,
            risk_ceiling: RiskLevel::High,
            ambiguity: AmbiguityPolicy::BoundedEvidence,
            safety_facts: &[],
        },
        required_native: READ_SEARCH_GIT,
        optional_external: STRUCTURAL_SYMBOLS,
        context: INSPECTION_CONTEXT,
        prepared_state: NO_PREPARATION,
        execution_floor: ExecutionFloor {
            profile: ProfileClass::Economy,
            reasoning: Reasoning::Medium,
        },
        validation: READ_ONLY_VALIDATION,
        escalation: CORE_ESCALATION,
        cleanup: TEMP_CLEANUP,
        fallback: FallbackPolicy::NativeThenNeedsEvidence,
    },
    PlaybookContract {
        schema_version: PLAYBOOK_SCHEMA_VERSION,
        archetype: Archetype::FocusedBugFix,
        applicability: Applicability {
            task_kinds: EDIT_TASKS,
            risk_floor: RiskLevel::Low,
            risk_ceiling: RiskLevel::Medium,
            ambiguity: AmbiguityPolicy::NeedsEvidence,
            safety_facts: &[],
        },
        required_native: EDIT_BUILD_TEST,
        optional_external: SYMBOLS,
        context: BUG_CONTEXT,
        prepared_state: NO_PREPARATION,
        execution_floor: ExecutionFloor {
            profile: ProfileClass::Standard,
            reasoning: Reasoning::Medium,
        },
        validation: CODE_VALIDATION,
        escalation: CORE_ESCALATION,
        cleanup: TEMP_CLEANUP,
        fallback: FallbackPolicy::NativeThenNeedsEvidence,
    },
    PlaybookContract {
        schema_version: PLAYBOOK_SCHEMA_VERSION,
        archetype: Archetype::FailingTestRepair,
        applicability: Applicability {
            task_kinds: EDIT_TASKS,
            risk_floor: RiskLevel::Low,
            risk_ceiling: RiskLevel::Medium,
            ambiguity: AmbiguityPolicy::NeedsEvidence,
            safety_facts: &[],
        },
        required_native: EDIT_TEST,
        optional_external: SYMBOLS,
        context: BUG_CONTEXT,
        prepared_state: NO_PREPARATION,
        execution_floor: ExecutionFloor {
            profile: ProfileClass::Standard,
            reasoning: Reasoning::Medium,
        },
        validation: CODE_VALIDATION,
        escalation: CORE_ESCALATION,
        cleanup: TEMP_CLEANUP,
        fallback: FallbackPolicy::NativeThenNeedsEvidence,
    },
    PlaybookContract {
        schema_version: PLAYBOOK_SCHEMA_VERSION,
        archetype: Archetype::FeatureImplementation,
        applicability: Applicability {
            task_kinds: EDIT_TASKS,
            risk_floor: RiskLevel::Low,
            risk_ceiling: RiskLevel::Medium,
            ambiguity: AmbiguityPolicy::NeedsEvidence,
            safety_facts: &[],
        },
        required_native: EDIT_BUILD_TEST,
        optional_external: STRUCTURAL_SYMBOLS,
        context: FEATURE_CONTEXT,
        prepared_state: COMPLETE_PREPARED_STATE_CONTRACT,
        execution_floor: ExecutionFloor {
            profile: ProfileClass::Standard,
            reasoning: Reasoning::Medium,
        },
        validation: CODE_VALIDATION,
        escalation: CAPABILITY_ESCALATION,
        cleanup: PREPARED_CLEANUP,
        fallback: FallbackPolicy::NativeThenNeedsEvidence,
    },
    PlaybookContract {
        schema_version: PLAYBOOK_SCHEMA_VERSION,
        archetype: Archetype::ApiChange,
        applicability: Applicability {
            task_kinds: EDIT_REFACTOR_TASKS,
            risk_floor: RiskLevel::Medium,
            risk_ceiling: RiskLevel::High,
            ambiguity: AmbiguityPolicy::NeedsEvidence,
            safety_facts: &[],
        },
        required_native: EDIT_BUILD_TEST,
        optional_external: EXTERNAL,
        context: API_CONTEXT,
        prepared_state: COMPLETE_PREPARED_STATE_CONTRACT,
        execution_floor: ExecutionFloor {
            profile: ProfileClass::Standard,
            reasoning: Reasoning::High,
        },
        validation: API_VALIDATION,
        escalation: CAPABILITY_ESCALATION,
        cleanup: PREPARED_CLEANUP,
        fallback: FallbackPolicy::NativeThenNeedsEvidence,
    },
    PlaybookContract {
        schema_version: PLAYBOOK_SCHEMA_VERSION,
        archetype: Archetype::Refactor,
        applicability: Applicability {
            task_kinds: REFACTOR_TASKS,
            risk_floor: RiskLevel::Medium,
            risk_ceiling: RiskLevel::High,
            ambiguity: AmbiguityPolicy::NeedsEvidence,
            safety_facts: &[],
        },
        required_native: EDIT_BUILD_TEST,
        optional_external: STRUCTURAL_SYMBOLS,
        context: REFACTOR_CONTEXT,
        prepared_state: COMPLETE_PREPARED_STATE_CONTRACT,
        execution_floor: ExecutionFloor {
            profile: ProfileClass::Standard,
            reasoning: Reasoning::High,
        },
        validation: REFACTOR_VALIDATION,
        escalation: CAPABILITY_ESCALATION,
        cleanup: PREPARED_CLEANUP,
        fallback: FallbackPolicy::NativeThenNeedsEvidence,
    },
    PlaybookContract {
        schema_version: PLAYBOOK_SCHEMA_VERSION,
        archetype: Archetype::SecuritySensitiveChange,
        applicability: Applicability {
            task_kinds: EDIT_REFACTOR_TASKS,
            risk_floor: RiskLevel::High,
            risk_ceiling: RiskLevel::High,
            ambiguity: AmbiguityPolicy::NeedsEvidence,
            safety_facts: SECURITY_FACT,
        },
        required_native: EDIT_BUILD_TEST,
        optional_external: STRUCTURAL,
        context: SECURITY_CONTEXT,
        prepared_state: COMPLETE_PREPARED_STATE_CONTRACT,
        execution_floor: ExecutionFloor {
            profile: ProfileClass::Strong,
            reasoning: Reasoning::High,
        },
        validation: SECURITY_VALIDATION,
        escalation: SAFETY_ESCALATION,
        cleanup: PREPARED_CLEANUP,
        fallback: FallbackPolicy::NativeThenBlock,
    },
    PlaybookContract {
        schema_version: PLAYBOOK_SCHEMA_VERSION,
        archetype: Archetype::CiConfigRepair,
        applicability: Applicability {
            task_kinds: EDIT_TASKS,
            risk_floor: RiskLevel::Low,
            risk_ceiling: RiskLevel::High,
            ambiguity: AmbiguityPolicy::NeedsEvidence,
            safety_facts: &[],
        },
        required_native: EDIT_BUILD_TEST,
        optional_external: REMOTE,
        context: CI_CONTEXT,
        prepared_state: COMPLETE_PREPARED_STATE_CONTRACT,
        execution_floor: ExecutionFloor {
            profile: ProfileClass::Standard,
            reasoning: Reasoning::Medium,
        },
        validation: CI_VALIDATION,
        escalation: CAPABILITY_ESCALATION,
        cleanup: PREPARED_CLEANUP,
        fallback: FallbackPolicy::NativeThenNeedsEvidence,
    },
    PlaybookContract {
        schema_version: PLAYBOOK_SCHEMA_VERSION,
        archetype: Archetype::DependencyUpdate,
        applicability: Applicability {
            task_kinds: EDIT_TASKS,
            risk_floor: RiskLevel::Medium,
            risk_ceiling: RiskLevel::High,
            ambiguity: AmbiguityPolicy::NeedsEvidence,
            safety_facts: &[],
        },
        required_native: EDIT_BUILD_TEST,
        optional_external: EXTERNAL,
        context: DEPENDENCY_CONTEXT,
        prepared_state: COMPLETE_PREPARED_STATE_CONTRACT,
        execution_floor: ExecutionFloor {
            profile: ProfileClass::Standard,
            reasoning: Reasoning::High,
        },
        validation: DEPENDENCY_VALIDATION,
        escalation: CAPABILITY_ESCALATION,
        cleanup: PREPARED_CLEANUP,
        fallback: FallbackPolicy::NativeThenNeedsEvidence,
    },
    PlaybookContract {
        schema_version: PLAYBOOK_SCHEMA_VERSION,
        archetype: Archetype::DocumentationChange,
        applicability: Applicability {
            task_kinds: INSPECT_EDIT_TASKS,
            risk_floor: RiskLevel::Low,
            risk_ceiling: RiskLevel::Medium,
            ambiguity: AmbiguityPolicy::NeedsEvidence,
            safety_facts: &[],
        },
        required_native: &[
            NativeCapability::ReadFiles,
            NativeCapability::Search,
            NativeCapability::Edit,
        ],
        optional_external: NONE_EXTERNAL,
        context: DOC_CONTEXT,
        prepared_state: NO_PREPARATION,
        execution_floor: ExecutionFloor {
            profile: ProfileClass::Economy,
            reasoning: Reasoning::Medium,
        },
        validation: DOC_VALIDATION,
        escalation: CORE_ESCALATION,
        cleanup: TEMP_CLEANUP,
        fallback: FallbackPolicy::NativeThenNeedsEvidence,
    },
    PlaybookContract {
        schema_version: PLAYBOOK_SCHEMA_VERSION,
        archetype: Archetype::ReleasePreparation,
        applicability: Applicability {
            task_kinds: INSPECT_EDIT_TASKS,
            risk_floor: RiskLevel::High,
            risk_ceiling: RiskLevel::High,
            ambiguity: AmbiguityPolicy::NeedsEvidence,
            safety_facts: &[],
        },
        required_native: &[
            NativeCapability::ReadFiles,
            NativeCapability::Search,
            NativeCapability::Git,
            NativeCapability::Build,
            NativeCapability::Tests,
        ],
        optional_external: EXTERNAL_REMOTE,
        context: RELEASE_CONTEXT,
        prepared_state: COMPLETE_PREPARED_STATE_CONTRACT,
        execution_floor: ExecutionFloor {
            profile: ProfileClass::Strong,
            reasoning: Reasoning::High,
        },
        validation: RELEASE_VALIDATION,
        escalation: SAFETY_ESCALATION,
        cleanup: PREPARED_CLEANUP,
        fallback: FallbackPolicy::NativeThenBlock,
    },
];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ContractError {
    WrongSchema,
    DuplicateArchetype,
    IncompleteArchetypeSet,
    EmptyApplicability,
    InvalidRiskRange,
    EmptyNativeRequirements,
    EmptyContext,
    EmptyValidation,
    EmptyEscalation,
    PartialPreparedStateContract,
    SecurityFloorWeakened,
    SafetyFallbackWeakened,
}

pub fn validate_contracts(playbooks: &[PlaybookContract]) -> Result<(), ContractError> {
    let mut archetypes = BTreeSet::new();
    for playbook in playbooks {
        if playbook.schema_version != PLAYBOOK_SCHEMA_VERSION {
            return Err(ContractError::WrongSchema);
        }
        if !archetypes.insert(playbook.archetype) {
            return Err(ContractError::DuplicateArchetype);
        }
        if playbook.applicability.task_kinds.is_empty() {
            return Err(ContractError::EmptyApplicability);
        }
        if playbook.applicability.risk_floor > playbook.applicability.risk_ceiling {
            return Err(ContractError::InvalidRiskRange);
        }
        if playbook.required_native.is_empty() {
            return Err(ContractError::EmptyNativeRequirements);
        }
        if playbook.context.is_empty() {
            return Err(ContractError::EmptyContext);
        }
        if playbook.validation.is_empty() {
            return Err(ContractError::EmptyValidation);
        }
        if playbook.escalation.is_empty() {
            return Err(ContractError::EmptyEscalation);
        }
        if !playbook.prepared_state.is_empty()
            && playbook.prepared_state != COMPLETE_PREPARED_STATE_CONTRACT
        {
            return Err(ContractError::PartialPreparedStateContract);
        }
        if playbook.archetype == Archetype::SecuritySensitiveChange
            && (playbook.applicability.risk_floor != RiskLevel::High
                || playbook.execution_floor.profile != ProfileClass::Strong
                || playbook.execution_floor.reasoning != Reasoning::High
                || !playbook
                    .applicability
                    .safety_facts
                    .contains(&SafetyFact::SecuritySensitive))
        {
            return Err(ContractError::SecurityFloorWeakened);
        }
        if playbook.applicability.risk_floor == RiskLevel::High
            && (playbook.fallback != FallbackPolicy::NativeThenBlock
                || playbook.execution_floor.profile != ProfileClass::Strong
                || playbook.execution_floor.reasoning != Reasoning::High)
        {
            return Err(ContractError::SafetyFallbackWeakened);
        }
    }
    if archetypes != Archetype::ALL.into_iter().collect() {
        return Err(ContractError::IncompleteArchetypeSet);
    }
    Ok(())
}

pub fn validate_builtin_contracts() -> Result<(), ContractError> {
    validate_contracts(BUILTIN_PLAYBOOKS)
}

pub fn builtin(archetype: Archetype) -> &'static PlaybookContract {
    BUILTIN_PLAYBOOKS
        .iter()
        .find(|playbook| playbook.archetype == archetype)
        .expect("all Archetype values have a built-in contract")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn builtins_are_bounded_versioned_and_valid() {
        assert_eq!(BUILTIN_PLAYBOOKS.len(), 11);
        assert_eq!(validate_builtin_contracts(), Ok(()));
        assert_eq!(
            BUILTIN_PLAYBOOKS
                .iter()
                .map(|playbook| playbook.id())
                .collect::<BTreeSet<_>>()
                .len(),
            BUILTIN_PLAYBOOKS.len()
        );
    }

    #[test]
    fn every_archetype_is_present_exactly_once() {
        for archetype in Archetype::ALL {
            assert_eq!(builtin(archetype).archetype, archetype);
        }
    }

    #[test]
    fn incomplete_builtin_set_is_rejected() {
        let mut contracts = BUILTIN_PLAYBOOKS.to_vec();
        contracts.pop();
        assert_eq!(
            validate_contracts(&contracts),
            Err(ContractError::IncompleteArchetypeSet)
        );
    }

    #[test]
    fn external_capabilities_are_augmentations_not_hidden_prerequisites() {
        for playbook in BUILTIN_PLAYBOOKS {
            assert!(!playbook.required_native.is_empty());
            // External needs have no execution authority in this contract. A later
            // resource planner must resolve them against verified capability state.
            for need in playbook.optional_external {
                assert!(matches!(
                    need,
                    CapabilityNeed::StructuralImpact
                        | CapabilityNeed::SymbolNavigation
                        | CapabilityNeed::ExternalApiReference
                        | CapabilityNeed::RemoteRepository
                ));
            }
        }
    }

    #[test]
    fn prepared_state_is_all_or_nothing() {
        for playbook in BUILTIN_PLAYBOOKS {
            assert!(
                playbook.prepared_state.is_empty()
                    || playbook.prepared_state == COMPLETE_PREPARED_STATE_CONTRACT
            );
        }
    }

    #[test]
    fn high_risk_floors_cannot_degrade_to_soft_fallback() {
        for playbook in BUILTIN_PLAYBOOKS {
            if playbook.applicability.risk_floor == RiskLevel::High {
                assert_eq!(playbook.fallback, FallbackPolicy::NativeThenBlock);
                assert_eq!(playbook.execution_floor.profile, ProfileClass::Strong);
                assert_eq!(playbook.execution_floor.reasoning, Reasoning::High);
            }
        }
    }

    #[test]
    fn explanation_is_enum_only_and_has_no_provider_or_model_identity() {
        let rendered = BUILTIN_PLAYBOOKS
            .iter()
            .map(|playbook| playbook.render())
            .collect::<Vec<_>>()
            .join("\n");
        for forbidden in [
            "gpt-",
            "openai",
            "anthropic",
            "gemini",
            "/home/",
            "api_key",
            "Bearer ",
        ] {
            assert!(
                !rendered
                    .to_ascii_lowercase()
                    .contains(&forbidden.to_ascii_lowercase())
            );
        }
        assert!(rendered.contains("no selection or execution"));
        assert!(rendered.contains("NativeThenBlock"));
    }

    #[test]
    fn weakened_high_risk_contract_is_rejected() {
        let mut contracts = BUILTIN_PLAYBOOKS.to_vec();
        let release = contracts
            .iter_mut()
            .find(|playbook| playbook.archetype == Archetype::ReleasePreparation)
            .expect("release playbook");
        release.execution_floor.profile = ProfileClass::Economy;
        release.execution_floor.reasoning = Reasoning::Medium;
        release.fallback = FallbackPolicy::NativeThenNeedsEvidence;
        assert_eq!(
            validate_contracts(&contracts),
            Err(ContractError::SafetyFallbackWeakened)
        );
    }

    #[test]
    fn security_contract_has_mandatory_safety_semantics() {
        let security = builtin(Archetype::SecuritySensitiveChange);
        assert_eq!(security.applicability.risk_floor, RiskLevel::High);
        assert_eq!(security.applicability.risk_ceiling, RiskLevel::High);
        assert_eq!(security.execution_floor.profile, ProfileClass::Strong);
        assert_eq!(security.execution_floor.reasoning, Reasoning::High);
        assert!(
            security
                .validation
                .contains(&ValidationObligation::SecurityReview)
        );
        assert!(
            security
                .escalation
                .contains(&EscalationTrigger::SafetyEvidenceConflict)
        );
        assert_eq!(security.fallback, FallbackPolicy::NativeThenBlock);
    }
}
