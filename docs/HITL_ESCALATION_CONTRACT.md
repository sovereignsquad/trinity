# Human-in-the-Loop Escalation Contract

## Purpose

This document defines when and how `{trinity}` escalates unresolved runtime work to human review.

## Core Rule

Human review must happen after bounded machine work by default.

If normal runtime work requires human intervention in the middle of every cycle, the system is defective.

## Escalation Triggers

Escalation is required when one or more of the following conditions holds:

- combined confidence remains below threshold after bounded rework
- a meaningful minority report persists across loops
- adapter risk policy requires human judgment
- prior human corrections indicate the runtime is likely repeating a known error pattern
- the cycle enters an explicitly high-risk or policy-sensitive state

## Required Controls

Every adapter-supported runtime must define or inherit:

- minimum combined confidence
- maximum loop count
- maximum rework count
- disagreement severity threshold
- high-risk escalation policy

These controls may vary by adapter, but the runtime contract remains generic.

## Escalation Payload

A human escalation artifact must include:

- the current majority result
- the current minority report when present
- evidence anchors
- retrieved memory factors
- loop history summary
- unresolved questions
- recommended human decision target

This payload must be inspectable and traceable.

## Human Outcome Types

At minimum, human resolution must support:

- approve majority
- approve minority
- reject both and supply correction
- request further evidence
- suppress output

## Post-Escalation Behavior

Human resolution must feed:

- runtime memory
- disagreement memory when applicable
- bounded export artifacts for later Train use

Human resolution must not automatically become uncontrolled global model mutation.

## Product Semantics

### `{reply}`

Human escalation may resolve:

- whether to send a risky or ambiguous reply
- whether to clarify, defer, or refuse
- whether a minority safer route should override the majority

### `{spot}`

Human escalation may resolve:

- whether a row should be treated as threatening or benign
- whether a borderline interpretation requires formal review
- whether the minority interpretation should drive downstream review handling

## Hard Rules

- do not hide escalations inside product-local heuristics
- do not escalate because of unbounded prompt uncertainty alone
- do not bypass the bounded loop just because a human is available
- do not treat human review as an excuse to skip memory updates
