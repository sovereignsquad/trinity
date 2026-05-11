"""Gobii browser-use task contracts for bounded Trinity ops integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


def _require_text(value: str, *, field_name: str) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{field_name} is required.")


def _require_timezone(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


class GobiiTaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class GobiiTaskCreateRequest:
    """Minimal create-task payload for Gobii browser-use tasks."""

    prompt: str
    agent_id: str | None = None
    webhook: str | None = None
    output_schema: dict[str, Any] | None = None
    wait_seconds: int | None = None

    def __post_init__(self) -> None:
        _require_text(self.prompt, field_name="prompt")


@dataclass(frozen=True, slots=True)
class GobiiTaskRecord:
    """Normalized Gobii browser-use task record."""

    id: str
    status: GobiiTaskStatus
    created_at: datetime
    updated_at: datetime
    prompt: str | None = None
    agent_id: str | None = None
    error_message: str | None = None
    credits_cost: str | None = None
    webhook: str | None = None
    webhook_last_status_code: int | None = None
    webhook_last_error: str | None = None
    adapter_name: str | None = None
    company_id: str | None = None
    raw_payload: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _require_text(self.id, field_name="id")
        _require_timezone(self.created_at, field_name="created_at")
        _require_timezone(self.updated_at, field_name="updated_at")
