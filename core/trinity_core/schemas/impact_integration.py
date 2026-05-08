"""Impact adapter integration contracts owned by the Trinity runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .candidate import CandidateRecord, CandidateScores
from .evidence import EvidenceUnit

IMPACT_CONTRACT_VERSION = "trinity.impact.v1alpha1"
IMPACT_ADAPTER_CONTRACT_VERSION = IMPACT_CONTRACT_VERSION


def _require_timezone(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


def _require_text(value: str, *, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required.")


class ImpactRecommendationDisposition(StrEnum):
    """Canonical operator outcomes for Impact recommendation candidates."""

    SHOWN = "SHOWN"
    APPLIED = "APPLIED"
    DEFERRED = "DEFERRED"
    REJECTED = "REJECTED"
    IGNORED = "IGNORED"


@dataclass(frozen=True, slots=True)
class ImpactRuntimeSnapshot:
    """One normalized runtime row from an Impact profile."""

    runtime_id: str
    status: str
    installed: bool
    reachable: bool | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.runtime_id, field_name="runtime_id")
        _require_text(self.status, field_name="status")


@dataclass(frozen=True, slots=True)
class ImpactModelSnapshot:
    """One normalized model row from an Impact profile."""

    model_id: str
    runtime_id: str
    locality: str
    presence: str

    def __post_init__(self) -> None:
        _require_text(self.model_id, field_name="model_id")
        _require_text(self.runtime_id, field_name="runtime_id")
        _require_text(self.locality, field_name="locality")
        _require_text(self.presence, field_name="presence")


@dataclass(frozen=True, slots=True)
class ImpactProfileSnapshot:
    """Canonical Impact snapshot used to request ranked operator recommendations."""

    project_ref: str
    profile_ref: str
    requested_at: datetime
    machine_class: str
    os_name: str
    architecture: str
    readiness_summary: str
    runtimes: tuple[ImpactRuntimeSnapshot, ...] = ()
    models: tuple[ImpactModelSnapshot, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    contract_version: str = IMPACT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.project_ref, field_name="project_ref")
        _require_text(self.profile_ref, field_name="profile_ref")
        _require_timezone(self.requested_at, field_name="requested_at")
        _require_text(self.machine_class, field_name="machine_class")
        _require_text(self.os_name, field_name="os_name")
        _require_text(self.architecture, field_name="architecture")
        _require_text(self.readiness_summary, field_name="readiness_summary")


@dataclass(frozen=True, slots=True)
class ImpactRecommendationCandidate:
    """Ranked Impact recommendation candidate surfaced by Trinity."""

    candidate_id: UUID
    profile_ref: str
    rank: int
    headline: str
    recommendation_text: str
    rationale: str
    risk_flags: tuple[str, ...]
    scores: CandidateScores
    source_evidence_ids: tuple[UUID, ...]
    contract_version: str = IMPACT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.profile_ref, field_name="profile_ref")
        _require_text(self.headline, field_name="headline")
        _require_text(self.recommendation_text, field_name="recommendation_text")
        _require_text(self.rationale, field_name="rationale")
        if self.rank < 1:
            raise ValueError("rank must be greater than or equal to 1.")
        if not self.source_evidence_ids:
            raise ValueError("source_evidence_ids is required.")

    @classmethod
    def from_candidate_record(
        cls,
        candidate: CandidateRecord,
        *,
        profile_ref: str,
        rank: int,
        risk_flags: tuple[str, ...] = (),
    ) -> ImpactRecommendationCandidate:
        return cls(
            candidate_id=candidate.candidate_id,
            profile_ref=profile_ref,
            rank=rank,
            headline=candidate.title,
            recommendation_text=candidate.content,
            rationale=candidate.evaluation_reason or candidate.title,
            risk_flags=risk_flags,
            scores=candidate.scores,
            source_evidence_ids=candidate.lineage.source_evidence_ids,
        )


@dataclass(frozen=True, slots=True)
class ImpactRankedRecommendationSet:
    """Top-ranked recommendations returned to the Impact adapter for one cycle."""

    cycle_id: UUID
    profile_ref: str
    generated_at: datetime
    recommendations: tuple[ImpactRecommendationCandidate, ...]
    trace_ref: str | None = None
    contract_version: str = IMPACT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.profile_ref, field_name="profile_ref")
        _require_timezone(self.generated_at, field_name="generated_at")
        if not self.recommendations:
            raise ValueError("recommendations is required.")


@dataclass(frozen=True, slots=True)
class ImpactRecommendationOutcomeEvent:
    """Deterministic operator outcome emitted from Impact back into Trinity."""

    profile_ref: str
    cycle_id: UUID
    disposition: ImpactRecommendationDisposition
    occurred_at: datetime
    candidate_id: UUID | None = None
    final_note: str | None = None
    contract_version: str = IMPACT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.profile_ref, field_name="profile_ref")
        _require_timezone(self.occurred_at, field_name="occurred_at")


@dataclass(frozen=True, slots=True)
class ImpactRuntimeTraceExport:
    """Replayable Impact trace export for adapter verification and future learning."""

    cycle_id: UUID
    exported_at: datetime
    snapshot_hash: str
    profile_snapshot: ImpactProfileSnapshot
    evidence_units: tuple[EvidenceUnit, ...]
    candidates: tuple[CandidateRecord, ...]
    frontier_candidate_ids: tuple[UUID, ...]
    ranked_recommendation_set: ImpactRankedRecommendationSet
    feedback_events: tuple[ImpactRecommendationOutcomeEvent, ...] = ()
    model_routes: Mapping[str, str] = field(default_factory=dict)
    contract_version: str = IMPACT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_timezone(self.exported_at, field_name="exported_at")
        _require_text(self.snapshot_hash, field_name="snapshot_hash")
        if not self.frontier_candidate_ids:
            raise ValueError("frontier_candidate_ids is required.")
