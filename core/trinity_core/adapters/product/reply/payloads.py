"""Reply-owned payload parsing and mapping for Trinity runtime contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from trinity_core.schemas import (
    DocumentRecord,
    DraftOutcomeDisposition,
    DraftOutcomeEvent,
    GoldenExample,
    MemoryEvent,
    MemoryEventKind,
    ThreadContextSnippet,
    ThreadMessageRole,
    ThreadMessageSnapshot,
    ThreadSnapshot,
)


def thread_snapshot_from_payload(payload: dict[str, Any]) -> ThreadSnapshot:
    return ThreadSnapshot(
        company_id=UUID(payload["company_id"]),
        thread_ref=str(payload["thread_ref"]),
        channel=str(payload["channel"]),
        contact_handle=str(payload["contact_handle"]),
        latest_inbound_text=str(payload["latest_inbound_text"]),
        requested_at=_parse_datetime(payload["requested_at"]),
        messages=tuple(
            ThreadMessageSnapshot(
                message_id=str(item["message_id"]),
                role=ThreadMessageRole(str(item["role"])),
                text=str(item["text"]),
                occurred_at=_parse_datetime(item["occurred_at"]),
                channel=str(item["channel"]),
                source=str(item["source"]),
                handle=str(item["handle"]),
            )
            for item in payload.get("messages", [])
        ),
        context_snippets=tuple(
            ThreadContextSnippet(
                source=str(item["source"]),
                path=str(item["path"]),
                text=str(item["text"]),
            )
            for item in payload.get("context_snippets", [])
        ),
        golden_examples=tuple(
            GoldenExample(
                path=str(item["path"]),
                text=str(item["text"]),
            )
            for item in payload.get("golden_examples", [])
        ),
        metadata={str(key): value for key, value in payload.get("metadata", {}).items()},
        contract_version=str(payload.get("contract_version") or "trinity.reply.v1alpha1"),
    )


def outcome_event_from_payload(payload: dict[str, Any]) -> DraftOutcomeEvent:
    candidate_id = payload.get("candidate_id")
    return DraftOutcomeEvent(
        company_id=UUID(payload["company_id"]),
        cycle_id=UUID(payload["cycle_id"]),
        thread_ref=str(payload["thread_ref"]),
        channel=str(payload["channel"]),
        disposition=DraftOutcomeDisposition(str(payload["disposition"])),
        occurred_at=_parse_datetime(payload["occurred_at"]),
        candidate_id=UUID(candidate_id) if candidate_id else None,
        original_draft_text=payload.get("original_draft_text"),
        final_text=payload.get("final_text"),
        edit_distance=float(payload["edit_distance"])
        if payload.get("edit_distance") is not None
        else None,
        latency_ms=int(payload["latency_ms"]) if payload.get("latency_ms") is not None else None,
        send_result=payload.get("send_result"),
        notes=payload.get("notes"),
        contract_version=str(payload.get("contract_version") or "trinity.reply.v1alpha1"),
    )


def memory_event_from_payload(payload: dict[str, Any]) -> MemoryEvent:
    return MemoryEvent(
        company_id=UUID(payload["company_id"]),
        event_kind=MemoryEventKind(str(payload["event_kind"])),
        source_ref=str(payload["source_ref"]),
        occurred_at=_parse_datetime(payload["occurred_at"]),
        thread_ref=payload.get("thread_ref"),
        channel=payload.get("channel"),
        contact_handle=payload.get("contact_handle"),
        content_text=payload.get("content_text"),
        metadata=payload.get("metadata", {}),
        contract_version=str(payload.get("contract_version") or "trinity.reply.v1alpha1"),
    )


def document_record_from_payload(payload: dict[str, Any]) -> DocumentRecord:
    occurred_at = payload.get("occurred_at")
    return DocumentRecord(
        company_id=UUID(payload["company_id"]),
        document_ref=str(payload["document_ref"]),
        source=str(payload["source"]),
        path=str(payload["path"]),
        title=payload.get("title"),
        content_text=str(payload.get("content_text") or ""),
        occurred_at=_parse_datetime(occurred_at) if occurred_at else None,
        metadata=payload.get("metadata", {}),
        contract_version=str(payload.get("contract_version") or "trinity.reply.v1alpha1"),
    )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware.")
    return parsed
