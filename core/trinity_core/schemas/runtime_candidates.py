"""Governed runtime-candidate import contracts for selective Train handoff."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

RUNTIME_CANDIDATE_IMPORT_CONTRACT_VERSION = "trinity_runtime_candidate_import.v1"


def _require_text(value: str, *, field_name: str) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{field_name} is required.")


def _require_timezone(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


class RuntimeCandidateFamily(StrEnum):
    MEMORY = "runtime-memory-candidate"
    SUMMARY = "runtime-summary-candidate"
    REPLY_SUPPORT = "runtime-reply-support-candidate"


class RuntimeCandidateState(StrEnum):
    STAGED = "staged"
    ADOPTED = "adopted"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class RuntimeCandidateRecord:
    candidate_id: str
    candidate_family: RuntimeCandidateFamily
    source_snapshot_ref: str
    producer_export_ref: str
    record_index: int
    text: str
    candidate_state: RuntimeCandidateState = RuntimeCandidateState.STAGED
    document_title: str | None = None
    document_path: str | None = None
    document_class: str | None = None
    record_chunk_index: int | None = None
    confidence: float = 0.0
    confidence_reason: str = ""
    freshness: str = ""
    freshness_bucket: str = ""
    conflict_flags: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    adoption_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.candidate_id, field_name="candidate_id")
        _require_text(self.source_snapshot_ref, field_name="source_snapshot_ref")
        _require_text(self.producer_export_ref, field_name="producer_export_ref")
        _require_text(self.text, field_name="text")
        if self.record_index < 0:
            raise ValueError("record_index must be non-negative.")
        if self.record_chunk_index is not None and self.record_chunk_index < 0:
            raise ValueError("record_chunk_index must be non-negative when provided.")


@dataclass(frozen=True, slots=True)
class RuntimeCandidateImportBundle:
    import_id: str
    adapter_name: str
    company_id: UUID
    artifact_ref: str
    imported_at: datetime
    manifest_path: str
    bundle_kind: str
    source_snapshot_ref: str
    candidate_family_counts: Mapping[str, int]
    source_stats: Mapping[str, int]
    lineage: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    candidates: tuple[RuntimeCandidateRecord, ...] = ()
    contract_version: str = RUNTIME_CANDIDATE_IMPORT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.import_id, field_name="import_id")
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_text(self.artifact_ref, field_name="artifact_ref")
        _require_text(self.manifest_path, field_name="manifest_path")
        _require_text(self.bundle_kind, field_name="bundle_kind")
        _require_text(self.source_snapshot_ref, field_name="source_snapshot_ref")
        _require_timezone(self.imported_at, field_name="imported_at")
