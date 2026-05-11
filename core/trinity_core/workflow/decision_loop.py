"""Consensus, confidence, and bounded loop helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from statistics import mean
from uuid import UUID

from trinity_core.schemas import (
    CandidateRecord,
    CandidateState,
    ConfidenceBundle,
    ConsensusDecision,
    HumanEscalation,
    LoopAction,
    LoopDecision,
    MinorityReport,
    StageOpinion,
)

from .frontier import FrontierEntry


def synthesize_consensus_decision(
    *,
    cycle_id: UUID,
    adapter_name: str,
    majority_candidate: CandidateRecord | None,
    frontier_entries: tuple[FrontierEntry, ...],
    generated_candidates: tuple[CandidateRecord, ...],
    refined_candidates: tuple[CandidateRecord, ...],
    evaluated_candidates: tuple[CandidateRecord, ...],
    memory_factors: tuple[str, ...] = (),
    disagreement_threshold: float = 0.18,
) -> ConsensusDecision:
    stage_opinions = (
        _stage_opinion("generator", generated_candidates),
        _stage_opinion("refiner", refined_candidates),
        _stage_opinion("evaluator", evaluated_candidates),
    )
    confidence_bundle = build_confidence_bundle(
        frontier_entries=frontier_entries,
        stage_opinions=stage_opinions,
    )
    minority = _build_minority_report(
        cycle_id=cycle_id,
        adapter_name=adapter_name,
        majority_candidate=majority_candidate,
        frontier_entries=frontier_entries,
        memory_factors=memory_factors,
        disagreement_threshold=disagreement_threshold,
    )
    if minority is not None:
        confidence_bundle = ConfidenceBundle(
            generator_confidence=confidence_bundle.generator_confidence,
            refiner_confidence=confidence_bundle.refiner_confidence,
            evaluator_confidence=confidence_bundle.evaluator_confidence,
            frontier_confidence=confidence_bundle.frontier_confidence,
            combined_confidence=confidence_bundle.combined_confidence,
            disagreement_severity=minority.disagreement_severity,
        )
    return ConsensusDecision(
        majority_candidate_id=majority_candidate.candidate_id if majority_candidate else None,
        majority_reason="Top eligible frontier candidate after stage execution.",
        stage_opinions=stage_opinions,
        confidence_bundle=confidence_bundle,
        minority_report=minority,
        metadata={
            "frontier_count": len(frontier_entries),
            "eligible_count": sum(
                1
                for candidate in evaluated_candidates
                if candidate.state is CandidateState.EVALUATED
            ),
        },
    )


def build_confidence_bundle(
    *,
    frontier_entries: tuple[FrontierEntry, ...],
    stage_opinions: tuple[StageOpinion, ...],
) -> ConfidenceBundle:
    generator_conf = _opinion_confidence(stage_opinions, "generator")
    refiner_conf = _opinion_confidence(stage_opinions, "refiner")
    evaluator_conf = _opinion_confidence(stage_opinions, "evaluator")
    frontier_conf = max(
        (min(1.0, max(0.0, entry.frontier_score / 100.0)) for entry in frontier_entries),
        default=0.0,
    )
    combined = mean((generator_conf, refiner_conf, evaluator_conf, frontier_conf))
    return ConfidenceBundle(
        generator_confidence=generator_conf,
        refiner_confidence=refiner_conf,
        evaluator_confidence=evaluator_conf,
        frontier_confidence=frontier_conf,
        combined_confidence=combined,
    )


def decide_loop_action(
    decision: ConsensusDecision,
    *,
    loop_count: int,
    max_loop_count: int,
    minimum_combined_confidence: float = 0.6,
    disagreement_escalation_threshold: float = 0.75,
) -> LoopDecision:
    return decide_loop_action_from_signals(
        confidence_bundle=decision.confidence_bundle,
        minority_report=decision.minority_report,
        loop_count=loop_count,
        max_loop_count=max_loop_count,
        minimum_combined_confidence=minimum_combined_confidence,
        disagreement_escalation_threshold=disagreement_escalation_threshold,
    )


def decide_loop_action_from_signals(
    *,
    confidence_bundle: ConfidenceBundle,
    minority_report: MinorityReport | None,
    loop_count: int,
    max_loop_count: int,
    minimum_combined_confidence: float = 0.6,
    disagreement_escalation_threshold: float = 0.75,
    prior_human_correction: bool = False,
    high_risk: bool = False,
) -> LoopDecision:
    metadata = {
        "minimum_combined_confidence": minimum_combined_confidence,
        "disagreement_escalation_threshold": disagreement_escalation_threshold,
        "minority_report_present": minority_report is not None,
        "prior_human_correction": prior_human_correction,
        "high_risk": high_risk,
    }
    if (
        minority_report is not None
        and minority_report.disagreement_severity >= disagreement_escalation_threshold
        and loop_count >= max_loop_count
    ):
        return LoopDecision(
            action=LoopAction.ESCALATE,
            reason="Persistent high-severity minority report after bounded loop budget.",
            loop_count=loop_count,
            max_loop_count=max_loop_count,
            confidence_bundle=confidence_bundle,
            minority_report=minority_report,
            metadata=metadata,
        )
    if high_risk and loop_count >= max_loop_count:
        return LoopDecision(
            action=LoopAction.ESCALATE,
            reason="High-risk adapter policy requires human review after bounded machine work.",
            loop_count=loop_count,
            max_loop_count=max_loop_count,
            confidence_bundle=confidence_bundle,
            minority_report=minority_report,
            metadata=metadata,
        )
    if prior_human_correction and loop_count >= max_loop_count:
        return LoopDecision(
            action=LoopAction.ESCALATE,
            reason="Prior human correction indicates this cycle should return to human review.",
            loop_count=loop_count,
            max_loop_count=max_loop_count,
            confidence_bundle=confidence_bundle,
            minority_report=minority_report,
            metadata=metadata,
        )
    if confidence_bundle.combined_confidence < minimum_combined_confidence:
        action = LoopAction.REWORK if loop_count < max_loop_count else LoopAction.ESCALATE
        reason = (
            "Combined confidence below runtime threshold."
            if action is LoopAction.REWORK
            else "Combined confidence stayed below threshold after bounded loop budget."
        )
        return LoopDecision(
            action=action,
            reason=reason,
            loop_count=loop_count,
            max_loop_count=max_loop_count,
            confidence_bundle=confidence_bundle,
            minority_report=minority_report,
            metadata=metadata,
        )
    return LoopDecision(
        action=LoopAction.ACCEPT,
        reason="Combined confidence cleared the current runtime threshold.",
        loop_count=loop_count,
        max_loop_count=max_loop_count,
        confidence_bundle=confidence_bundle,
        minority_report=minority_report,
        metadata=metadata,
    )


def build_hitl_escalation(
    *,
    cycle_id: UUID,
    adapter_name: str,
    company_id: UUID,
    majority_result_ref: str,
    decision_target: str,
    loop_decision: LoopDecision,
    evidence_anchors: tuple[str, ...] = (),
    memory_factors: tuple[str, ...] = (),
    unresolved_questions: tuple[str, ...] = (),
    created_at: datetime | None = None,
) -> HumanEscalation:
    history = (
        f"loop {loop_decision.loop_count}/{loop_decision.max_loop_count}: "
        f"{loop_decision.action.value} ({loop_decision.reason})",
    )
    questions = unresolved_questions or _default_unresolved_questions(
        loop_decision.minority_report,
        loop_decision,
    )
    return HumanEscalation(
        cycle_id=cycle_id,
        adapter=adapter_name,
        company_id=company_id,
        majority_result_ref=majority_result_ref,
        decision_target=decision_target,
        escalation_reason=loop_decision.reason,
        loop_history_summary=history,
        unresolved_questions=questions,
        evidence_anchors=evidence_anchors,
        memory_factors=memory_factors,
        minority_report=loop_decision.minority_report,
        created_at=created_at or datetime.now(UTC),
    )


def _stage_opinion(stage_name: str, candidates: tuple[CandidateRecord, ...]) -> StageOpinion:
    if not candidates:
        return StageOpinion(
            stage_name=stage_name,
            candidate_id=None,
            confidence=0.0,
            disposition="empty",
            rationale="No candidates survived this stage.",
        )
    candidate = candidates[0]
    return StageOpinion(
        stage_name=stage_name,
        candidate_id=candidate.candidate_id,
        confidence=min(1.0, max(0.0, candidate.scores.confidence / 10.0)),
        disposition=candidate.state.value.lower(),
        rationale=candidate.evaluation_reason or f"Top candidate after {stage_name} stage.",
    )


def _opinion_confidence(opinions: tuple[StageOpinion, ...], stage_name: str) -> float:
    for opinion in opinions:
        if opinion.stage_name == stage_name:
            return opinion.confidence
    return 0.0


def _build_minority_report(
    *,
    cycle_id: UUID,
    adapter_name: str,
    majority_candidate: CandidateRecord | None,
    frontier_entries: tuple[FrontierEntry, ...],
    memory_factors: tuple[str, ...],
    disagreement_threshold: float,
) -> MinorityReport | None:
    if majority_candidate is None or len(frontier_entries) < 2:
        return None
    alternate = frontier_entries[1]
    gap = abs(frontier_entries[0].frontier_score - alternate.frontier_score) / 100.0
    if gap > disagreement_threshold:
        return None
    severity = (
        max(0.0, min(1.0, 1.0 - (gap / disagreement_threshold)))
        if disagreement_threshold > 0
        else 1.0
    )
    if severity < 0.25:
        return None
    return MinorityReport(
        cycle_id=cycle_id,
        adapter=adapter_name,
        company_id=majority_candidate.company_id,
        majority_result_ref=str(majority_candidate.candidate_id),
        minority_result_ref=str(alternate.candidate.candidate_id),
        dissent_source="frontier_alternate",
        dissent_reason=(
            "Top two frontier candidates remain close enough to preserve "
            "a dissenting route."
        ),
        disagreement_severity=severity,
        evidence_anchors=tuple(
            str(evidence_id)
            for evidence_id in alternate.candidate.lineage.source_evidence_ids
        ),
        memory_factors=memory_factors,
        recommended_action=LoopAction.REWORK.value,
        created_at=datetime.now(UTC),
    )


def _default_unresolved_questions(
    minority_report: MinorityReport | None,
    loop_decision: LoopDecision,
) -> tuple[str, ...]:
    questions = [loop_decision.reason]
    if minority_report is not None:
        questions.append(minority_report.dissent_reason)
    return tuple(questions)
