# Minority Report Contract

## Purpose

This document defines the `minority_report` contract inside `{trinity}`.

The term is intentional.
It refers to a meaningful dissenting interpretation or predicted path, not to random variance.

## Why This Exists

Three-stage systems lose value if disagreement is always collapsed into one final answer.

`{trinity}` must preserve meaningful dissent because:

- disagreement can indicate unresolved risk
- disagreement can indicate an alternate next best action
- disagreement can reveal memory conflict
- disagreement can reveal evaluator overreach or generator blind spots
- disagreement can be proven right later and should become future supervisory memory

## Definition

A `minority_report` is a structured runtime artifact representing a plausible but dissenting interpretation that materially differs from the current majority result.

It is emitted only when the dissent is meaningful enough to affect:

- acceptance
- rework
- escalation
- later audit
- later learning

## What Qualifies

A minority report exists when at least one of the following is true:

- one stage proposes a materially different next best action
- one stage predicts a materially different threat interpretation
- one route predicts significantly higher risk than the majority
- one route recommends escalation while the majority does not
- one interpretation remains plausible because evidence is ambiguous or memory conflicts

Not enough on its own:

- a tiny score difference
- stylistic variation without outcome consequences
- noise from low-quality duplicate candidates

## Required Fields

Minimum logical fields:

- `cycle_id`
- `adapter`
- `company_id`
- `majority_result_ref`
- `minority_result_ref`
- `dissent_source`
- `dissent_reason`
- `disagreement_severity`
- `evidence_anchors`
- `memory_factors`
- `recommended_action`
- `created_at`

### `dissent_source`

The source of dissent must be explicit, for example:

- generator
- refiner
- evaluator
- alternate route
- memory conflict

### `recommended_action`

Allowed values should be bounded to runtime actions such as:

- accept_majority
- rework
- escalate_human
- preserve_for_audit

## Operational Use

Minority reports must be usable by:

- the confidence gate
- the rework loop
- Human-in-the-Loop escalation
- runtime traces
- memory updates
- Train exports

## Cross-Project Meaning

The contract is generic.
The product meaning is adapter-owned.

### `{reply}`

A minority report may represent:

- a safer but less direct reply path
- a clarification-first route
- a risk-managed refusal or defer route

### `{spot}`

A minority report may represent:

- an alternate threat classification rationale
- a high-risk interpretation that merits review
- disagreement between benign and harmful readings

## Lifecycle

A minority report must be tracked to outcome when possible.

Possible later resolutions:

- majority was correct
- minority was correct
- both were incomplete
- human chose a third path

Those outcomes should feed disagreement memory.

## Hard Rules

- do not suppress minority reports just to keep output simple
- do not expose every tiny dissent as a minority report
- do not let the product adapter redefine the contract into product-only terminology
- do not treat a minority report as a synonym for failure
