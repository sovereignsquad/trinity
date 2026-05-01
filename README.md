# {trinity}

`trinity` is a local-first runtime workflow for turning raw evidence into ranked, decision-ready candidates.

It is the runtime brain layer for systems such as:

- omnichannel reply drafting
- domain-specific advisory assistants
- tutoring systems
- knowledge surfacing
- action recommendation

`{trinity}` is not the same system as `{train}`.

- `{trinity}` runs the workflow that produces candidates
- `{train}` improves bounded pieces of that workflow later

The likely first downstream embedding is `{reply}`, but `{reply}` must not define the whole runtime.

## What It Does

`{trinity}` is designed to solve four problems at once:

1. high evidence volume
2. noisy and overlapping signals
3. limited human attention
4. the need to learn from feedback over time

Its purpose is not to generate prose for its own sake.

Its purpose is to maintain a small, high-utility, continuously refreshed operational frontier from a much larger internal candidate inventory.

## Core Workflow

The workflow is intentionally staged:

1. ingest evidence
2. generate candidates
3. refine candidates
4. evaluate candidates
5. select the frontier
6. learn from user feedback

The intended machine-first flow is:

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

The operator-facing frontier is intentionally small:

```text
FrontierSize = min(3, eligible items)
```

## Core Runtime Concepts

Canonical runtime artifacts:

- `EvidenceUnit`
- `KnowledgeItem`
- `ActionItem`
- `FeedbackEvent`

Canonical lifecycle states:

- `GENERATED`
- `REFINED`
- `EVALUATED`
- `REWORK`
- `SUPPRESSED`
- `ARCHIVED`
- `DELIVERED` for action items only

Canonical scoring dimensions:

- `impact`
- `confidence`
- `ease`
- `qualityScore`
- `urgencyScore`
- `freshnessScore`
- `feedbackScore`

## Repository Purpose

This repository exists to define and build:

- the runtime workflow contract
- the local data and memory model
- the candidate lifecycle and execution seams
- the macOS operator shell
- the evaluation and feedback pipeline
- the interfaces that downstream products such as `{reply}` can embed

## Current Implemented Contracts

The repository currently implements these foundational runtime layers:

1. Evidence ingestion
   Deterministic canonicalization, exact-hash deduplication, provenance handling, and tenant-bound evidence semantics.
2. Candidate lifecycle
   Explicit candidate types, lifecycle states, legal transitions, lineage preservation, and rework routes.
3. Stage execution
   Separate generator, refiner, and evaluator contracts with deterministic normalization and explicit failure surfacing.
4. Runtime storage resolution
   Code-level enforcement that default app data, cache, and log directories resolve outside the repository working tree.

Relevant docs:

- [{trinity} Overview](./docs/TRINITY_OVERVIEW.md)
- [Evidence Ingestion Contract](./docs/EVIDENCE_INGESTION_CONTRACT.md)
- [Candidate Lifecycle Contract](./docs/CANDIDATE_LIFECYCLE_CONTRACT.md)
- [Stage Execution Contract](./docs/STAGE_EXECUTION_CONTRACT.md)
- [Runtime Storage Policy](./docs/RUNTIME_STORAGE_POLICY.md)

## What Is Planned Next

The runtime is not complete yet.

Still on the critical path:

- frontier selection, suppression, merge, and ranking semantics
- tenant-bound persistence and cycle orchestration
- feedback memory and replayability
- the `{reply}` product adapter contract
- real macOS operator screens beyond scaffold
- local model adapter seams

## Platform Direction

Near term:

- finish the workflow core
- lock the ranking and frontier semantics
- build persistence and feedback memory
- build the first local macOS shell slices
- prepare runtime seams that `{train}` can optimize later

Longer term:

- integrate with `{reply}` as the first production embedding
- support multilingual local inference and ranking
- support domain-specific brains built on the same workflow

## Initial Repository Shape

```text
trinity/
  apps/
    macos/
  core/
    trinity_core/
  docs/
  tests/
```

## Local Development

Python tooling:

```bash
uv sync --dev
uv run ruff check .
uv run pytest
```

macOS app:

```bash
cd apps/macos
swift build
```

## Additional Repository Docs

Primary orientation and operating docs:

- [docs/TRINITY_OVERVIEW.md](./docs/TRINITY_OVERVIEW.md)
- [docs/BRAIN.md](./docs/BRAIN.md)
- [docs/TRINITY_FORMAL_PRODUCTION_DEFINITION.md](./docs/TRINITY_FORMAL_PRODUCTION_DEFINITION.md)
- [docs/TRINITY_PSEUDOCODE_SPECIFICATION.md](./docs/TRINITY_PSEUDOCODE_SPECIFICATION.md)
- [docs/RUNTIME_STORAGE_POLICY.md](./docs/RUNTIME_STORAGE_POLICY.md)
- [docs/STATUS.md](./docs/STATUS.md)
- [docs/HANDOVER.md](./docs/HANDOVER.md)

## License

This repository is licensed under `Apache-2.0`.
