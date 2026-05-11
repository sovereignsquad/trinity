"""Bounded Spot reasoning contracts owned by the Trinity runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid5

from .runtime_decision import ConfidenceBundle, MinorityReport

SPOT_CONTRACT_VERSION = "trinity.spot.v1alpha1"
SPOT_TRAINING_BUNDLE_CONTRACT_VERSION = SPOT_CONTRACT_VERSION


def _require_text(value: str, *, field_name: str) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{field_name} is required.")


def _require_timezone(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class SpotReasoningRequest:
    company_id: UUID
    run_id: str
    row_ref: str
    language: str
    message_text: str
    source_platform: str | None = None
    source_handle: str | None = None
    occurred_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = SPOT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.run_id, field_name="run_id")
        _require_text(self.row_ref, field_name="row_ref")
        _require_text(self.language, field_name="language")
        _require_text(self.message_text, field_name="message_text")
        if self.occurred_at is not None:
            _require_timezone(self.occurred_at, field_name="occurred_at")


@dataclass(frozen=True, slots=True)
class SpotReasoningCandidate:
    candidate_key: str
    interpretation: str
    rationale: str
    threat_label_hint: str | None = None
    review_recommended: bool = False

    def __post_init__(self) -> None:
        _require_text(self.candidate_key, field_name="candidate_key")
        _require_text(self.interpretation, field_name="interpretation")
        _require_text(self.rationale, field_name="rationale")


class SpotReviewDisposition(StrEnum):
    CONFIRMED_POSITIVE = "CONFIRMED_POSITIVE"
    CONFIRMED_NEGATIVE = "CONFIRMED_NEGATIVE"
    CORRECTED = "CORRECTED"
    SUPPRESSED = "SUPPRESSED"


@dataclass(frozen=True, slots=True)
class SpotReviewOutcome:
    company_id: UUID
    cycle_id: UUID
    run_id: str
    row_ref: str
    selected_candidate_key: str
    disposition: SpotReviewDisposition
    final_label: str
    occurred_at: datetime
    reviewer_notes: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = SPOT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.run_id, field_name="run_id")
        _require_text(self.row_ref, field_name="row_ref")
        _require_text(self.selected_candidate_key, field_name="selected_candidate_key")
        _require_text(self.final_label, field_name="final_label")
        _require_timezone(self.occurred_at, field_name="occurred_at")


@dataclass(frozen=True, slots=True)
class SpotReasoningResult:
    company_id: UUID
    run_id: str
    row_ref: str
    generated_at: datetime
    candidates: tuple[SpotReasoningCandidate, ...]
    selected_candidate_key: str
    confidence_bundle: ConfidenceBundle
    review_required: bool = False
    review_reason: str = ""
    policy_sensitive: bool = False
    automatic_disposition: str = "review_required"
    human_override_allowed: bool = True
    deeper_analysis_available: bool = True
    escalation_recommended: bool = False
    minority_report: MinorityReport | None = None
    trace_ref: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = SPOT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.run_id, field_name="run_id")
        _require_text(self.row_ref, field_name="row_ref")
        _require_text(self.selected_candidate_key, field_name="selected_candidate_key")
        _require_timezone(self.generated_at, field_name="generated_at")
        if not self.candidates:
            raise ValueError("candidates is required.")
        candidate_keys = {candidate.candidate_key for candidate in self.candidates}
        if self.selected_candidate_key not in candidate_keys:
            raise ValueError("selected_candidate_key must exist in candidates.")
        _require_text(self.automatic_disposition, field_name="automatic_disposition")
        if self.review_required or self.policy_sensitive:
            _require_text(self.review_reason, field_name="review_reason")


@dataclass(frozen=True, slots=True)
class SpotTrainingBundle:
    bundle_id: UUID
    bundle_type: str
    exported_at: datetime
    spot_reasoning_request: SpotReasoningRequest
    spot_reasoning_result: SpotReasoningResult
    spot_review_outcome: SpotReviewOutcome
    labels: Mapping[str, str] = field(default_factory=dict)
    contract_version: str = SPOT_TRAINING_BUNDLE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.bundle_type, field_name="bundle_type")
        _require_timezone(self.exported_at, field_name="exported_at")
        if self.spot_reasoning_request.run_id != self.spot_review_outcome.run_id:
            raise ValueError("spot review outcome run_id must match the reasoning request.")
        if self.spot_reasoning_result.run_id != self.spot_review_outcome.run_id:
            raise ValueError("spot review outcome run_id must match the reasoning result.")

    @classmethod
    def build_bundle_id(cls, *, cycle_id: UUID, bundle_type: str) -> UUID:
        namespace = UUID("db9a8028-bd02-59a4-a9e9-dfefc470b8df")
        return uuid5(namespace, f"{cycle_id}:{bundle_type}")
