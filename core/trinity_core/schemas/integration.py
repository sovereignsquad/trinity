"""Product-facing integration contracts owned by the Trinity runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .candidate import CandidateRecord, CandidateScores, CandidateType

REPLY_CONTRACT_VERSION = "trinity.reply.v1alpha1"


class ReplyFeedbackDisposition(StrEnum):
    """Canonical feedback outcomes accepted from downstream products."""

    ACCEPTED = "ACCEPTED"
    EDITED = "EDITED"
    REJECTED = "REJECTED"
    SENT = "SENT"


@dataclass(frozen=True, slots=True)
class ReplyEvidenceEnvelope:
    """Minimal evidence payload a downstream reply product can hand to Trinity."""

    company_id: UUID
    conversation_ref: str
    channel: str
    sender_handle: str
    message_text: str
    occurred_at: datetime
    external_message_id: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)
    contract_version: str = REPLY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise ValueError("Reply evidence timestamps must be timezone-aware.")
        if not self.conversation_ref.strip():
            raise ValueError("conversation_ref is required.")
        if not self.channel.strip():
            raise ValueError("channel is required.")
        if not self.sender_handle.strip():
            raise ValueError("sender_handle is required.")
        if not self.message_text.strip():
            raise ValueError("message_text is required.")


@dataclass(frozen=True, slots=True)
class ReplyDraftCandidate:
    """Normalized reply candidate returned from Trinity to a product shell."""

    company_id: UUID
    candidate_id: UUID
    conversation_ref: str
    recipient_handle: str
    channel: str
    draft_text: str
    rationale: str
    scores: CandidateScores
    source_evidence_ids: tuple[UUID, ...]
    candidate_type: CandidateType = CandidateType.ACTION
    contract_version: str = REPLY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.conversation_ref.strip():
            raise ValueError("conversation_ref is required.")
        if not self.recipient_handle.strip():
            raise ValueError("recipient_handle is required.")
        if not self.channel.strip():
            raise ValueError("channel is required.")
        if not self.draft_text.strip():
            raise ValueError("draft_text is required.")
        if not self.rationale.strip():
            raise ValueError("rationale is required.")
        if not self.source_evidence_ids:
            raise ValueError("source_evidence_ids is required.")

    @classmethod
    def from_candidate_record(
        cls,
        candidate: CandidateRecord,
        *,
        conversation_ref: str,
        recipient_handle: str,
        channel: str,
    ) -> ReplyDraftCandidate:
        return cls(
            company_id=candidate.company_id,
            candidate_id=candidate.candidate_id,
            conversation_ref=conversation_ref,
            recipient_handle=recipient_handle,
            channel=channel,
            draft_text=candidate.content,
            rationale=candidate.evaluation_reason or candidate.title,
            scores=candidate.scores,
            source_evidence_ids=candidate.lineage.source_evidence_ids,
            candidate_type=candidate.candidate_type,
        )


@dataclass(frozen=True, slots=True)
class ReplyFeedbackEvent:
    """Feedback emitted from a product shell back into Trinity memory."""

    company_id: UUID
    candidate_id: UUID
    conversation_ref: str
    disposition: ReplyFeedbackDisposition
    occurred_at: datetime
    notes: str | None = None
    edited_text: str | None = None
    contract_version: str = REPLY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise ValueError("Reply feedback timestamps must be timezone-aware.")
        if not self.conversation_ref.strip():
            raise ValueError("conversation_ref is required.")
        if self.disposition is ReplyFeedbackDisposition.EDITED and not (
            self.edited_text and self.edited_text.strip()
        ):
            raise ValueError("edited_text is required for EDITED feedback.")
