"""Memory and event contracts for the live Trinity runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from .integration import REPLY_CONTRACT_VERSION


def _require_timezone(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


def _require_text(value: str, *, field_name: str) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{field_name} is required.")


class MemoryEventKind(StrEnum):
    INBOUND_MESSAGE_RECORDED = "inbound_message_recorded"
    OUTBOUND_MESSAGE_RECORDED = "outbound_message_recorded"
    CONTACT_UPSERTED = "contact_upserted"
    DOCUMENT_REGISTERED = "document_registered"
    DOCUMENT_DELETED = "document_deleted"
    THREAD_VIEWED = "thread_viewed"
    DRAFT_SHOWN = "draft_shown"
    DRAFT_SELECTED = "draft_selected"
    DRAFT_EDITED = "draft_edited"


class MemoryScopeKind(StrEnum):
    GLOBAL = "GLOBAL"
    ADAPTER = "ADAPTER"
    PROJECT = "PROJECT"
    COMPANY = "COMPANY"
    ITEM_FAMILY = "ITEM_FAMILY"
    TOPIC = "TOPIC"
    STAGE = "STAGE"
    HUMAN_RESOLUTION = "HUMAN_RESOLUTION"


class MemoryRecordFamily(StrEnum):
    EVIDENCE = "evidence"
    PREFERENCE = "preference"
    CORRECTION = "correction"
    ANTI_PATTERN = "anti_pattern"
    SUCCESSFUL_PATTERN = "successful_pattern"
    DISAGREEMENT = "disagreement"
    HUMAN_RESOLUTION = "human_resolution"


class MemoryTier(StrEnum):
    CORE = "core"
    WORKING = "working"
    ARCHIVAL = "archival"


@dataclass(frozen=True, slots=True)
class MemoryScope:
    scope_kind: MemoryScopeKind
    scope_ref: str

    def __post_init__(self) -> None:
        _require_text(self.scope_ref, field_name="scope_ref")


@dataclass(frozen=True, slots=True)
class RetrievedMemoryRecord:
    record_key: str
    family: MemoryRecordFamily
    scope: MemoryScope
    content: str
    updated_at: datetime
    tier: MemoryTier = MemoryTier.WORKING
    relevance_score: float = 0.0
    selection_reason: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.record_key, field_name="record_key")
        _require_text(self.content, field_name="content")
        _require_timezone(self.updated_at, field_name="updated_at")


@dataclass(frozen=True, slots=True)
class RetrievedMemoryContext:
    scopes: tuple[MemoryScope, ...]
    records: tuple[RetrievedMemoryRecord, ...]
    selected_keys: tuple[str, ...]
    retrieval_context_hash: str
    tier_counts: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.scopes:
            raise ValueError("scopes is required.")
        _require_text(self.retrieval_context_hash, field_name="retrieval_context_hash")


@dataclass(frozen=True, slots=True)
class MemoryEvent:
    company_id: UUID
    event_kind: MemoryEventKind
    source_ref: str
    occurred_at: datetime
    thread_ref: str | None = None
    channel: str | None = None
    contact_handle: str | None = None
    content_text: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = REPLY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.source_ref, field_name="source_ref")
        _require_timezone(self.occurred_at, field_name="occurred_at")


@dataclass(frozen=True, slots=True)
class SelfProfile:
    company_id: UUID
    summary: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ContactProfile:
    company_id: UUID
    contact_handle: str
    display_name: str | None = None
    summary: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_text(self.contact_handle, field_name="contact_handle")


@dataclass(frozen=True, slots=True)
class RelationshipProfile:
    company_id: UUID
    contact_handle: str
    summary: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_text(self.contact_handle, field_name="contact_handle")


@dataclass(frozen=True, slots=True)
class ThreadState:
    company_id: UUID
    thread_ref: str
    channel: str
    contact_handle: str
    latest_inbound_text: str = ""
    last_event_at: datetime | None = None
    last_snapshot_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.thread_ref, field_name="thread_ref")
        _require_text(self.channel, field_name="channel")
        _require_text(self.contact_handle, field_name="contact_handle")


@dataclass(frozen=True, slots=True)
class MemoryFact:
    company_id: UUID
    fact_key: str
    scope_ref: str
    content: str
    provenance_ref: str
    created_at: datetime
    updated_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.fact_key, field_name="fact_key")
        _require_text(self.scope_ref, field_name="scope_ref")
        _require_text(self.content, field_name="content")
        _require_text(self.provenance_ref, field_name="provenance_ref")
        _require_timezone(self.created_at, field_name="created_at")
        _require_timezone(self.updated_at, field_name="updated_at")


@dataclass(frozen=True, slots=True)
class MemorySummary:
    company_id: UUID
    summary_key: str
    scope_ref: str
    content: str
    updated_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.summary_key, field_name="summary_key")
        _require_text(self.scope_ref, field_name="scope_ref")
        _require_text(self.content, field_name="content")
        _require_timezone(self.updated_at, field_name="updated_at")


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    company_id: UUID
    document_ref: str
    source: str
    path: str
    title: str | None = None
    content_text: str = ""
    occurred_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = REPLY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.document_ref, field_name="document_ref")
        _require_text(self.source, field_name="source")
        _require_text(self.path, field_name="path")
        if self.occurred_at is not None:
            _require_timezone(self.occurred_at, field_name="occurred_at")


@dataclass(frozen=True, slots=True)
class RetrievalChunk:
    company_id: UUID
    chunk_ref: str
    document_ref: str
    content: str
    created_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.chunk_ref, field_name="chunk_ref")
        _require_text(self.document_ref, field_name="document_ref")
        _require_text(self.content, field_name="content")
        _require_timezone(self.created_at, field_name="created_at")
