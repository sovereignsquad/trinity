from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from trinity_core.schemas import (
    CandidateState,
    CandidateType,
    EvidenceSourceRef,
    EvidenceSourceType,
)
from trinity_core.workflow import (
    EvaluationDisposition,
    GeneratorExecutionInput,
    InMemoryEvidenceStore,
    RawEvaluationResult,
    RawEvidenceInput,
    RawGeneratedCandidate,
    RawRefinerResult,
    RefinerDisposition,
    execute_candidate_pipeline,
    ingest_evidence,
    run_generator_stage,
)


def test_pipeline_executes_stages_as_distinct_contracts() -> None:
    evidence = _make_evidence()
    call_order: list[str] = []

    def generator_runner(stage_input: GeneratorExecutionInput) -> tuple[RawGeneratedCandidate, ...]:
        call_order.append("generator")
        assert len(stage_input.evidence_units) == 1
        return (
            RawGeneratedCandidate(
                candidate_type=CandidateType.KNOWLEDGE,
                title="  Upsell risk is rising  ",
                content=" Expansion conversations are slowing in the top segment. ",
                source_evidence_ids=(str(evidence.evidence_id),),
                impact=8,
                confidence=7,
                ease=6,
                semantic_tags=("Revenue", " Revenue ", "expansion"),
            ),
        )

    def refiner_runner(stage_input):  # type: ignore[no-untyped-def]
        call_order.append("refiner")
        assert len(stage_input.evidence_units) == 1
        assert stage_input.evidence_units[0].evidence_id == evidence.evidence_id
        parent = stage_input.generated_candidates[0]
        return (
            RawRefinerResult(
                disposition=RefinerDisposition.REFINE,
                parent_candidate_id=str(parent.candidate_id),
                content=(
                    "Top-segment expansion conversations are slowing and now need intervention."
                ),
                semantic_tags=("revenue", "intervention"),
            ),
        )

    def evaluator_runner(stage_input):  # type: ignore[no-untyped-def]
        call_order.append("evaluator")
        assert len(stage_input.evidence_units) == 1
        assert stage_input.evidence_units[0].evidence_id == evidence.evidence_id
        candidate = stage_input.refined_candidates[0]
        assert stage_input.evidence_lineage[str(candidate.candidate_id)] == (
            str(evidence.evidence_id),
        )
        return (
            RawEvaluationResult(
                candidate_id=str(candidate.candidate_id),
                disposition=EvaluationDisposition.ELIGIBLE,
                impact=9,
                confidence=8,
                ease=7,
                quality_score=88.0,
                urgency_score=79.0,
                freshness_score=73.0,
                feedback_score=0.0,
                reason="High-value opportunity with strong support.",
            ),
        )

    pipeline = execute_candidate_pipeline(
        GeneratorExecutionInput(
            company_id=evidence.company_id,
            evidence_units=(evidence,),
            strategic_context={"goal": "protect expansion revenue"},
        ),
        generator_runner=generator_runner,
        refiner_runner=refiner_runner,
        evaluator_runner=evaluator_runner,
        now=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
    )

    assert call_order == ["generator", "refiner", "evaluator"]
    assert pipeline.generated.records[0].state == CandidateState.GENERATED
    assert pipeline.generated.records[0].semantic_tags == ("revenue", "expansion")
    assert pipeline.refined.records[0].state == CandidateState.REFINED
    assert (
        pipeline.refined.records[0].lineage.parent_candidate_id
        == pipeline.generated.records[0].candidate_id
    )
    assert pipeline.evaluated.records[0].state == CandidateState.EVALUATED
    assert pipeline.evaluated.records[0].scores.quality_score == 88.0


def test_generator_stage_surfaces_invalid_raw_output() -> None:
    evidence = _make_evidence()

    result = run_generator_stage(
        GeneratorExecutionInput(
            company_id=evidence.company_id,
            evidence_units=(evidence,),
        ),
        lambda _stage_input: (
            RawGeneratedCandidate(
                candidate_type=CandidateType.KNOWLEDGE,
                title=" ",
                content="Valid content",
                source_evidence_ids=(str(evidence.evidence_id),),
                impact=5,
                confidence=5,
                ease=5,
            ),
        ),
        now=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
    )

    assert result.records == ()
    assert len(result.failures) == 1
    assert result.failures[0].stage_name == "generator"
    assert result.failures[0].item_key == "generated[0]"


def test_stage_exception_is_surfaced_explicitly() -> None:
    evidence = _make_evidence()

    result = run_generator_stage(
        GeneratorExecutionInput(
            company_id=evidence.company_id,
            evidence_units=(evidence,),
        ),
        lambda _stage_input: (_ for _ in ()).throw(RuntimeError("generator backend unavailable")),
        now=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
    )

    assert result.records == ()
    assert result.failures[0].message == "generator backend unavailable"


def test_evaluator_rework_disposition_maps_to_lifecycle_route() -> None:
    evidence = _make_evidence()

    pipeline = execute_candidate_pipeline(
        GeneratorExecutionInput(company_id=evidence.company_id, evidence_units=(evidence,)),
        generator_runner=lambda _stage_input: (
            RawGeneratedCandidate(
                candidate_type=CandidateType.ACTION,
                title="Draft a recovery email",
                content="Send a recovery note to delayed expansion accounts.",
                source_evidence_ids=(str(evidence.evidence_id),),
                impact=7,
                confidence=6,
                ease=7,
            ),
        ),
        refiner_runner=lambda stage_input: (
            RawRefinerResult(
                disposition=RefinerDisposition.REFINE,
                parent_candidate_id=str(stage_input.generated_candidates[0].candidate_id),
            ),
        ),
        evaluator_runner=lambda stage_input: (
            RawEvaluationResult(
                candidate_id=str(stage_input.refined_candidates[0].candidate_id),
                disposition=EvaluationDisposition.REGENERATE,
                impact=6,
                confidence=4,
                ease=5,
                quality_score=49.0,
                urgency_score=70.0,
                freshness_score=66.0,
                feedback_score=0.0,
                reason="Promising idea but weak support.",
            ),
        ),
        now=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
    )

    candidate = pipeline.evaluated.records[0]
    assert candidate.state == CandidateState.REWORK
    assert str(candidate.rework_route) == "REGENERATE"


def _make_evidence():
    company_id = uuid4()
    store = InMemoryEvidenceStore()
    result = ingest_evidence(
        RawEvidenceInput(
            company_id=company_id,
            source_type=EvidenceSourceType.EMAIL,
            source_ref=EvidenceSourceRef(external_id="email-1"),
            content="Expansion calls are slowing in the top segment.",
            freshness_duration=timedelta(days=2),
        ),
        store=store,
        now=datetime(2026, 5, 1, 11, 0, tzinfo=UTC),
    )
    assert result.accepted is not None
    return result.accepted
