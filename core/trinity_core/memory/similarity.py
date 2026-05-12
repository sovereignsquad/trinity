"""Deterministic memory-derived similarity signals for candidate scoring."""

from __future__ import annotations

import re
from dataclasses import replace
from difflib import SequenceMatcher

from trinity_core.schemas import (
    CandidateRecord,
    CandidateScoreProfile,
    MemoryRecordFamily,
    RetrievedMemoryContext,
    RetrievedMemoryRecord,
    ScoreDimensionProfile,
    ScoreFactor,
)

_SIGNAL_FAMILIES: tuple[MemoryRecordFamily, ...] = (
    MemoryRecordFamily.SUCCESSFUL_PATTERN,
    MemoryRecordFamily.CORRECTION,
    MemoryRecordFamily.ANTI_PATTERN,
    MemoryRecordFamily.DISAGREEMENT,
    MemoryRecordFamily.HUMAN_RESOLUTION,
)


def apply_memory_similarity_signals(
    candidate: CandidateRecord,
    memory_context: RetrievedMemoryContext,
) -> CandidateRecord:
    """Attach bounded similarity factors from retrieved memory to candidate scoring."""

    similarity_profile = build_memory_similarity_profile(candidate, memory_context)
    if similarity_profile is None:
        return candidate
    merged_profile = _merge_score_profiles(candidate.scores.score_profile, similarity_profile)
    return replace(
        candidate,
        scores=replace(candidate.scores, score_profile=merged_profile),
    )


def build_memory_similarity_profile(
    candidate: CandidateRecord,
    memory_context: RetrievedMemoryContext,
) -> CandidateScoreProfile | None:
    """Build a score-profile fragment from memory-family similarity signals."""

    candidate_text = _candidate_similarity_text(candidate)
    if not candidate_text:
        return None

    best_matches = {
        family: _best_family_match(candidate_text, memory_context.records, family)
        for family in _SIGNAL_FAMILIES
    }
    known_similarity = max((score for score, _record in best_matches.values()), default=0.0)
    novelty = round(max(0.0, min(1.0, 1.0 - known_similarity)), 4)

    impact_factors: list[ScoreFactor] = []
    confidence_factors: list[ScoreFactor] = []
    delivery_factors: list[ScoreFactor] = []

    success_score, success_record = best_matches[MemoryRecordFamily.SUCCESSFUL_PATTERN]
    if success_record is not None:
        impact_factors.append(
            _factor_from_match(
                name="success_similarity",
                score=success_score,
                record=success_record,
                rationale="Similar work previously matched a successful runtime pattern.",
            )
        )
        confidence_factors.append(
            _factor_from_match(
                name="trust_similarity",
                score=success_score,
                record=success_record,
                rationale="Similar work previously aligned with accepted or successful outcomes.",
            )
        )

    human_score, human_record = best_matches[MemoryRecordFamily.HUMAN_RESOLUTION]
    if human_record is not None:
        confidence_factors.append(
            _factor_from_match(
                name="human_resolution_similarity",
                score=human_score,
                record=human_record,
                rationale="Human-resolved history overlaps with this candidate shape.",
            )
        )

    anti_score, anti_record = best_matches[MemoryRecordFamily.ANTI_PATTERN]
    if anti_record is not None:
        confidence_factors.append(
            _factor_from_match(
                name="failure_similarity",
                score=anti_score,
                record=anti_record,
                rationale="Similar work previously mapped to an anti-pattern outcome.",
            )
        )
        delivery_factors.append(
            _factor_from_match(
                name="failure_similarity",
                score=anti_score,
                record=anti_record,
                rationale=(
                    "Similar work previously failed or was rejected, increasing delivery risk."
                ),
            )
        )

    correction_score, correction_record = best_matches[MemoryRecordFamily.CORRECTION]
    if correction_record is not None:
        delivery_factors.append(
            _factor_from_match(
                name="correction_similarity",
                score=correction_score,
                record=correction_record,
                rationale="Similar work previously required human correction before delivery.",
            )
        )

    disagreement_score, disagreement_record = best_matches[MemoryRecordFamily.DISAGREEMENT]
    if disagreement_record is not None:
        confidence_factors.append(
            _factor_from_match(
                name="disagreement_similarity",
                score=disagreement_score,
                record=disagreement_record,
                rationale="Similar work previously triggered runtime disagreement.",
            )
        )

    if novelty > 0.0:
        confidence_factors.append(
            ScoreFactor(
                name="novelty_penalty",
                value=novelty,
                rationale="This candidate has limited overlap with retrieved company history.",
                provenance="memory_similarity",
            )
        )

    if not impact_factors and not confidence_factors and not delivery_factors:
        return None

    return CandidateScoreProfile(
        impact=(
            ScoreDimensionProfile(
                factors=tuple(impact_factors),
                rationale=(
                    "Historical successful patterns increase confidence that this work matters "
                    "for this company."
                ),
                evidence_anchors=tuple(
                    anchor for factor in impact_factors for anchor in factor.evidence_anchors
                ),
                provenance="memory_similarity",
            )
            if impact_factors
            else None
        ),
        confidence=(
            ScoreDimensionProfile(
                factors=tuple(confidence_factors),
                rationale=(
                    "Retrieved company history, corrections, disagreements, and novelty shape "
                    "how trustworthy this candidate looks."
                ),
                evidence_anchors=tuple(
                    anchor for factor in confidence_factors for anchor in factor.evidence_anchors
                ),
                provenance="memory_similarity",
            )
            if confidence_factors
            else None
        ),
        delivery_difficulty=(
            ScoreDimensionProfile(
                factors=tuple(delivery_factors),
                rationale=(
                    "Past failures and human corrections increase the expected delivery burden "
                    "for similar work."
                ),
                evidence_anchors=tuple(
                    anchor for factor in delivery_factors for anchor in factor.evidence_anchors
                ),
                provenance="memory_similarity",
            )
            if delivery_factors
            else None
        ),
        provenance="memory_similarity",
    )


