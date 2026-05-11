# Cross-Project Memory Boundaries

## Purpose

This document defines how `{trinity}` memory can be reused across multiple downstream projects without leaking one product's semantics into another.

## Problem

`{trinity}` is intended to help both `{reply}` and `{spot}`.

That creates a real risk:

- useful cross-project learning can exist
- product-specific behavior can also contaminate another product if boundaries are weak

The system must support sharing and isolation at the same time.

## Shared Versus Isolated Memory

### Shared Memory

Memory may be shared across projects only when the lesson is product-neutral.

Examples:

- evidence deduplication patterns
- general risk-elevation lessons
- stable contradiction patterns
- disagreement outcomes about ambiguous reasoning

### Isolated Memory

Memory must remain isolated when it is tied to product semantics.

Examples:

- Reply wording and drafting preferences
- Reply transport-safe phrasing habits
- Spot category-boundary heuristics
- Spot reviewer guidance tied to taxonomy interpretation

## Default Rule

When uncertain, prefer isolation over sharing.

Cross-project sharing should be earned by explicit classification of a memory family as reusable.

## Required Memory Labels

Cross-project memory records must be classifiable by:

- project scope
- adapter scope
- reuse eligibility
- trust level

Suggested reuse eligibility labels:

- `project_only`
- `adapter_family`
- `cross_project_safe`

## `{reply}` Boundary

Memory originating from `{reply}` must not automatically shape:

- Spot threat labels
- Spot review thresholds
- Spot explanation rules

Allowed exceptions require explicit runtime classification as cross-project-safe.

## `{spot}` Boundary

Memory originating from `{spot}` must not automatically shape:

- Reply tone
- Reply brevity
- Reply delivery style
- Reply clarification strategy

Allowed exceptions require explicit runtime classification as cross-project-safe.

## Human Feedback Boundary

Human corrections are especially sensitive.

They may:

- update project-local runtime memory immediately
- become cross-project lessons only after explicit classification
- become Train input only through bounded export rules

They may not:

- silently become broad global model mutation
- silently overwrite another project's local runtime assumptions

## Acceptance Checks

The cross-project boundary is working only when:

- Reply quality changes are attributable to Reply or explicitly shared memory
- Spot reasoning changes are attributable to Spot or explicitly shared memory
- shared memory is inspectable and intentionally classified
- no downstream project is forced to inherit another product's language or output shape
