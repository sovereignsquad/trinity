"""Frontier selection helpers for the Trinity eligible candidate pool."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from trinity_core.schemas import CandidateRecord, CandidateState


@dataclass(frozen=True, slots=True)
class FrontierEntry:
    """Stable user-facing frontier record."""

    candidate: CandidateRecord
    frontier_score: float
    rank: int


def build_frontier(
    candidates: Iterable[CandidateRecord],
    *,
    limit: int = 3,
) -> tuple[FrontierEntry, ...]:
    """Return the top-ranked eligible candidates for operator attention."""

    if limit < 1:
        raise ValueError("limit must be positive.")

    deduped = _dedupe_candidates(candidates)
    eligible = [candidate for candidate in deduped if _is_frontier_eligible(candidate)]
    ranked = sorted(
        eligible,
        key=lambda candidate: (-frontier_score(candidate), str(candidate.candidate_id)),
    )[:limit]

    return tuple(
        FrontierEntry(candidate=candidate, frontier_score=frontier_score(candidate), rank=index)
        for index, candidate in enumerate(ranked, start=1)
    )


def frontier_score(candidate: CandidateRecord) -> float:
    """Canonical frontier score built from evaluator outputs plus normalized ICE."""

    scores = candidate.scores
    quality = _percent(scores.quality_score)
    urgency = _percent(scores.urgency_score)
    freshness = _percent(scores.freshness_score)
    feedback = _percent(scores.feedback_score)
    ice = (scores.ice_score / 1000.0) * 100.0

    return round(
        (quality * 0.35)
        + (urgency * 0.25)
        + (freshness * 0.20)
        + (feedback * 0.10)
        + (ice * 0.10),
        6,
    )


def _is_frontier_eligible(candidate: CandidateRecord) -> bool:
    return candidate.state is CandidateState.EVALUATED


def _dedupe_candidates(candidates: Iterable[CandidateRecord]) -> tuple[CandidateRecord, ...]:
    best_by_cluster: dict[UUID | str, CandidateRecord] = {}

    for candidate in candidates:
        cluster_key: UUID | str = (
            candidate.duplicate_cluster_id or candidate.lineage.version_family_id
        )
        existing = best_by_cluster.get(cluster_key)
        if existing is None or frontier_score(candidate) > frontier_score(existing):
            best_by_cluster[cluster_key] = candidate

    return tuple(best_by_cluster.values())


def _percent(value: float | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(100.0, float(value)))
