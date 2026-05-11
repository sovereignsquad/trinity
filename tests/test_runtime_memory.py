from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from trinity_core.memory import ReplyMemoryResolver, ReplyMemoryStore
from trinity_core.ops.cycle_store import dataclass_payload
from trinity_core.reply_runtime import ReplyRuntime
from trinity_core.schemas import (
    AcceptedArtifactVersion,
    CandidateDraft,
    CandidateScores,
    CandidateType,
    ContactProfile,
    DocumentRecord,
    MemoryEvent,
    MemoryEventKind,
    MemoryScopeKind,
    MemorySummary,
    MemoryTier,
    PreparedDraftSet,
    RankedDraftSet,
    ThreadMessageRole,
    ThreadMessageSnapshot,
    ThreadSnapshot,
    ThreadState,
)


def test_reply_memory_store_persists_events_and_prepared_drafts(tmp_path: Path) -> None:
    store = ReplyMemoryStore(db_path=tmp_path / "runtime_memory.sqlite3")
    company_id = uuid4()
    occurred_at = datetime.now(UTC)

    event = MemoryEvent(
        company_id=company_id,
        event_kind=MemoryEventKind.INBOUND_MESSAGE_RECORDED,
        source_ref="imessage:thread-1:42",
        occurred_at=occurred_at,
        thread_ref="reply:imessage:alice",
        channel="imessage",
        contact_handle="alice",
        content_text="Need the update today.",
        metadata={"display_name": "Alice"},
    )
    store.record_event(event)
    store.upsert_contact_profile(
        ContactProfile(
            company_id=company_id,
            contact_handle="alice",
            display_name="Alice",
            summary="Warm lead",
            metadata={"channel": "imessage"},
            updated_at=occurred_at,
        )
    )
    store.upsert_thread_state(
        ThreadState(
            company_id=company_id,
            thread_ref="reply:imessage:alice",
            channel="imessage",
            contact_handle="alice",
            latest_inbound_text="Need the update today.",
            last_event_at=occurred_at,
            last_snapshot_at=occurred_at,
            metadata={"message_count": 3},
        )
    )
    store.mark_thread_dirty(company_id, "reply:imessage:alice", reason="inbound_message_recorded")

    ranked = RankedDraftSet(
        cycle_id=uuid4(),
        thread_ref="reply:imessage:alice",
        channel="imessage",
        generated_at=occurred_at,
        drafts=(
            CandidateDraft(
                company_id=company_id,
                candidate_id=uuid4(),
                thread_ref="reply:imessage:alice",
                recipient_handle="alice",
                channel="imessage",
                rank=1,
                draft_text="I can send the update today.",
                rationale="Direct next step.",
                risk_flags=(),
                delivery_eligible=True,
                scores=CandidateScores(impact=8, confidence=7, ease=8),
                source_evidence_ids=(uuid4(),),
                candidate_type=CandidateType.ACTION,
            ),
        ),
        trace_ref="/tmp/runtime-trace.json",
        accepted_artifact_version=AcceptedArtifactVersion(
            artifact_key="reply_ranker_policy",
            version="reply_ranker_policy.v0",
            source_project="trinity",
            accepted_at=occurred_at,
        ),
    )
    prepared = PreparedDraftSet(
        company_id=company_id,
        thread_ref="reply:imessage:alice",
        prepared_at=occurred_at,
        expires_at=occurred_at + timedelta(minutes=5),
        source_thread_version="reply:imessage:alice:3",
        retrieval_context_hash="ctx-1",
        generation_reason="test",
        ranked_draft_set=ranked,
    )
    store.save_prepared_draft(prepared)

    payload = store.load_prepared_draft_payload(company_id, "reply:imessage:alice")

    assert payload is not None
    assert payload["thread_ref"] == "reply:imessage:alice"
    assert payload["generation_reason"] == "test"
    assert payload["ranked_draft_set"]["drafts"][0]["draft_text"] == "I can send the update today."
    assert store.latest_snapshot_payload(company_id, "reply:imessage:alice") is None
    assert dataclass_payload(prepared)["retrieval_context_hash"] == "ctx-1"

    store.register_document(
        DocumentRecord(
            company_id=company_id,
            document_ref="note-1",
            source="notes",
            path="notes://alice/1",
            title="Alice note",
            content_text="Operator note",
            occurred_at=occurred_at,
            metadata={},
        )
    )
    store.delete_document(company_id, "note-1")


