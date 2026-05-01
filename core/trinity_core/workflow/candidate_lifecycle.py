"""Candidate lifecycle helpers and explicit state transition rules."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from trinity_core.schemas import (
    CandidateLineage,
    CandidateRecord,
    CandidateScores,
    CandidateState,
    CandidateType,
    ReworkRoute,
)

_ALLOWED_TRANSITIONS: dict[CandidateState, frozenset[CandidateState]] = {
    CandidateState.GENERATED: frozenset(
        {CandidateState.REFINED, CandidateState.SUPPRESSED, CandidateState.ARCHIVED}
    ),
    CandidateState.REFINED: frozenset(
        {
            CandidateState.EVALUATED,
            CandidateState.REWORK,
            CandidateState.SUPPRESSED,
            CandidateState.ARCHIVED,
        }
    ),
    CandidateState.EVALUATED: frozenset(
        {
            CandidateState.REWORK,
            CandidateState.SUPPRESSED,
            CandidateState.ARCHIVED,
            CandidateState.DELIVERED,
        }
    ),
    CandidateState.REWORK: frozenset(
        {CandidateState.REFINED, CandidateState.SUPPRESSED, CandidateState.ARCHIVED}
    ),
    CandidateState.SUPPRESSED: frozenset({CandidateState.REWORK, CandidateState.ARCHIVED}),
    CandidateState.ARCHIVED: frozenset(),
    CandidateState.DELIVERED: frozenset({CandidateState.REWORK, CandidateState.ARCHIVED}),
}


def _require_timezone(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("Lifecycle timestamps must be timezone-aware.")
    return now


def create_candidate(
    *,
    company_id: UUID,
    candidate_type: CandidateType,
    title: str,
    content: str,
    source_evidence_ids: tuple[UUID, ...] = (),
    source_candidate_ids: tuple[UUID, ...] = (),
    scores: CandidateScores,
    semantic_tags: tuple[str, ...] = (),
    now: datetime | None = None,
) -> CandidateRecord:
    """Create a new generated candidate with a fresh version family."""

    created_at = _require_timezone(now or datetime.now(UTC))
    return CandidateRecord(
        company_id=company_id,
        candidate_id=uuid4(),
        candidate_type=candidate_type,
        state=CandidateState.GENERATED,
        title=title,
        content=content,
        lineage=CandidateLineage(
            version_family_id=uuid4(),
            source_evidence_ids=source_evidence_ids,
            source_candidate_ids=source_candidate_ids,
        ),
        scores=scores,
        semantic_tags=semantic_tags,
        created_at=created_at,
        updated_at=created_at,
    )


def advance_candidate(
    candidate: CandidateRecord,
    *,
    target_state: CandidateState,
    now: datetime | None = None,
    rework_route: ReworkRoute | None = None,
    evaluation_reason: str | None = None,
    delivery_target_ref: str | None = None,
) -> CandidateRecord:
    """Transition one candidate through the explicit lifecycle state machine."""

    transition_time = _require_timezone(now or datetime.now(UTC))
    allowed = _ALLOWED_TRANSITIONS[candidate.state]
    if target_state not in allowed:
        raise ValueError(
            f"Illegal candidate transition: {candidate.state} -> {target_state}."
        )
    if (
        target_state == CandidateState.DELIVERED
        and candidate.candidate_type != CandidateType.ACTION
    ):
        raise ValueError("Only action candidates can transition to DELIVERED.")
    if target_state == CandidateState.REWORK and rework_route is None:
        raise ValueError("Rework transitions require an explicit rework route.")
    if target_state != CandidateState.REWORK and rework_route is not None:
        raise ValueError("Rework route can only be used for REWORK transitions.")
    if target_state == CandidateState.DELIVERED and not delivery_target_ref:
        raise ValueError("Delivered action candidates require a delivery target reference.")

    return replace(
        candidate,
        state=target_state,
        updated_at=transition_time,
        evaluated_at=(
            transition_time
            if target_state
            in {
                CandidateState.EVALUATED,
                CandidateState.REWORK,
                CandidateState.SUPPRESSED,
                CandidateState.ARCHIVED,
            }
            else candidate.evaluated_at
        ),
        last_reworked_at=(
            transition_time if target_state == CandidateState.REWORK else candidate.last_reworked_at
        ),
        last_delivered_at=(
            transition_time
            if target_state == CandidateState.DELIVERED
            else candidate.last_delivered_at
        ),
        rework_route=rework_route,
        evaluation_reason=evaluation_reason,
        delivery_target_ref=(
            delivery_target_ref
            if target_state == CandidateState.DELIVERED
            else candidate.delivery_target_ref
        ),
    )


def fork_candidate_version(
    candidate: CandidateRecord,
    *,
    target_state: CandidateState,
    now: datetime | None = None,
    title: str | None = None,
    content: str | None = None,
    scores: CandidateScores | None = None,
    semantic_tags: tuple[str, ...] | None = None,
    rework_route: ReworkRoute | None = None,
    source_candidate_ids: tuple[UUID, ...] = (),
) -> CandidateRecord:
    """Create a new version in the same family for refinement or rework flows."""

    version_time = _require_timezone(now or datetime.now(UTC))
    if target_state not in {CandidateState.REFINED, CandidateState.REWORK}:
        raise ValueError("Version forking is only supported for REFINED or REWORK states.")
    if target_state == CandidateState.REFINED and candidate.state not in {
        CandidateState.GENERATED,
        CandidateState.REWORK,
    }:
        raise ValueError("Only generated or rework candidates can fork into REFINED.")
    if target_state == CandidateState.REWORK and candidate.state not in {
        CandidateState.REFINED,
        CandidateState.SUPPRESSED,
        CandidateState.DELIVERED,
    }:
        raise ValueError("Only refined, suppressed, or delivered candidates can fork into REWORK.")
    if target_state == CandidateState.REWORK and rework_route is None:
        raise ValueError("Rework versions require an explicit rework route.")

    lineage_sources = tuple(dict.fromkeys((candidate.candidate_id, *source_candidate_ids)))

    return CandidateRecord(
        company_id=candidate.company_id,
        candidate_id=uuid4(),
        candidate_type=candidate.candidate_type,
        state=target_state,
        title=title or candidate.title,
        content=content or candidate.content,
        lineage=CandidateLineage(
            version_family_id=candidate.lineage.version_family_id,
            parent_candidate_id=candidate.candidate_id,
            source_evidence_ids=candidate.lineage.source_evidence_ids,
            source_candidate_ids=lineage_sources,
        ),
        scores=scores or candidate.scores,
        semantic_tags=semantic_tags if semantic_tags is not None else candidate.semantic_tags,
        duplicate_cluster_id=candidate.duplicate_cluster_id,
        created_at=candidate.created_at,
        updated_at=version_time,
        last_presented_at=candidate.last_presented_at,
        last_feedback_at=candidate.last_feedback_at,
        last_reworked_at=(
            version_time if target_state == CandidateState.REWORK else candidate.last_reworked_at
        ),
        last_delivered_at=candidate.last_delivered_at,
        evaluated_at=candidate.evaluated_at,
        rework_route=rework_route,
        evaluation_reason=candidate.evaluation_reason,
        delivery_target_ref=candidate.delivery_target_ref,
    )
