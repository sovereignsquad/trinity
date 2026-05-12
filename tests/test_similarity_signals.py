from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from trinity_core.memory import apply_memory_similarity_signals, build_memory_similarity_profile
from trinity_core.schemas import (
    CandidateLineage,
    CandidateRecord,
    CandidateScores,
    CandidateState,
    CandidateType,
    MemoryRecordFamily,
    MemoryScope,
    MemoryScopeKind,
    MemoryTier,
    RetrievedMemoryContext,
    RetrievedMemoryRecord,
)


def test_build_memory_similarity_profile_derives_family_signals() -> None:
    candidate = _candidate(
        title="Send updated numbers today",
        content="Send the updated numbers today in a concise direct reply.",
    )
    context = RetrievedMemoryContext(
        scopes=(MemoryScope(MemoryScopeKind.COMPANY, f"company:{candidate.company_id}"),),
        records=(
            _record(
                family=MemoryRecordFamily.SUCCESSFUL_PATTERN,
                record_key="summary:success",
                content="A concise direct reply that sends the updated numbers today worked well.",
            ),
            _record(
                family=MemoryRecordFamily.ANTI_PATTERN,
                record_key="summary:anti",
                content="Avoid vague requests for confirmation when the numbers can be sent now.",
            ),
            _record(
                family=MemoryRecordFamily.CORRECTION,
                record_key="summary:correction",
                content=(
                    "Human corrected a reply by shortening the update and removing extra "
                    "context."
                ),
            ),
            _record(
                family=MemoryRecordFamily.DISAGREEMENT,
                record_key="summary:disagreement",
                content="A safer route was previously debated for direct number updates.",
            ),
        ),
        selected_keys=("summary:success", "summary:anti"),
        retrieval_context_hash="ctx-1",
        tier_counts={"working": 4},
    )

    profile = build_memory_similarity_profile(candidate, context)

    assert profile is not None
    assert profile.impact is not None
    assert any(factor.name == "success_similarity" for factor in profile.impact.factors)
    assert profile.impact.rationale
    assert profile.confidence is not None
    assert any(factor.name == "trust_similarity" for factor in profile.confidence.factors)
    assert any(factor.name == "failure_similarity" for factor in profile.confidence.factors)
    assert any(factor.name == "disagreement_similarity" for factor in profile.confidence.factors)
    assert any(factor.name == "novelty_penalty" for factor in profile.confidence.factors)
    assert profile.confidence.rationale
    assert profile.delivery_difficulty is not None
    assert any(
        factor.name == "correction_similarity"
        for factor in profile.delivery_difficulty.factors
    )
    assert profile.delivery_difficulty.rationale


def test_apply_memory_similarity_signals_merges_with_existing_profile() -> None:
    candidate = _candidate(
        title="Send direct update",
        content="Send the direct update today.",
        scores=CandidateScores(
            impact=8,
            confidence=7,
            ease=6,
            score_profile={
                "impact": {
                    "factors": [
                        {"name": "strategic_alignment", "value": 0.9, "provenance": "generator"}
                    ],
                    "provenance": "generator",
                },
                "provenance": "generator",
            },
        ),
    )
    context = RetrievedMemoryContext(
        scopes=(MemoryScope(MemoryScopeKind.COMPANY, f"company:{candidate.company_id}"),),
        records=(
            _record(
                family=MemoryRecordFamily.SUCCESSFUL_PATTERN,
                record_key="summary:success",
                content="Sending a direct update today worked well.",
            ),
        ),
        selected_keys=("summary:success",),
        retrieval_context_hash="ctx-2",
        tier_counts={"working": 1},
    )

    updated = apply_memory_similarity_signals(candidate, context)

    assert updated.scores.score_profile is not None
    assert updated.scores.score_profile.impact is not None
    assert [factor.name for factor in updated.scores.score_profile.impact.factors] == [
        "strategic_alignment",
        "success_similarity",
    ]


def _candidate(
    *,
    title: str,
    content: str,
    scores: CandidateScores | None = None,
) -> CandidateRecord:
    now = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
    return CandidateRecord(
        company_id=uuid4(),
        candidate_id=uuid4(),
        candidate_type=CandidateType.ACTION,
        state=CandidateState.EVALUATED,
        title=title,
        content=content,
        lineage=CandidateLineage(version_family_id=uuid4(), source_evidence_ids=(uuid4(),)),
        scores=scores or CandidateScores(impact=8, confidence=7, ease=6),
        created_at=now,
        updated_at=now,
        evaluated_at=now,
        semantic_tags=("direct", "update"),
        evaluation_reason="Ready for ranking.",
    )


def _record(
    *,
    family: MemoryRecordFamily,
    record_key: str,
    content: str,
) -> RetrievedMemoryRecord:
    return RetrievedMemoryRecord(
        record_key=record_key,
        family=family,
        scope=MemoryScope(MemoryScopeKind.COMPANY, "company:test"),
        content=content,
        updated_at=datetime(2026, 5, 12, 11, 0, tzinfo=UTC),
        tier=MemoryTier.WORKING,
        relevance_score=200.0,
        selection_reason="family-match",
        metadata={"family": family.value},
    )
