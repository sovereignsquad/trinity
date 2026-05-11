"""Bounded Gobii-backed tracked-entity enrichment workflow helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trinity_core.ops.cycle_store import dataclass_payload, write_json_atomic
from trinity_core.ops.gobii_normalization import (
    GobiiNormalizationError,
    normalize_gobii_task_output,
)
from trinity_core.ops.gobii_tasks import (
    GobiiTaskClient,
    GobiiTaskRecord,
    GobiiTaskStatus,
    load_gobii_task_record,
    persist_gobii_task_record,
)
from trinity_core.ops.runtime_storage import resolve_adapter_runtime_paths
from trinity_core.schemas import (
    GOBII_TRACKED_ENTITY_PROFILE_WORKFLOW_KIND,
    EvidenceSourceType,
    GobiiNormalizedArtifactBundle,
    GobiiTaskCreateRequest,
    GobiiTaskNormalizationRequest,
    GobiiTrackedEntityEnrichmentBundle,
    GobiiTrackedEntityEnrichmentRequest,
)


@dataclass(frozen=True, slots=True)
class GobiiEnrichmentPaths:
    """Persistent paths for bounded Gobii enrichment workflow artifacts."""

    adapter_name: str
    root_dir: Path
    bundles_dir: Path


def resolve_gobii_enrichment_paths(adapter_name: str) -> GobiiEnrichmentPaths:
    adapter_paths = resolve_adapter_runtime_paths(
        adapter_name,
        repo_root=Path(__file__).resolve().parents[3],
    )
    root_dir = adapter_paths.root_dir / "gobii_enrichment"
    bundles_dir = root_dir / "bundles"
    for path in (root_dir, bundles_dir):
        path.mkdir(parents=True, exist_ok=True)
    return GobiiEnrichmentPaths(
        adapter_name=adapter_paths.adapter_name,
        root_dir=root_dir,
        bundles_dir=bundles_dir,
    )


def build_gobii_tracked_entity_enrichment_bundle(
    adapter_name: str,
    request: GobiiTrackedEntityEnrichmentRequest,
    *,
    agent_id: str | None = None,
    webhook: str | None = None,
    wait_seconds: int | None = None,
) -> GobiiTrackedEntityEnrichmentBundle:
    metadata = dict(request.metadata)
    metadata.update(
        {
            "workflow_kind": GOBII_TRACKED_ENTITY_PROFILE_WORKFLOW_KIND,
            "entity_ref": request.entity_ref,
        }
    )
    return GobiiTrackedEntityEnrichmentBundle(
        adapter_name=adapter_name,
        workflow_kind=GOBII_TRACKED_ENTITY_PROFILE_WORKFLOW_KIND,
        created_at=datetime.now(UTC),
        request=request,
        task_create_request=_build_task_create_request(
            request,
            agent_id=agent_id,
            webhook=webhook,
            wait_seconds=wait_seconds,
        ),
        metadata=metadata,
    )


def persist_gobii_tracked_entity_enrichment_bundle(
    bundle: GobiiTrackedEntityEnrichmentBundle,
) -> Path:
    paths = resolve_gobii_enrichment_paths(bundle.adapter_name)
    safe_entity_ref = bundle.request.entity_ref.replace("/", "_")
    path = paths.bundles_dir / f"{safe_entity_ref}.json"
    write_json_atomic(path, dataclass_payload(bundle))
    return path


def load_gobii_tracked_entity_enrichment_bundle(
    path: str | Path,
) -> GobiiTrackedEntityEnrichmentBundle:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Gobii enrichment bundle payload must be a JSON object.")
    from trinity_core.schemas import gobii_tracked_entity_enrichment_bundle_from_payload

    return gobii_tracked_entity_enrichment_bundle_from_payload(payload)


def submit_gobii_tracked_entity_enrichment_bundle(
    bundle: GobiiTrackedEntityEnrichmentBundle,
    client: GobiiTaskClient,
) -> tuple[GobiiTrackedEntityEnrichmentBundle, Path, GobiiTaskRecord, Path]:
    record = client.create_task(bundle.task_create_request)
    record = replace(
        record,
        adapter_name=bundle.adapter_name,
        company_id=str(bundle.request.company_id),
    )
    record_path = persist_gobii_task_record(bundle.adapter_name, record)
    persisted_bundle = replace(
        bundle,
        task_id=record.id,
        task_record_path=str(record_path),
    )
    bundle_path = persist_gobii_tracked_entity_enrichment_bundle(persisted_bundle)
    return persisted_bundle, bundle_path, record, record_path


def normalize_gobii_tracked_entity_enrichment_bundle(
    adapter_name: str,
    bundle: GobiiTrackedEntityEnrichmentBundle,
) -> tuple[GobiiNormalizedArtifactBundle, Path]:
    task_record, task_record_path = _resolve_completed_task_record(adapter_name, bundle)
    normalization_request = _build_normalization_request(bundle, task_record, task_record_path)
    return normalize_gobii_task_output(adapter_name, normalization_request)


def _build_task_create_request(
    request: GobiiTrackedEntityEnrichmentRequest,
    *,
    agent_id: str | None,
    webhook: str | None,
    wait_seconds: int | None,
) -> GobiiTaskCreateRequest:
    prompt_lines = [
        "Collect one bounded profile enrichment artifact for the provided tracked entity.",
        f"Entity name: {request.entity_name}",
        f"Entity ref: {request.entity_ref}",
        f"Target profile URL: {request.target_profile_url}",
        (
            f"Current company hint: {request.company_name}"
            if request.company_name
            else "Current company hint: unknown"
        ),
        f"Role hint: {request.role_hint}" if request.role_hint else "Role hint: unknown",
        "Return only structured JSON that matches the requested output schema.",
        "Do not browse unrelated surfaces, send messages, or mutate any external system.",
    ]
    if request.notes:
        prompt_lines.append("Operator notes:")
        prompt_lines.extend(f"- {note}" for note in request.notes)

    return GobiiTaskCreateRequest(
        prompt="\n".join(prompt_lines),
        agent_id=agent_id,
        webhook=webhook,
        output_schema=_tracked_entity_profile_output_schema(),
        wait_seconds=wait_seconds,
    )


def _tracked_entity_profile_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "entity_name",
            "profile_url",
            "summary",
            "evidence_points",
        ],
        "properties": {
            "entity_name": {"type": "string"},
            "profile_url": {"type": "string"},
            "headline": {"type": "string"},
            "current_company": {"type": "string"},
            "location": {"type": "string"},
            "summary": {"type": "string"},
            "evidence_points": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
        },
    }


def _resolve_completed_task_record(
    adapter_name: str,
    bundle: GobiiTrackedEntityEnrichmentBundle,
) -> tuple[GobiiTaskRecord, Path]:
    if not bundle.task_record_path:
        raise GobiiNormalizationError(
            "Gobii enrichment bundle is missing task_record_path; submit or fetch the task first."
        )
    task_record_path = Path(bundle.task_record_path)
    if not task_record_path.exists():
        raise GobiiNormalizationError(f"Gobii task record does not exist: {task_record_path}")
    record = load_gobii_task_record(task_record_path)
    if record.status is not GobiiTaskStatus.COMPLETED:
        raise GobiiNormalizationError(
            f"Gobii enrichment task must be completed before normalization: {record.id}"
        )
    if record.adapter_name and record.adapter_name != adapter_name:
        raise GobiiNormalizationError(
            "Gobii enrichment task adapter mismatch: expected "
            f"{adapter_name}, got {record.adapter_name}."
        )
    return record, task_record_path


def _build_normalization_request(
    bundle: GobiiTrackedEntityEnrichmentBundle,
    task_record: GobiiTaskRecord,
    task_record_path: Path,
) -> GobiiTaskNormalizationRequest:
    result = _extract_result_payload(task_record)
    profile_url = _require_result_text(result, "profile_url")
    summary = _require_result_text(result, "summary")
    entity_name = _require_result_text(result, "entity_name")
    evidence_points = _require_result_text_list(result, "evidence_points")
    headline = _optional_text(result.get("headline"))
    current_company = _optional_text(result.get("current_company"))
    location = _optional_text(result.get("location"))

    content_lines = [f"Profile enrichment for {entity_name}"]
    if headline:
        content_lines.append(f"Headline: {headline}")
    if current_company:
        content_lines.append(f"Current company: {current_company}")
    if location:
        content_lines.append(f"Location: {location}")
    content_lines.append(f"Summary: {summary}")
    content_lines.append("Evidence points:")
    content_lines.extend(f"- {item}" for item in evidence_points)

    metadata = dict(bundle.request.metadata)
    metadata.update(
        {
            "gobii_workflow_kind": bundle.workflow_kind,
            "entity_ref": bundle.request.entity_ref,
            "entity_name": bundle.request.entity_name,
            "target_profile_url": bundle.request.target_profile_url,
            "evidence_point_count": str(len(evidence_points)),
        }
    )
    if bundle.request.company_name:
        metadata["company_name"] = bundle.request.company_name
    if bundle.request.role_hint:
        metadata["role_hint"] = bundle.request.role_hint

    topic_hints = [bundle.request.entity_name, "profile_enrichment"]
    if bundle.request.company_name:
        topic_hints.append(bundle.request.company_name)

    return GobiiTaskNormalizationRequest(
        company_id=bundle.request.company_id,
        task_id=task_record.id,
        task_record_path=str(task_record_path),
        document_ref=f"gobii-profile-enrichment:{bundle.request.entity_ref}",
        path=profile_url,
        title=f"Gobii profile enrichment: {bundle.request.entity_name}",
        content_text="\n".join(content_lines),
        source_type=EvidenceSourceType.WEB,
        occurred_at=task_record.updated_at,
        source_external_id=bundle.request.entity_ref,
        source_locator=profile_url,
        raw_origin_uri=profile_url,
        topic_hints=tuple(topic_hints),
        metadata=metadata,
    )


def _extract_result_payload(task_record: GobiiTaskRecord) -> dict[str, Any]:
    raw_payload = task_record.raw_payload
    if not isinstance(raw_payload, dict):
        raise GobiiNormalizationError(
            f"Gobii enrichment task is missing structured raw_payload: {task_record.id}"
        )
    result = raw_payload.get("result")
    if not isinstance(result, dict):
        raise GobiiNormalizationError(
            f"Gobii enrichment task result must be a JSON object: {task_record.id}"
        )
    return result


def _require_result_text(payload: dict[str, Any], field_name: str) -> str:
    value = _optional_text(payload.get(field_name))
    if value is None:
        raise GobiiNormalizationError(
            f"Gobii enrichment task result is missing required field '{field_name}'."
        )
    return value


def _require_result_text_list(payload: dict[str, Any], field_name: str) -> tuple[str, ...]:
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise GobiiNormalizationError(
            f"Gobii enrichment task result field '{field_name}' must be a list of strings."
        )
    normalized = tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
    if not normalized:
        raise GobiiNormalizationError(
            f"Gobii enrichment task result field '{field_name}' must include at least one string."
        )
    return normalized


def _optional_text(value: Any) -> str | None:
    normalized = str(value).strip() if value is not None else ""
    return normalized or None
