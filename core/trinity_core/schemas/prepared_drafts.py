"""Prepared draft contracts for active-thread runtime refresh."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .integration import RankedDraftSet


def _require_text(value: str, *, field_name: str) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{field_name} is required.")


def _require_timezone(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class PreparedDraftSet:
    company_id: UUID
    thread_ref: str
    prepared_at: datetime
    expires_at: datetime
    source_thread_version: str
    retrieval_context_hash: str
    generation_reason: str
    ranked_draft_set: RankedDraftSet

    def __post_init__(self) -> None:
        _require_text(self.thread_ref, field_name="thread_ref")
        _require_text(self.source_thread_version, field_name="source_thread_version")
        _require_text(self.retrieval_context_hash, field_name="retrieval_context_hash")
        _require_text(self.generation_reason, field_name="generation_reason")
        _require_timezone(self.prepared_at, field_name="prepared_at")
        _require_timezone(self.expires_at, field_name="expires_at")


@dataclass(frozen=True, slots=True)
class PreparedDraftRefreshCandidate:
    """One active thread that should be refreshed by the bounded control plane."""

    company_id: UUID
    thread_ref: str
    channel: str
    contact_handle: str
    refresh_reason: str
    priority_rank: int
    refresh_recommended: bool
    dirty: bool = False
    stale: bool = False
    missing_prepared_draft: bool = False
    last_event_at: datetime | None = None
    last_snapshot_at: datetime | None = None
    dirty_at: datetime | None = None
    prepared_at: datetime | None = None
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_text(self.thread_ref, field_name="thread_ref")
        _require_text(self.channel, field_name="channel")
        _require_text(self.contact_handle, field_name="contact_handle")
        _require_text(self.refresh_reason, field_name="refresh_reason")
        if self.priority_rank < 1:
            raise ValueError("priority_rank must be greater than or equal to 1.")
        for field_name in (
            "last_event_at",
            "last_snapshot_at",
            "dirty_at",
            "prepared_at",
            "expires_at",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _require_timezone(value, field_name=field_name)


@dataclass(frozen=True, slots=True)
class PreparedDraftRefreshPlan:
    """Inspectable bounded refresh plan for one tenant's active threads."""

    company_id: UUID
    generated_at: datetime
    stale_before: datetime
    limit: int
    candidates: tuple[PreparedDraftRefreshCandidate, ...] = ()

    def __post_init__(self) -> None:
        _require_timezone(self.generated_at, field_name="generated_at")
        _require_timezone(self.stale_before, field_name="stale_before")
        if self.limit < 1:
            raise ValueError("limit must be greater than or equal to 1.")