def test_reply_memory_resolver_builds_scoped_runtime_context(tmp_path: Path) -> None:
    store = ReplyMemoryStore(db_path=tmp_path / "runtime_memory.sqlite3")
    resolver = ReplyMemoryResolver(store)
    company_id = uuid4()
    occurred_at = datetime.now(UTC)

    store.upsert_contact_profile(
        ContactProfile(
            company_id=company_id,
            contact_handle="alice",
            display_name="Alice",
            summary="Prefers concise updates.",
            metadata={"channel": "imessage"},
            updated_at=occurred_at,
        )
    )
    store.upsert_thread_state(
        ThreadState(
            company_id=company_id,
            thread_ref="reply:imessage:alice",
            channel="imessage",
            contact_handle="alice",
            latest_inbound_text="Need the update today.",
            last_event_at=occurred_at,
            last_snapshot_at=occurred_at,
            metadata={"message_count": 3},
        )
    )
    store.save_summary(
        MemorySummary(
            company_id=company_id,
            summary_key="success_pattern",
            scope_ref=f"company:{company_id}",
            content="Fast direct updates usually perform well.",
            updated_at=occurred_at,
            metadata={"family": "successful_pattern"},
        )
    )
    store.save_summary(
        MemorySummary(
            company_id=company_id,
            summary_key="human_resolution_recent",
            scope_ref="human:thread:reply:imessage:alice",
            content="Human resolved a risky thread by choosing a concise reply.",
            updated_at=occurred_at,
            metadata={"family": "human_resolution"},
        )
    )
    store.save_summary(
        MemorySummary(
            company_id=company_id,
            summary_key="disagreement_recent",
            scope_ref=f"company:{company_id}",
            content="Minority safer route was later chosen by a human.",
            updated_at=occurred_at,
            metadata={"family": "disagreement"},
        )
    )

    from trinity_core.schemas import ThreadSnapshot

    snapshot = ThreadSnapshot(
        company_id=company_id,
        thread_ref="reply:imessage:alice",
        channel="imessage",
        contact_handle="alice",
        latest_inbound_text="Need the update today.",
        requested_at=occurred_at,
        metadata={"topic_hints": "pricing"},
    )

    context = resolver.resolve_for_snapshot(snapshot)

    assert context.retrieval_context_hash
    assert context.tier_counts["core"] >= 2
    assert any(record.tier is MemoryTier.CORE for record in context.records)
    assert any(record.tier is MemoryTier.WORKING for record in context.records)
    assert any(scope.scope_kind is MemoryScopeKind.COMPANY for scope in context.scopes)
    assert any(record.record_key == "contact:alice" for record in context.records)
    assert any(record.record_key == "thread:reply:imessage:alice" for record in context.records)
    assert any(
        record.record_key.startswith("summary:success_pattern")
        for record in context.records
    )
    assert any(record.family.value == "human_resolution" for record in context.records)
    assert any(record.family.value == "disagreement" for record in context.records)
    assert context.records[0].relevance_score >= context.records[-1].relevance_score
    assert context.records[0].tier is MemoryTier.CORE
    assert "tier:core" in context.records[0].selection_reason
    assert any(
        scope_reason in context.records[0].selection_reason
        for scope_reason in ("scope:human_resolution", "scope:item_family")
    )


def test_reply_memory_store_builds_prepared_draft_refresh_plan(tmp_path: Path) -> None:
    store = ReplyMemoryStore(db_path=tmp_path / "runtime_memory.sqlite3")
    company_id = uuid4()
    now = datetime.now(UTC)

    store.upsert_thread_state(
        ThreadState(
            company_id=company_id,
            thread_ref="reply:imessage:dirty",
            channel="imessage",
            contact_handle="dirty",
            latest_inbound_text="Need the update today.",
            last_event_at=now,
            last_snapshot_at=now,
            metadata={},
        ),
        snapshot=_thread_snapshot(company_id, "reply:imessage:dirty", "dirty", now),
    )
    store.mark_thread_dirty(company_id, "reply:imessage:dirty", reason="inbound_message_recorded")
    store.save_prepared_draft(_prepared_draft(company_id, "reply:imessage:dirty", now))

    store.upsert_thread_state(
        ThreadState(
            company_id=company_id,
            thread_ref="reply:imessage:missing",
            channel="imessage",
            contact_handle="missing",
            latest_inbound_text="Checking in.",
            last_event_at=now - timedelta(minutes=1),
            last_snapshot_at=now - timedelta(minutes=1),
            metadata={},
        ),
        snapshot=_thread_snapshot(company_id, "reply:imessage:missing", "missing", now),
    )

    stale_prepared_at = now - timedelta(minutes=30)
    store.upsert_thread_state(
        ThreadState(
            company_id=company_id,
            thread_ref="reply:imessage:stale",
            channel="imessage",
            contact_handle="stale",
            latest_inbound_text="Do you have a draft?",
            last_event_at=now - timedelta(minutes=2),
            last_snapshot_at=now - timedelta(minutes=2),
            metadata={},
        ),
        snapshot=_thread_snapshot(company_id, "reply:imessage:stale", "stale", now),
    )
    store.save_prepared_draft(
        _prepared_draft(
            company_id,
            "reply:imessage:stale",
            stale_prepared_at,
            expires_at=stale_prepared_at + timedelta(minutes=15),
        )
    )

    store.upsert_thread_state(
        ThreadState(
            company_id=company_id,
            thread_ref="reply:imessage:fresh",
            channel="imessage",
            contact_handle="fresh",
            latest_inbound_text="Fresh thread.",
            last_event_at=now - timedelta(minutes=3),
            last_snapshot_at=now - timedelta(minutes=3),
            metadata={},
        ),
        snapshot=_thread_snapshot(company_id, "reply:imessage:fresh", "fresh", now),
    )
    store.save_prepared_draft(_prepared_draft(company_id, "reply:imessage:fresh", now))

    plan = store.build_prepared_draft_refresh_plan(company_id, limit=10, now=now)

    assert [candidate.thread_ref for candidate in plan.candidates] == [
        "reply:imessage:dirty",
        "reply:imessage:missing",
        "reply:imessage:stale",
    ]
    assert plan.candidates[0].dirty is True
    assert plan.candidates[0].refresh_reason == "dirty:inbound_message_recorded"
    assert plan.candidates[1].missing_prepared_draft is True
    assert plan.candidates[1].refresh_reason == "missing_prepared_draft"
    assert plan.candidates[2].stale is True
    assert plan.candidates[2].refresh_reason == "stale_prepared_draft"


