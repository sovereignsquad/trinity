from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from trinity_core.schemas import CandidateScores, CandidateState, CandidateType, ReworkRoute
from trinity_core.workflow import advance_candidate, create_candidate, fork_candidate_version


def test_generated_candidate_forks_to_refined_with_lineage_preserved() -> None:
    company_id = uuid4()
    evidence_id = uuid4()
    generated = create_candidate(
        company_id=company_id,
        candidate_type=CandidateType.KNOWLEDGE,
        title="Shift outreach toward stalled enterprise accounts",
        content="Enterprise prospects have stalled after pricing review.",
        source_evidence_ids=(evidence_id,),
        scores=CandidateScores(impact=8, confidence=6, ease=5),
        semantic_tags=("sales", "enterprise"),
        now=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
    )

    refined = fork_candidate_version(
        generated,
        target_state=CandidateState.REFINED,
        now=datetime(2026, 5, 1, 12, 10, tzinfo=UTC),
        content="Refocus outreach on enterprise prospects stalled after pricing review.",
    )

    assert refined.state == CandidateState.REFINED
    assert refined.candidate_id != generated.candidate_id
    assert refined.lineage.version_family_id == generated.lineage.version_family_id
    assert refined.lineage.parent_candidate_id == generated.candidate_id
    assert refined.lineage.source_evidence_ids == (evidence_id,)
    assert refined.lineage.source_candidate_ids == (generated.candidate_id,)


def test_refined_candidate_can_transition_to_evaluated() -> None:
    refined = fork_candidate_version(
        create_candidate(
            company_id=uuid4(),
            candidate_type=CandidateType.KNOWLEDGE,
            title="Flag onboarding friction in week one",
            content="Users drop during the first-week setup flow.",
            source_evidence_ids=(uuid4(),),
            scores=CandidateScores(impact=7, confidence=7, ease=6),
            now=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        ),
        target_state=CandidateState.REFINED,
        now=datetime(2026, 5, 1, 12, 5, tzinfo=UTC),
    )

    evaluated = advance_candidate(
        refined,
        target_state=CandidateState.EVALUATED,
        now=datetime(2026, 5, 1, 12, 15, tzinfo=UTC),
        evaluation_reason="High support and clear actionability.",
    )

    assert evaluated.state == CandidateState.EVALUATED
    assert evaluated.evaluated_at == datetime(2026, 5, 1, 12, 15, tzinfo=UTC)
    assert evaluated.evaluation_reason == "High support and clear actionability."


def test_illegal_transition_fails_closed() -> None:
    generated = create_candidate(
        company_id=uuid4(),
        candidate_type=CandidateType.KNOWLEDGE,
        title="Watch churn in Spanish-language accounts",
        content="Recent support sentiment fell sharply in Spanish-language cohorts.",
        source_evidence_ids=(uuid4(),),
        scores=CandidateScores(impact=6, confidence=6, ease=6),
        now=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
    )

    with pytest.raises(
        ValueError,
        match="Illegal candidate transition: GENERATED -> EVALUATED.",
    ):
        advance_candidate(
            generated,
            target_state=CandidateState.EVALUATED,
            now=datetime(2026, 5, 1, 12, 5, tzinfo=UTC),
        )


def test_rework_requires_explicit_route_and_preserves_family() -> None:
    refined = fork_candidate_version(
        create_candidate(
            company_id=uuid4(),
            candidate_type=CandidateType.ACTION,
            title="Offer a pricing follow-up to at-risk accounts",
            content="Send a pricing clarification to accounts stalled for more than 10 days.",
            source_evidence_ids=(uuid4(),),
            scores=CandidateScores(impact=9, confidence=5, ease=7),
            now=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        ),
        target_state=CandidateState.REFINED,
        now=datetime(2026, 5, 1, 12, 5, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="Rework transitions require an explicit rework route."):
        advance_candidate(
            refined,
            target_state=CandidateState.REWORK,
            now=datetime(2026, 5, 1, 12, 6, tzinfo=UTC),
        )

    rework = fork_candidate_version(
        refined,
        target_state=CandidateState.REWORK,
        now=datetime(2026, 5, 1, 12, 7, tzinfo=UTC),
        rework_route=ReworkRoute.REVISE,
    )

    assert rework.state == CandidateState.REWORK
    assert rework.rework_route == ReworkRoute.REVISE
    assert rework.lineage.version_family_id == refined.lineage.version_family_id
    assert rework.lineage.parent_candidate_id == refined.candidate_id


def test_delivery_is_action_only() -> None:
    evaluated_action = advance_candidate(
        fork_candidate_version(
            create_candidate(
                company_id=uuid4(),
                candidate_type=CandidateType.ACTION,
                title="Schedule a recovery call",
                content="Book a recovery call with customers who declined renewal.",
                source_evidence_ids=(uuid4(),),
                scores=CandidateScores(impact=8, confidence=6, ease=8),
                now=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            ),
            target_state=CandidateState.REFINED,
            now=datetime(2026, 5, 1, 12, 5, tzinfo=UTC),
        ),
        target_state=CandidateState.EVALUATED,
        now=datetime(2026, 5, 1, 12, 10, tzinfo=UTC),
    )
    delivered = advance_candidate(
        evaluated_action,
        target_state=CandidateState.DELIVERED,
        now=datetime(2026, 5, 1, 12, 20, tzinfo=UTC),
        delivery_target_ref="reply://draft/42",
    )

    assert delivered.state == CandidateState.DELIVERED
    assert delivered.last_delivered_at == datetime(2026, 5, 1, 12, 20, tzinfo=UTC)
    assert delivered.delivery_target_ref == "reply://draft/42"

    evaluated_knowledge = advance_candidate(
        fork_candidate_version(
            create_candidate(
                company_id=uuid4(),
                candidate_type=CandidateType.KNOWLEDGE,
                title="Explain why renewal risk is concentrated",
                content="Renewal risk clusters around accounts with unresolved billing disputes.",
                source_evidence_ids=(uuid4(),),
                scores=CandidateScores(impact=7, confidence=8, ease=5),
                now=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            ),
            target_state=CandidateState.REFINED,
            now=datetime(2026, 5, 1, 12, 5, tzinfo=UTC),
        ),
        target_state=CandidateState.EVALUATED,
        now=datetime(2026, 5, 1, 12, 10, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="Only action candidates can transition to DELIVERED."):
        advance_candidate(
            evaluated_knowledge,
            target_state=CandidateState.DELIVERED,
            now=datetime(2026, 5, 1, 12, 20, tzinfo=UTC),
            delivery_target_ref="reply://draft/43",
        )
