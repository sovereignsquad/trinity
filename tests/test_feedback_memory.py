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
    ReplyFeedbackDisposition,
    ReplyFeedbackEvent,
)
from trinity_core.workflow import apply_reply_feedback


def test_apply_reply_feedback_updates_feedback_score_and_timestamp() -> None:
    candidate = _make_candidate()
    event = ReplyFeedbackEvent(
        company_id=candidate.company_id,
        candidate_id=candidate.candidate_id,
        conversation_ref="reply:linkedin:alice",
        disposition=ReplyFeedbackDisposition.ACCEPTED,
        occurred_at=datetime(2026, 5, 1, 13, 0, tzinfo=UTC),
    )

    updated = apply_reply_feedback(candidate, event)

    assert updated.scores.feedback_score == 18.0
    assert updated.last_feedback_at == event.occurred_at
    assert updated.updated_at == event.occurred_at


def test_apply_reply_feedback_can_mark_action_candidate_sent() -> None:
    candidate = _make_candidate()
    event = ReplyFeedbackEvent(
        company_id=candidate.company_id,
        candidate_id=candidate.candidate_id,
        conversation_ref="reply:imessage:bob",
        disposition=ReplyFeedbackDisposition.SENT,
        occurred_at=datetime(2026, 5, 1, 13, 0, tzinfo=UTC),
    )

    updated = apply_reply_feedback(candidate, event)

    assert updated.state is CandidateState.DELIVERED
    assert updated.last_delivered_at == event.occurred_at
    assert updated.delivery_target_ref == "reply:imessage:bob"


def test_apply_reply_feedback_rejects_mismatched_ids() -> None:
    candidate = _make_candidate()
    event = ReplyFeedbackEvent(
        company_id=uuid4(),
        candidate_id=candidate.candidate_id,
        conversation_ref="reply:whatsapp:carol",
        disposition=ReplyFeedbackDisposition.REJECTED,
        occurred_at=datetime(2026, 5, 1, 13, 0, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="company_id"):
        apply_reply_feedback(candidate, event)


def _make_candidate() -> CandidateRecord:
    now = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    return CandidateRecord(
        company_id=uuid4(),
        candidate_id=uuid4(),
        candidate_type=CandidateType.ACTION,
        state=CandidateState.EVALUATED,
        title="Draft recovery note",
        content="Send the recovery note.",
        lineage=CandidateLineage(version_family_id=uuid4(), source_evidence_ids=(uuid4(),)),
        scores=CandidateScores(
            impact=8,
            confidence=7,
            ease=6,
            quality_score=80.0,
            urgency_score=78.0,
            freshness_score=76.0,
            feedback_score=10.0,
        ),
        created_at=now,
        updated_at=now,
        evaluated_at=now,
        evaluation_reason="Ready for operator review.",
    )
