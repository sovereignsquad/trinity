"""Feedback-application helpers for product-originated Trinity events."""

from __future__ import annotations

from dataclasses import replace

from trinity_core.schemas import (
    CandidateRecord,
    CandidateState,
    CandidateType,
    ReplyFeedbackDisposition,
    ReplyFeedbackEvent,
)


def apply_reply_feedback(candidate: CandidateRecord, event: ReplyFeedbackEvent) -> CandidateRecord:
    """Apply downstream product feedback to a candidate record deterministically."""

    if candidate.company_id != event.company_id:
        raise ValueError("Feedback company_id must match candidate company_id.")
    if candidate.candidate_id != event.candidate_id:
        raise ValueError("Feedback candidate_id must match candidate_id.")

    feedback_score = _clamp_percent(
        candidate.scores.feedback_score + _feedback_delta(event.disposition)
    )
    updated_scores = replace(candidate.scores, feedback_score=feedback_score)

    next_candidate = replace(
        candidate,
        scores=updated_scores,
        updated_at=event.occurred_at,
        last_feedback_at=event.occurred_at,
    )

    if event.disposition is ReplyFeedbackDisposition.EDITED:
        return replace(next_candidate, content=event.edited_text or candidate.content)

    if event.disposition is ReplyFeedbackDisposition.SENT:
        if candidate.candidate_type is not CandidateType.ACTION:
            raise ValueError("Only action candidates can be marked SENT.")
        return replace(
            next_candidate,
            state=CandidateState.DELIVERED,
            last_delivered_at=event.occurred_at,
            delivery_target_ref=event.conversation_ref,
        )

    return next_candidate


def _feedback_delta(disposition: ReplyFeedbackDisposition) -> float:
    return {
        ReplyFeedbackDisposition.ACCEPTED: 8.0,
        ReplyFeedbackDisposition.EDITED: 5.0,
        ReplyFeedbackDisposition.REJECTED: -12.0,
        ReplyFeedbackDisposition.SENT: 12.0,
    }[disposition]


def _clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, float(value)))
