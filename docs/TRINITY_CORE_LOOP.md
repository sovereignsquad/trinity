# Trinity Core Loop

## Purpose

This document defines the canonical runtime loop for `{trinity}` as the proper core system.

It exists to make one thing explicit:

- `{trinity}` is not only a bounded policy seam for `{reply}`
- `{trinity}` is the continuous reasoning-and-memory runtime that downstream products consume

## Core Runtime Law

The system must do its own reasoning work before requesting human help.

Human intervention is supervisory and corrective.
It is not the default middle of the runtime.

## Canonical Loop

The canonical runtime loop is:

```text
Evidence ingestion
  -> memory scope resolution
  -> scoped memory retrieval
  -> Generator
  -> Refiner
  -> Evaluator
  -> consensus synthesis
  -> minority-report synthesis
  -> confidence gate
  -> accept or rework
  -> Human-in-the-Loop escalation when loop budget is exhausted
  -> memory update
  -> bounded export for Train
```

## Runtime Stages

### 1. Evidence Ingestion

`{trinity}` receives normalized evidence from a downstream product adapter.

Examples:

- `{reply}` sends one thread snapshot plus bounded runtime context
- `{spot}` should send one message or evidence cluster plus bounded row context

Core rules:

- evidence must be traceable
- evidence must be tenant-bound
- evidence must remain product-neutral once it crosses the adapter boundary

### 2. Memory Scope Resolution

Before reasoning begins, `{trinity}` resolves the memory scopes that apply to the current cycle.

Typical scopes:

- global
- adapter
- project
- company
- thread or item family
- topic
- stage
- human-resolution

### 3. Scoped Memory Retrieval

The runtime loads memory that can affect the current reasoning cycle.

Memory is not optional context garnish.
It is a first-class runtime input.

Retrieved memory may influence:

- candidate generation
- refinement choices
- evaluator judgments
- ranking or eligibility
- escalation decisions

### 4. Generator

The Generator maximizes useful recall under explicit constraints.

It produces plausible candidate interpretations, actions, or outputs from evidence plus memory.

### 5. Refiner

The Refiner reduces entropy.

It can:

- rewrite
- enrich
- merge
- split
- normalize
- suppress

### 6. Evaluator

The Evaluator determines current runtime quality and disposition.

It is responsible for:

- eligibility
- quality judgment
- revision pressure
- risk detection
- escalation hints

### 7. Consensus Synthesis

After stage execution, `{trinity}` computes the current majority interpretation.

Consensus is not equivalent to:

- simple average score
- the last stage winning by default
- the product adapter deciding stage semantics

Consensus must be an explicit runtime artifact.

### 8. Minority Report Synthesis

If a meaningful dissenting interpretation exists, `{trinity}` emits a `minority_report`.

The minority report is not noise.
It is a first-class alternate interpretation, path, or decision candidate.

Typical minority-report cases:

- one stage predicts a materially different next best action
- one route predicts higher risk than the majority
- one interpretation remains plausible but unresolved
- one reasoning branch conflicts with dominant memory or evidence weighting

### 9. Confidence Gate

The runtime combines stage-level and consensus-level signals into a bounded decision:

- accept
- rework
- escalate

The confidence gate must consider:

- combined confidence
- disagreement severity
- adapter risk policy
- prior loop count
- prior human corrections on similar items

### 10. Rework Loop

If confidence is too low or disagreement is too meaningful to ignore, the runtime loops.

Rework may:

- retrieve additional memory
- shift prompts or role constraints
- route to stricter evaluation behavior
- re-rank candidates
- narrow the decision space

Rework is a machine-return path.
It is not a synonym for human review.

### 11. Human-in-the-Loop Escalation

If the runtime cannot resolve the cycle within bounded limits, it escalates.

Escalation is required when:

- loop budget is exhausted
- disagreement remains high
- confidence remains below threshold
- the adapter-specific risk policy requires human judgment

### 12. Memory Update

Every completed cycle must feed runtime memory.

Memory updates may come from:

- accepted outputs
- rejected outputs
- edits
- suppressions
- escalations
- human resolutions
- downstream operational outcomes

### 13. Bounded Export For Train

`{train}` receives bounded artifacts after runtime work completes.

`{train}` may optimize:

- thresholds
- routing rules
- prompt or policy artifacts
- evaluator heuristics

`{train}` may not bypass runtime ownership.

## Product-Specific Meaning

The core loop is shared.
The product semantics are not.

### `{reply}`

The output is reply-oriented candidate drafting and ranking.

### `{spot}`

The output should be per-message reasoning and threat interpretation artifacts.

`{spot}` remains owner of:

- closed-set taxonomy enforcement
- workbook output
- audit packaging

## Acceptance Checks

The core loop is correctly implemented only when:

- memory retrieval happens before stage reasoning
- disagreement can survive into runtime artifacts
- low-confidence cycles can rework without defaulting immediately to human review
- unresolved work escalates through a bounded HiTL contract
- Train receives bounded exports after runtime ownership has completed
