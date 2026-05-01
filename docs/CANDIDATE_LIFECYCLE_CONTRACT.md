# Candidate Lifecycle Contract

## Purpose

This document defines the runtime-level candidate lifecycle contract for `{trinity}`.

It implements the delivery target of issue `#4`.

## Contract Objects

The runtime now exposes these candidate-layer objects in `core/trinity_core/`:

- `CandidateType`
- `CandidateState`
- `ReworkRoute`
- `CandidateLineage`
- `CandidateScores`
- `CandidateRecord`

The workflow layer now exposes:

- `create_candidate()`
- `advance_candidate()`
- `fork_candidate_version()`

## Candidate Types

The lifecycle currently supports two core candidate families:

- `KNOWLEDGE`
- `ACTION`

`DELIVERED` is action-only.

## Candidate States

The canonical lifecycle vocabulary is:

- `GENERATED`
- `REFINED`
- `EVALUATED`
- `REWORK`
- `SUPPRESSED`
- `ARCHIVED`
- `DELIVERED`

## Required Candidate Fields

Each candidate record carries:

- tenant identity
- candidate identity
- candidate type
- explicit lifecycle state
- title and content
- version-family lineage
- scoring dimensions
- semantic tags
- duplicate-cluster linkage
- required timestamps

Action candidates may additionally carry:

- `last_delivered_at`
- `delivery_target_ref`

## Scoring Contract

Every candidate carries:

- `impact`
- `confidence`
- `ease`

And may carry derived scores such as:

- `quality_score`
- `urgency_score`
- `freshness_score`
- `feedback_score`

`ice_score` is defined as:

```text
impact * confidence * ease
```

## Lineage Contract

Lineage is explicit and version-family based.

Each candidate tracks:

- `version_family_id`
- `parent_candidate_id`
- `source_evidence_ids`
- `source_candidate_ids`

Refinement and rework create new candidate versions in the same family rather than erasing history.

## Explicit Transition Rules

The runtime currently allows:

- `GENERATED -> REFINED`
- `GENERATED -> SUPPRESSED`
- `GENERATED -> ARCHIVED`
- `REFINED -> EVALUATED`
- `REFINED -> REWORK`
- `REFINED -> SUPPRESSED`
- `REFINED -> ARCHIVED`
- `EVALUATED -> REWORK`
- `EVALUATED -> SUPPRESSED`
- `EVALUATED -> ARCHIVED`
- `EVALUATED -> DELIVERED` for `ACTION` only
- `REWORK -> REFINED`
- `REWORK -> SUPPRESSED`
- `REWORK -> ARCHIVED`
- `SUPPRESSED -> REWORK`
- `SUPPRESSED -> ARCHIVED`
- `DELIVERED -> REWORK`
- `DELIVERED -> ARCHIVED`

Illegal transitions fail closed.

## Rework Contract

`REWORK` requires an explicit route.

Supported routes are:

- `REVISE`
- `REGENERATE`
- `MERGE`
- `ENRICH`
- `DOWNRANK_ONLY`

## Current Non-Goals

This increment does not yet implement:

- generator execution
- refiner execution
- evaluator execution
- persistence-backed candidate storage
- frontier ranking

Those belong in later issues.

## Verification

This contract is verified through deterministic tests covering:

- refinement lineage preservation
- legal lifecycle transitions
- illegal transition rejection
- rework route requirements
- action-only delivery rules
