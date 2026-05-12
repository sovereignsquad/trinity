"""Deterministic candidate score calibration and audit helpers."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from trinity_core.schemas import CandidateRecord, HeadlineScoreSnapshot, ScoreFactor


def calibrate_candidate_scores(
    candidates: tuple[CandidateRecord, ...],
) -> tuple[CandidateRecord, ...]:
    """Apply bounded calibration and audit rules before frontier ranking."""

    tuple_counts = Counter(
        (candidate.scores.impact, candidate.scores.confidence, candidate.scores.ease)
        for candidate in candidates
    )
    return tuple(
        _calibrate_candidate(candidate, repeated_tuple_count=tuple_counts[_score_tuple(candidate)])
        for candidate in candidates
    )


def _calibrate_candidate(
    candidate: CandidateRecord,
    *,
    repeated_tuple_count: int,
) -> CandidateRecord:
    scores = candidate.scores
    proposed = scores.proposed_scores or HeadlineScoreSnapshot(
        impact=scores.impact,
        confidence=scores.confidence,
        ease=scores.ease,
    )
    impact = scores.impact
    confidence = scores.confidence
    ease = scores.ease
    flags: list[str] = list(scores.audit_flags)
    notes: list[str] = list(scores.calibration_notes)

    impact_factors = _dimension_factors(scores, "impact")
    confidence_factors = _dimension_factors(scores, "confidence")
    delivery_factors = _dimension_factors(scores, "delivery_difficulty")

    if repeated_tuple_count > 1 and not impact_factors and not confidence_factors:
        confidence = max(1, confidence - 1)
        flags.append("unsupported_repeated_tuple")
        notes.append("Repeated score tuple lacked supporting impact/confidence factors.")

    novelty = _factor_value(confidence_factors, "novelty_penalty")
    trust = _factor_value(confidence_factors, "trust_similarity")
    failure = max(
        _factor_value(confidence_factors, "failure_similarity"),
        _factor_value(delivery_factors, "failure_similarity"),
    )
    correction = _factor_value(delivery_factors, "correction_similarity")
    disagreement = _factor_value(confidence_factors, "disagreement_similarity")

    if novelty >= 0.65 and trust < 0.35:
        impact = max(1, impact - 1)
        confidence = max(1, confidence - 1)
        flags.append("high_novelty_low_history")
        notes.append("High novelty with weak prior support reduced impact and confidence.")

    if failure >= 0.45 and trust < 0.45:
        confidence = max(1, confidence - 1)
        flags.append("failure_history_penalty")
        notes.append("Failure-heavy history reduced confidence.")

    if correction >= 0.45 or failure >= 0.45:
        ease = max(1, ease - 1)
        flags.append("delivery_risk_penalty")
        notes.append("Correction/failure history increased delivery difficulty.")

    if disagreement >= 0.45:
        confidence = max(1, confidence - 1)
        flags.append("historical_disagreement_penalty")
        notes.append("Past disagreement on similar work reduced confidence.")

    if impact >= 8 and not impact_factors:
        impact = max(1, impact - 1)
        flags.append("unsupported_high_impact")
        notes.append("High impact claim lacked explicit impact-support factors.")

    if ease >= 8 and not delivery_factors:
        ease = max(1, ease - 1)
        flags.append("unsupported_easy_delivery")
        notes.append("High ease claim lacked explicit delivery-difficulty support.")

    if (
        impact == scores.impact
        and confidence == scores.confidence
        and ease == scores.ease
        and proposed == scores.proposed_scores
        and tuple(flags) == scores.audit_flags
        and tuple(notes) == scores.calibration_notes
    ):
        return candidate

    calibrated_scores = replace(
        scores,
        impact=impact,
        confidence=confidence,
        ease=ease,
        proposed_scores=proposed,
        audit_flags=tuple(dict.fromkeys(flags)),
        calibration_notes=tuple(dict.fromkeys(notes)),
    )
    return replace(candidate, scores=calibrated_scores)


def _score_tuple(candidate: CandidateRecord) -> tuple[int, int, int]:
    return candidate.scores.impact, candidate.scores.confidence, candidate.scores.ease


def _dimension_factors(candidate_scores, dimension: str) -> tuple[ScoreFactor, ...]:
    profile = candidate_scores.score_profile
    if profile is None:
        return ()
    dimension_profile = getattr(profile, dimension, None)
    if dimension_profile is None:
        return ()
    return tuple(dimension_profile.factors)


def _factor_value(factors: tuple[ScoreFactor, ...], name: str) -> float:
    for factor in factors:
        if factor.name == name:
            return float(factor.value)
    return 0.0