def _best_family_match(
    candidate_text: str,
    records: tuple[RetrievedMemoryRecord, ...],
    family: MemoryRecordFamily,
) -> tuple[float, RetrievedMemoryRecord | None]:
    best_score = 0.0
    best_record: RetrievedMemoryRecord | None = None
    for record in records:
        if record.family is not family:
            continue
        score = _similarity_score(candidate_text, record.content)
        if score > best_score:
            best_score = score
            best_record = record
    return round(best_score, 4), best_record


def _similarity_score(left: str, right: str) -> float:
    normalized_left = _normalize_text(left)
    normalized_right = _normalize_text(right)
    if not normalized_left or not normalized_right:
        return 0.0
    sequence_ratio = SequenceMatcher(a=normalized_left, b=normalized_right).ratio()
    tokens_left = _tokens(normalized_left)
    tokens_right = _tokens(normalized_right)
    token_overlap = 0.0
    if tokens_left and tokens_right:
        token_overlap = len(tokens_left & tokens_right) / len(tokens_left | tokens_right)
    return round((sequence_ratio * 0.6) + (token_overlap * 0.4), 4)


def _candidate_similarity_text(candidate: CandidateRecord) -> str:
    parts = [candidate.title, candidate.content]
    if candidate.semantic_tags:
        parts.append(" ".join(candidate.semantic_tags))
    return _normalize_text(" ".join(part for part in parts if part))


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").lower().split()).strip()


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value) if len(token) >= 3}


def _factor_from_match(
    *,
    name: str,
    score: float,
    record: RetrievedMemoryRecord,
    rationale: str,
) -> ScoreFactor:
    return ScoreFactor(
        name=name,
        value=score,
        rationale=rationale,
        evidence_anchors=(record.record_key,),
        provenance="memory_similarity",
    )


def _merge_score_profiles(
    base: CandidateScoreProfile | None,
    overlay: CandidateScoreProfile,
) -> CandidateScoreProfile:
    return CandidateScoreProfile(
        impact=_merge_dimensions(base.impact if base is not None else None, overlay.impact),
        confidence=_merge_dimensions(
            base.confidence if base is not None else None,
            overlay.confidence,
        ),
        delivery_difficulty=_merge_dimensions(
            base.delivery_difficulty if base is not None else None,
            overlay.delivery_difficulty,
        ),
        provenance=(
            " | ".join(
                part
                for part in (
                    base.provenance if base is not None else "",
                    overlay.provenance,
                )
                if part
            )
            or overlay.provenance
        ),
    )


def _merge_dimensions(
    base: ScoreDimensionProfile | None,
    overlay: ScoreDimensionProfile | None,
) -> ScoreDimensionProfile | None:
    if base is None:
        return overlay
    if overlay is None:
        return base
    evidence_anchors = tuple(dict.fromkeys((*base.evidence_anchors, *overlay.evidence_anchors)))
    provenance = " | ".join(part for part in (base.provenance, overlay.provenance) if part)
    rationale = " | ".join(part for part in (base.rationale, overlay.rationale) if part)
    return ScoreDimensionProfile(
        factors=(*base.factors, *overlay.factors),
        rationale=rationale,
        evidence_anchors=evidence_anchors,
        provenance=provenance,
    )
