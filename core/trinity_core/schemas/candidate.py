"""Candidate lifecycle contracts for the Trinity runtime."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
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
class ScoreFactor:
    """One explicit sub-signal contributing to a headline candidate score."""

    name: str
    value: float
    rationale: str = ""
    evidence_anchors: tuple[str, ...] = ()
    provenance: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Score factors require a non-empty name.")
        if not math.isfinite(float(self.value)):
            raise ValueError("Score factor values must be finite numbers.")
        object.__setattr__(
            self,
            "evidence_anchors",
            tuple(str(anchor).strip() for anchor in self.evidence_anchors if str(anchor).strip()),
        )


@dataclass(frozen=True, slots=True)
class ScoreDimensionProfile:
    """Factor bundle and provenance for one headline score dimension."""

    factors: tuple[ScoreFactor, ...] = ()
    rationale: str = ""
    evidence_anchors: tuple[str, ...] = ()
    provenance: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "factors", tuple(_score_factor(item) for item in self.factors))
        object.__setattr__(
            self,
            "evidence_anchors",
            tuple(str(anchor).strip() for anchor in self.evidence_anchors if str(anchor).strip()),
        )


@dataclass(frozen=True, slots=True)
class CandidateScoreProfile:
    """Explicit factor-level profile behind candidate headline scores."""

    impact: ScoreDimensionProfile | None = None
    confidence: ScoreDimensionProfile | None = None
    delivery_difficulty: ScoreDimensionProfile | None = None
    provenance: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "impact", _score_dimension(self.impact))
        object.__setattr__(self, "confidence", _score_dimension(self.confidence))
        object.__setattr__(
            self,
            "delivery_difficulty",
            _score_dimension(self.delivery_difficulty),
        )


@dataclass(frozen=True, slots=True)
class HeadlineScoreSnapshot:
    """One explicit top-line score tuple preserved before calibration."""

    impact: int
    confidence: int
    ease: int

    def __post_init__(self) -> None:
        for value in (self.impact, self.confidence, self.ease):
            if value < 1 or value > 10:
                raise ValueError("Headline scores must be between 1 and 10.")

    @property
    def delivery_difficulty(self) -> int:
        return self.ease


@dataclass(frozen=True, slots=True)
class CandidateScores:
    """Scoring dimensions used across generation, evaluation, and ranking.

    Compatibility note:
    `ease` remains the persisted public field, but its intended runtime meaning is
    delivery difficulty rather than generic textual convenience.
    """

    impact: int
    confidence: int
    ease: int
    quality_score: float | None = None
    urgency_score: float | None = None
    freshness_score: float | None = None
    feedback_score: float = 0.0
    score_profile: CandidateScoreProfile | None = None
    proposed_scores: HeadlineScoreSnapshot | None = None
    audit_flags: tuple[str, ...] = ()
    calibration_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value in (self.impact, self.confidence, self.ease):
            if value < 1 or value > 10:
                raise ValueError("Impact, confidence, and ease must be between 1 and 10.")
        object.__setattr__(self, "score_profile", _score_profile(self.score_profile))
        object.__setattr__(self, "proposed_scores", _headline_scores(self.proposed_scores))
        object.__setattr__(
            self,
            "audit_flags",
            tuple(str(flag).strip() for flag in self.audit_flags if str(flag).strip()),
        )
        object.__setattr__(
            self,
            "calibration_notes",
            tuple(str(note).strip() for note in self.calibration_notes if str(note).strip()),
        )

    @property
    def ice_score(self) -> int:
        return self.impact * self.confidence * self.ease

    @property
    def delivery_difficulty(self) -> int:
        """Compatibility-preserving semantic alias for the third headline score."""

        return self.ease


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


def _score_factor(value: ScoreFactor | dict[str, Any]) -> ScoreFactor:
    if isinstance(value, ScoreFactor):
        return value
    if isinstance(value, dict):
        return ScoreFactor(
            name=str(value.get("name") or ""),
            value=float(value.get("value") or 0.0),
            rationale=str(value.get("rationale") or ""),
            evidence_anchors=tuple(value.get("evidence_anchors", ())),
            provenance=str(value.get("provenance") or ""),
        )
    raise TypeError("Score factors must be ScoreFactor instances or dict payloads.")


def _score_dimension(
    value: ScoreDimensionProfile | dict[str, Any] | None,
) -> ScoreDimensionProfile | None:
    if value is None or isinstance(value, ScoreDimensionProfile):
        return value
    if isinstance(value, dict):
        return ScoreDimensionProfile(
            factors=tuple(value.get("factors", ())),
            rationale=str(value.get("rationale") or ""),
            evidence_anchors=tuple(value.get("evidence_anchors", ())),
            provenance=str(value.get("provenance") or ""),
        )
    raise TypeError("Score dimension profiles must be ScoreDimensionProfile or dict payloads.")


def _score_profile(
    value: CandidateScoreProfile | dict[str, Any] | None,
) -> CandidateScoreProfile | None:
    if value is None or isinstance(value, CandidateScoreProfile):
        return value
    if isinstance(value, dict):
        return CandidateScoreProfile(
            impact=value.get("impact"),
            confidence=value.get("confidence"),
            delivery_difficulty=value.get("delivery_difficulty"),
            provenance=str(value.get("provenance") or ""),
        )
    raise TypeError("score_profile must be CandidateScoreProfile or dict payload.")


def _headline_scores(
    value: HeadlineScoreSnapshot | dict[str, Any] | None,
) -> HeadlineScoreSnapshot | None:
    if value is None or isinstance(value, HeadlineScoreSnapshot):
        return value
    if isinstance(value, dict):
        return HeadlineScoreSnapshot(
            impact=int(value.get("impact") or 0),
            confidence=int(value.get("confidence") or 0),
            ease=int(value.get("ease") or 0),
        )
    raise TypeError("proposed_scores must be HeadlineScoreSnapshot or dict payload.")
