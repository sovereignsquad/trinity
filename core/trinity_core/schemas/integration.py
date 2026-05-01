"""Product-facing integration contracts owned by the Trinity runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from .candidate import CandidateRecord, CandidateScores, CandidateType
from .evidence import EvidenceUnit

REPLY_CONTRACT_VERSION = "trinity.reply.v1alpha1"


def _require_timezone(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


def _require_text(value: str, *, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required.")


class ReplyFeedbackDisposition(StrEnum):
    """Canonical feedback outcomes accepted from downstream products."""

    ACCEPTED = "ACCEPTED"
    EDITED = "EDITED"
    REJECTED = "REJECTED"
    SENT = "SENT"


class ThreadMessageRole(StrEnum):
    """Stable roles inside a reply thread snapshot."""

    CONTACT = "CONTACT"
    OPERATOR = "OPERATOR"


class DraftOutcomeDisposition(StrEnum):
    """Canonical operator outcomes for Trinity-ranked drafts."""

    SHOWN = "SHOWN"
    SELECTED = "SELECTED"
    SENT_AS_IS = "SENT_AS_IS"
    EDITED_THEN_SENT = "EDITED_THEN_SENT"
    REJECTED = "REJECTED"
    IGNORED = "IGNORED"
    MANUAL_REPLACEMENT = "MANUAL_REPLACEMENT"
    REWORK_REQUESTED = "REWORK_REQUESTED"


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
        _require_timezone(self.occurred_at, field_name="occurred_at")
        _require_text(self.conversation_ref, field_name="conversation_ref")
        _require_text(self.channel, field_name="channel")
        _require_text(self.sender_handle, field_name="sender_handle")
        _require_text(self.message_text, field_name="message_text")


@dataclass(frozen=True, slots=True)
class ThreadMessageSnapshot:
    """One normalized message in a product thread snapshot."""

    message_id: str
    role: ThreadMessageRole
    text: str
    occurred_at: datetime
    channel: str
    source: str
    handle: str

    def __post_init__(self) -> None:
        _require_text(self.message_id, field_name="message_id")
        _require_text(self.text, field_name="text")
        _require_timezone(self.occurred_at, field_name="occurred_at")
        _require_text(self.channel, field_name="channel")
        _require_text(self.source, field_name="source")
        _require_text(self.handle, field_name="handle")


@dataclass(frozen=True, slots=True)
class ThreadContextSnippet:
    """One retrieved context snippet supplied by Reply."""

    source: str
    path: str
    text: str

    def __post_init__(self) -> None:
        _require_text(self.source, field_name="source")
        _require_text(self.path, field_name="path")
        _require_text(self.text, field_name="text")


@dataclass(frozen=True, slots=True)
class GoldenExample:
    """One product-provided example draft used for downstream style hints."""

    path: str
    text: str

    def __post_init__(self) -> None:
        _require_text(self.path, field_name="path")
        _require_text(self.text, field_name="text")


@dataclass(frozen=True, slots=True)
class ThreadSnapshot:
    """Canonical product snapshot used to request ranked drafts from Trinity."""

    company_id: UUID
    thread_ref: str
    channel: str
    contact_handle: str
    latest_inbound_text: str
    requested_at: datetime
    messages: tuple[ThreadMessageSnapshot, ...] = ()
    context_snippets: tuple[ThreadContextSnippet, ...] = ()
    golden_examples: tuple[GoldenExample, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    contract_version: str = REPLY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.thread_ref, field_name="thread_ref")
        _require_text(self.channel, field_name="channel")
        _require_text(self.contact_handle, field_name="contact_handle")
        _require_text(self.latest_inbound_text, field_name="latest_inbound_text")
        _require_timezone(self.requested_at, field_name="requested_at")


@dataclass(frozen=True, slots=True)
class AcceptedArtifactVersion:
    """Declared Trinity artifact version that produced one runtime result."""

    artifact_key: str
    version: str
    source_project: str
    accepted_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.artifact_key, field_name="artifact_key")
        _require_text(self.version, field_name="version")
        _require_text(self.source_project, field_name="source_project")
        _require_timezone(self.accepted_at, field_name="accepted_at")


@dataclass(frozen=True, slots=True)
class CandidateDraft:
    """Ranked product-facing draft candidate emitted by Trinity."""

    company_id: UUID
    candidate_id: UUID
    thread_ref: str
    recipient_handle: str
    channel: str
    rank: int
    draft_text: str
    rationale: str
    risk_flags: tuple[str, ...]
    delivery_eligible: bool
    scores: CandidateScores
    source_evidence_ids: tuple[UUID, ...]
    candidate_type: CandidateType = CandidateType.ACTION
    contract_version: str = REPLY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.thread_ref, field_name="thread_ref")
        _require_text(self.recipient_handle, field_name="recipient_handle")
        _require_text(self.channel, field_name="channel")
        _require_text(self.draft_text, field_name="draft_text")
        _require_text(self.rationale, field_name="rationale")
        if self.rank < 1:
            raise ValueError("rank must be greater than or equal to 1.")
        if not self.source_evidence_ids:
            raise ValueError("source_evidence_ids is required.")

    @classmethod
    def from_candidate_record(
        cls,
        candidate: CandidateRecord,
        *,
        thread_ref: str,
        recipient_handle: str,
        channel: str,
        rank: int = 1,
        risk_flags: tuple[str, ...] = (),
        delivery_eligible: bool = True,
    ) -> CandidateDraft:
        return cls(
            company_id=candidate.company_id,
            candidate_id=candidate.candidate_id,
            thread_ref=thread_ref,
            recipient_handle=recipient_handle,
            channel=channel,
            rank=rank,
            draft_text=candidate.content,
            rationale=candidate.evaluation_reason or candidate.title,
            risk_flags=risk_flags,
            delivery_eligible=delivery_eligible,
            scores=candidate.scores,
            source_evidence_ids=candidate.lineage.source_evidence_ids,
            candidate_type=candidate.candidate_type,
        )


@dataclass(frozen=True, slots=True)
class RankedDraftSet:
    """Top-ranked drafts returned to Reply for one Trinity cycle."""

    cycle_id: UUID
    thread_ref: str
    channel: str
    generated_at: datetime
    drafts: tuple[CandidateDraft, ...]
    accepted_artifact_version: AcceptedArtifactVersion
    trace_ref: str | None = None
    contract_version: str = REPLY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.thread_ref, field_name="thread_ref")
        _require_text(self.channel, field_name="channel")
        _require_timezone(self.generated_at, field_name="generated_at")
        if not self.drafts:
            raise ValueError("drafts is required.")


@dataclass(frozen=True, slots=True)
class ReplyDraftCandidate:
    """Backward-compatible alias for one normalized reply candidate."""

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
        _require_text(self.conversation_ref, field_name="conversation_ref")
        _require_text(self.recipient_handle, field_name="recipient_handle")
        _require_text(self.channel, field_name="channel")
        _require_text(self.draft_text, field_name="draft_text")
        _require_text(self.rationale, field_name="rationale")
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
class DraftOutcomeEvent:
    """Deterministic operator outcome emitted from Reply back into Trinity."""

    company_id: UUID
    cycle_id: UUID
    thread_ref: str
    channel: str
    disposition: DraftOutcomeDisposition
    occurred_at: datetime
    candidate_id: UUID | None = None
    original_draft_text: str | None = None
    final_text: str | None = None
    edit_distance: float | None = None
    latency_ms: int | None = None
    send_result: str | None = None
    notes: str | None = None
    contract_version: str = REPLY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_text(self.thread_ref, field_name="thread_ref")
        _require_text(self.channel, field_name="channel")
        _require_timezone(self.occurred_at, field_name="occurred_at")
        if self.edit_distance is not None and not 0.0 <= self.edit_distance <= 1.0:
            raise ValueError("edit_distance must be between 0.0 and 1.0.")
        if self.latency_ms is not None and self.latency_ms < 0:
            raise ValueError("latency_ms cannot be negative.")
        if self.disposition is DraftOutcomeDisposition.EDITED_THEN_SENT and not (
            self.final_text and self.final_text.strip()
        ):
            raise ValueError("final_text is required for EDITED_THEN_SENT outcomes.")


@dataclass(frozen=True, slots=True)
class ReplyFeedbackEvent:
    """Backward-compatible feedback contract for Trinity candidate memory."""

    company_id: UUID
    candidate_id: UUID
    conversation_ref: str
    disposition: ReplyFeedbackDisposition
    occurred_at: datetime
    notes: str | None = None
    edited_text: str | None = None
    contract_version: str = REPLY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_timezone(self.occurred_at, field_name="occurred_at")
        _require_text(self.conversation_ref, field_name="conversation_ref")
        if self.disposition is ReplyFeedbackDisposition.EDITED and not (
            self.edited_text and self.edited_text.strip()
        ):
            raise ValueError("edited_text is required for EDITED feedback.")


@dataclass(frozen=True, slots=True)
class RuntimeTraceExport:
    """Replayable Trinity export for Train trace ingestion."""

    cycle_id: UUID
    exported_at: datetime
    snapshot_hash: str
    thread_snapshot: ThreadSnapshot
    evidence_units: tuple[EvidenceUnit, ...]
    candidates: tuple[CandidateRecord, ...]
    frontier_candidate_ids: tuple[UUID, ...]
    ranked_draft_set: RankedDraftSet
    accepted_artifact_version: AcceptedArtifactVersion
    feedback_events: tuple[DraftOutcomeEvent, ...] = ()
    model_routes: Mapping[str, str] = field(default_factory=dict)
    contract_version: str = REPLY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_timezone(self.exported_at, field_name="exported_at")
        _require_text(self.snapshot_hash, field_name="snapshot_hash")
        if not self.frontier_candidate_ids:
            raise ValueError("frontier_candidate_ids is required.")
