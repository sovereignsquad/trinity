from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from trinity_core.cli import main
from trinity_core.ops.cycle_store import write_json_atomic
from trinity_core.reply_runtime import ReplyRuntime
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


def _thread_snapshot(
    *,
    company_id: UUID,
    requested_at: datetime,
    thread_ref: str = "reply:email:test@example.com",
    latest_inbound_text: str = "Can you send the latest draft?",
) -> ThreadSnapshot:
    return ThreadSnapshot(
        company_id=company_id,
        thread_ref=thread_ref,
        channel="email",
        contact_handle="test@example.com",
        latest_inbound_text=latest_inbound_text,
        requested_at=requested_at,
        messages=(
            ThreadMessageSnapshot(
                message_id=f"msg-{requested_at.day}",
                role=ThreadMessageRole.CONTACT,
                text=latest_inbound_text,
                occurred_at=requested_at,
                channel="email",
                source="reply",
                handle="test@example.com",
            ),
        ),
        context_snippets=(
            ThreadContextSnippet(
                source="reply-note",
                path=f"/notes/{requested_at.day}.md",
                text="Customer prefers direct responses.",
            ),
        ),
        golden_examples=(
            GoldenExample(
                path=f"/examples/{requested_at.day}.txt",
                text="Keep it short and explicit.",
            ),
        ),
        metadata={
            "tenant_scope": str(company_id),
            "attachment_refs": [f"thread-attachment-{requested_at.day}"],
        },
    )


def _seed_runtime_state(
    runtime: ReplyRuntime,
    company_id: UUID,
) -> tuple[dict[str, object], dict[str, object]]:
    early_snapshot = _thread_snapshot(
        company_id=company_id,
        requested_at=datetime(2026, 5, 10, 9, 0, tzinfo=UTC),
        thread_ref="reply:email:early@example.com",
        latest_inbound_text="Please send the earlier update.",
    )
    later_snapshot = _thread_snapshot(
        company_id=company_id,
        requested_at=datetime(2026, 5, 16, 9, 0, tzinfo=UTC),
        thread_ref="reply:email:later@example.com",
        latest_inbound_text="Please send the final update.",
    )
    early_ranked = runtime.suggest(early_snapshot)
    later_ranked = runtime.suggest(later_snapshot)

    runtime.ingest_memory_event(
        MemoryEvent(
            company_id=company_id,
            event_kind=MemoryEventKind.INBOUND_MESSAGE_RECORDED,
            source_ref="reply:event:early",
            occurred_at=datetime(2026, 5, 9, 8, 0, tzinfo=UTC),
            thread_ref=early_snapshot.thread_ref,
            channel=early_snapshot.channel,
            contact_handle=early_snapshot.contact_handle,
            content_text="Earlier runtime event.",
            metadata={"attachment_refs": ["mem-attach-early"]},
        )
    )
    runtime.ingest_memory_event(
        MemoryEvent(
            company_id=company_id,
            event_kind=MemoryEventKind.DRAFT_EDITED,
            source_ref="reply:event:later",
            occurred_at=datetime(2026, 5, 16, 10, 0, tzinfo=UTC),
            thread_ref=later_snapshot.thread_ref,
            channel=later_snapshot.channel,
            contact_handle=later_snapshot.contact_handle,
            content_text="Later runtime event.",
            metadata={
                "attachment_refs": ["mem-attach-later"],
                "document_ref": "doc-later",
                "source_ref": "reply:later",
                "confidence_score": 0.91,
            },
        )
    )
    runtime.register_document(
        DocumentRecord(
            company_id=company_id,
            document_ref="doc-later",
            source="reply",
            path="/docs/later.md",
            title="Later doc",
            content_text="Document body",
            occurred_at=datetime(2026, 5, 16, 10, 5, tzinfo=UTC),
            metadata={
                "attachment_refs": ["doc-attach-later"],
                "thread_ref": later_snapshot.thread_ref,
            },
        )
    )
    runtime.record_outcome(
        DraftOutcomeEvent(
            company_id=company_id,
            cycle_id=early_ranked.cycle_id,
            thread_ref=early_snapshot.thread_ref,
            channel=early_snapshot.channel,
            disposition=DraftOutcomeDisposition.SENT_AS_IS,
            occurred_at=datetime(2026, 5, 10, 9, 5, tzinfo=UTC),
            candidate_id=early_ranked.drafts[0].candidate_id,
            original_draft_text="I can send the earlier update by noon today.",
            final_text="I can send the earlier update by noon today.",
        )
    )
    runtime.record_outcome(
        DraftOutcomeEvent(
            company_id=company_id,
            cycle_id=later_ranked.cycle_id,
            thread_ref=later_snapshot.thread_ref,
            channel=later_snapshot.channel,
            disposition=DraftOutcomeDisposition.EDITED_THEN_SENT,
            occurred_at=datetime(2026, 5, 16, 10, 15, tzinfo=UTC),
            candidate_id=later_ranked.drafts[0].candidate_id,
            original_draft_text="I can send the final update today after I confirm the last figure.",
            final_text="I can send the final update today after I confirm the last figure.",
            edit_distance=0.25,
        )
    )
    return (
        runtime.build_source_export(company_id=company_id, snapshot_ref="snapshot-a"),
        runtime.build_outcome_export(company_id=company_id, snapshot_ref="snapshot-a"),
    )


