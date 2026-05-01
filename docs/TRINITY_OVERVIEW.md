# Trinity Overview

## Purpose

This document is the consolidated overview of `{trinity}`.

It explains:

- what `{trinity}` is
- what `{trinity}` does
- how `{trinity}` works
- what `{trinity}` is capable of
- what is already implemented in this repository
- what is still planned

This is a summary document.

The detailed source of truth still lives in:

- [README.md](/Users/Shared/Projects/trinity/README.md)
- [docs/BRAIN.md](/Users/Shared/Projects/trinity/docs/BRAIN.md)
- [docs/TRINITY_FORMAL_PRODUCTION_DEFINITION.md](/Users/Shared/Projects/trinity/docs/TRINITY_FORMAL_PRODUCTION_DEFINITION.md)
- [docs/TRINITY_PSEUDOCODE_SPECIFICATION.md](/Users/Shared/Projects/trinity/docs/TRINITY_PSEUDOCODE_SPECIFICATION.md)
- [docs/EVIDENCE_INGESTION_CONTRACT.md](/Users/Shared/Projects/trinity/docs/EVIDENCE_INGESTION_CONTRACT.md)
- [docs/CANDIDATE_LIFECYCLE_CONTRACT.md](/Users/Shared/Projects/trinity/docs/CANDIDATE_LIFECYCLE_CONTRACT.md)
- [docs/STAGE_EXECUTION_CONTRACT.md](/Users/Shared/Projects/trinity/docs/STAGE_EXECUTION_CONTRACT.md)

## System Identity

`{trinity}` is a local-first runtime workflow for converting raw evidence into ranked, decision-ready candidates.

It is the runtime layer for systems such as:

- omnichannel reply drafting
- domain-specific advisory assistants
- tutoring systems
- knowledge surfacing
- action recommendation

`{trinity}` is not:

- `{train}`
- a single product UI
- a prompt-chaining gimmick
- a human review queue

The key distinction is:

- `{trinity}` runs the workflow that produces candidates
- `{train}` improves pieces of that workflow through bounded optimization

## Core Objective

The objective of `{trinity}` is not to generate prose for its own sake.

The objective is to maintain a small, high-utility, continuously refreshed operational frontier from a much larger internal candidate inventory.

In practice, `{trinity}` is trying to solve:

1. high evidence volume
2. noisy and overlapping signals
3. limited human attention
4. the need for learning from feedback over time

## Core Workflow

The core loop of `{trinity}` is:

1. ingest evidence
2. generate candidates
3. refine candidates
4. evaluate candidates
5. surface the frontier
6. learn from user feedback

The intended processing order is:

```text
Evidence
  -> Generator
  -> Refiner
  -> Evaluator
  -> Eligible Candidate Pool
  -> Frontier Selector
  -> User Feedback
  -> Reprocessing and Memory Update
```

The system is designed so machine processing happens before human attention by default.

Human feedback is supervisory, not structural.

## Core Artifacts

The canonical artifact types are:

- `EvidenceUnit`
- `KnowledgeItem`
- `ActionItem`
- `FeedbackEvent`

The main derived collections are:

- `GeneratedCandidateSet`
- `RefinedCandidateSet`
- `EvaluatedCandidateSet`
- `EligibleCandidatePool`
- `Frontier`

## Candidate Lifecycle

The canonical lifecycle vocabulary is:

- `GENERATED`
- `REFINED`
- `EVALUATED`
- `REWORK`
- `SUPPRESSED`
- `ARCHIVED`
- `DELIVERED` for action items only

The runtime uses explicit lifecycle rules, not implied state changes.

The current implemented lifecycle contract includes:

- candidate types: `KNOWLEDGE`, `ACTION`
- version-family lineage
- legal and illegal transition handling
- explicit rework routes
- action-only delivery semantics

## Evidence Model

`EvidenceUnit` is the canonical raw input object.

Every evidence unit is expected to be:

