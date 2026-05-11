# Memory Architecture

## Purpose

This document defines how runtime memory must work inside `{trinity}`.

It exists to prevent two failure modes:

1. treating memory as a passive log instead of an active runtime dependency
2. treating every memory update as implicit global model mutation

## Memory Role

`{trinity}` memory is the live supervisory layer that changes future runtime behavior.

Memory is used to:

- improve generation
- constrain refinement
- inform evaluation
- affect ranking or eligibility
- support escalation decisions

Memory is not:

- the same thing as model fine-tuning
- a product-owned cache hidden outside runtime contracts
- a substitute for bounded Train promotion workflows

## Memory Layers

`{trinity}` must distinguish between at least three learning speeds.

### Fast Layer

Immediate runtime memory:

- thread facts
- contact facts
- recent outcomes
- recent corrections
- recent explanations
- unresolved disagreements

This layer may change live runtime behavior immediately through retrieval.

### Medium Layer

Structured lessons and accepted runtime-local patterns:

- preferred phrasing
- anti-patterns
- correction patterns
- reviewer preferences
- tenant-specific threat patterns

This layer may influence runtime immediately after validation and storage, but remains bounded and auditable.

### Slow Layer

Offline optimization artifacts for `{train}`:

- proposal bundles
- holdout replay inputs
- policy candidates
- threshold candidates
- evaluator heuristic candidates

This layer must not mutate the runtime directly.

## Runtime Memory Tiers

The current runtime contract now also distinguishes between three retrieval tiers:

### Core Tier

Always-visible state that should stay intentionally small:

- contact profile summary
- current thread or row state
- current-item human-resolution summaries

Core-tier memory is selected first and should remain the smallest retrieval slice.

### Working Tier

Active supervisory memory that is useful often but should not be pinned forever:

- company-scoped preferences
- correction patterns
- anti-patterns
- successful patterns
- disagreement summaries
- topic or stage-scoped summaries

Working-tier memory is retrieved after core memory and is the main live-behavior shaping layer.

### Archival Tier

Longer-tail factual or evidence material that should be queried on demand:

- retrieval chunks from normalized documents
- broader historical evidence context

Archival-tier memory is retrievable, but it should not crowd out core or working state by default.

## Current Deterministic Placement Rules

The current code uses these placement rules:

- contact profiles and thread/row state -> `core`
- `human:*`, `thread:*`, and `row:*` summaries -> `core`
- `company:*`, `topic:*`, `stage:*`, `adapter:*`, and `project:*` summaries -> `working`
- retrieval chunks -> `archival`

These rules are intentionally simple and inspectable. They can evolve later, but they should remain deterministic.

## Memory Scopes

Every memory record must declare scope.

Minimum required scopes:

- `GLOBAL`
- `ADAPTER`
- `PROJECT`
- `COMPANY`
- `ITEM_FAMILY`
- `TOPIC`
- `STAGE`
- `HUMAN_RESOLUTION`

Scope resolution must prefer narrower valid memory over broader memory when both apply.

## Memory Families

Minimum required record families:

- evidence memory
- preference memory
- correction memory
- anti-pattern memory
- successful-pattern memory
- disagreement memory
- human-resolution memory

### Evidence Memory

Durable facts or normalized evidence summaries that should influence later reasoning.

### Preference Memory

Soft or hard preferences discovered through feedback or stable operator behavior.

### Correction Memory

Specific edits, fixes, or reversals that should shape future outputs.

### Anti-Pattern Memory

Known bad patterns that should reduce confidence or trigger suppression.

### Successful-Pattern Memory

Known good patterns that proved valuable in downstream outcomes.

### Disagreement Memory

Historical cases where majority and minority views diverged, including which side proved correct.

### Human-Resolution Memory

Human decisions that resolved unresolved runtime work and should become future supervisory guidance.

## Memory Retrieval Contract

Runtime memory retrieval must be explicit.

For each cycle, `{trinity}` must be able to show:

- which scopes were searched
- which records were selected
- which tier each selected record came from
- why they were selected
- which stage or decision they influenced

This is required for auditability and later Train exports.

## Memory Update Contract

Memory updates happen at runtime completion boundaries.

Eligible update sources:

- accepted machine outputs
- declined machine outputs
- edited outputs
- suppressed outputs
- human escalations
- final human resolutions
- downstream delivery or review outcomes

Every update must preserve:

- tenant identity
- source cycle identity
- source evidence anchors
- source adapter
- update family
- confidence or trust level when applicable

## Boundary With Model Mutation

The following distinction is mandatory:

- memory retrieval changes live behavior by changing context
- promoted artifacts change governed runtime behavior by explicit adoption
- model fine-tuning changes model internals and must remain bounded and deliberate

Therefore:

- raw feedback must not automatically become global model mutation
- client data must not silently become model-training data
- memory storage must remain auditable and removable in ways that direct model mutation is not

## Cross-Project Rule

Memory must support sharing without semantic leakage.

Allowed:

- reuse abstract reasoning lessons across projects when they are product-neutral
- store project-specific records under project or adapter scope

Not allowed:

- leaking Reply drafting preferences into Spot threat reasoning by default
- leaking Spot classification heuristics into Reply style behavior by default

## Implementation Bias

Bias toward:

- explicit scopes
- explicit memory family tags
- traceable retrieval
- runtime-owned storage
- reversible and inspectable updates

Avoid:

- heuristic hidden memory channels
- product-local memory systems outside `{trinity}`
- unclear boundaries between memory and Train optimization
