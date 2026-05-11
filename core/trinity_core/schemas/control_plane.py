"""Control-plane job and run contracts for bounded recurring Trinity workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


def _require_text(value: str, *, field_name: str) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{field_name} is required.")


def _require_timezone(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


class ControlPlaneJobKind(StrEnum):
    REPLY_PROVIDER_COMPARISON = "reply_provider_comparison"
    REPLY_PREPARED_DRAFT_REFRESH = "reply_prepared_draft_refresh"


class ControlPlaneRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ControlPlaneJob:
    """One bounded recurring-workflow job definition."""

    job_id: str
    adapter_name: str
    job_kind: ControlPlaneJobKind
    created_at: datetime
    payload: dict[str, Any]
    schedule_hint: str | None = None
    description: str | None = None
    labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.job_id, field_name="job_id")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_timezone(self.created_at, field_name="created_at")


@dataclass(frozen=True, slots=True)
class ControlPlaneRun:
    """Inspectable execution record for one control-plane job run."""

    run_id: UUID
    job_id: str
    adapter_name: str
    job_kind: ControlPlaneJobKind
    status: ControlPlaneRunStatus
    started_at: datetime
    completed_at: datetime
    payload: dict[str, Any]
    outputs: dict[str, Any] = field(default_factory=dict)
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.job_id, field_name="job_id")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_timezone(self.started_at, field_name="started_at")
        _require_timezone(self.completed_at, field_name="completed_at")
