"""Candidate lifecycle contracts for the Trinity runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class CandidateType(StrEnum):
    """Top-level candidate families surfaced by Trinity."""

    KNOWLEDGE = "KNOWLEDGE"
    ACTION = "ACTION"


class CandidateState(StrEnum):
    """Canonical runtime states for candidates."""

    GENERATED = "GENERATED"
    REFINED = "REFINED"
    EVALUATED = "EVALUATED"
    REWORK = "REWORK"
    SUPPRESSED = "SUPPRESSED"
    ARCHIVED = "ARCHIVED"
    DELIVERED = "DELIVERED"


class ReworkRoute(StrEnum):
    """Machine rework routes defined in the formal production model."""

    REVISE = "REVISE"
    REGENERATE = "REGENERATE"
    MERGE = "MERGE"
    ENRICH = "ENRICH"
    DOWNRANK_ONLY = "DOWNRANK_ONLY"


@dataclass(frozen=True, slots=True)
class CandidateLineage:
    """Version-family lineage for refinement and rework tracking."""

    version_family_id: UUID
    parent_candidate_id: UUID | None = None
    source_evidence_ids: tuple[UUID, ...] = ()
    source_candidate_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateScores:
    """Scoring dimensions used across generation, evaluation, and ranking."""

    impact: int
    confidence: int
    ease: int
    quality_score: float | None = None
    urgency_score: float | None = None
    freshness_score: float | None = None
    feedback_score: float = 0.0

    def __post_init__(self) -> None:
        for value in (self.impact, self.confidence, self.ease):
            if value < 1 or value > 10:
                raise ValueError("Impact, confidence, and ease must be between 1 and 10.")

    @property
    def ice_score(self) -> int:
        return self.impact * self.confidence * self.ease


@dataclass(frozen=True, slots=True)
class CandidateRecord:
    """Stable candidate contract shared by runtime stages and app surfaces."""

    company_id: UUID
    candidate_id: UUID
    candidate_type: CandidateType
    state: CandidateState
    title: str
    content: str
    lineage: CandidateLineage
    scores: CandidateScores
    created_at: datetime
    updated_at: datetime
    semantic_tags: tuple[str, ...] = ()
    duplicate_cluster_id: UUID | None = None
    last_presented_at: datetime | None = None
    last_feedback_at: datetime | None = None
    last_reworked_at: datetime | None = None
    last_delivered_at: datetime | None = None
    evaluated_at: datetime | None = None
    rework_route: ReworkRoute | None = None
    evaluation_reason: str | None = None
    delivery_target_ref: str | None = None

    def __post_init__(self) -> None:
        for timestamp in (
            self.created_at,
            self.updated_at,
            self.last_presented_at,
            self.last_feedback_at,
            self.last_reworked_at,
            self.last_delivered_at,
            self.evaluated_at,
        ):
            if timestamp is not None and timestamp.tzinfo is None:
                raise ValueError("Candidate timestamps must be timezone-aware.")

        if self.updated_at < self.created_at:
            raise ValueError("Candidate updated_at cannot be earlier than created_at.")
        if not self.title.strip():
            raise ValueError("Candidate title is required.")
        if not self.content.strip():
            raise ValueError("Candidate content is required.")
        if not self.lineage.source_evidence_ids and not self.lineage.source_candidate_ids:
            raise ValueError("Candidate lineage must reference evidence or prior candidates.")
        if self.state == CandidateState.REWORK and self.rework_route is None:
            raise ValueError("Rework candidates must carry a rework route.")
        if self.state != CandidateState.REWORK and self.rework_route is not None:
            raise ValueError("Rework route is only valid for rework candidates.")
        if self.state == CandidateState.DELIVERED and self.candidate_type != CandidateType.ACTION:
            raise ValueError("Only action candidates can be delivered.")
        if self.candidate_type != CandidateType.ACTION and self.last_delivered_at is not None:
            raise ValueError("Knowledge candidates cannot track delivery timestamps.")
        if self.candidate_type != CandidateType.ACTION and self.delivery_target_ref is not None:
            raise ValueError("Knowledge candidates cannot carry delivery targets.")
