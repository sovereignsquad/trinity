"""Explicit contracts for one bounded Gobii-backed tracked-entity enrichment workflow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from .gobii_tasks import GobiiTaskCreateRequest

GOBII_ENRICHMENT_CONTRACT_VERSION = "trinity.gobii-enrichment.v1alpha1"
GOBII_TRACKED_ENTITY_PROFILE_WORKFLOW_KIND = "tracked_entity_profile_enrichment"


def _require_text(value: str, *, field_name: str) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{field_name} is required.")


def _require_timezone(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class GobiiTrackedEntityEnrichmentRequest:
    """Bounded request envelope for one profile-enrichment proof path."""

    company_id: UUID
    entity_ref: str
    entity_name: str
    target_profile_url: str
    company_name: str | None = None
    role_hint: str | None = None
    notes: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    contract_version: str = GOBII_ENRICHMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.entity_ref, field_name="entity_ref")
        _require_text(self.entity_name, field_name="entity_name")
        _require_text(self.target_profile_url, field_name="target_profile_url")


@dataclass(frozen=True, slots=True)
class GobiiTrackedEntityEnrichmentBundle:
    """Persisted, inspectable contract for one Gobii enrichment task submission."""

    adapter_name: str
    workflow_kind: str
    created_at: datetime
    request: GobiiTrackedEntityEnrichmentRequest
    task_create_request: GobiiTaskCreateRequest
    task_id: str | None = None
    task_record_path: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = GOBII_ENRICHMENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.adapter_name, field_name="adapter_name")
        _require_text(self.workflow_kind, field_name="workflow_kind")
        _require_timezone(self.created_at, field_name="created_at")
        if self.workflow_kind != GOBII_TRACKED_ENTITY_PROFILE_WORKFLOW_KIND:
            raise ValueError(f"Unsupported workflow_kind: {self.workflow_kind}")


def gobii_tracked_entity_enrichment_request_from_payload(
    payload: Mapping[str, Any],
) -> GobiiTrackedEntityEnrichmentRequest:
    company_id = payload.get("company_id")
    if company_id is None:
        raise ValueError("company_id is required.")
    return GobiiTrackedEntityEnrichmentRequest(
        company_id=UUID(str(company_id)),
        entity_ref=str(payload["entity_ref"]),
        entity_name=str(payload["entity_name"]),
        target_profile_url=str(payload["target_profile_url"]),
        company_name=(
            str(payload["company_name"]) if payload.get("company_name") is not None else None
        ),
        role_hint=(str(payload["role_hint"]) if payload.get("role_hint") is not None else None),
        notes=tuple(str(item) for item in payload.get("notes", [])),
        metadata={
            str(key): str(value)
            for key, value in dict(payload.get("metadata", {})).items()
        },
    )


def gobii_tracked_entity_enrichment_bundle_from_payload(
    payload: Mapping[str, Any],
) -> GobiiTrackedEntityEnrichmentBundle:
    return GobiiTrackedEntityEnrichmentBundle(
        adapter_name=str(payload["adapter_name"]),
        workflow_kind=str(payload["workflow_kind"]),
        created_at=_parse_datetime(str(payload["created_at"])),
        request=gobii_tracked_entity_enrichment_request_from_payload(
            dict(payload["request"])
        ),
        task_create_request=GobiiTaskCreateRequest(
            prompt=str(dict(payload["task_create_request"])["prompt"]),
            agent_id=(
                str(dict(payload["task_create_request"])["agent_id"])
                if dict(payload["task_create_request"]).get("agent_id") is not None
                else None
            ),
            webhook=(
                str(dict(payload["task_create_request"])["webhook"])
                if dict(payload["task_create_request"]).get("webhook") is not None
                else None
            ),
            output_schema=dict(payload["task_create_request"]).get("output_schema"),
            wait_seconds=(
                int(dict(payload["task_create_request"])["wait_seconds"])
                if dict(payload["task_create_request"]).get("wait_seconds") is not None
                else None
            ),
        ),
        task_id=(str(payload["task_id"]).strip() if payload.get("task_id") else None),
        task_record_path=(
            str(payload["task_record_path"]).strip() if payload.get("task_record_path") else None
        ),
        metadata=dict(payload.get("metadata", {})),
    )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
