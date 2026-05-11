"""Explicit contracts for normalizing Gobii task output into Trinity-owned artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from .evidence import EvidenceSourceType, EvidenceUnit
from .gobii_tasks import GobiiTaskRecord
from .memory import DocumentRecord, MemoryEvent

GOBII_NORMALIZATION_CONTRACT_VERSION = "trinity.gobii-normalization.v1alpha1"


def _require_text(value: str, *, field_name: str) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{field_name} is required.")


def _require_timezone(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class GobiiTaskNormalizationRequest:
    """Explicit adapter-safe envelope for Gobii output ingestion."""

    company_id: UUID
    document_ref: str
    path: str
    content_text: str
    source_type: EvidenceSourceType
    task_id: str | None = None
    task_record_path: str | None = None
    title: str | None = None
    occurred_at: datetime | None = None
    thread_ref: str | None = None
    channel: str | None = None
    contact_handle: str | None = None
    source_external_id: str | None = None
    source_locator: str | None = None
    raw_origin_uri: str | None = None
    topic_hints: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    contract_version: str = GOBII_NORMALIZATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.document_ref, field_name="document_ref")
        _require_text(self.path, field_name="path")
        _require_text(self.content_text, field_name="content_text")
        if not self.task_id and not self.task_record_path:
            raise ValueError("Either task_id or task_record_path is required.")
        if any(
            value is not None
            for value in (self.thread_ref, self.channel, self.contact_handle)
        ):
            if not self.thread_ref or not self.channel or not self.contact_handle:
                raise ValueError(
                    "thread_ref, channel, and contact_handle must be provided together."
                )
        if self.occurred_at is not None:
            _require_timezone(self.occurred_at, field_name="occurred_at")


@dataclass(frozen=True, slots=True)
class GobiiNormalizedArtifactBundle:
    """Persisted Trinity-owned artifact produced from one Gobii task result."""

    adapter_name: str
    company_id: UUID
    task_record_path: str
    normalized_at: datetime
    task_record: GobiiTaskRecord
    document: DocumentRecord
    memory_event: MemoryEvent
    evidence_unit: EvidenceUnit
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = GOBII_NORMALIZATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_text(self.task_record_path, field_name="task_record_path")
        _require_timezone(self.normalized_at, field_name="normalized_at")
        if self.task_record.company_id and self.task_record.company_id != str(self.company_id):
            raise ValueError("task_record.company_id must match bundle company_id.")
        if self.document.company_id != self.company_id:
            raise ValueError("document.company_id must match bundle company_id.")
        if self.memory_event.company_id != self.company_id:
            raise ValueError("memory_event.company_id must match bundle company_id.")
        if self.evidence_unit.company_id != self.company_id:
            raise ValueError("evidence_unit.company_id must match bundle company_id.")
