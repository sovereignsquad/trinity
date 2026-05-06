# Stage Execution Contract

## Purpose

This document defines the execution contract for the three core `{trinity}` stages:

- generator
- refiner
- evaluator

## Runtime Boundary

The stage layer is reusable runtime orchestration code.

It is not:

- model-backend code
- product-adapter mapping code
- UI code
- transport or approval logic

The runtime owns:

- stage input contracts
- raw stage result contracts
- deterministic normalization into candidate schemas
- explicit partial-failure reporting
- end-to-end stage orchestration

## Adapter Boundary

Adapters may:

- build runtime requests
- supply strategic context
- map operator outcomes back into runtime events

Adapters may not redefine stage semantics. Generator, refiner, and evaluator contracts must remain consistent across products unless the core runtime contract itself changes.

## Core Objects

The workflow layer exposes:

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
- canonical evidence units
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
- canonical evidence units
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

- stage-runner exceptions, such as backend failures
- item normalization failures, such as invalid raw output or unknown references

Failures are returned as `StageFailure` records instead of being silently ignored or misrepresented as valid downstream work.

## Orchestration Model

`execute_candidate_pipeline()` runs:

1. generator
2. refiner
3. evaluator

Each stage consumes only the normalized outputs of the previous stage.

Canonical evidence is re-injected into refiner and evaluator inputs so later passes remain grounded in the original evidence batch rather than becoming candidate-only self-reference loops.

Suppressed refiner outputs do not continue to evaluation.

## Verification

This contract is verified through deterministic tests covering:

- end-to-end stage wiring
- deterministic normalization of raw generator output
- explicit surfacing of invalid raw output
- explicit surfacing of stage exceptions
- evaluator rework disposition mapping into lifecycle routes
