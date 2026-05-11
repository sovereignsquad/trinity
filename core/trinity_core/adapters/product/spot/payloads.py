"""Spot-owned payload parsing for Trinity bounded reasoning contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from trinity_core.schemas import SpotReasoningRequest, SpotReviewDisposition, SpotReviewOutcome


def spot_reasoning_request_from_payload(payload: dict[str, Any]) -> SpotReasoningRequest:
    occurred_at = payload.get("occurred_at")
    return SpotReasoningRequest(
        company_id=UUID(str(payload["company_id"])),
        run_id=str(payload["run_id"]),
        row_ref=str(payload["row_ref"]),
        language=str(payload["language"]),
        message_text=str(payload["message_text"]),
        source_platform=str(payload["source_platform"]) if payload.get("source_platform") else None,
        source_handle=str(payload["source_handle"]) if payload.get("source_handle") else None,
        occurred_at=_parse_datetime(occurred_at) if occurred_at else None,
        metadata={str(key): value for key, value in payload.get("metadata", {}).items()},
        contract_version=str(payload.get("contract_version") or "trinity.spot.v1alpha1"),
    )


def spot_review_outcome_from_payload(payload: dict[str, Any]) -> SpotReviewOutcome:
    return SpotReviewOutcome(
        company_id=UUID(str(payload["company_id"])),
        cycle_id=UUID(str(payload["cycle_id"])),
        run_id=str(payload["run_id"]),
        row_ref=str(payload["row_ref"]),
        selected_candidate_key=str(payload["selected_candidate_key"]),
        disposition=SpotReviewDisposition(str(payload["disposition"])),
        final_label=str(payload["final_label"]),
        occurred_at=_parse_datetime(str(payload["occurred_at"])),
        reviewer_notes=(
            str(payload["reviewer_notes"]) if payload.get("reviewer_notes") is not None else None
        ),
        metadata={str(key): value for key, value in payload.get("metadata", {}).items()},
        contract_version=str(payload.get("contract_version") or "trinity.spot.v1alpha1"),
    )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware.")
    return parsed
