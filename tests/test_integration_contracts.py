from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from trinity_core.ops.cycle_store import RuntimeCyclePaths, RuntimeCycleStore
from trinity_core.reply_runtime import ReplyRuntime
from trinity_core.schemas import (
    AcceptedArtifactVersion,
    CandidateLineage,
    CandidateRecord,
    CandidateScores,
    CandidateState,
    CandidateType,
    DraftOutcomeDisposition,
    DraftOutcomeEvent,
    RankedDraftSet,
    ReplyDraftCandidate,
    ReplyEvidenceEnvelope,
    ReplyFeedbackDisposition,
    ReplyFeedbackEvent,
    ThreadContextSnippet,
    ThreadMessageRole,
    ThreadMessageSnapshot,
    ThreadSnapshot,
)


def test_reply_draft_candidate_can_be_built_from_runtime_candidate() -> None:
    company_id = uuid4()
    evidence_id = uuid4()
    candidate = CandidateRecord(
        company_id=company_id,
        candidate_id=uuid4(),
        candidate_type=CandidateType.ACTION,
        state=CandidateState.EVALUATED,
        title="Draft recovery note",
        content="Send a concise recovery note to the stakeholder.",
        lineage=CandidateLineage(version_family_id=uuid4(), source_evidence_ids=(evidence_id,)),
        scores=CandidateScores(
            impact=8,
            confidence=7,
            ease=6,
            quality_score=84.0,
            urgency_score=80.0,
            freshness_score=79.0,
            feedback_score=25.0,
        ),
        created_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        evaluated_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        evaluation_reason="Best current action for the conversation.",
    )

    draft = ReplyDraftCandidate.from_candidate_record(
        candidate,
        conversation_ref="reply:linkedin:alice",
        recipient_handle="linkedin://alice",
        channel="linkedin",
    )

    assert draft.conversation_ref == "reply:linkedin:alice"
    assert draft.rationale == "Best current action for the conversation."
    assert draft.source_evidence_ids == (evidence_id,)


def test_reply_evidence_envelope_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ReplyEvidenceEnvelope(
            company_id=uuid4(),
            conversation_ref="reply:imessage:bob",
            channel="imessage",
            sender_handle="+36301234567",
            message_text="Need the updated numbers.",
            occurred_at=datetime(2026, 5, 1, 12, 0),
        )


def test_reply_feedback_event_requires_edited_text_for_edited_disposition() -> None:
    with pytest.raises(ValueError, match="edited_text"):
        ReplyFeedbackEvent(
            company_id=uuid4(),
            candidate_id=uuid4(),
            conversation_ref="reply:whatsapp:carol",
            disposition=ReplyFeedbackDisposition.EDITED,
            occurred_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        )


def test_thread_snapshot_requires_timezone_aware_requested_at() -> None:
    with pytest.raises(ValueError, match="requested_at"):
        ThreadSnapshot(
            company_id=uuid4(),
            thread_ref="reply:linkedin:alice",
            channel="linkedin",
            contact_handle="linkedin://alice",
            latest_inbound_text="Can you send the update?",
            requested_at=datetime(2026, 5, 1, 12, 0),
        )


def test_ranked_draft_set_requires_non_empty_drafts() -> None:
    with pytest.raises(ValueError, match="drafts"):
        RankedDraftSet(
            cycle_id=uuid4(),
            thread_ref="reply:linkedin:alice",
            channel="linkedin",
            generated_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            drafts=(),
            accepted_artifact_version=AcceptedArtifactVersion(
                artifact_key="reply_ranker_policy",
                version="v0",
                source_project="trinity",
                accepted_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            ),
        )


def test_reply_runtime_persists_cycle_and_feedback(tmp_path: Path) -> None:
    runtime = ReplyRuntime(
        store=RuntimeCycleStore(
            RuntimeCyclePaths(
                root_dir=tmp_path,
                cycles_dir=tmp_path / "cycles",
                exports_dir=tmp_path / "exports",
            )
        )
    )
    runtime.store.paths.cycles_dir.mkdir(parents=True, exist_ok=True)
    runtime.store.paths.exports_dir.mkdir(parents=True, exist_ok=True)
    snapshot = ThreadSnapshot(
        company_id=uuid4(),
        thread_ref="reply:linkedin:alice",
        channel="linkedin",
        contact_handle="linkedin://alice",
        latest_inbound_text="Can you send the updated numbers today?",
        requested_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        messages=(
            ThreadMessageSnapshot(
                message_id="msg-1",
                role=ThreadMessageRole.CONTACT,
                text="Can you send the updated numbers today?",
                occurred_at=datetime(2026, 5, 1, 11, 59, tzinfo=UTC),
                channel="linkedin",
                source="linkedin",
                handle="linkedin://alice",
            ),
        ),
        context_snippets=(
            ThreadContextSnippet(
                source="vector-store",
                path="snippet://alice/1",
                text="Alice asked for the Q2 pricing table.",
            ),
        ),
    )

    ranked = runtime.suggest(snapshot)

    assert len(ranked.drafts) == 3
    assert runtime.store.cycle_path(ranked.cycle_id).exists()
    assert runtime.store.export_path(ranked.cycle_id).exists()

    outcome = DraftOutcomeEvent(
        company_id=snapshot.company_id,
        cycle_id=ranked.cycle_id,
        thread_ref=snapshot.thread_ref,
        channel=snapshot.channel,
        candidate_id=ranked.drafts[0].candidate_id,
        disposition=DraftOutcomeDisposition.SENT_AS_IS,
        occurred_at=datetime(2026, 5, 1, 12, 1, tzinfo=UTC),
        original_draft_text=ranked.drafts[0].draft_text,
        final_text=ranked.drafts[0].draft_text,
        edit_distance=0.0,
        latency_ms=1000,
        send_result="ok",
    )

    result = runtime.record_outcome(outcome)

    assert result["status"] == "ok"
    payload = runtime.store.load_cycle(ranked.cycle_id)
    assert payload["feedback_events"][0]["disposition"] == DraftOutcomeDisposition.SENT_AS_IS.value
    assert payload["frontier_candidate_ids"]
    assert payload["accepted_artifact_version"]["artifact_key"] == "reply_ranker_policy"