def test_reply_runtime_refresh_prepared_draft_skips_fresh_and_refreshes_dirty(
    tmp_path: Path,
) -> None:
    runtime = ReplyRuntime(store=None)
    runtime.memory_store = ReplyMemoryStore(db_path=tmp_path / "runtime_memory.sqlite3")
    company_id = uuid4()
    now = datetime.now(UTC)
    snapshot = _thread_snapshot(company_id, "reply:imessage:alice", "alice", now)

    runtime.suggest(snapshot)

    skipped = runtime.refresh_prepared_draft(
        company_id=company_id,
        thread_ref="reply:imessage:alice",
        generation_reason="dirty_thread_refresh",
    )

    assert skipped["status"] == "skipped_fresh"
    assert skipped["overwrite_mode"] == "if_stale_or_dirty"

    runtime.memory_store.mark_thread_dirty(
        company_id,
        "reply:imessage:alice",
        reason="inbound_message_recorded",
    )
    refreshed = runtime.refresh_prepared_draft(
        company_id=company_id,
        thread_ref="reply:imessage:alice",
        generation_reason="dirty_thread_refresh",
    )

    assert refreshed["status"] == "ok"
    assert refreshed["overwrite_reason"] == "inbound_message_recorded"
    assert refreshed["prepared_draft_set"]["generation_reason"] == "dirty_thread_refresh"
    assert (
        runtime.memory_store.load_dirty_thread_payload(company_id, "reply:imessage:alice") is None
    )


def _thread_snapshot(
    company_id,
    thread_ref: str,
    handle: str,
    now: datetime,
) -> ThreadSnapshot:
    return ThreadSnapshot(
        company_id=company_id,
        thread_ref=thread_ref,
        channel="imessage",
        contact_handle=handle,
        latest_inbound_text="Need the update today.",
        requested_at=now,
        messages=(
            ThreadMessageSnapshot(
                message_id=f"{thread_ref}:1",
                role=ThreadMessageRole.CONTACT,
                text="Need the update today.",
                occurred_at=now,
                channel="imessage",
                source="reply",
                handle=handle,
            ),
        ),
    )


def _prepared_draft(
    company_id,
    thread_ref: str,
    prepared_at: datetime,
    *,
    expires_at: datetime | None = None,
) -> PreparedDraftSet:
    ranked = RankedDraftSet(
        cycle_id=uuid4(),
        thread_ref=thread_ref,
        channel="imessage",
        generated_at=prepared_at,
        drafts=(
            CandidateDraft(
                company_id=company_id,
                candidate_id=uuid4(),
                thread_ref=thread_ref,
                recipient_handle=thread_ref.rsplit(":", 1)[-1],
                channel="imessage",
                rank=1,
                draft_text="I can send the update today.",
                rationale="Direct next step.",
                risk_flags=(),
                delivery_eligible=True,
                scores=CandidateScores(impact=8, confidence=7, ease=8),
                source_evidence_ids=(uuid4(),),
                candidate_type=CandidateType.ACTION,
            ),
        ),
        trace_ref="/tmp/runtime-trace.json",
        accepted_artifact_version=AcceptedArtifactVersion(
            artifact_key="reply_ranker_policy",
            version="reply_ranker_policy.v0",
            source_project="trinity",
            accepted_at=prepared_at,
        ),
    )
    return PreparedDraftSet(
        company_id=company_id,
        thread_ref=thread_ref,
        prepared_at=prepared_at,
        expires_at=expires_at or (prepared_at + timedelta(minutes=15)),
        source_thread_version=f"{thread_ref}:1",
        retrieval_context_hash=f"ctx:{thread_ref}",
        generation_reason="test",
        ranked_draft_set=ranked,
    )
