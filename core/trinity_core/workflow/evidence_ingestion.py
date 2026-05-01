"""Deterministic evidence ingestion helpers."""

from __future__ import annotations

import hashlib
import html
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from trinity_core.schemas import (
    EvidenceFreshnessWindow,
    EvidenceProvenance,
    EvidenceSourceRef,
    EvidenceSourceType,
    EvidenceUnit,
)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def canonicalize_content(raw_content: str) -> str:
    """Normalize raw evidence content into a stable hashing representation."""

    unescaped = html.unescape(raw_content)
    without_tags = _HTML_TAG_RE.sub(" ", unescaped)
    normalized = without_tags.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\u00a0", " ")
    lines = [line.strip() for line in normalized.split("\n")]
    collapsed = "\n".join(filter(None, lines))
    collapsed = _WHITESPACE_RE.sub(" ", collapsed)
    canonical = collapsed.strip()
    if not canonical:
        raise ValueError("Canonical content is empty after normalization.")
    return canonical


def compute_content_hash(canonical_content: str) -> str:
    """Compute the exact-hash deduplication key for canonical evidence content."""

    return hashlib.sha256(canonical_content.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RawEvidenceInput:
    """Minimal source-neutral payload required for evidence ingestion."""

    company_id: UUID
    source_type: EvidenceSourceType
    source_ref: EvidenceSourceRef
    content: str
    metadata: Mapping[str, str] = field(default_factory=dict)
    topic_hints: tuple[str, ...] = ()
    freshness_duration: timedelta = timedelta(days=7)
    provenance: EvidenceProvenance | None = None


@dataclass(frozen=True, slots=True)
class DuplicateEvidenceSuppressed:
    """Duplicate suppression decision surfaced explicitly to callers."""

    company_id: UUID
    existing_evidence_id: UUID
    duplicate_content_hash: str


@dataclass(frozen=True, slots=True)
class EvidenceIngestionResult:
    """Outcome of one ingestion attempt."""

    accepted: EvidenceUnit | None = None
    suppressed_duplicate: DuplicateEvidenceSuppressed | None = None

    def __post_init__(self) -> None:
        if (self.accepted is None) == (self.suppressed_duplicate is None):
            raise ValueError("Exactly one ingestion outcome must be populated.")


class InMemoryEvidenceStore:
    """Tenant-bound evidence store used to enforce exact-hash dedup semantics."""

    def __init__(self) -> None:
        self._by_company_and_hash: dict[tuple[UUID, str], EvidenceUnit] = {}

    def get_by_hash(self, *, company_id: UUID, content_hash: str) -> EvidenceUnit | None:
        return self._by_company_and_hash.get((company_id, content_hash))

    def save(self, evidence: EvidenceUnit) -> None:
        self._by_company_and_hash[(evidence.company_id, evidence.content_hash)] = evidence


def ingest_evidence(
    raw_evidence: RawEvidenceInput,
    *,
    store: InMemoryEvidenceStore,
    now: datetime | None = None,
) -> EvidenceIngestionResult:
    """Canonicalize, hash, and either persist or suppress one evidence payload."""

    ingested_at = now or datetime.now(UTC)
    if ingested_at.tzinfo is None:
        raise ValueError("Ingestion time must be timezone-aware.")

    canonical_content = canonicalize_content(raw_evidence.content)
    content_hash = compute_content_hash(canonical_content)

    existing = store.get_by_hash(company_id=raw_evidence.company_id, content_hash=content_hash)
    if existing:
        return EvidenceIngestionResult(
            suppressed_duplicate=DuplicateEvidenceSuppressed(
                company_id=raw_evidence.company_id,
                existing_evidence_id=existing.evidence_id,
                duplicate_content_hash=content_hash,
            )
        )

    evidence = EvidenceUnit(
        company_id=raw_evidence.company_id,
        evidence_id=uuid4(),
        source_type=raw_evidence.source_type,
        source_ref=raw_evidence.source_ref,
        content_raw=raw_evidence.content,
        content_canonical=canonical_content,
        content_hash=content_hash,
        metadata=dict(raw_evidence.metadata),
        topic_hints=raw_evidence.topic_hints,
        created_at=ingested_at,
        updated_at=ingested_at,
        freshness_window=EvidenceFreshnessWindow.from_duration(
            starts_at=ingested_at,
            duration=raw_evidence.freshness_duration,
        ),
        provenance=raw_evidence.provenance,
    )
    store.save(evidence)
    return EvidenceIngestionResult(accepted=evidence)
