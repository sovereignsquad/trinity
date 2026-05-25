"""Versioned portable export contracts for the governed Train producer seam."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

PORTABLE_EXPORT_CONTRACT_VERSION = "trinity_portable_export.v1"


def _require_text(value: str, *, field_name: str) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{field_name} is required.")


def _require_timezone(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


class PortableExportFamily(StrEnum):
    SOURCE = "source"
    OUTCOME = "outcome"
    MEMORY = "memory"
    DELTA = "delta"


@dataclass(frozen=True, slots=True)
class PortableExportManifestEntry:
    """One included runtime source family and record count."""

    family_name: str
    record_count: int
    source_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.family_name, field_name="family_name")
        if self.record_count < 0:
            raise ValueError("record_count must be non-negative.")


@dataclass(frozen=True, slots=True)
class PortableExportLineage:
    """Replay and snapshot lineage for one persisted portable export."""

    export_id: str
    schema_version: str
    prior_export_id: str | None = None
    prior_snapshot_ref: str | None = None
    cutoff_ref: str | None = None
    extended_export_ids: tuple[str, ...] = ()
    record_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.export_id, field_name="export_id")
        _require_text(self.schema_version, field_name="schema_version")


@dataclass(frozen=True, slots=True)
class PortableExportIntegrity:
    """Deterministic integrity metadata for a portable export envelope."""

    content_sha256: str
    record_ids_sha256: str
    canonicalization: str = "json_sorted_keys_v1"

    def __post_init__(self) -> None:
        _require_text(self.content_sha256, field_name="content_sha256")
        _require_text(self.record_ids_sha256, field_name="record_ids_sha256")
        _require_text(self.canonicalization, field_name="canonicalization")


@dataclass(frozen=True, slots=True)
class SourceExportRecord:
    """Stable raw source record exported for knowledge and delta pack builds."""

    record_id: str
    record_type: str
    producer_adapter: str
    tenant_scope: str
    occurred_at: datetime
    source_ref: str
    runtime_ref: str
    provenance_refs: tuple[str, ...] = ()
    attachment_refs: tuple[str, ...] = ()
    quality_metadata: Mapping[str, Any] = field(default_factory=dict)
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.record_id, field_name="record_id")
        _require_text(self.record_type, field_name="record_type")
        _require_text(self.producer_adapter, field_name="producer_adapter")
        _require_text(self.tenant_scope, field_name="tenant_scope")
        _require_text(self.source_ref, field_name="source_ref")
        _require_text(self.runtime_ref, field_name="runtime_ref")
        _require_timezone(self.occurred_at, field_name="occurred_at")


@dataclass(frozen=True, slots=True)
class OutcomeExportRecord:
    """Stable supervised outcome or candidate-variant record for core training."""

    record_id: str
    record_type: str
    producer_adapter: str
    tenant_scope: str
    occurred_at: datetime
    cycle_id: str
    thread_ref: str
    runtime_ref: str
    provenance_refs: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    quality_metadata: Mapping[str, Any] = field(default_factory=dict)
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.record_id, field_name="record_id")
        _require_text(self.record_type, field_name="record_type")
        _require_text(self.producer_adapter, field_name="producer_adapter")
        _require_text(self.tenant_scope, field_name="tenant_scope")
        _require_text(self.cycle_id, field_name="cycle_id")
        _require_text(self.thread_ref, field_name="thread_ref")
        _require_text(self.runtime_ref, field_name="runtime_ref")
        _require_timezone(self.occurred_at, field_name="occurred_at")


@dataclass(frozen=True, slots=True)
class MemoryExportRecord:
    """Stable structured memory record exported for knowledge and delta packs."""

    record_id: str
    record_type: str
    producer_adapter: str
    tenant_scope: str
    occurred_at: datetime
    scope_ref: str
    runtime_ref: str
    provenance_refs: tuple[str, ...] = ()
    evidence_anchors: tuple[str, ...] = ()
    freshness_metadata: Mapping[str, Any] = field(default_factory=dict)
    confidence_metadata: Mapping[str, Any] = field(default_factory=dict)
    conflict_metadata: Mapping[str, Any] = field(default_factory=dict)
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.record_id, field_name="record_id")
        _require_text(self.record_type, field_name="record_type")
        _require_text(self.producer_adapter, field_name="producer_adapter")
        _require_text(self.tenant_scope, field_name="tenant_scope")
        _require_text(self.scope_ref, field_name="scope_ref")
        _require_text(self.runtime_ref, field_name="runtime_ref")
        _require_timezone(self.occurred_at, field_name="occurred_at")


@dataclass(frozen=True, slots=True)
class SourceExportEnvelope:
    export_family: PortableExportFamily
    export_version: str
    producer_system: str
    producer_adapter: str
    tenant_scope: str
    created_at: datetime
    snapshot_ref: str
    source_manifest: tuple[PortableExportManifestEntry, ...]
    record_count: int
    lineage: PortableExportLineage
    integrity: PortableExportIntegrity
    records: tuple[SourceExportRecord, ...]
    contract_version: str = PORTABLE_EXPORT_CONTRACT_VERSION


@dataclass(frozen=True, slots=True)
class OutcomeExportEnvelope:
    export_family: PortableExportFamily
    export_version: str
    producer_system: str
    producer_adapter: str
    tenant_scope: str
    created_at: datetime
    snapshot_ref: str
    source_manifest: tuple[PortableExportManifestEntry, ...]
    record_count: int
    lineage: PortableExportLineage
    integrity: PortableExportIntegrity
    records: tuple[OutcomeExportRecord, ...]
    contract_version: str = PORTABLE_EXPORT_CONTRACT_VERSION


@dataclass(frozen=True, slots=True)
class MemoryExportEnvelope:
    export_family: PortableExportFamily
    export_version: str
    producer_system: str
    producer_adapter: str
    tenant_scope: str
    created_at: datetime
    snapshot_ref: str
    source_manifest: tuple[PortableExportManifestEntry, ...]
    record_count: int
    lineage: PortableExportLineage
    integrity: PortableExportIntegrity
    records: tuple[MemoryExportRecord, ...]
    contract_version: str = PORTABLE_EXPORT_CONTRACT_VERSION


@dataclass(frozen=True, slots=True)
class DeltaExportEnvelope:
    export_family: PortableExportFamily
    export_version: str
    producer_system: str
    producer_adapter: str
    tenant_scope: str
    created_at: datetime
    cutoff_ref: str
    snapshot_ref: str
    source_manifest: tuple[PortableExportManifestEntry, ...]
    record_count: int
    lineage: PortableExportLineage
    integrity: PortableExportIntegrity
    source_records: tuple[SourceExportRecord, ...]
    outcome_records: tuple[OutcomeExportRecord, ...]
    memory_records: tuple[MemoryExportRecord, ...]
    contract_version: str = PORTABLE_EXPORT_CONTRACT_VERSION
