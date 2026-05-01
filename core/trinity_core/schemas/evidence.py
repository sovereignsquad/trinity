"""Evidence contracts for the Trinity runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID


class EvidenceSourceType(StrEnum):
    """Product-neutral source classes for ingested evidence."""

    EMAIL = "EMAIL"
    NOTE = "NOTE"
    DOCUMENT = "DOCUMENT"
    TRANSCRIPT = "TRANSCRIPT"
    CRM = "CRM"
    WEB = "WEB"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class EvidenceSourceRef:
    """Stable external identity for one upstream source artifact."""

    external_id: str
    locator: str | None = None
    version: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceFreshnessWindow:
    """How long evidence should be treated as fresh by downstream stages."""

    starts_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if self.starts_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("Freshness window timestamps must be timezone-aware.")
        if self.expires_at <= self.starts_at:
            raise ValueError("Freshness window must expire after it starts.")

    @classmethod
    def from_duration(
        cls, *, starts_at: datetime, duration: timedelta
    ) -> EvidenceFreshnessWindow:
        if duration <= timedelta(0):
            raise ValueError("Freshness duration must be positive.")
        return cls(starts_at=starts_at, expires_at=starts_at + duration)


@dataclass(frozen=True, slots=True)
class EvidenceProvenance:
    """Audit trail for how Trinity collected and ingested evidence."""

    collected_at: datetime
    collector: str
    ingestion_channel: str
    raw_origin_uri: str | None = None
    ingestion_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.collected_at.tzinfo is None:
            raise ValueError("Provenance timestamp must be timezone-aware.")
        if not self.collector.strip():
            raise ValueError("Provenance collector is required.")
        if not self.ingestion_channel.strip():
            raise ValueError("Provenance ingestion channel is required.")


@dataclass(frozen=True, slots=True)
class EvidenceUnit:
    """Canonical runtime representation of one evidence artifact."""

    company_id: UUID
    evidence_id: UUID
    source_type: EvidenceSourceType
    source_ref: EvidenceSourceRef
    content_raw: str
    content_canonical: str
    content_hash: str
    metadata: Mapping[str, str]
    topic_hints: tuple[str, ...] = field(default_factory=tuple)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    freshness_window: EvidenceFreshnessWindow | None = None
    provenance: EvidenceProvenance | None = None

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("Evidence timestamps must be timezone-aware.")
        if self.updated_at < self.created_at:
            raise ValueError("Evidence updated_at cannot be earlier than created_at.")
        if not self.content_raw.strip():
            raise ValueError("Evidence raw content is required.")
        if not self.content_canonical.strip():
            raise ValueError("Evidence canonical content is required.")
        if not self.content_hash.strip():
            raise ValueError("Evidence content hash is required.")
        if self.freshness_window and self.freshness_window.starts_at < self.created_at:
            raise ValueError("Freshness window cannot start before evidence creation.")
        if self.provenance and self.provenance.collected_at > self.created_at:
            raise ValueError("Provenance collection cannot occur after evidence creation.")
