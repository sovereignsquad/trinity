from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from trinity_core.schemas import (
    CandidateLineage,
    CandidateRecord,
    CandidateScores,
    CandidateState,
    CandidateType,
    ReworkRoute,
)
from trinity_core.workflow import build_frontier, frontier_score


def test_build_frontier_orders_eligible_candidates_by_frontier_score() -> None:
    first = _make_candidate(
        title="Recover expansion account",
        quality_score=91.0,
        urgency_score=84.0,
        freshness_score=82.0,
        feedback_score=61.0,
    )
    second = _make_candidate(
        title="Draft routine follow-up",
        quality_score=78.0,
        urgency_score=63.0,
        freshness_score=77.0,
        feedback_score=44.0,
    )
    third = _make_candidate(
        title="Capture note",
        quality_score=55.0,
        urgency_score=34.0,
        freshness_score=51.0,
        feedback_score=18.0,
    )

    frontier = build_frontier((third, second, first))

    assert [entry.candidate.title for entry in frontier] == [
        "Recover expansion account",
        "Draft routine follow-up",
        "Capture note",
    ]
    assert frontier[0].rank == 1
    assert frontier[0].frontier_score > frontier[1].frontier_score > frontier[2].frontier_score


def test_build_frontier_filters_non_evaluated_candidates_and_dedupes_clusters() -> None:
    duplicate_cluster = uuid4()
    best_duplicate = _make_candidate(
        title="Best duplicate",
        duplicate_cluster_id=duplicate_cluster,
        quality_score=87.0,
        urgency_score=77.0,
        freshness_score=70.0,
        feedback_score=55.0,
    )
    weaker_duplicate = _make_candidate(
        title="Weaker duplicate",
        duplicate_cluster_id=duplicate_cluster,
        quality_score=72.0,
        urgency_score=61.0,
        freshness_score=58.0,
        feedback_score=33.0,
    )
    rework = _make_candidate(
        title="Needs rework",
        state=CandidateState.REWORK,
        quality_score=99.0,
        urgency_score=99.0,
        freshness_score=99.0,
        feedback_score=99.0,
        rework_route=ReworkRoute.REVISE,
    )

    frontier = build_frontier((best_duplicate, weaker_duplicate, rework), limit=3)

    assert len(frontier) == 1
    assert frontier[0].candidate.title == "Best duplicate"


def test_frontier_score_uses_zero_for_missing_optional_scores() -> None:
    candidate = _make_candidate(
        title="Sparse evaluator output",
        quality_score=None,
        urgency_score=None,
        freshness_score=None,
        feedback_score=0.0,
    )

    assert frontier_score(candidate) > 0.0


def _make_candidate(
    *,
    title: str,
    state: CandidateState = CandidateState.EVALUATED,
    duplicate_cluster_id=None,
    quality_score: float | None,
    urgency_score: float | None,
    freshness_score: float | None,
    feedback_score: float,
    rework_route=None,
) -> CandidateRecord:
    now = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    return CandidateRecord(
        company_id=uuid4(),
        candidate_id=uuid4(),
        candidate_type=CandidateType.ACTION,
        state=state,
        title=title,
        content=title,
        lineage=CandidateLineage(
            version_family_id=uuid4(),
            source_evidence_ids=(uuid4(),),
        ),
        scores=CandidateScores(
            impact=8,
            confidence=7,
            ease=6,
            quality_score=quality_score,
            urgency_score=urgency_score,
            freshness_score=freshness_score,
            feedback_score=feedback_score,
        ),
        created_at=now,
        updated_at=now,
        evaluated_at=now,
        duplicate_cluster_id=duplicate_cluster_id,
        rework_route=rework_route,
        evaluation_reason="Ready for ranking.",
    )
