"""Bounded post-training dataset contracts owned by Trinity."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

POST_TRAINING_DATASET_CONTRACT_VERSION = "trinity.post_training_dataset.v1alpha1"


def _require_timezone(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


def _require_text(value: str, *, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required.")


class PostTrainingPurpose(StrEnum):
    """Training-purpose families preserved on one post-training dataset."""

    SFT = "sft"
    LORA = "lora"
    QLORA = "qlora"


class PostTrainingExampleKind(StrEnum):
    """Operator-governed example family preserved by Trinity."""

    POSITIVE = "positive"
    CORRECTED = "corrected"
    NEGATIVE = "negative"
    ABSTAIN = "abstain"


class PostTrainingAnnotationStatus(StrEnum):
    """Curation state preserved for one post-training example."""

    CURATED = "curated"
    REVIEW_REQUIRED = "review_required"
    EXCLUDED = "excluded"


class PostTrainingSplitKind(StrEnum):
    """Deterministic split buckets for post-training datasets."""

    TRAIN = "train"
    VALIDATION = "validation"
    HOLDOUT = "holdout"


class PostTrainingDatasetStatus(StrEnum):
    """Lifecycle state for one persisted post-training dataset."""

    CANDIDATE = "candidate"
    CURATED = "curated"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class PostTrainingMessage:
    """One normalized chat-style message for supervised post-training."""

    role: str
    content: str

    def __post_init__(self) -> None:
        _require_text(self.role, field_name="role")
        _require_text(self.content, field_name="content")


@dataclass(frozen=True, slots=True)
class PostTrainingExample:
    """One provenance-linked teachable example derived from runtime artifacts."""

    example_id: str
    adapter_name: str
    company_id: UUID
    source_bundle_id: UUID
    source_cycle_id: UUID | None
    source_candidate_id: UUID | None
    example_kind: PostTrainingExampleKind
    annotation_status: PostTrainingAnnotationStatus
    task_kind: str
    messages: tuple[PostTrainingMessage, ...]
    target_text: str | None = None
    annotation_rationale: str | None = None
    input_payload: Mapping[str, Any] = field(default_factory=dict)
    target_payload: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, str] = field(default_factory=dict)
    contract_version: str = POST_TRAINING_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.example_id, field_name="example_id")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_text(self.task_kind, field_name="task_kind")
        if not self.messages:
            raise ValueError("messages is required.")
        if self.target_text is not None and not self.target_text.strip():
            raise ValueError("target_text cannot be blank when provided.")
        if self.annotation_rationale is not None and not self.annotation_rationale.strip():
            raise ValueError("annotation_rationale cannot be blank when provided.")


@dataclass(frozen=True, slots=True)
class PostTrainingDataset:
    """Persisted Trinity-owned dataset for bounded local post-training work."""

    dataset_id: str
    name: str
    adapter_name: str
    created_at: datetime
    status: PostTrainingDatasetStatus
    purposes: tuple[PostTrainingPurpose, ...]
    examples: tuple[PostTrainingExample, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = POST_TRAINING_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.dataset_id, field_name="dataset_id")
        _require_text(self.name, field_name="name")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_timezone(self.created_at, field_name="created_at")
        if not self.purposes:
            raise ValueError("purposes is required.")
        if not self.examples:
            raise ValueError("examples is required.")


@dataclass(frozen=True, slots=True)
class PostTrainingCurationDecision:
    """One persisted operator decision over a post-training example."""

    decision_id: str
    dataset_id: str
    adapter_name: str
    example_id: str
    annotation_status: PostTrainingAnnotationStatus
    rationale: str
    reviewed_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = POST_TRAINING_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.decision_id, field_name="decision_id")
        _require_text(self.dataset_id, field_name="dataset_id")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_text(self.example_id, field_name="example_id")
        _require_text(self.rationale, field_name="rationale")
        _require_timezone(self.reviewed_at, field_name="reviewed_at")


@dataclass(frozen=True, slots=True)
class PostTrainingSplitAssignment:
    """One deterministic example-to-split assignment."""

    example_id: str
    split_kind: PostTrainingSplitKind

    def __post_init__(self) -> None:
        _require_text(self.example_id, field_name="example_id")


@dataclass(frozen=True, slots=True)
class PostTrainingDatasetSplit:
    """Persisted deterministic split for one Trinity-owned post-training dataset."""

    split_id: str
    dataset_id: str
    adapter_name: str
    created_at: datetime
    validation_ratio: float
    holdout_ratio: float
    assignments: tuple[PostTrainingSplitAssignment, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = POST_TRAINING_DATASET_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.split_id, field_name="split_id")
        _require_text(self.dataset_id, field_name="dataset_id")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_timezone(self.created_at, field_name="created_at")
        if not 0.0 <= self.validation_ratio < 1.0:
            raise ValueError("validation_ratio must be between 0.0 and 1.0.")
        if not 0.0 <= self.holdout_ratio < 1.0:
            raise ValueError("holdout_ratio must be between 0.0 and 1.0.")
        if self.validation_ratio + self.holdout_ratio >= 1.0:
            raise ValueError("validation_ratio + holdout_ratio must be less than 1.0.")
        if not self.assignments:
            raise ValueError("assignments is required.")