- tenant-bound
- canonicalized
- exact-deduplicated by canonical hash
- timestamped
- traceable to origin

The evidence layer is intended to support both:

- single evidence processing
- grouped evidence processing

This matters because many useful candidates are inferable only from evidence sets, not isolated evidence units.

## Stage Model

`{trinity}` is intentionally staged.

### Generator

The `Generator` is the recall-maximizing stage.

Its job is to transform evidence into plausible candidate artifacts with sufficient breadth and structured first-pass scoring.

It must support:

- `1 evidence -> 1 candidate`
- `1 evidence -> many candidates`
- `many evidence -> 1 candidate`
- `many evidence -> many candidates`

### Refiner

The `Refiner` is the entropy-reducing stage.

Its job is to transform a noisy candidate set into a smaller, cleaner, more evaluable set.

It must be able to:

- rewrite
- enrich
- normalize
- merge
- split
- suppress
- version
- reframe

### Evaluator

The `Evaluator` is the precision-maximizing stage.

Its job is to determine which refined candidates are eligible for surfacing, which require rework, and which should be suppressed or archived.

Its canonical dispositions are:

- `ELIGIBLE`
- `REVISE`
- `REGENERATE`
- `MERGE`
- `SUPPRESS`
- `ARCHIVE`

## Knowledge and Action

`{trinity}` is designed to produce both knowledge artifacts and action artifacts.

The intended flow is not only:

- evidence -> knowledge

but also:

- evidence -> knowledge -> action

The system is explicitly expected to support:

- `1 knowledge -> 1 action`
- `1 knowledge -> many actions`
- `many knowledge -> 1 action`
- `many knowledge -> many actions`

## Scoring Model

All candidates are expected to carry at least:

- `impact`
- `confidence`
- `ease`

These define:

```text
iceScore = impact * confidence * ease
```

Additional expected scoring dimensions are:

- `qualityScore`
- `urgencyScore`
- `freshnessScore`
- `feedbackScore`

`iceScore` alone is not enough for frontier ranking.

## Frontier Model

The `Frontier` is the user-facing top layer of the eligible candidate pool.

It is:

- dynamic
- ranked
- intentionally small

It is not:

- a queue
- a backlog
- a permanent inbox

The intended frontier constraint is:

```text
FrontierSize = min(3, count(eligible items))
```

The frontier should prefer:

1. `EVALUATED`
2. `REFINED`
3. `GENERATED`

The ranking model is expected to consider:

- state weight
- `iceScore`
- `qualityScore`
- `urgencyScore`
- `freshnessScore`
- `feedbackScore`
- strategic priority
- duplicate dominance
- rework status
- rot risk

## Feedback and Memory

Feedback is a first-class signal.

Canonical feedback actions include:

- `ACCEPT`
- `DECLINE`
- `COMMENT`
- `MODIFY_ACCEPT`
- `DELIVER`
- `POSTPONE`
- `PIN_EVIDENCE`
- `SUPPRESS`
- `REWORK_REQUEST`

The intended memory layer exists so feedback changes future behavior.

Memory is expected to produce:

- hard constraints
- soft preferences
- terminology corrections
- preferred action patterns
- anti-patterns
- duplicate suppression hints
- ranking hints

## Time, Rot, and Maintenance

`{trinity}` treats time as a first-class signal.

Candidates are expected to track timestamps such as:

- `createdAt`
- `updatedAt`
- `lastPresentedAt`
- `lastFeedbackAt`
- `lastReworkedAt`
- `lastDeliveredAt` for action items

The system also includes the concept of rot:

- stale context
- expired timing windows
- superseded evidence
- already-resolved opportunities

Rotten items should be:

- downranked
- reworked
- or archived

The intended maintenance model includes:

- evidence deduplication
- candidate deduplication
- duplicate-family reconciliation
- revisiting high-potential declined items
- revisiting stale refined items
- re-evaluating aging evaluated items
- updating memory from feedback
- recomputing the frontier

## Long-Term Invariants

The repository defines these durable invariants:

