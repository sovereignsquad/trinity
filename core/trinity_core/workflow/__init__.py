"""Workflow contracts and deterministic orchestration helpers."""

from .candidate_lifecycle import advance_candidate, create_candidate, fork_candidate_version
from .evidence_ingestion import (
    DuplicateEvidenceSuppressed,
    EvidenceIngestionResult,
    InMemoryEvidenceStore,
    RawEvidenceInput,
    canonicalize_content,
    compute_content_hash,
    ingest_evidence,
)
from .feedback_memory import apply_reply_feedback
from .frontier import FrontierEntry, build_frontier, frontier_score
from .stage_execution import (
    CandidatePipelineResult,
    EvaluationDisposition,
    EvaluatorExecutionInput,
    GeneratorExecutionInput,
    RawEvaluationResult,
    RawGeneratedCandidate,
    RawRefinerResult,
    RefinerDisposition,
    RefinerExecutionInput,
    StageExecutionResult,
    StageFailure,
    execute_candidate_pipeline,
    run_evaluator_stage,
    run_generator_stage,
    run_refiner_stage,
)

__all__ = [
    "advance_candidate",
    "CandidatePipelineResult",
    "create_candidate",
    "DuplicateEvidenceSuppressed",
    "EvaluationDisposition",
    "EvidenceIngestionResult",
    "EvaluatorExecutionInput",
    "execute_candidate_pipeline",
    "build_frontier",
    "FrontierEntry",
    "frontier_score",
    "GeneratorExecutionInput",
    "InMemoryEvidenceStore",
    "RawEvidenceInput",
    "RawEvaluationResult",
    "RawGeneratedCandidate",
    "RawRefinerResult",
    "RefinerDisposition",
    "RefinerExecutionInput",
    "run_evaluator_stage",
    "run_generator_stage",
    "run_refiner_stage",
    "StageExecutionResult",
    "StageFailure",
    "canonicalize_content",
    "compute_content_hash",
    "fork_candidate_version",
    "ingest_evidence",
    "apply_reply_feedback",
]