def test_portable_export_families_are_distinct_and_stable(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    company_id = uuid4()
    runtime = ReplyRuntime()
    source_first, outcome_first = _seed_runtime_state(runtime, company_id)
    memory_first = runtime.build_memory_export(company_id=company_id, snapshot_ref="snapshot-a")

    source_second = runtime.build_source_export(company_id=company_id, snapshot_ref="snapshot-a")
    outcome_second = runtime.build_outcome_export(company_id=company_id, snapshot_ref="snapshot-a")
    memory_second = runtime.build_memory_export(company_id=company_id, snapshot_ref="snapshot-a")

    assert source_first["export"]["integrity"] == source_second["export"]["integrity"]
    assert outcome_first["export"]["integrity"] == outcome_second["export"]["integrity"]
    assert memory_first["export"]["integrity"] == memory_second["export"]["integrity"]

    source_types = {record["record_type"] for record in source_first["export"]["records"]}
    outcome_types = {record["record_type"] for record in outcome_first["export"]["records"]}
    memory_types = {record["record_type"] for record in memory_first["export"]["records"]}

    assert {
        "thread_snapshot",
        "message",
        "context_snippet",
        "golden_example",
        "document",
        "memory_event",
    } <= source_types
    assert {"candidate_variant", "supervision_event", "final_outcome"} <= outcome_types
    assert {"memory_summary", "contact_profile", "thread_state"} <= memory_types
    assert "memory_summary" not in source_types
    assert "document" not in outcome_types
    assert "candidate_variant" not in memory_types


def test_outcome_export_excludes_shown_only_feedback_from_final_supervision(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    company_id = uuid4()
    runtime = ReplyRuntime()
    snapshot = _thread_snapshot(
        company_id=company_id,
        requested_at=datetime(2026, 5, 21, 9, 0, tzinfo=UTC),
        thread_ref="reply:whatsapp:shown-only",
        latest_inbound_text="Valaszolj kerlek.",
    )
    ranked = runtime.suggest(snapshot)
    runtime.record_outcome(
        DraftOutcomeEvent(
            company_id=company_id,
            cycle_id=ranked.cycle_id,
            thread_ref=snapshot.thread_ref,
            channel=snapshot.channel,
            disposition=DraftOutcomeDisposition.SHOWN,
            occurred_at=datetime(2026, 5, 21, 9, 5, tzinfo=UTC),
            candidate_id=ranked.drafts[0].candidate_id,
            original_draft_text=ranked.drafts[0].draft_text,
            final_text=None,
        )
    )

    outcome_export = runtime.build_outcome_export(
        company_id=company_id,
        snapshot_ref="snapshot-shown",
    )
    final_records = [
        record
        for record in outcome_export["export"]["records"]
        if record["record_type"] == "final_outcome"
    ]
    candidate_records = [
        record
        for record in outcome_export["export"]["records"]
        if record["record_type"] == "candidate_variant"
    ]

    assert final_records == []
    assert candidate_records
    assert all(
        record["quality_metadata"].get("supervision_ready") is False
        for record in candidate_records
    )
    assert all(
        record["quality_metadata"].get("variant_state") == "unresolved"
        for record in candidate_records
    )


def test_outcome_export_excludes_generic_placeholder_final_supervision(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    company_id = uuid4()
    runtime = ReplyRuntime()
    snapshot = _thread_snapshot(
        company_id=company_id,
        requested_at=datetime(2026, 5, 21, 9, 0, tzinfo=UTC),
        thread_ref="reply:whatsapp:generic-placeholder",
        latest_inbound_text="Valaszolj a lanyoknak kerlek",
    )
    ranked = runtime.suggest(snapshot)
    runtime.record_outcome(
        DraftOutcomeEvent(
            company_id=company_id,
            cycle_id=ranked.cycle_id,
            thread_ref=snapshot.thread_ref,
            channel=snapshot.channel,
            disposition=DraftOutcomeDisposition.SENT_AS_IS,
            occurred_at=datetime(2026, 5, 21, 9, 5, tzinfo=UTC),
            candidate_id=ranked.drafts[0].candidate_id,
            original_draft_text="Thanks 242910582800433, I saw this. I can move this forward.",
            final_text="Thanks 242910582800433, I saw this. I can move this forward.",
        )
    )

    outcome_export = runtime.build_outcome_export(
        company_id=company_id,
        snapshot_ref="snapshot-generic",
    )
    final_records = [
        record
        for record in outcome_export["export"]["records"]
        if record["record_type"] == "final_outcome"
    ]

    assert final_records == []


def test_record_outcome_recovers_missing_cycle_with_synthetic_historical_payload(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    company_id = uuid4()
    runtime = ReplyRuntime()
    cycle_id = uuid4()
    outcome = DraftOutcomeEvent(
        company_id=company_id,
        cycle_id=cycle_id,
        thread_ref="reply:whatsapp:+36705957647",
        channel="whatsapp",
        disposition=DraftOutcomeDisposition.SENT_AS_IS,
        occurred_at=datetime(2026, 5, 21, 9, 5, tzinfo=UTC),
        candidate_id=uuid4(),
        original_draft_text="Kérek egy linket",
        final_text="Kérek egy linket",
    )

    result = runtime.record_outcome(outcome)
    outcome_export = runtime.build_outcome_export(
        company_id=company_id,
        snapshot_ref="snapshot-historical-recovery",
    )
    final_records = [
        record
        for record in outcome_export["export"]["records"]
        if record["record_type"] == "final_outcome"
    ]
    source_export = runtime.build_source_export(
        company_id=company_id,
        snapshot_ref="snapshot-historical-recovery",
    )

    assert result["status"] == "ok"
    assert final_records
    assert final_records[0]["payload"]["final_text"] == "Kérek egy linket"
    assert all(
        str(record["payload"].get("metadata", {}).get("historical_outcome_backfill") or "").lower() != "true"
        for record in source_export["export"]["records"]
        if record["record_type"] == "thread_snapshot"
    )


def test_source_export_preserves_reply_mapping_and_attachment_refs(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    company_id = uuid4()
    runtime = ReplyRuntime()
    source_export, _ = _seed_runtime_state(runtime, company_id)

    message_records = [
        record
        for record in source_export["export"]["records"]
        if record["record_type"] == "message"
    ]
    document_records = [
        record
        for record in source_export["export"]["records"]
        if record["record_type"] == "document"
    ]
    memory_event_records = [
        record
        for record in source_export["export"]["records"]
        if record["record_type"] == "memory_event"
    ]

    assert any(record["payload"]["source"] == "reply" for record in message_records)
    assert any(
        record["payload"]["thread_ref"].startswith("reply:email:") for record in message_records
    )
    assert any("doc-attach-later" in record["attachment_refs"] for record in document_records)
    assert any("mem-attach-later" in record["attachment_refs"] for record in memory_event_records)


def test_build_source_export_rejects_cross_tenant_trace_payload(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    runtime = ReplyRuntime()
    company_id = uuid4()
    other_company_id = uuid4()
    cycle_id = uuid4()
    bad_payload = {
        "cycle_id": str(cycle_id),
        "exported_at": "2026-05-20T09:00:00+00:00",
        "thread_snapshot": {
            "company_id": str(other_company_id),
            "thread_ref": "reply:email:bad@example.com",
            "channel": "email",
            "contact_handle": "bad@example.com",
            "latest_inbound_text": "Bad tenant payload",
            "requested_at": "2026-05-20T09:00:00+00:00",
            "messages": [],
            "context_snippets": [],
            "golden_examples": [],
            "metadata": {},
        },
        "ranked_draft_set": {"cycle_id": str(cycle_id), "trace_ref": "bad-trace", "drafts": []},
        "candidates": [],
        "feedback_events": [],
    }
    path = runtime.store.export_path(cycle_id, company_id=company_id)
    write_json_atomic(path, bad_payload)

    with pytest.raises(ValueError, match="Cross-tenant trace payload rejected"):
        runtime.build_source_export(company_id=company_id, snapshot_ref="snapshot-cross")


def test_delta_export_preserves_cutoff_lineage_and_validation(
    monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    company_id = uuid4()
    runtime = ReplyRuntime()
    _seed_runtime_state(runtime, company_id)

    delta_result = runtime.build_delta_export(
        company_id=company_id,
        cutoff_at=datetime(2026, 5, 12, 0, 0, tzinfo=UTC),
        snapshot_ref="snapshot-b",
        prior_snapshot_ref="snapshot-a",
    )
    delta_export = delta_result["export"]

    assert delta_export["lineage"]["cutoff_ref"] == "2026-05-12T00:00:00+00:00"
    assert delta_export["lineage"]["prior_snapshot_ref"] == "snapshot-a"
    assert delta_export["record_count"] == (
        len(delta_export["source_records"])
        + len(delta_export["outcome_records"])
        + len(delta_export["memory_records"])
    )
    assert all(
        datetime.fromisoformat(record["occurred_at"]) > datetime(2026, 5, 12, 0, 0, tzinfo=UTC)
        for group in ("source_records", "outcome_records", "memory_records")
        for record in delta_export[group]
    )

    exit_code = main(
        [
            "validate-export-lineage",
            "--adapter",
            "reply",
            "--company-id",
            str(company_id),
            "--export-family",
            "delta",
            "--export-id",
            str(delta_result["export_id"]),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["errors"] == []


def test_cli_build_and_inspect_portable_export_contract(
    monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TRINITY_APP_SUPPORT_DIR", str(tmp_path / "app_support"))
    company_id = uuid4()
    runtime = ReplyRuntime()
    _seed_runtime_state(runtime, company_id)

    exit_code = main(
        [
            "build-source-export",
            "--adapter",
            "reply",
            "--company-id",
            str(company_id),
            "--snapshot-ref",
            "snapshot-cli",
        ]
    )
    build_payload = json.loads(capsys.readouterr().out)
    inspect_exit = main(
        [
            "inspect-export-metadata",
            "--adapter",
            "reply",
            "--company-id",
            str(company_id),
            "--export-family",
            "source",
            "--export-id",
            str(build_payload["export_id"]),
        ]
    )
    inspect_payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert inspect_exit == 0
    assert build_payload["export"]["export_family"] == "source"
    assert inspect_payload["contract_version"] == "trinity_portable_export_inspect.v1"
    assert inspect_payload["record_count"] == build_payload["export"]["record_count"]
