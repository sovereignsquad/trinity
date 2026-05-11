"""Normalize Gobii task output into Trinity-owned document, memory, and evidence artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from trinity_core.memory.storage import ReplyMemoryStore
from trinity_core.ops.cycle_store import dataclass_payload, write_json_atomic
from trinity_core.ops.gobii_tasks import (
    GobiiTaskClientError,
    load_gobii_task_record,
    load_persisted_gobii_task_record,
)
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths
from trinity_core.schemas import (
    DocumentRecord,
    EvidenceProvenance,
    EvidenceSourceRef,
    EvidenceSourceType,
    EvidenceUnit,
    GobiiNormalizedArtifactBundle,
    GobiiTaskNormalizationRequest,
    GobiiTaskRecord,
    GobiiTaskStatus,
    MemoryEvent,
    MemoryEventKind,
)
from trinity_core.workflow import InMemoryEvidenceStore, RawEvidenceInput, ingest_evidence


class GobiiNormalizationError(RuntimeError):
    """Raised when Gobii output cannot be normalized safely into Trinity artifacts."""


@dataclass(frozen=True, slots=True)
class GobiiNormalizationPaths:
    """Persistent paths for normalized Gobii artifact bundles."""

    adapter_name: str
    root_dir: Path
    normalized_dir: Path


def resolve_gobii_normalization_paths(adapter_name: str) -> GobiiNormalizationPaths:
    adapter_paths = resolve_adapter_runtime_paths(
        adapter_name,
        repo_root=Path(__file__).resolve().parents[3],
    )
    root_dir = adapter_paths.root_dir / "gobii_tasks"
    normalized_dir = root_dir / "normalized"
    for path in (root_dir, normalized_dir):
        path.mkdir(parents=True, exist_ok=True)
    return GobiiNormalizationPaths(
        adapter_name=adapter_paths.adapter_name,
        root_dir=root_dir,
        normalized_dir=normalized_dir,
    )


def normalize_gobii_task_output(
    adapter_name: str,
    request: GobiiTaskNormalizationRequest,
) -> tuple[GobiiNormalizedArtifactBundle, Path]:
    task_record, task_record_path = _resolve_task_record(adapter_name, request)
    _validate_task_binding(adapter_name, request.company_id, task_record, task_record_path)
    if task_record.status is not GobiiTaskStatus.COMPLETED:
        raise GobiiNormalizationError(
            f"Gobii task must be completed before normalization: {task_record.id}"
        )

    normalized_at = datetime.now(UTC)
    artifact_metadata = _artifact_metadata(task_record, task_record_path, request, normalized_at)
    document = DocumentRecord(
        company_id=request.company_id,
        document_ref=request.document_ref,
        source="gobii",
        path=request.path,
        title=request.title,
        content_text=request.content_text,
        occurred_at=request.occurred_at or task_record.updated_at,
        metadata=artifact_metadata,
    )
    memory_event = MemoryEvent(
        company_id=request.company_id,
        event_kind=MemoryEventKind.DOCUMENT_REGISTERED,
        source_ref=document.document_ref,
        occurred_at=normalized_at,
        thread_ref=request.thread_ref,
        channel=request.channel,
        contact_handle=request.contact_handle,
        content_text=document.title or document.content_text[:160],
        metadata=artifact_metadata,
    )
    evidence = _build_evidence(task_record, task_record_path, request, normalized_at)

    memory_store = ReplyMemoryStore(adapter_name=adapter_name)
    memory_store.register_document(document)
    memory_store.record_event(memory_event)
    if request.thread_ref:
        memory_store.mark_thread_dirty(
            request.company_id,
            request.thread_ref,
            reason="gobii_document_registered",
        )

    bundle = GobiiNormalizedArtifactBundle(
        adapter_name=adapter_name,
        company_id=request.company_id,
        task_record_path=str(task_record_path),
        normalized_at=normalized_at,
        task_record=task_record,
        document=document,
        memory_event=memory_event,
        evidence_unit=evidence,
        metadata={
            "normalizer": "trinity.gobii",
            "topic_hints": list(request.topic_hints),
        },
    )
    bundle_path = persist_gobii_normalized_artifact_bundle(bundle)
    return bundle, bundle_path


def persist_gobii_normalized_artifact_bundle(bundle: GobiiNormalizedArtifactBundle) -> Path:
    paths = resolve_gobii_normalization_paths(bundle.adapter_name)
    safe_document_ref = bundle.document.document_ref.replace("/", "_")
    path = paths.normalized_dir / f"{bundle.task_record.id}--{safe_document_ref}.json"
    write_json_atomic(path, dataclass_payload(bundle))
    return path


def gobii_task_normalization_request_from_payload(
    payload: dict[str, Any],
) -> GobiiTaskNormalizationRequest:
    occurred_at = payload.get("occurred_at")
    company_id = payload.get("company_id")
    if company_id is None:
        raise ValueError("company_id is required.")
    return GobiiTaskNormalizationRequest(
        company_id=UUID(str(company_id)),
        document_ref=str(payload["document_ref"]),
        path=str(payload["path"]),
        content_text=str(payload["content_text"]),
        source_type=_evidence_source_type(str(payload["source_type"])),
        task_id=(str(payload["task_id"]).strip() if payload.get("task_id") else None),
        task_record_path=(
            str(payload["task_record_path"]).strip()
            if payload.get("task_record_path")
            else None
        ),
        title=(str(payload["title"]) if payload.get("title") is not None else None),
        occurred_at=_parse_datetime(str(occurred_at)) if occurred_at else None,
        thread_ref=(str(payload["thread_ref"]).strip() if payload.get("thread_ref") else None),
        channel=(str(payload["channel"]).strip() if payload.get("channel") else None),
        contact_handle=(
            str(payload["contact_handle"]).strip()
            if payload.get("contact_handle")
            else None
        ),
        source_external_id=(
            str(payload["source_external_id"]).strip()
            if payload.get("source_external_id")
            else None
        ),
        source_locator=(
            str(payload["source_locator"]).strip()
            if payload.get("source_locator")
            else None
        ),
        raw_origin_uri=(
            str(payload["raw_origin_uri"]).strip()
            if payload.get("raw_origin_uri")
            else None
        ),
        topic_hints=tuple(str(item) for item in payload.get("topic_hints", [])),
        metadata={
            str(key): str(value)
            for key, value in dict(payload.get("metadata", {})).items()
        },
        contract_version=str(
            payload.get("contract_version") or "trinity.gobii-normalization.v1alpha1"
        ),
    )


def _resolve_task_record(
    adapter_name: str,
    request: GobiiTaskNormalizationRequest,
) -> tuple[GobiiTaskRecord, Path]:
    if request.task_record_path:
        path = Path(request.task_record_path)
        if not path.exists():
            raise GobiiNormalizationError(f"Gobii task record does not exist: {path}")
        return load_gobii_task_record(path), path
    assert request.task_id is not None
    try:
        return load_persisted_gobii_task_record(adapter_name, request.task_id)
    except GobiiTaskClientError as exc:
        raise GobiiNormalizationError(str(exc)) from exc


def _validate_task_binding(
    adapter_name: str,
    company_id: UUID,
    task_record: GobiiTaskRecord,
    task_record_path: Path,
) -> None:
    if not task_record.adapter_name or not task_record.company_id:
        raise GobiiNormalizationError(
            "Gobii task record is missing Trinity adapter/company binding; "
            f"refusing normalization for {task_record_path}."
        )
    if task_record.adapter_name != adapter_name:
        raise GobiiNormalizationError(
            f"Gobii task record adapter mismatch: expected {adapter_name}, "
            f"got {task_record.adapter_name}."
        )
    if task_record.company_id != str(company_id):
        raise GobiiNormalizationError(
            f"Gobii task record company mismatch: expected {company_id}, "
            f"got {task_record.company_id}."
        )


def _artifact_metadata(
    task_record: GobiiTaskRecord,
    task_record_path: Path,
    request: GobiiTaskNormalizationRequest,
    normalized_at: datetime,
) -> dict[str, str]:
    metadata: dict[str, str] = dict(request.metadata)
    metadata.update(
        {
            "gobii_task_id": task_record.id,
            "gobii_task_status": task_record.status.value,
            "gobii_task_record_path": str(task_record_path),
            "gobii_task_created_at": task_record.created_at.isoformat(),
            "gobii_task_updated_at": task_record.updated_at.isoformat(),
            "gobii_normalized_at": normalized_at.isoformat(),
            "gobii_source_type": request.source_type.value,
            "gobii_normalization_contract_version": request.contract_version,
        }
    )
    if task_record.agent_id:
        metadata["gobii_agent_id"] = task_record.agent_id
    if task_record.prompt:
        metadata["gobii_task_prompt"] = task_record.prompt
    if request.thread_ref:
        metadata["thread_ref"] = request.thread_ref
    if request.channel:
        metadata["channel"] = request.channel
    if request.contact_handle:
        metadata["contact_handle"] = request.contact_handle
    return metadata


def _build_evidence(
    task_record: GobiiTaskRecord,
    task_record_path: Path,
    request: GobiiTaskNormalizationRequest,
    normalized_at: datetime,
) -> EvidenceUnit:
    source_ref = EvidenceSourceRef(
        external_id=request.source_external_id or request.document_ref,
        locator=request.source_locator or request.path,
        version=task_record.updated_at.isoformat(),
    )
    provenance = EvidenceProvenance(
        collected_at=task_record.updated_at,
        collector=f"gobii:{task_record.agent_id or 'browser-use'}",
        ingestion_channel="gobii_task_normalization",
        raw_origin_uri=request.raw_origin_uri or request.path,
        ingestion_notes=(
            f"task_id={task_record.id}",
            f"task_record_path={task_record_path}",
        ),
    )
    result = ingest_evidence(
        RawEvidenceInput(
            company_id=request.company_id,
            source_type=request.source_type,
            source_ref=source_ref,
            content=request.content_text,
            metadata=_artifact_metadata(task_record, task_record_path, request, normalized_at),
            topic_hints=request.topic_hints,
            freshness_duration=timedelta(days=7),
            provenance=provenance,
        ),
        store=InMemoryEvidenceStore(),
        now=normalized_at,
    )
    assert result.accepted is not None
    return result.accepted


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _evidence_source_type(value: str):
    return EvidenceSourceType(value)
