"""Portable export builders and persistence for the governed Train producer seam."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4, uuid5

from trinity_core.adapters import REPLY_ADAPTER_NAME, normalize_adapter_name
from trinity_core.memory.storage import ReplyMemoryStore
from trinity_core.ops.cycle_store import RuntimeCycleStore, dataclass_payload, write_json_atomic
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths
from trinity_core.schemas import (
    PORTABLE_EXPORT_CONTRACT_VERSION,
    DeltaExportEnvelope,
    DraftOutcomeDisposition,
    MemoryExportEnvelope,
    MemoryExportRecord,
    OutcomeExportEnvelope,
    OutcomeExportRecord,
    PortableExportFamily,
    PortableExportIntegrity,
    PortableExportLineage,
    PortableExportManifestEntry,
    SourceExportEnvelope,
    SourceExportRecord,
)

SOURCE_EXPORT_VERSION = "trinity.source_export.v1"
OUTCOME_EXPORT_VERSION = "trinity.outcome_export.v1"
MEMORY_EXPORT_VERSION = "trinity.memory_export.v1"
DELTA_EXPORT_VERSION = "trinity.delta_export.v1"
GENERIC_SUPERVISION_MARKERS = (
    "thank you for asking",
    "i've taken note",
    "let's proceed with",
    "i saw this",
    "move this forward",
    "confirm the exact outcome",
    "my read is",
    "you have a child",
    "contact the pediatrician",
    "develop a plan",
)
PORTABLE_EXPORT_SCHEMA_VERSION = "portable_export_schema.v1"
PORTABLE_EXPORT_NAMESPACE = UUID("e3ac61df-fcb7-4731-9df8-9953f68bd7b8")
PORTABLE_EXPORT_INSPECT_SCHEMA_VERSION = "trinity_portable_export_inspect.v1"
PORTABLE_EXPORT_VALIDATION_SCHEMA_VERSION = "trinity_portable_export_validation.v1"


@dataclass(frozen=True, slots=True)
class PortableExportPaths:
    adapter_name: str
    root_dir: Path
    companies_dir: Path


def resolve_portable_export_paths(
    adapter_name: str = REPLY_ADAPTER_NAME,
) -> PortableExportPaths:
    adapter_paths = resolve_adapter_runtime_paths(
        adapter_name,
        repo_root=Path(__file__).resolve().parents[3],
    )
    root_dir = adapter_paths.root_dir / "portable_exports"
    companies_dir = root_dir / "companies"
    companies_dir.mkdir(parents=True, exist_ok=True)
    return PortableExportPaths(
        adapter_name=normalize_adapter_name(adapter_name),
        root_dir=root_dir,
        companies_dir=companies_dir,
    )


class PortableExportStore:
    """Persist and inspect explicit portable export envelopes by family."""

    def __init__(
        self,
        paths: PortableExportPaths | None = None,
        *,
        adapter_name: str = REPLY_ADAPTER_NAME,
    ) -> None:
        self.paths = paths or resolve_portable_export_paths(adapter_name)

    def export_path(
        self,
        *,
        family: PortableExportFamily,
        company_id: UUID | str,
        export_id: str,
    ) -> Path:
        return self._company_family_dir(company_id, family) / f"{export_id}.json"

    def save_export(
        self,
        *,
        family: PortableExportFamily,
        company_id: UUID | str,
        export_id: str,
        payload: dict[str, Any],
    ) -> Path:
        return write_json_atomic(
            self.export_path(family=family, company_id=company_id, export_id=export_id),
            payload,
        )

    def load_export(
        self,
        *,
        family: PortableExportFamily,
        company_id: UUID | str,
        export_id: str,
    ) -> dict[str, Any]:
        return json.loads(
            self.export_path(family=family, company_id=company_id, export_id=export_id).read_text(
                encoding="utf-8"
            )
        )

    def list_export_paths(
        self,
        *,
        family: PortableExportFamily,
        company_id: UUID | str,
    ) -> tuple[Path, ...]:
        return tuple(sorted(self._company_family_dir(company_id, family).glob("*.json")))

    def _company_family_dir(self, company_id: UUID | str, family: PortableExportFamily) -> Path:
        company_dir = self.paths.companies_dir / str(company_id).strip().lower()
        family_dir = company_dir / family.value
        family_dir.mkdir(parents=True, exist_ok=True)
        return family_dir


def build_source_export(
    *,
    adapter_name: str,
    company_id: UUID | str,
    snapshot_ref: str | None = None,
    cycle_store: RuntimeCycleStore | None = None,
    memory_store: ReplyMemoryStore | None = None,
    export_store: PortableExportStore | None = None,
) -> dict[str, Any]:
    source_records = _collect_source_records(
        adapter_name=adapter_name,
        company_id=company_id,
        cycle_store=cycle_store,
        memory_store=memory_store,
    )
    export_id = _build_export_id(PortableExportFamily.SOURCE, company_id, snapshot_ref)
    created_at = datetime.now(UTC)
    scope = str(company_id).strip().lower()
    manifest = _build_manifest(source_records, family_label="source_record")
    lineage = PortableExportLineage(
        export_id=export_id,
        schema_version=PORTABLE_EXPORT_SCHEMA_VERSION,
        record_ids=tuple(record.record_id for record in source_records),
        metadata={"record_family": PortableExportFamily.SOURCE.value},
    )
    envelope = SourceExportEnvelope(
        export_family=PortableExportFamily.SOURCE,
        export_version=SOURCE_EXPORT_VERSION,
        producer_system="{trinity}",
        producer_adapter=normalize_adapter_name(adapter_name),
        tenant_scope=scope,
        created_at=created_at,
        snapshot_ref=snapshot_ref or export_id,
        source_manifest=manifest,
        record_count=len(source_records),
        lineage=lineage,
        integrity=_build_integrity_payload(source_records),
        records=source_records,
        contract_version=PORTABLE_EXPORT_CONTRACT_VERSION,
    )
    payload = dataclass_payload(envelope)
    path = (export_store or PortableExportStore(adapter_name=adapter_name)).save_export(
        family=PortableExportFamily.SOURCE,
        company_id=company_id,
        export_id=export_id,
        payload=payload,
    )
    return {"export_id": export_id, "export_path": str(path), "export": payload}


def build_outcome_export(
    *,
    adapter_name: str,
    company_id: UUID | str,
    snapshot_ref: str | None = None,
    cycle_store: RuntimeCycleStore | None = None,
    export_store: PortableExportStore | None = None,
) -> dict[str, Any]:
    outcome_records = _collect_outcome_records(
        adapter_name=adapter_name,
        company_id=company_id,
        cycle_store=cycle_store,
    )
    export_id = _build_export_id(PortableExportFamily.OUTCOME, company_id, snapshot_ref)
    created_at = datetime.now(UTC)
    scope = str(company_id).strip().lower()
    manifest = _build_manifest(outcome_records, family_label="outcome_record")
    lineage = PortableExportLineage(
        export_id=export_id,
        schema_version=PORTABLE_EXPORT_SCHEMA_VERSION,
        record_ids=tuple(record.record_id for record in outcome_records),
        metadata={"record_family": PortableExportFamily.OUTCOME.value},
    )
    envelope = OutcomeExportEnvelope(
        export_family=PortableExportFamily.OUTCOME,
        export_version=OUTCOME_EXPORT_VERSION,
        producer_system="{trinity}",
        producer_adapter=normalize_adapter_name(adapter_name),
        tenant_scope=scope,
        created_at=created_at,
        snapshot_ref=snapshot_ref or export_id,
        source_manifest=manifest,
        record_count=len(outcome_records),
        lineage=lineage,
        integrity=_build_integrity_payload(outcome_records),
        records=outcome_records,
        contract_version=PORTABLE_EXPORT_CONTRACT_VERSION,
    )
    payload = dataclass_payload(envelope)
    path = (export_store or PortableExportStore(adapter_name=adapter_name)).save_export(
        family=PortableExportFamily.OUTCOME,
        company_id=company_id,
        export_id=export_id,
        payload=payload,
    )
    return {"export_id": export_id, "export_path": str(path), "export": payload}


def build_memory_export(
    *,
    adapter_name: str,
    company_id: UUID | str,
    snapshot_ref: str | None = None,
    memory_store: ReplyMemoryStore | None = None,
    export_store: PortableExportStore | None = None,
) -> dict[str, Any]:
    memory_records = _collect_memory_records(
        adapter_name=adapter_name,
        company_id=company_id,
        memory_store=memory_store,
    )
    export_id = _build_export_id(PortableExportFamily.MEMORY, company_id, snapshot_ref)
    created_at = datetime.now(UTC)
    scope = str(company_id).strip().lower()
    manifest = _build_manifest(memory_records, family_label="memory_record")
    lineage = PortableExportLineage(
        export_id=export_id,
        schema_version=PORTABLE_EXPORT_SCHEMA_VERSION,
        record_ids=tuple(record.record_id for record in memory_records),
        metadata={"record_family": PortableExportFamily.MEMORY.value},
    )
    envelope = MemoryExportEnvelope(
        export_family=PortableExportFamily.MEMORY,
        export_version=MEMORY_EXPORT_VERSION,
        producer_system="{trinity}",
        producer_adapter=normalize_adapter_name(adapter_name),
        tenant_scope=scope,
        created_at=created_at,
        snapshot_ref=snapshot_ref or export_id,
        source_manifest=manifest,
        record_count=len(memory_records),
        lineage=lineage,
        integrity=_build_integrity_payload(memory_records),
        records=memory_records,
        contract_version=PORTABLE_EXPORT_CONTRACT_VERSION,
    )
    payload = dataclass_payload(envelope)
    path = (export_store or PortableExportStore(adapter_name=adapter_name)).save_export(
        family=PortableExportFamily.MEMORY,
        company_id=company_id,
        export_id=export_id,
        payload=payload,
    )
    return {"export_id": export_id, "export_path": str(path), "export": payload}


def build_delta_export(
    *,
    adapter_name: str,
    company_id: UUID | str,
    cutoff_at: datetime,
    snapshot_ref: str,
    prior_snapshot_ref: str | None = None,
    prior_export_id: str | None = None,
    cycle_store: RuntimeCycleStore | None = None,
    memory_store: ReplyMemoryStore | None = None,
    export_store: PortableExportStore | None = None,
) -> dict[str, Any]:
    source_records = _collect_source_records(
        adapter_name=adapter_name,
        company_id=company_id,
        cycle_store=cycle_store,
        memory_store=memory_store,
        occurred_after=cutoff_at,
    )
    outcome_records = _collect_outcome_records(
        adapter_name=adapter_name,
        company_id=company_id,
        cycle_store=cycle_store,
        occurred_after=cutoff_at,
    )
    memory_records = _collect_memory_records(
        adapter_name=adapter_name,
        company_id=company_id,
        memory_store=memory_store,
        occurred_after=cutoff_at,
    )
    export_id = _build_export_id(PortableExportFamily.DELTA, company_id, snapshot_ref)
    created_at = datetime.now(UTC)
    scope = str(company_id).strip().lower()
    combined_records: tuple[Any, ...] = source_records + outcome_records + memory_records
    lineage = PortableExportLineage(
        export_id=export_id,
        schema_version=PORTABLE_EXPORT_SCHEMA_VERSION,
        prior_export_id=prior_export_id,
        prior_snapshot_ref=prior_snapshot_ref,
        cutoff_ref=cutoff_at.isoformat(),
        record_ids=tuple(record.record_id for record in combined_records),
        metadata={"record_family": PortableExportFamily.DELTA.value},
    )
    envelope = DeltaExportEnvelope(
        export_family=PortableExportFamily.DELTA,
        export_version=DELTA_EXPORT_VERSION,
        producer_system="{trinity}",
        producer_adapter=normalize_adapter_name(adapter_name),
        tenant_scope=scope,
        created_at=created_at,
        cutoff_ref=cutoff_at.isoformat(),
        snapshot_ref=snapshot_ref,
        source_manifest=(
            PortableExportManifestEntry(
                family_name="source_records",
                record_count=len(source_records),
            ),
            PortableExportManifestEntry(
                family_name="outcome_records",
                record_count=len(outcome_records),
            ),
            PortableExportManifestEntry(
                family_name="memory_records",
                record_count=len(memory_records),
            ),
        ),
        record_count=len(combined_records),
        lineage=lineage,
        integrity=_build_integrity_payload(combined_records),
        source_records=source_records,
        outcome_records=outcome_records,
        memory_records=memory_records,
        contract_version=PORTABLE_EXPORT_CONTRACT_VERSION,
    )
    payload = dataclass_payload(envelope)
    path = (export_store or PortableExportStore(adapter_name=adapter_name)).save_export(
        family=PortableExportFamily.DELTA,
        company_id=company_id,
        export_id=export_id,
        payload=payload,
    )
    return {"export_id": export_id, "export_path": str(path), "export": payload}


def inspect_portable_export(
    *,
    adapter_name: str,
    company_id: UUID | str,
    export_family: str,
    export_id: str,
    export_store: PortableExportStore | None = None,
) -> dict[str, Any]:
    family = PortableExportFamily(str(export_family))
    payload = (export_store or PortableExportStore(adapter_name=adapter_name)).load_export(
        family=family,
        company_id=company_id,
        export_id=export_id,
    )
    record_count = int(payload.get("record_count") or 0)
    lineage = payload.get("lineage") or {}
    return {
        "contract_version": PORTABLE_EXPORT_INSPECT_SCHEMA_VERSION,
        "adapter": normalize_adapter_name(adapter_name),
        "export_family": family.value,
        "export_id": export_id,
        "record_count": record_count,
        "created_at": payload.get("created_at"),
        "snapshot_ref": payload.get("snapshot_ref"),
        "cutoff_ref": payload.get("cutoff_ref"),
        "tenant_scope": payload.get("tenant_scope"),
        "export_version": payload.get("export_version"),
        "lineage": lineage,
        "source_manifest": payload.get("source_manifest", []),
        "integrity": payload.get("integrity", {}),
        "export_path": str(
            (export_store or PortableExportStore(adapter_name=adapter_name)).export_path(
                family=family,
                company_id=company_id,
                export_id=export_id,
            )
        ),
    }


def validate_portable_export_lineage(
    *,
    adapter_name: str,
    company_id: UUID | str,
    export_family: str,
    export_id: str,
    export_store: PortableExportStore | None = None,
) -> dict[str, Any]:
    family = PortableExportFamily(str(export_family))
    payload = (export_store or PortableExportStore(adapter_name=adapter_name)).load_export(
        family=family,
        company_id=company_id,
        export_id=export_id,
    )
    errors: list[str] = []
    tenant_scope = str(payload.get("tenant_scope") or "").strip().lower()
    expected_scope = str(company_id).strip().lower()
    if tenant_scope != expected_scope:
        errors.append("tenant_scope_mismatch")
    if family is PortableExportFamily.DELTA:
        cutoff_ref = str(payload.get("cutoff_ref") or "").strip()
        if not cutoff_ref:
            errors.append("missing_cutoff_ref")
        lineage = payload.get("lineage") or {}
        if not str(
            lineage.get("prior_snapshot_ref") or lineage.get("prior_export_id") or ""
        ).strip():
            errors.append("missing_prior_boundary_ref")
        cutoff_at = _parse_datetime(cutoff_ref) if cutoff_ref else None
        if cutoff_at is not None:
            for record_group in ("source_records", "outcome_records", "memory_records"):
                for record in payload.get(record_group, []):
                    occurred_at = _parse_datetime(str(record.get("occurred_at") or ""))
                    if occurred_at is None or occurred_at <= cutoff_at:
                        errors.append(f"cutoff_violation:{record_group}:{record.get('record_id')}")
    else:
        lineage = payload.get("lineage") or {}
        if not lineage.get("export_id"):
            errors.append("missing_export_id")
    return {
        "contract_version": PORTABLE_EXPORT_VALIDATION_SCHEMA_VERSION,
        "adapter": normalize_adapter_name(adapter_name),
        "export_family": family.value,
        "export_id": export_id,
        "valid": not errors,
        "errors": errors,
    }


def _collect_source_records(
    *,
    adapter_name: str,
    company_id: UUID | str,
    cycle_store: RuntimeCycleStore | None = None,
    memory_store: ReplyMemoryStore | None = None,
    occurred_after: datetime | None = None,
) -> tuple[SourceExportRecord, ...]:
    cycle_store = cycle_store or RuntimeCycleStore(adapter_name=adapter_name)
    traces = cycle_store.list_export_payloads(company_id)
    store = memory_store or ReplyMemoryStore(adapter_name=adapter_name)
    records: dict[str, SourceExportRecord] = {}
    scope = str(company_id).strip().lower()
    for trace in traces:
        _require_trace_tenant(trace, scope)
        cycle_id = str(
            trace.get("cycle_id") or trace.get("ranked_draft_set", {}).get("cycle_id") or ""
        )
        runtime_ref = str(trace.get("ranked_draft_set", {}).get("trace_ref") or cycle_id)
        snapshot = trace.get("thread_snapshot") or {}
        metadata = snapshot.get("metadata") or {}
        if str(metadata.get("historical_outcome_backfill") or "").strip().lower() == "true":
            continue
        requested_at = _parse_datetime(
            str(snapshot.get("requested_at") or trace.get("exported_at") or "")
        )
        if requested_at is not None and _after_cutoff(requested_at, occurred_after):
            thread_ref = str(snapshot.get("thread_ref") or "")
            messages = snapshot.get("messages", [])
            record_id = _stable_record_id("source_thread", scope, cycle_id, thread_ref)
            records[record_id] = SourceExportRecord(
                record_id=record_id,
                record_type="thread_snapshot",
                producer_adapter=normalize_adapter_name(adapter_name),
                tenant_scope=scope,
                occurred_at=requested_at,
                source_ref=thread_ref or cycle_id,
                runtime_ref=runtime_ref,
                provenance_refs=(cycle_id,),
                attachment_refs=tuple(_attachment_refs(snapshot.get("metadata"))),
                payload={
                    "channel": snapshot.get("channel"),
                    "contact_handle": snapshot.get("contact_handle"),
                    "latest_inbound_text": snapshot.get("latest_inbound_text"),
                    "message_ids": [item.get("message_id") for item in messages],
                    "metadata": snapshot.get("metadata", {}),
                },
            )
            for message in messages:
                occurred_at = _parse_datetime(str(message.get("occurred_at") or ""))
                if occurred_at is None or not _after_cutoff(occurred_at, occurred_after):
                    continue
                message_id = str(message.get("message_id") or "")
                record_id = _stable_record_id("source_message", scope, thread_ref, message_id)
                records[record_id] = SourceExportRecord(
                    record_id=record_id,
                    record_type="message",
                    producer_adapter=normalize_adapter_name(adapter_name),
                    tenant_scope=scope,
                    occurred_at=occurred_at,
                    source_ref=message_id or thread_ref,
                    runtime_ref=runtime_ref,
                    provenance_refs=(cycle_id, thread_ref),
                    payload={
                        "thread_ref": thread_ref,
                        "role": message.get("role"),
                        "text": message.get("text"),
                        "channel": message.get("channel"),
                        "source": message.get("source"),
                        "handle": message.get("handle"),
                    },
                )
            for index, snippet in enumerate(snapshot.get("context_snippets", [])):
                record_id = _stable_record_id(
                    "source_context_snippet",
                    scope,
                    cycle_id,
                    str(index),
                    str(snippet.get("path") or ""),
                )
                records[record_id] = SourceExportRecord(
                    record_id=record_id,
                    record_type="context_snippet",
                    producer_adapter=normalize_adapter_name(adapter_name),
                    tenant_scope=scope,
                    occurred_at=requested_at,
                    source_ref=str(snippet.get("path") or thread_ref or cycle_id),
                    runtime_ref=runtime_ref,
                    provenance_refs=(cycle_id, thread_ref),
                    payload={
                        "thread_ref": thread_ref,
                        "source": snippet.get("source"),
                        "path": snippet.get("path"),
                        "text": snippet.get("text"),
                    },
                )
            for index, example in enumerate(snapshot.get("golden_examples", [])):
                record_id = _stable_record_id(
                    "source_golden_example",
                    scope,
                    cycle_id,
                    str(index),
                    str(example.get("path") or ""),
                )
                records[record_id] = SourceExportRecord(
                    record_id=record_id,
                    record_type="golden_example",
                    producer_adapter=normalize_adapter_name(adapter_name),
                    tenant_scope=scope,
                    occurred_at=requested_at,
                    source_ref=str(example.get("path") or cycle_id),
                    runtime_ref=runtime_ref,
                    provenance_refs=(cycle_id, thread_ref),
                    payload={"path": example.get("path"), "text": example.get("text")},
                )
    for event in store.list_memory_events(company_id, occurred_after=occurred_after):
        record_id = _stable_record_id(
            "source_memory_event",
            scope,
            event.event_kind.value,
            event.source_ref,
        )
        records[record_id] = SourceExportRecord(
            record_id=record_id,
            record_type="memory_event",
            producer_adapter=normalize_adapter_name(adapter_name),
            tenant_scope=scope,
            occurred_at=event.occurred_at,
            source_ref=event.source_ref,
            runtime_ref=f"memory_event:{event.event_kind.value}:{event.source_ref}",
            provenance_refs=tuple(
                str(value)
                for value in (
                    event.thread_ref,
                    event.contact_handle,
                    event.metadata.get("document_ref"),
                )
                if str(value or "").strip()
            ),
            attachment_refs=tuple(_attachment_refs(event.metadata)),
            payload={
                "event_kind": event.event_kind.value,
                "thread_ref": event.thread_ref,
                "channel": event.channel,
                "contact_handle": event.contact_handle,
                "content_text": event.content_text,
                "metadata": dict(event.metadata),
            },
        )
    for document in store.list_documents(company_id, occurred_after=occurred_after):
        occurred_at = document.occurred_at or datetime.now(UTC)
        record_id = _stable_record_id("source_document", scope, document.document_ref)
        records[record_id] = SourceExportRecord(
            record_id=record_id,
            record_type="document",
            producer_adapter=normalize_adapter_name(adapter_name),
            tenant_scope=scope,
            occurred_at=occurred_at,
            source_ref=document.document_ref,
            runtime_ref=f"document:{document.document_ref}",
            provenance_refs=tuple(
                str(value)
                for value in (
                    document.path,
                    document.metadata.get("source_ref"),
                    document.metadata.get("thread_ref"),
                )
                if str(value or "").strip()
            ),
            attachment_refs=tuple(_attachment_refs(document.metadata)),
            payload={
                "source": document.source,
                "path": document.path,
                "title": document.title,
                "content_text": document.content_text,
                "metadata": dict(document.metadata),
            },
        )
    return tuple(sorted(records.values(), key=_source_sort_key))


def _collect_outcome_records(
    *,
    adapter_name: str,
    company_id: UUID | str,
    cycle_store: RuntimeCycleStore | None = None,
    occurred_after: datetime | None = None,
) -> tuple[OutcomeExportRecord, ...]:
    cycle_store = cycle_store or RuntimeCycleStore(adapter_name=adapter_name)
    traces = cycle_store.list_export_payloads(company_id)
    records: dict[str, OutcomeExportRecord] = {}
    scope = str(company_id).strip().lower()
    for trace in traces:
        _require_trace_tenant(trace, scope)
        cycle_id = str(
            trace.get("cycle_id") or trace.get("ranked_draft_set", {}).get("cycle_id") or ""
        )
        snapshot = trace.get("thread_snapshot") or {}
        thread_ref = str(snapshot.get("thread_ref") or "")
        runtime_ref = str(trace.get("ranked_draft_set", {}).get("trace_ref") or cycle_id)
        ranked_drafts = trace.get("ranked_draft_set", {}).get("drafts", [])
        feedback_events = trace.get("feedback_events", [])
        final_event = _final_feedback_event(feedback_events)
        supervision_event = _supervision_ready_feedback_event(feedback_events)
        selected_candidate_id = str(supervision_event.get("candidate_id") or "")
        artifact = trace.get("accepted_artifact_version") or {}
        policy_resolution = trace.get("policy_resolution") or {}
        ranked_by_id = {str(item.get("candidate_id") or ""): item for item in ranked_drafts}
        for candidate in trace.get("candidates", []):
            occurred_at = _parse_datetime(
                str(trace.get("exported_at") or snapshot.get("requested_at") or "")
            )
            if occurred_at is None or not _after_cutoff(occurred_at, occurred_after):
                continue
            candidate_id = str(candidate.get("candidate_id") or "")
            surfaced = candidate_id in ranked_by_id
            variant_state = _candidate_variant_state(
                candidate_id,
                selected_candidate_id,
                final_event,
            )
            record_id = _stable_record_id(
                "outcome_candidate_variant",
                scope,
                cycle_id,
                candidate_id,
            )
            records[record_id] = OutcomeExportRecord(
                record_id=record_id,
                record_type="candidate_variant",
                producer_adapter=normalize_adapter_name(adapter_name),
                tenant_scope=scope,
                occurred_at=occurred_at,
                cycle_id=cycle_id,
                thread_ref=thread_ref,
                runtime_ref=runtime_ref,
                provenance_refs=tuple(
                    str(item) for item in candidate.get("source_evidence_ids", [])
                ),
                artifact_refs=tuple(
                    value
                    for value in (
                        _artifact_ref(artifact),
                        str(policy_resolution.get("accepted_artifact_version") or ""),
                    )
                    if value
                ),
                quality_metadata={
                    "surfaced": surfaced,
                    "variant_state": variant_state,
                    "final_disposition": str(final_event.get("disposition") or ""),
                    "supervision_ready": bool(supervision_event),
                    "rank": ranked_by_id.get(candidate_id, {}).get("rank"),
                    "scores": candidate.get("scores", {}),
                },
                payload={
                    "thread_ref": thread_ref,
                    "title": candidate.get("title"),
                    "content": candidate.get("content"),
                    "candidate_type": candidate.get("candidate_type"),
                    "evaluation_reason": candidate.get("evaluation_reason"),
                    "draft_text": ranked_by_id.get(candidate_id, {}).get("draft_text"),
                    "rationale": ranked_by_id.get(candidate_id, {}).get("rationale"),
                    "risk_flags": ranked_by_id.get(candidate_id, {}).get("risk_flags", []),
                    "delivery_eligible": ranked_by_id.get(candidate_id, {}).get(
                        "delivery_eligible"
                    ),
                },
            )
        for event in feedback_events:
            occurred_at = _parse_datetime(str(event.get("occurred_at") or ""))
            if occurred_at is None or not _after_cutoff(occurred_at, occurred_after):
                continue
            candidate_id = str(event.get("candidate_id") or "")
            record_id = _stable_record_id(
                "outcome_supervision_event",
                scope,
                cycle_id,
                str(event.get("disposition") or ""),
                candidate_id or "none",
                str(event.get("occurred_at") or ""),
            )
            records[record_id] = OutcomeExportRecord(
                record_id=record_id,
                record_type="supervision_event",
                producer_adapter=normalize_adapter_name(adapter_name),
                tenant_scope=scope,
                occurred_at=occurred_at,
                cycle_id=cycle_id,
                thread_ref=str(event.get("thread_ref") or thread_ref),
                runtime_ref=runtime_ref,
                provenance_refs=(candidate_id,) if candidate_id else (),
                artifact_refs=(_artifact_ref(artifact),) if _artifact_ref(artifact) else (),
                quality_metadata={
                    "edit_distance": event.get("edit_distance"),
                    "latency_ms": event.get("latency_ms"),
                    "send_result": event.get("send_result"),
                },
                payload={
                    "disposition": event.get("disposition"),
                    "original_draft_text": event.get("original_draft_text"),
                    "final_text": event.get("final_text"),
                    "notes": event.get("notes"),
                },
            )
        if supervision_event:
            occurred_at = _parse_datetime(str(supervision_event.get("occurred_at") or ""))
            if occurred_at is not None and _after_cutoff(occurred_at, occurred_after):
                accepted_draft_text = ranked_by_id.get(
                    selected_candidate_id,
                    {},
                ).get("draft_text")
                final_text = supervision_event.get("final_text")
                original_draft_text = supervision_event.get("original_draft_text")
                if not _is_exportable_supervision_text(
                    final_text or accepted_draft_text or original_draft_text
                ):
                    continue
                record_id = _stable_record_id("outcome_final", scope, cycle_id)
                records[record_id] = OutcomeExportRecord(
                    record_id=record_id,
                    record_type="final_outcome",
                    producer_adapter=normalize_adapter_name(adapter_name),
                    tenant_scope=scope,
                    occurred_at=occurred_at,
                    cycle_id=cycle_id,
                    thread_ref=str(supervision_event.get("thread_ref") or thread_ref),
                    runtime_ref=runtime_ref,
                    provenance_refs=tuple(
                        item
                        for item in (
                            str(supervision_event.get("candidate_id") or ""),
                            selected_candidate_id,
                        )
                        if item
                    ),
                    artifact_refs=tuple(
                        value
                        for value in (
                            _artifact_ref(artifact),
                            str(policy_resolution.get("accepted_artifact_version") or ""),
                        )
                        if value
                    ),
                    quality_metadata={
                        "disposition": supervision_event.get("disposition"),
                        "edit_distance": supervision_event.get("edit_distance"),
                        "supervision_ready": True,
                    },
                    payload={
                        "selected_candidate_id": selected_candidate_id or None,
                        "accepted_draft_text": accepted_draft_text,
                        "original_draft_text": original_draft_text,
                        "final_text": final_text,
                        "notes": supervision_event.get("notes"),
                    },
                )
    return tuple(sorted(records.values(), key=_outcome_sort_key))


def _collect_memory_records(
    *,
    adapter_name: str,
    company_id: UUID | str,
    memory_store: ReplyMemoryStore | None = None,
    occurred_after: datetime | None = None,
) -> tuple[MemoryExportRecord, ...]:
    store = memory_store or ReplyMemoryStore(adapter_name=adapter_name)
    scope = str(company_id).strip().lower()
    records: dict[str, MemoryExportRecord] = {}
    for summary in store.list_memory_summaries(company_id, limit=10000):
        if not _after_cutoff(summary.updated_at, occurred_after):
            continue
        record_id = _stable_record_id(
            "memory_summary",
            scope,
            summary.summary_key,
            summary.scope_ref,
        )
        records[record_id] = MemoryExportRecord(
            record_id=record_id,
            record_type="memory_summary",
            producer_adapter=normalize_adapter_name(adapter_name),
            tenant_scope=scope,
            occurred_at=summary.updated_at,
            scope_ref=summary.scope_ref,
            runtime_ref=f"memory_summary:{summary.summary_key}:{summary.scope_ref}",
            provenance_refs=_refs_from_metadata(
                summary.metadata,
                ("provenance_ref", "source_ref", "thread_ref"),
            ),
            evidence_anchors=_refs_from_metadata(
                summary.metadata,
                ("evidence_anchors", "source_refs"),
            ),
            freshness_metadata={"updated_at": summary.updated_at.isoformat()},
            confidence_metadata=_metadata_block(
                summary.metadata,
                ("confidence", "confidence_score"),
            ),
            conflict_metadata=_metadata_block(summary.metadata, ("conflicts", "conflict_refs")),
            payload={
                "summary_key": summary.summary_key,
                "content": summary.content,
                "metadata": dict(summary.metadata),
            },
        )
    for profile in store.list_contact_profiles(company_id):
        updated_at = profile.updated_at or datetime.now(UTC)
        if not _after_cutoff(updated_at, occurred_after):
            continue
        record_id = _stable_record_id("memory_contact_profile", scope, profile.contact_handle)
        records[record_id] = MemoryExportRecord(
            record_id=record_id,
            record_type="contact_profile",
            producer_adapter=normalize_adapter_name(adapter_name),
            tenant_scope=scope,
            occurred_at=updated_at,
            scope_ref=profile.contact_handle,
            runtime_ref=f"contact_profile:{profile.contact_handle}",
            provenance_refs=_refs_from_metadata(profile.metadata, ("source_ref", "thread_ref")),
            evidence_anchors=_refs_from_metadata(
                profile.metadata,
                ("evidence_anchors", "source_refs"),
            ),
            freshness_metadata={"updated_at": updated_at.isoformat()},
            confidence_metadata=_metadata_block(
                profile.metadata,
                ("confidence", "confidence_score"),
            ),
            conflict_metadata=_metadata_block(profile.metadata, ("conflicts", "conflict_refs")),
            payload={
                "display_name": profile.display_name,
                "summary": profile.summary,
                "metadata": dict(profile.metadata),
            },
        )
    for state in store.list_thread_states(company_id):
        occurred_at = state.last_snapshot_at or state.last_event_at or datetime.now(UTC)
        if not _after_cutoff(occurred_at, occurred_after):
            continue
        record_id = _stable_record_id("memory_thread_state", scope, state.thread_ref)
        records[record_id] = MemoryExportRecord(
            record_id=record_id,
            record_type="thread_state",
            producer_adapter=normalize_adapter_name(adapter_name),
            tenant_scope=scope,
            occurred_at=occurred_at,
            scope_ref=state.thread_ref,
            runtime_ref=f"thread_state:{state.thread_ref}",
            provenance_refs=_refs_from_metadata(state.metadata, ("source_ref", "thread_ref")),
            evidence_anchors=_refs_from_metadata(
                state.metadata,
                ("evidence_anchors", "source_refs"),
            ),
            freshness_metadata={
                "last_event_at": state.last_event_at.isoformat() if state.last_event_at else None,
                "last_snapshot_at": state.last_snapshot_at.isoformat()
                if state.last_snapshot_at
                else None,
            },
            confidence_metadata=_metadata_block(state.metadata, ("confidence", "confidence_score")),
            conflict_metadata=_metadata_block(state.metadata, ("conflicts", "conflict_refs")),
            payload={
                "channel": state.channel,
                "contact_handle": state.contact_handle,
                "latest_inbound_text": state.latest_inbound_text,
                "metadata": dict(state.metadata),
            },
        )
    return tuple(sorted(records.values(), key=_memory_sort_key))


def _build_manifest(
    records: tuple[Any, ...],
    *,
    family_label: str,
) -> tuple[PortableExportManifestEntry, ...]:
    counts: dict[str, int] = {}
    for record in records:
        counts[str(record.record_type)] = counts.get(str(record.record_type), 0) + 1
    return tuple(
        PortableExportManifestEntry(
            family_name=f"{family_label}:{record_type}",
            record_count=counts[record_type],
        )
        for record_type in sorted(counts)
    )


def _build_integrity_payload(records: tuple[Any, ...]) -> PortableExportIntegrity:
    records_payload = [dataclass_payload(record) for record in records]
    content_json = json.dumps(records_payload, sort_keys=True, separators=(",", ":"))
    record_ids_json = json.dumps(
        [record["record_id"] for record in records_payload],
        sort_keys=True,
        separators=(",", ":"),
    )
    return PortableExportIntegrity(
        content_sha256=hashlib.sha256(content_json.encode("utf-8")).hexdigest(),
        record_ids_sha256=hashlib.sha256(record_ids_json.encode("utf-8")).hexdigest(),
    )


def _build_export_id(
    family: PortableExportFamily,
    company_id: UUID | str,
    snapshot_ref: str | None,
) -> str:
    return f"{family.value}-{str(company_id).strip().lower()}-{snapshot_ref or uuid4().hex}"


def _stable_record_id(*parts: str) -> str:
    joined = "::".join(str(part or "").strip() for part in parts)
    return str(uuid5(PORTABLE_EXPORT_NAMESPACE, joined))


def _parse_datetime(value: str) -> datetime | None:
    if not str(value or "").strip():
        return None
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _after_cutoff(value: datetime, cutoff: datetime | None) -> bool:
    return cutoff is None or value > cutoff


def _attachment_refs(metadata: Any) -> tuple[str, ...]:
    if not isinstance(metadata, dict):
        return ()
    refs: list[str] = []
    for key in ("attachment_refs", "attachment_ids", "attachments", "file_refs"):
        value = metadata.get(key)
        if isinstance(value, list):
            refs.extend(str(item) for item in value if str(item or "").strip())
        elif isinstance(value, str) and value.strip():
            refs.append(value.strip())
    return tuple(sorted(set(refs)))


def _require_trace_tenant(trace: dict[str, Any], expected_scope: str) -> None:
    actual = str(trace.get("thread_snapshot", {}).get("company_id") or "").strip().lower()
    if actual != expected_scope:
        raise ValueError(
            "Cross-tenant trace payload rejected: "
            f"expected {expected_scope}, found {actual or 'missing'}."
        )


def _artifact_ref(artifact: dict[str, Any]) -> str:
    artifact_key = str(artifact.get("artifact_key") or "").strip()
    version = str(artifact.get("version") or "").strip()
    if not artifact_key or not version:
        return ""
    return f"{artifact_key}:{version}"


def _final_feedback_event(feedback_events: list[dict[str, Any]]) -> dict[str, Any]:
    if not feedback_events:
        return {}
    return sorted(
        feedback_events,
        key=lambda item: (
            str(item.get("occurred_at") or ""),
            str(item.get("disposition") or ""),
            str(item.get("candidate_id") or ""),
        ),
    )[-1]


def _supervision_ready_feedback_event(feedback_events: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [
        item
        for item in feedback_events
        if _is_supervision_ready_disposition(str(item.get("disposition") or ""))
    ]
    if not eligible:
        return {}
    return sorted(
        eligible,
        key=lambda item: (
            str(item.get("occurred_at") or ""),
            str(item.get("disposition") or ""),
            str(item.get("candidate_id") or ""),
        ),
    )[-1]


def _is_supervision_ready_disposition(disposition: str) -> bool:
    normalized = str(disposition or "").strip()
    return normalized in {
        DraftOutcomeDisposition.SENT_AS_IS.value,
        DraftOutcomeDisposition.EDITED_THEN_SENT.value,
        DraftOutcomeDisposition.MANUAL_REPLACEMENT.value,
    }


def _is_exportable_supervision_text(value: Any) -> bool:
    normalized = " ".join(str(value or "").strip().lower().split())
    if not normalized:
        return False
    if re.match(r"^thanks\s+[0-9]{6,}", normalized):
        return False
    return not any(marker in normalized for marker in GENERIC_SUPERVISION_MARKERS)


def _candidate_variant_state(
    candidate_id: str,
    selected_candidate_id: str,
    final_event: dict[str, Any],
) -> str:
    disposition = str(final_event.get("disposition") or "").strip()
    if candidate_id and candidate_id == selected_candidate_id:
        if disposition == "REJECTED":
            return "rejected"
        if disposition == "EDITED_THEN_SENT":
            return "accepted_edited"
        return "accepted"
    if not selected_candidate_id:
        return "unresolved"
    if disposition == "REJECTED":
        return "rejected"
    return "superseded"


def _refs_from_metadata(metadata: dict[str, Any], keys: tuple[str, ...]) -> tuple[str, ...]:
    refs: list[str] = []
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, list):
            refs.extend(str(item) for item in value if str(item or "").strip())
        elif isinstance(value, str) and value.strip():
            refs.append(value.strip())
    return tuple(sorted(set(refs)))


def _metadata_block(metadata: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: metadata[key] for key in keys if key in metadata}


def _source_sort_key(record: SourceExportRecord) -> tuple[str, str]:
    return (record.occurred_at.isoformat(), record.record_id)


def _outcome_sort_key(record: OutcomeExportRecord) -> tuple[str, str]:
    return (record.occurred_at.isoformat(), record.record_id)


def _memory_sort_key(record: MemoryExportRecord) -> tuple[str, str]:
    return (record.occurred_at.isoformat(), record.record_id)
