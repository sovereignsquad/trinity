# Stage Execution Contract

## Purpose

This document defines the execution contract for the three core `{trinity}` stages:

- generator
- refiner
- evaluator

It implements issue `#5`.

## Runtime Boundary

The stage layer is runtime orchestration code.

It is not:

- model-backend code
- product-adapter code
- UI code

The runtime owns:

- stage input contracts
- raw stage result contracts
- deterministic normalization into candidate schemas
- explicit partial-failure reporting
- end-to-end stage orchestration

## Core Objects

The workflow layer now exposes:

- `GeneratorExecutionInput`
- `RawGeneratedCandidate`
- `RefinerExecutionInput`
- `RawRefinerResult`
- `EvaluatorExecutionInput`
- `RawEvaluationResult`
- `StageFailure`
- `StageExecutionResult`
- `CandidatePipelineResult`

And these stage runners:

- `run_generator_stage()`
- `run_refiner_stage()`
- `run_evaluator_stage()`
- `execute_candidate_pipeline()`

## Generator Contract

The generator receives:

- tenant identity
- evidence units
- strategic context
- memory constraints
- active knowledge inventory
- active action inventory
- topic anchors

The generator emits raw candidates that include:

- candidate type
- title
- content
- source evidence ids
- `impact`
- `confidence`
- `ease`
- semantic tags

Normalization then:

- trims and validates title/content
- verifies referenced evidence exists in the input batch
- clamps score dimensions into runtime ranges
- normalizes tags deterministically
- creates `GENERATED` candidates through the lifecycle contract

## Refiner Contract

The refiner receives:

- tenant identity
- generated candidates
- strategic context
- feedback memory
- ranking context

The refiner emits raw results with one of two dispositions:

- `REFINE`
- `SUPPRESS`

Normalization then:

- verifies the referenced parent candidate exists
- forks a new `REFINED` version in the same family for refinement outputs
- preserves lineage
- maps suppressions into explicit `SUPPRESSED` candidates

## Evaluator Contract

The evaluator receives:

- tenant identity
- refined candidates
- evidence lineage
- strategic policy
- feedback memory
- active inventory state
- ranking context

The evaluator emits canonical dispositions:

- `ELIGIBLE`
- `REVISE`
- `REGENERATE`
- `MERGE`
- `SUPPRESS`
- `ARCHIVE`

Normalization then:

- validates the candidate exists and is currently `REFINED`
- writes normalized scoring fields onto the candidate
- maps dispositions to lifecycle states
- maps rework dispositions to explicit rework routes
- records evaluation reason and evaluation time

## Failure Model

Failures are surfaced explicitly.

There are two failure classes:

- stage-runner exceptions, such as backend or adapter failures
- item normalization failures, such as invalid raw output or unknown references

Failures are returned as `StageFailure` records instead of being silently ignored or misrepresented as valid downstream work.

## Orchestration Model

`execute_candidate_pipeline()` runs:

1. generator
2. refiner
3. evaluator

Each stage consumes only the normalized outputs of the previous stage.

Suppressed refiner outputs do not continue to evaluation.

This keeps stage boundaries explicit and makes later optimization work by `{train}` inspectable.

## Current Non-Goals

This increment does not yet implement:

- model adapters
- persistence-backed execution logs
- frontier ranking
- semantic duplicate clustering
- feedback replay

Those belong in later issues.

## Verification

This contract is verified through deterministic tests covering:

- end-to-end stage wiring
- deterministic normalization of raw generator output
- explicit surfacing of invalid raw output
- explicit surfacing of stage exceptions
- evaluator rework disposition mapping into lifecycle routes
