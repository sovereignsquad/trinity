"""Stage execution contracts for generator, refiner, and evaluator."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from trinity_core.schemas import (
    CandidateRecord,
    CandidateScores,
    CandidateState,
    CandidateType,
    EvidenceUnit,
    ReworkRoute,
)
from trinity_core.workflow.candidate_lifecycle import (
    advance_candidate,
    create_candidate,
    fork_candidate_version,
)


class RefinerDisposition(StrEnum):
    """Normalized refiner output categories."""

    REFINE = "REFINE"
    SUPPRESS = "SUPPRESS"


class EvaluationDisposition(StrEnum):
    """Canonical evaluator dispositions."""

    ELIGIBLE = "ELIGIBLE"
    REVISE = "REVISE"
    REGENERATE = "REGENERATE"
    MERGE = "MERGE"
    SUPPRESS = "SUPPRESS"
    ARCHIVE = "ARCHIVE"


@dataclass(frozen=True, slots=True)
class StageFailure:
    """Explicit stage failure surfaced to callers."""

    stage_name: str
    message: str
    item_key: str | None = None


@dataclass(frozen=True, slots=True)
class StageExecutionResult:
    """Normalized stage outcome containing records and surfaced failures."""

    stage_name: str
    records: tuple[CandidateRecord, ...] = ()
    failures: tuple[StageFailure, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidatePipelineResult:
    """End-to-end pipeline outcome across the three core stages."""

    generated: StageExecutionResult
    refined: StageExecutionResult
    evaluated: StageExecutionResult


@dataclass(frozen=True, slots=True)
class GeneratorExecutionInput:
    """Input contract for generator execution."""

    company_id: UUID
    evidence_units: tuple[EvidenceUnit, ...]
    strategic_context: Mapping[str, str] = field(default_factory=dict)
    memory_constraints: Mapping[str, str] = field(default_factory=dict)
    active_knowledge_inventory: tuple[CandidateRecord, ...] = ()
    active_action_inventory: tuple[CandidateRecord, ...] = ()
    topic_anchors: tuple[str, ...] = ()
    freshness_reference: datetime | None = None


@dataclass(frozen=True, slots=True)
class RawGeneratedCandidate:
    """Raw generator output before runtime normalization."""

    candidate_type: CandidateType
    title: str
    content: str
    source_evidence_ids: tuple[str, ...]
    impact: int
    confidence: int
    ease: int
    semantic_tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RefinerExecutionInput:
    """Input contract for refiner execution."""

    company_id: UUID
    generated_candidates: tuple[CandidateRecord, ...]
    evidence_units: tuple[EvidenceUnit, ...] = ()
    strategic_context: Mapping[str, str] = field(default_factory=dict)
    feedback_memory: Mapping[str, str] = field(default_factory=dict)
    ranking_context: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RawRefinerResult:
    """Raw refiner output before runtime normalization."""

    disposition: RefinerDisposition
    parent_candidate_id: str
    title: str | None = None
    content: str | None = None
    impact: int | None = None
    confidence: int | None = None
    ease: int | None = None
    semantic_tags: tuple[str, ...] | None = None
    source_candidate_ids: tuple[str, ...] = ()
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluatorExecutionInput:
    """Input contract for evaluator execution."""

    company_id: UUID
    refined_candidates: tuple[CandidateRecord, ...]
    evidence_units: tuple[EvidenceUnit, ...] = ()
    evidence_lineage: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    strategic_policy: Mapping[str, str] = field(default_factory=dict)
    feedback_memory: Mapping[str, str] = field(default_factory=dict)
    active_inventory_state: Mapping[str, str] = field(default_factory=dict)
    ranking_context: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RawEvaluationResult:
    """Raw evaluator output before runtime normalization."""

    candidate_id: str
    disposition: EvaluationDisposition
    impact: int
    confidence: int
    ease: int
    quality_score: float
    urgency_score: float
    freshness_score: float
    feedback_score: float
    reason: str
    rework_route: ReworkRoute | None = None


GeneratorRunner = Callable[[GeneratorExecutionInput], Iterable[RawGeneratedCandidate]]
RefinerRunner = Callable[[RefinerExecutionInput], Iterable[RawRefinerResult]]
EvaluatorRunner = Callable[[EvaluatorExecutionInput], Iterable[RawEvaluationResult]]


def _require_timezone(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("Stage execution timestamps must be timezone-aware.")
    return now


def _normalize_text(value: str, *, field_name: str) -> str:
    normalized = " ".join(value.split()).strip()
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    return normalized


def _normalize_tags(tags: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(tag.strip().lower() for tag in tags if tag.strip()))


def _normalize_scores(
    *,
    impact: int,
    confidence: int,
    ease: int,
    quality_score: float | None = None,
    urgency_score: float | None = None,
    freshness_score: float | None = None,
    feedback_score: float = 0.0,
) -> CandidateScores:
    return CandidateScores(
        impact=max(1, min(10, impact)),
        confidence=max(1, min(10, confidence)),
        ease=max(1, min(10, ease)),
        quality_score=_clamp_float(quality_score) if quality_score is not None else None,
        urgency_score=_clamp_float(urgency_score) if urgency_score is not None else None,
        freshness_score=_clamp_float(freshness_score) if freshness_score is not None else None,
        feedback_score=_clamp_float(feedback_score),
    )


def _clamp_float(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _failure(stage_name: str, exc: Exception, item_key: str | None = None) -> StageFailure:
    return StageFailure(stage_name=stage_name, message=str(exc), item_key=item_key)


def run_generator_stage(
    stage_input: GeneratorExecutionInput,
    runner: GeneratorRunner,
    *,
    now: datetime | None = None,
) -> StageExecutionResult:
    """Execute and normalize the generator stage."""

    stage_time = _require_timezone(now or datetime.now(UTC))
    try:
        raw_candidates = tuple(runner(stage_input))
    except Exception as exc:
        return StageExecutionResult(stage_name="generator", failures=(_failure("generator", exc),))

    records: list[CandidateRecord] = []
    failures: list[StageFailure] = []
    valid_evidence_ids = {str(evidence.evidence_id) for evidence in stage_input.evidence_units}

    for index, raw in enumerate(raw_candidates):
        item_key = f"generated[{index}]"
        try:
            if not raw.source_evidence_ids:
                raise ValueError("Generated candidates must reference at least one evidence unit.")
            if any(source_id not in valid_evidence_ids for source_id in raw.source_evidence_ids):
                raise ValueError("Generated candidate references unknown evidence.")
            source_evidence_ids = tuple(
                evidence.evidence_id
                for evidence in stage_input.evidence_units
                if str(evidence.evidence_id) in raw.source_evidence_ids
            )

            candidate = create_candidate(
                company_id=stage_input.company_id,
                candidate_type=raw.candidate_type,
                title=_normalize_text(raw.title, field_name="Generated candidate title"),
                content=_normalize_text(raw.content, field_name="Generated candidate content"),
                source_evidence_ids=source_evidence_ids,
                scores=_normalize_scores(
                    impact=raw.impact,
                    confidence=raw.confidence,
                    ease=raw.ease,
                ),
                semantic_tags=_normalize_tags(raw.semantic_tags),
                now=stage_time,
            )
            records.append(candidate)
        except Exception as exc:
            failures.append(_failure("generator", exc, item_key))

    return StageExecutionResult(
        stage_name="generator",
        records=tuple(records),
        failures=tuple(failures),
    )


def run_refiner_stage(
    stage_input: RefinerExecutionInput,
    runner: RefinerRunner,
    *,
    now: datetime | None = None,
) -> StageExecutionResult:
    """Execute and normalize the refiner stage."""

    stage_time = _require_timezone(now or datetime.now(UTC))
    try:
        raw_results = tuple(runner(stage_input))
    except Exception as exc:
        return StageExecutionResult(stage_name="refiner", failures=(_failure("refiner", exc),))

    records: list[CandidateRecord] = []
    failures: list[StageFailure] = []
    candidates_by_id = {
        str(candidate.candidate_id): candidate for candidate in stage_input.generated_candidates
    }

    for index, raw in enumerate(raw_results):
        item_key = f"refined[{index}]"
        try:
            parent = candidates_by_id.get(raw.parent_candidate_id)
            if parent is None:
                raise ValueError("Refiner result references unknown candidate.")

            if raw.disposition == RefinerDisposition.SUPPRESS:
                records.append(
                    advance_candidate(
                        parent,
                        target_state=CandidateState.SUPPRESSED,
                        now=stage_time,
                        evaluation_reason=raw.reason or "Suppressed during refinement.",
                    )
                )
                continue

            scores = _normalize_scores(
                impact=raw.impact if raw.impact is not None else parent.scores.impact,
                confidence=(
                    raw.confidence if raw.confidence is not None else parent.scores.confidence
                ),
                ease=raw.ease if raw.ease is not None else parent.scores.ease,
                quality_score=parent.scores.quality_score,
                urgency_score=parent.scores.urgency_score,
                freshness_score=parent.scores.freshness_score,
                feedback_score=parent.scores.feedback_score,
            )
            source_candidate_ids = tuple(
                (
                    parent.candidate_id
                    if source_id == raw.parent_candidate_id
                    else candidates_by_id[source_id].candidate_id
                )
                for source_id in dict.fromkeys((raw.parent_candidate_id, *raw.source_candidate_ids))
                if source_id in candidates_by_id
            )
            refined = fork_candidate_version(
                parent,
                target_state=CandidateState.REFINED,
                now=stage_time,
                title=(
                    _normalize_text(raw.title, field_name="Refined candidate title")
                    if raw.title is not None
                    else parent.title
                ),
                content=(
                    _normalize_text(raw.content, field_name="Refined candidate content")
                    if raw.content is not None
                    else parent.content
                ),
                scores=scores,
                semantic_tags=(
                    _normalize_tags(raw.semantic_tags)
                    if raw.semantic_tags is not None
                    else parent.semantic_tags
                ),
                source_candidate_ids=source_candidate_ids,
            )
            records.append(refined)
        except Exception as exc:
            failures.append(_failure("refiner", exc, item_key))

    return StageExecutionResult(
        stage_name="refiner",
        records=tuple(records),
        failures=tuple(failures),
    )


def run_evaluator_stage(
    stage_input: EvaluatorExecutionInput,
    runner: EvaluatorRunner,
    *,
    now: datetime | None = None,
) -> StageExecutionResult:
    """Execute and normalize the evaluator stage."""

    stage_time = _require_timezone(now or datetime.now(UTC))
    try:
        raw_results = tuple(runner(stage_input))
    except Exception as exc:
        return StageExecutionResult(stage_name="evaluator", failures=(_failure("evaluator", exc),))

    records: list[CandidateRecord] = []
    failures: list[StageFailure] = []
    candidates_by_id = {
        str(candidate.candidate_id): candidate for candidate in stage_input.refined_candidates
    }

    for index, raw in enumerate(raw_results):
        item_key = f"evaluated[{index}]"
        try:
            candidate = candidates_by_id.get(raw.candidate_id)
            if candidate is None:
                raise ValueError("Evaluator result references unknown candidate.")
            if candidate.state != CandidateState.REFINED:
                raise ValueError("Evaluator input candidates must be in REFINED state.")

            scored_candidate = replace(
                candidate,
                scores=_normalize_scores(
                    impact=raw.impact,
                    confidence=raw.confidence,
                    ease=raw.ease,
                    quality_score=raw.quality_score,
                    urgency_score=raw.urgency_score,
                    freshness_score=raw.freshness_score,
                    feedback_score=raw.feedback_score,
                ),
            )
            records.append(
                _apply_evaluation_disposition(
                    scored_candidate,
                    raw_result=raw,
                    evaluated_at=stage_time,
                )
            )
        except Exception as exc:
            failures.append(_failure("evaluator", exc, item_key))

    return StageExecutionResult(
        stage_name="evaluator",
        records=tuple(records),
        failures=tuple(failures),
    )


def execute_candidate_pipeline(
    generator_input: GeneratorExecutionInput,
    *,
    generator_runner: GeneratorRunner,
    refiner_runner: RefinerRunner,
    evaluator_runner: EvaluatorRunner,
    strategic_context: Mapping[str, str] | None = None,
    feedback_memory: Mapping[str, str] | None = None,
    ranking_context: Mapping[str, str] | None = None,
    strategic_policy: Mapping[str, str] | None = None,
    active_inventory_state: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> CandidatePipelineResult:
    """Run the three core stages as distinct execution seams."""

    stage_time = _require_timezone(now or datetime.now(UTC))
    strategic_context = strategic_context or {}
    feedback_memory = feedback_memory or {}
    ranking_context = ranking_context or {}
    strategic_policy = strategic_policy or {}
    active_inventory_state = active_inventory_state or {}
    generated = run_generator_stage(generator_input, generator_runner, now=stage_time)
    refined = run_refiner_stage(
        RefinerExecutionInput(
            company_id=generator_input.company_id,
            evidence_units=generator_input.evidence_units,
            generated_candidates=generated.records,
            strategic_context=strategic_context,
            feedback_memory=feedback_memory,
            ranking_context=ranking_context,
        ),
        refiner_runner,
        now=stage_time,
    )
    evaluated = run_evaluator_stage(
        EvaluatorExecutionInput(
            company_id=generator_input.company_id,
            evidence_units=generator_input.evidence_units,
            refined_candidates=tuple(
                candidate
                for candidate in refined.records
                if candidate.state == CandidateState.REFINED
            ),
            evidence_lineage={
                str(candidate.candidate_id): tuple(
                    str(evidence_id) for evidence_id in candidate.lineage.source_evidence_ids
                )
                for candidate in refined.records
                if candidate.state == CandidateState.REFINED
            },
            strategic_policy=strategic_policy,
            feedback_memory=feedback_memory,
            active_inventory_state=active_inventory_state,
            ranking_context=ranking_context,
        ),
        evaluator_runner,
        now=stage_time,
    )
    return CandidatePipelineResult(generated=generated, refined=refined, evaluated=evaluated)


def _apply_evaluation_disposition(
    candidate: CandidateRecord,
    *,
    raw_result: RawEvaluationResult,
    evaluated_at: datetime,
) -> CandidateRecord:
    if raw_result.disposition == EvaluationDisposition.ELIGIBLE:
        return advance_candidate(
            candidate,
            target_state=CandidateState.EVALUATED,
            now=evaluated_at,
            evaluation_reason=raw_result.reason,
        )
    if raw_result.disposition == EvaluationDisposition.REVISE:
        return advance_candidate(
            candidate,
            target_state=CandidateState.REWORK,
            now=evaluated_at,
            rework_route=raw_result.rework_route or ReworkRoute.REVISE,
            evaluation_reason=raw_result.reason,
        )
    if raw_result.disposition == EvaluationDisposition.REGENERATE:
        return advance_candidate(
            candidate,
            target_state=CandidateState.REWORK,
            now=evaluated_at,
            rework_route=raw_result.rework_route or ReworkRoute.REGENERATE,
            evaluation_reason=raw_result.reason,
        )
    if raw_result.disposition == EvaluationDisposition.MERGE:
        return advance_candidate(
            candidate,
            target_state=CandidateState.REWORK,
            now=evaluated_at,
            rework_route=raw_result.rework_route or ReworkRoute.MERGE,
            evaluation_reason=raw_result.reason,
        )
    if raw_result.disposition == EvaluationDisposition.SUPPRESS:
        return advance_candidate(
            candidate,
            target_state=CandidateState.SUPPRESSED,
            now=evaluated_at,
            evaluation_reason=raw_result.reason,
        )
    return advance_candidate(
        candidate,
        target_state=CandidateState.ARCHIVED,
        now=evaluated_at,
        evaluation_reason=raw_result.reason,
    )
