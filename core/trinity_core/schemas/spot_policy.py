"""Bounded Spot review policy artifacts owned by Trinity."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from .spot_integration import SPOT_CONTRACT_VERSION


def _require_timezone(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


def _require_text(value: str, *, field_name: str) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{field_name} is required.")


@dataclass(frozen=True, slots=True)
class SpotReviewPolicy:
    """First bounded Spot policy family for review routing."""

    artifact_key: str
    version: str
    scope_kind: SpotReviewScopeKind
    scope_value: str | None
    created_at: datetime
    source_project: str
    auto_approve_negative_threshold: float
    positive_review_required: bool = True
    default_review_required: bool = True
    notes: str | None = None
    contract_version: str = SPOT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.artifact_key, field_name="artifact_key")
        _require_text(self.version, field_name="version")
        _require_timezone(self.created_at, field_name="created_at")
        _require_text(self.source_project, field_name="source_project")
        scope_value = _normalize_optional_text(self.scope_value)
        if self.scope_kind is SpotReviewScopeKind.GLOBAL and scope_value is not None:
            raise ValueError("scope_value must be omitted for global Spot policies.")
        if self.scope_kind is SpotReviewScopeKind.COMPANY and scope_value is None:
            raise ValueError("scope_value is required for company-scoped Spot policies.")
        if scope_value is not None:
            scope_value = scope_value.lower()
        object.__setattr__(self, "scope_value", scope_value)
        if not 0.0 <= self.auto_approve_negative_threshold <= 1.0:
            raise ValueError("auto_approve_negative_threshold must be between 0 and 1.")

    def matches_scope(self, *, company_id: UUID | str | None = None) -> bool:
        if self.scope_kind is SpotReviewScopeKind.GLOBAL:
            return True
        normalized_company_id = _normalize_company_id(company_id)
        if normalized_company_id is None:
            raise ValueError("company_id is required for company-scoped Spot policies.")
        return self.scope_value == normalized_company_id


class SpotReviewScopeKind(StrEnum):
    GLOBAL = "global"
    COMPANY = "company"


def spot_review_policy_from_payload(payload: Mapping[str, Any]) -> SpotReviewPolicy:
    """Parse one persisted payload back into a validated Spot review policy."""

    return SpotReviewPolicy(
        artifact_key=str(payload["artifact_key"]),
        version=str(payload["version"]),
        scope_kind=SpotReviewScopeKind(str(payload.get("scope_kind", "global"))),
        scope_value=payload.get("scope_value"),
        created_at=_parse_datetime(str(payload["created_at"])),
        source_project=str(payload["source_project"]),
        auto_approve_negative_threshold=float(payload["auto_approve_negative_threshold"]),
        positive_review_required=bool(payload.get("positive_review_required", True)),
        default_review_required=bool(payload.get("default_review_required", True)),
        notes=(
            str(payload["notes"]).strip()
            if payload.get("notes") is not None and str(payload["notes"]).strip()
            else None
        ),
        contract_version=str(payload.get("contract_version", SPOT_CONTRACT_VERSION)),
    )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("created_at must be timezone-aware.")
    return parsed


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_company_id(company_id: UUID | str | None) -> str | None:
    if company_id is None:
        return None
    return str(company_id).strip().lower() or None
