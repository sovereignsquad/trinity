from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from trinity_core.schemas import (
    CandidateLineage,
    CandidateRecord,
    CandidateScores,
    CandidateState,
    CandidateType,
)
from trinity_core.workflow import calibrate_candidate_scores


def test_calibrate_candidate_scores_preserves_proposed_and_applies_penalties() -> None:
    candidate = _candidate(
        title="Novel rollout idea",
        scores=CandidateScores(
            impact=9,
            confidence=8,
            ease=8,
            score_profile={
                "confidence": {
                    "factors": [
                        {"name": "novelty_penalty", "value": 0.8},
                        {"name": "failure_similarity", "value": 0.7},
                    ],
                    "rationale": "This work is novel and overlaps with a known anti-pattern.",
                }
            },
        ),
    )

    calibrated = calibrate_candidate_scores((candidate,))[0]

    assert calibrated.scores.proposed_scores is not None
    assert calibrated.scores.proposed_scores.impact == 9
    assert calibrated.scores.impact < calibrated.scores.proposed_scores.impact
    assert calibrated.scores.confidence < calibrated.scores.proposed_scores.confidence
    assert calibrated.scores.ease < calibrated.scores.proposed_scores.ease
    assert "high_novelty_low_history" in calibrated.scores.audit_flags
    assert "failure_history_penalty" in calibrated.scores.audit_flags
    assert "delivery_risk_penalty" in calibrated.scores.audit_flags
    assert calibrated.scores.calibration_notes


def test_calibrate_candidate_scores_flags_unsupported_repeated_tuple() -> None:
    candidates = (
        _candidate(title="One", scores=CandidateScores(impact=8, confidence=7, ease=6)),
        _candidate(title="Two", scores=CandidateScores(impact=8, confidence=7, ease=6)),
    )

    calibrated = calibrate_candidate_scores(candidates)

    assert "unsupported_repeated_tuple" in calibrated[0].scores.audit_flags
    assert "unsupported_repeated_tuple" in calibrated[1].scores.audit_flags
    assert calibrated[0].scores.proposed_scores is not None
    assert calibrated[0].scores.confidence == 6


def _candidate(*, title: str, scores: CandidateScores) -> CandidateRecord:
    now = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)
    return CandidateRecord(
        company_id=uuid4(),
        candidate_id=uuid4(),
        candidate_type=CandidateType.ACTION,
        state=CandidateState.EVALUATED,
        title=title,
        content=title,
        lineage=CandidateLineage(version_family_id=uuid4(), source_evidence_ids=(uuid4(),)),
        scores=scores,
        created_at=now,
        updated_at=now,
        evaluated_at=now,
        evaluation_reason="Ready for ranking.",
    )
