"""Replayable evaluation dataset contracts curated from runtime traces."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from .integration import AcceptedArtifactVersion, ThreadSnapshot

EVAL_DATASET_CONTRACT_VERSION = "trinity.eval-dataset.v1alpha1"


def _require_text(value: str, *, field_name: str) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{field_name} is required.")


def _require_timezone(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class CuratedEvalCase:
    """One replayable evaluation case promoted from a runtime trace."""

    case_id: str
    adapter_name: str
    curated_at: datetime
    curated_from_cycle_id: UUID
    curated_from_trace_ref: str | None
    selection_reason: str
    expected_text: str
    expected_disposition: str
    thread_snapshot: ThreadSnapshot
    accepted_artifact_version: AcceptedArtifactVersion
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = EVAL_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.case_id, field_name="case_id")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_text(self.selection_reason, field_name="selection_reason")
        _require_text(self.expected_text, field_name="expected_text")
        _require_text(self.expected_disposition, field_name="expected_disposition")
        _require_timezone(self.curated_at, field_name="curated_at")


@dataclass(frozen=True, slots=True)
class EvalDataset:
    """One persisted replayable evaluation dataset."""

    dataset_id: str
    name: str
    adapter_name: str
    created_at: datetime
    cases: tuple[CuratedEvalCase, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = EVAL_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.dataset_id, field_name="dataset_id")
        _require_text(self.name, field_name="name")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_timezone(self.created_at, field_name="created_at")


@dataclass(frozen=True, slots=True)
class EvalReplayCaseResult:
    """Replay result for one curated eval case."""

    case_id: str
    cycle_id: str
    trace_ref: str | None
    expected_text: str
    actual_text: str
    same_text: bool
    overlap_ratio: float
    edit_distance: float

    def __post_init__(self) -> None:
        _require_text(self.case_id, field_name="case_id")
        _require_text(self.cycle_id, field_name="cycle_id")
        _require_text(self.expected_text, field_name="expected_text")
        _require_text(self.actual_text, field_name="actual_text")


@dataclass(frozen=True, slots=True)
class EvalReplayReport:
    """Replay report for one curated dataset."""

    dataset_id: str
    adapter_name: str
    replayed_at: datetime
    case_results: tuple[EvalReplayCaseResult, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = EVAL_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.dataset_id, field_name="dataset_id")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_timezone(self.replayed_at, field_name="replayed_at")


@dataclass(frozen=True, slots=True)
class ScoreHealthTupleCluster:
    """Aggregate recurring final-score tuple observations across traces."""

    impact: int
    confidence: int
    ease: int
    occurrence_count: int
    flagged_occurrence_count: int
    flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value in (self.impact, self.confidence, self.ease):
            if value < 1 or value > 10:
                raise ValueError("Score tuple values must be between 1 and 10.")
        if self.occurrence_count < 1:
            raise ValueError("occurrence_count must be positive.")
        if self.flagged_occurrence_count < 0:
            raise ValueError("flagged_occurrence_count cannot be negative.")


@dataclass(frozen=True, slots=True)
class ScoreHealthReport:
    """Aggregate score-governance report derived from persisted runtime traces."""

    report_id: str
    adapter_name: str
    created_at: datetime
    trace_count: int
    candidate_count: int
    flagged_candidate_count: int
    flag_counts: Mapping[str, int] = field(default_factory=dict)
    tuple_clusters: tuple[ScoreHealthTupleCluster, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = EVAL_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.report_id, field_name="report_id")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_timezone(self.created_at, field_name="created_at")
        if self.trace_count < 0:
            raise ValueError("trace_count cannot be negative.")
        if self.candidate_count < 0:
            raise ValueError("candidate_count cannot be negative.")
        if self.flagged_candidate_count < 0:
            raise ValueError("flagged_candidate_count cannot be negative.")


@dataclass(frozen=True, slots=True)
class ScoreHealthReviewDecision:
    """Persisted operator decision for one score-health report."""

    decision_id: str
    report_id: str
    adapter_name: str
    decided_at: datetime
    status: str
    notes: str = ""
    replay_report_dataset_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = EVAL_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.decision_id, field_name="decision_id")
        _require_text(self.report_id, field_name="report_id")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_text(self.status, field_name="status")
        _require_timezone(self.decided_at, field_name="decided_at")


@dataclass(frozen=True, slots=True)
class ScoreHealthTrendReport:
    """Aggregate trend view across multiple score-health reports."""

    trend_report_id: str
    adapter_name: str
    created_at: datetime
    report_ids: tuple[str, ...]
    compared_report_count: int
    persistent_flags: Mapping[str, int] = field(default_factory=dict)
    rising_flags: Mapping[str, int] = field(default_factory=dict)
    recurring_tuple_clusters: tuple[ScoreHealthTupleCluster, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = EVAL_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.trend_report_id, field_name="trend_report_id")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_timezone(self.created_at, field_name="created_at")
        if self.compared_report_count < 0:
            raise ValueError("compared_report_count cannot be negative.")


@dataclass(frozen=True, slots=True)
class ScoreGovernancePolicy:
    """Deterministic policy thresholds for workflow-level score governance."""

    blocked_decision_statuses: tuple[str, ...] = ("investigate", "blocked_release")
    blocked_flags: tuple[str, ...] = ()
    max_flagged_candidate_ratio: float | None = None
    persistent_flag_tolerance: int | None = None
    rising_flag_tolerance: int | None = None
    recurring_tuple_cluster_tolerance: int | None = None

    def __post_init__(self) -> None:
        if self.max_flagged_candidate_ratio is not None and (
            self.max_flagged_candidate_ratio < 0.0 or self.max_flagged_candidate_ratio > 1.0
        ):
            raise ValueError("max_flagged_candidate_ratio must be between 0.0 and 1.0.")
        for value, field_name in (
            (self.persistent_flag_tolerance, "persistent_flag_tolerance"),
            (self.rising_flag_tolerance, "rising_flag_tolerance"),
            (self.recurring_tuple_cluster_tolerance, "recurring_tuple_cluster_tolerance"),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{field_name} cannot be negative.")


@dataclass(frozen=True, slots=True)
class ScoreGovernanceCheckResult:
    """Workflow-facing decision derived from score-health governance artifacts."""

    adapter_name: str
    allowed: bool
    override_required: bool
    decision_status: str | None = None
    report_id: str | None = None
    decision_id: str | None = None
    trend_report_id: str | None = None
    flagged_candidate_ratio: float | None = None
    blocking_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    contract_version: str = EVAL_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.adapter_name, field_name="adapter_name")


@dataclass(frozen=True, slots=True)
class ScoreGovernanceReleaseReport:
    """Persisted release-readiness view derived from score-governance artifacts."""

    release_report_id: str
    adapter_name: str
    created_at: datetime
    allowed: bool
    override_required: bool
    release_risk: str
    recommendation: str
    report_id: str | None = None
    decision_id: str | None = None
    trend_report_id: str | None = None
    replay_report_dataset_id: str | None = None
    decision_status: str | None = None
    flagged_candidate_ratio: float | None = None
    persistent_flag_count: int = 0
    rising_flag_count: int = 0
    recurring_tuple_cluster_count: int = 0
    blocking_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = EVAL_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.release_report_id, field_name="release_report_id")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_text(self.release_risk, field_name="release_risk")
        _require_text(self.recommendation, field_name="recommendation")
        _require_timezone(self.created_at, field_name="created_at")


@dataclass(frozen=True, slots=True)
class ScoreGovernanceTriageItem:
    """One operator work item derived from score-governance artifacts."""

    item_id: str
    adapter_name: str
    item_kind: str
    severity: str
    status: str
    summary: str
    report_id: str | None = None
    decision_id: str | None = None
    trend_report_id: str | None = None
    artifact_key: str | None = None
    artifact_version: str | None = None
    override_count: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = EVAL_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.item_id, field_name="item_id")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_text(self.item_kind, field_name="item_kind")
        _require_text(self.severity, field_name="severity")
        _require_text(self.status, field_name="status")
        _require_text(self.summary, field_name="summary")
        if self.override_count < 0:
            raise ValueError("override_count cannot be negative.")


@dataclass(frozen=True, slots=True)
class ScoreGovernanceTriageReport:
    """Persisted triage queue view for unresolved governance work."""

    triage_report_id: str
    adapter_name: str
    created_at: datetime
    item_count: int
    items: tuple[ScoreGovernanceTriageItem, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = EVAL_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.triage_report_id, field_name="triage_report_id")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_timezone(self.created_at, field_name="created_at")
        if self.item_count < 0:
            raise ValueError("item_count cannot be negative.")


@dataclass(frozen=True, slots=True)
class ScoreGovernanceTriageResolution:
    """Persisted operator resolution for one score-governance triage item."""

    resolution_id: str
    item_id: str
    adapter_name: str
    resolved_at: datetime
    resolution_status: str
    notes: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = EVAL_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.resolution_id, field_name="resolution_id")
        _require_text(self.item_id, field_name="item_id")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_text(self.resolution_status, field_name="resolution_status")
        _require_timezone(self.resolved_at, field_name="resolved_at")


@dataclass(frozen=True, slots=True)
class ScoreGovernanceReleaseDecision:
    """Persisted operator decision for one release-governance report."""

    release_decision_id: str
    release_report_id: str
    adapter_name: str
    decided_at: datetime
    decision_status: str
    notes: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = EVAL_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.release_decision_id, field_name="release_decision_id")
        _require_text(self.release_report_id, field_name="release_report_id")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_text(self.decision_status, field_name="decision_status")
        _require_timezone(self.decided_at, field_name="decided_at")


@dataclass(frozen=True, slots=True)
class ScoreGovernanceArtifactStatus:
    """Current governance lineage for one accepted artifact family."""

    artifact_key: str
    current_version: str
    acceptance_mode: str | None = None
    score_governance_status: str | None = None
    score_governance_report_id: str | None = None
    score_governance_decision_id: str | None = None
    score_governance_trend_report_id: str | None = None
    release_governance_report_id: str | None = None
    release_governance_decision_id: str | None = None
    release_governance_decision_status: str | None = None
    override_note_count: int = 0

    def __post_init__(self) -> None:
        _require_text(self.artifact_key, field_name="artifact_key")
        _require_text(self.current_version, field_name="current_version")
        if self.override_note_count < 0:
            raise ValueError("override_note_count cannot be negative.")


@dataclass(frozen=True, slots=True)
class ScoreGovernanceStatusSurface:
    """Joined operator-facing status view over governance artifacts."""

    adapter_name: str
    generated_at: datetime
    latest_score_health_report_id: str | None = None
    latest_review_decision_id: str | None = None
    latest_review_decision_status: str | None = None
    latest_trend_report_id: str | None = None
    latest_release_report_id: str | None = None
    latest_release_decision_id: str | None = None
    latest_release_decision_status: str | None = None
    open_triage_item_count: int = 0
    resolved_triage_resolution_count: int = 0
    artifact_statuses: tuple[ScoreGovernanceArtifactStatus, ...] = ()
    top_open_triage_summaries: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = EVAL_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_timezone(self.generated_at, field_name="generated_at")
        if self.open_triage_item_count < 0:
            raise ValueError("open_triage_item_count cannot be negative.")
        if self.resolved_triage_resolution_count < 0:
            raise ValueError("resolved_triage_resolution_count cannot be negative.")


@dataclass(frozen=True, slots=True)
class CrossAdapterScoreEntry:
    """Comparable score record surfaced across adapters."""

    adapter_name: str
    cycle_id: str
    candidate_id: str
    title: str
    candidate_type: str
    ice_score: float
    priority_score: float
    audit_flags: tuple[str, ...] = ()
    score_governance_status: str | None = None
    release_governance_decision_status: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_text(self.cycle_id, field_name="cycle_id")
        _require_text(self.candidate_id, field_name="candidate_id")
        _require_text(self.title, field_name="title")
        _require_text(self.candidate_type, field_name="candidate_type")


@dataclass(frozen=True, slots=True)
class CrossAdapterScoreReport:
    """Joined score-inspection report across one or more adapters."""

    report_id: str
    created_at: datetime
    adapter_names: tuple[str, ...]
    candidate_count: int
    entries: tuple[CrossAdapterScoreEntry, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = EVAL_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.report_id, field_name="report_id")
        _require_timezone(self.created_at, field_name="created_at")
        if self.candidate_count < 0:
            raise ValueError("candidate_count cannot be negative.")


@dataclass(frozen=True, slots=True)
class ScoreGovernanceAdapterDashboardSummary:
    """Aggregate governance-churn summary for one adapter."""

    adapter_name: str
    unresolved_triage_item_count: int
    override_transition_count: int
    persistent_flag_count: int
    rising_flag_count: int
    recurring_tuple_cluster_count: int
    latest_release_risk: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.adapter_name, field_name="adapter_name")
        for value, field_name in (
            (self.unresolved_triage_item_count, "unresolved_triage_item_count"),
            (self.override_transition_count, "override_transition_count"),
            (self.persistent_flag_count, "persistent_flag_count"),
            (self.rising_flag_count, "rising_flag_count"),
            (self.recurring_tuple_cluster_count, "recurring_tuple_cluster_count"),
        ):
            if value < 0:
                raise ValueError(f"{field_name} cannot be negative.")


@dataclass(frozen=True, slots=True)
class ScoreGovernanceDashboardReport:
    """Operator-facing governance dashboard artifact across adapters."""

    report_id: str
    created_at: datetime
    adapter_summaries: tuple[ScoreGovernanceAdapterDashboardSummary, ...]
    top_persistent_flags: Mapping[str, int] = field(default_factory=dict)
    top_rising_flags: Mapping[str, int] = field(default_factory=dict)
    unresolved_override_count: int = 0
    unresolved_triage_item_count: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = EVAL_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.report_id, field_name="report_id")
        _require_timezone(self.created_at, field_name="created_at")
        if self.unresolved_override_count < 0:
            raise ValueError("unresolved_override_count cannot be negative.")
        if self.unresolved_triage_item_count < 0:
            raise ValueError("unresolved_triage_item_count cannot be negative.")
