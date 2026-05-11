"""Generic runtime decision contracts for consensus, confidence, and loop control."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


def _require_text(value: str, *, field_name: str) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{field_name} is required.")


def _require_timezone(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


class LoopAction(StrEnum):
    ACCEPT = "accept"
    REWORK = "rework"
    ESCALATE = "escalate"


@dataclass(frozen=True, slots=True)
class StageOpinion:
    stage_name: str
    candidate_id: UUID | None
    confidence: float
    disposition: str
    rationale: str

    def __post_init__(self) -> None:
        _require_text(self.stage_name, field_name="stage_name")
        _require_text(self.disposition, field_name="disposition")
        _require_text(self.rationale, field_name="rationale")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0.")


@dataclass(frozen=True, slots=True)
class MinorityReport:
    cycle_id: UUID
    adapter: str
    company_id: UUID
    majority_result_ref: str
    minority_result_ref: str
    dissent_source: str
    dissent_reason: str
    disagreement_severity: float
    evidence_anchors: tuple[str, ...] = ()
    memory_factors: tuple[str, ...] = ()
    recommended_action: str = LoopAction.REWORK.value
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        _require_text(self.adapter, field_name="adapter")
        _require_text(self.majority_result_ref, field_name="majority_result_ref")
        _require_text(self.minority_result_ref, field_name="minority_result_ref")
        _require_text(self.dissent_source, field_name="dissent_source")
        _require_text(self.dissent_reason, field_name="dissent_reason")
        _require_text(self.recommended_action, field_name="recommended_action")
        if not 0.0 <= float(self.disagreement_severity) <= 1.0:
            raise ValueError("disagreement_severity must be between 0.0 and 1.0.")
        _require_timezone(self.created_at, field_name="created_at")


@dataclass(frozen=True, slots=True)
class ConfidenceBundle:
    generator_confidence: float
    refiner_confidence: float
    evaluator_confidence: float
    frontier_confidence: float
    combined_confidence: float
    disagreement_severity: float = 0.0

    def __post_init__(self) -> None:
        for field_name in (
            "generator_confidence",
            "refiner_confidence",
            "evaluator_confidence",
            "frontier_confidence",
            "combined_confidence",
            "disagreement_severity",
        ):
            value = float(getattr(self, field_name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must be between 0.0 and 1.0.")


@dataclass(frozen=True, slots=True)
class ConsensusDecision:
    majority_candidate_id: UUID | None
    majority_reason: str
    stage_opinions: tuple[StageOpinion, ...]
    confidence_bundle: ConfidenceBundle
    minority_report: MinorityReport | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.majority_reason, field_name="majority_reason")
        if not self.stage_opinions:
            raise ValueError("stage_opinions is required.")


@dataclass(frozen=True, slots=True)
class LoopDecision:
    action: LoopAction
    reason: str
    loop_count: int
    max_loop_count: int
    confidence_bundle: ConfidenceBundle
    minority_report: MinorityReport | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.reason, field_name="reason")
        if self.loop_count < 0:
            raise ValueError("loop_count cannot be negative.")
        if self.max_loop_count < 0:
            raise ValueError("max_loop_count cannot be negative.")


@dataclass(frozen=True, slots=True)
class HumanEscalation:
    cycle_id: UUID
    adapter: str
    company_id: UUID
    majority_result_ref: str
    decision_target: str
    escalation_reason: str
    loop_history_summary: tuple[str, ...]
    unresolved_questions: tuple[str, ...] = ()
    evidence_anchors: tuple[str, ...] = ()
    memory_factors: tuple[str, ...] = ()
    minority_report: MinorityReport | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        _require_text(self.adapter, field_name="adapter")
        _require_text(self.majority_result_ref, field_name="majority_result_ref")
        _require_text(self.decision_target, field_name="decision_target")
        _require_text(self.escalation_reason, field_name="escalation_reason")
        if not self.loop_history_summary:
            raise ValueError("loop_history_summary is required.")
        _require_timezone(self.created_at, field_name="created_at")
