from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from trinity_core.schemas import (
    CandidateLineage,
    CandidateRecord,
    CandidateScores,
    CandidateState,
    CandidateType,
    ReplyDraftCandidate,
    ReplyEvidenceEnvelope,
    ReplyFeedbackDisposition,
    ReplyFeedbackEvent,
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
