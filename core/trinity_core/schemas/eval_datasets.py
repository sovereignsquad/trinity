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