- the workflow is product-neutral
- the system is local-first
- the frontier is small on purpose
- feedback is first-class
- `{trinity}` runs brains
- `{train}` improves brains

## Current Repository Capabilities

The repository does not implement the entire formal system yet.

It currently implements three foundational runtime layers.

### 1. Evidence ingestion contract

Implemented in:

- [docs/EVIDENCE_INGESTION_CONTRACT.md](/Users/Shared/Projects/trinity/docs/EVIDENCE_INGESTION_CONTRACT.md)
- [core/trinity_core/workflow/evidence_ingestion.py](/Users/Shared/Projects/trinity/core/trinity_core/workflow/evidence_ingestion.py)
- [core/trinity_core/schemas/evidence.py](/Users/Shared/Projects/trinity/core/trinity_core/schemas/evidence.py)

Current implemented capabilities:

- deterministic canonicalization
- deterministic `sha256` exact-hash deduplication
- tenant-bound evidence isolation
- provenance validation
- freshness window validation
- explicit duplicate suppression outcomes

### 2. Candidate lifecycle contract

Implemented in:

- [docs/CANDIDATE_LIFECYCLE_CONTRACT.md](/Users/Shared/Projects/trinity/docs/CANDIDATE_LIFECYCLE_CONTRACT.md)
- [core/trinity_core/schemas/candidate.py](/Users/Shared/Projects/trinity/core/trinity_core/schemas/candidate.py)
- [core/trinity_core/workflow/candidate_lifecycle.py](/Users/Shared/Projects/trinity/core/trinity_core/workflow/candidate_lifecycle.py)

Current implemented capabilities:

- explicit candidate types and states
- legal transition enforcement
- illegal transition rejection
- version-family lineage preservation
- explicit rework routes
- action-only delivery handling

### 3. Stage execution contract

Implemented in:

- [docs/STAGE_EXECUTION_CONTRACT.md](/Users/Shared/Projects/trinity/docs/STAGE_EXECUTION_CONTRACT.md)
- [core/trinity_core/workflow/stage_execution.py](/Users/Shared/Projects/trinity/core/trinity_core/workflow/stage_execution.py)

Current implemented capabilities:

- explicit generator input/output contract
- explicit refiner input/output contract
- explicit evaluator input/output contract
- deterministic normalization into runtime candidate schemas
- explicit stage failure surfacing
- end-to-end stage orchestration across generator, refiner, and evaluator

## What `{trinity}` Is Capable Of By Design

By design, `{trinity}` is capable of:

- ingesting heterogeneous evidence under one common contract
- producing both knowledge and action candidates
- preserving provenance and lineage
- scoring and dispositioning candidates explicitly
- ranking a small operational frontier
- using feedback to influence future generation, refinement, evaluation, and ranking
- supporting downstream product embeddings such as `{reply}`
- exposing explicit seams that `{train}` can optimize later

## What Is Not Yet Implemented

The repository still does not fully implement:

- frontier selection code
- suppression, merge, and ranking semantics as working runtime logic
- persistence-backed cycle orchestration
- feedback memory and replayability
- model adapter layer
- `{reply}` product adapter contract
- real macOS operator screens beyond scaffold
- the full autonomous maintenance loop

These are planned next steps, not current delivered behavior.

## Runtime Data Placement

The repository working tree is for development assets.

Live runtime state should not be stored in the repository by default.

When persistence is implemented, runtime data should resolve to machine-local app storage outside the repo, with macOS defaults such as:

- `~/Library/Application Support/Trinity/`
- `~/Library/Caches/Trinity/`
- `~/Library/Logs/Trinity/`

See:

- [docs/RUNTIME_STORAGE_POLICY.md](/Users/Shared/Projects/trinity/docs/RUNTIME_STORAGE_POLICY.md)

## Practical Short Definition

`{trinity}` is a local-first, product-neutral runtime for transforming evidence into a continuously refreshed, auditable, high-utility frontier of knowledge and action candidates.
