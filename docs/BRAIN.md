# Brain

## Purpose

This document captures the durable mental model of `{trinity}`.

It is not a changelog.
It is not a task list.

## System Identity

`{trinity}` is a runtime workflow for converting raw evidence into ranked, decision-ready candidates.

Its core loop is:

1. ingest evidence
2. generate candidates
3. refine candidates
4. evaluate candidates
5. surface the frontier
6. learn from user feedback

## Long-Term Invariants

### Invariant 1

The workflow is product-neutral.

`{reply}` may be the first embedding, but it must not define the whole runtime.

### Invariant 2

The system is local-first.

### Invariant 3

The frontier is small on purpose.

The system should rank and suppress internally so the operator sees only the best current options.

### Invariant 4

Feedback is a first-class signal, not an afterthought.

### Invariant 5

`{trinity}` runs brains.

`{train}` improves brains.

