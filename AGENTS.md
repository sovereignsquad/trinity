# AGENTS

## Purpose

This file is the fast-entry operating brief for coding agents working in this repository.

Read this before making changes.

## Project Identity

`{trinity}` is a local-first candidate processing workflow.

It is not:

- the `{train}` optimizer
- a single product UI
- a single provider integration
- a one-off reply bot

The first downstream embedding is expected to be `{reply}`.

## Core Boundaries

Keep these layers separate:

1. `workflow.*`
2. `memory.*`
3. `adapter.product.*`
4. `adapter.model.*`
5. `apps.*`
6. `ops.*`

Do not collapse them into one implementation layer.

## Primary SSOT

Before changing code, read:

- `README.md`
- `docs/OPERATING_MODEL.md`
- `docs/TECH_STACK.md`
- `docs/REPOSITORY_CONTRACT.md`
- `docs/CODING_STANDARDS.md`
- `docs/DEFINITION_OF_DONE.md`
- `docs/STATUS.md`
- `docs/HANDOVER.md`

## Active Delivery Focus

Current active implementation lane:

- repository contract, runtime workflow contract, and macOS-first development baseline

Always check `docs/STATUS.md` before starting.

## Required Work Pattern

1. Confirm the active issue and acceptance checks.
2. Read the relevant SSOT docs.
3. Implement the smallest correct step on the critical path.
4. Update docs if architecture, setup, operations, or status changed.
5. Leave the repo in a resumable state.

## Documentation Rule

If you learn something future contributors or agents need:

- write it into the repo

Do not leave critical context in chat only.

## Native App UI Rule

When touching `apps/*` or other shipped operator surfaces, preserve the native-app standard:

- `{trinity}` is a native app, not a website
- do not introduce website-style UX metaphors into shipped operator flows
- keep core actions in shell chrome, panels, or dialogs
- require all shipped visual assets and iconography to be locally available offline
- use one consistent local icon system and one shared icon sizing contract
- prefer explicit visual rendering contracts over heuristic markup/path guessing

## Memory Rule

When significant work completes, update:

- `docs/STATUS.md`
- `docs/HANDOVER.md`

If you do not update those, the work is not properly handed over.

## Implementation Bias

Bias toward:

- explicit contracts
- deterministic processing
- local-first operation
- auditable lifecycle state
- macOS-first operator usability

Avoid:

- hidden prompt magic
- product-specific assumptions in core workflow code
- provider lock-in
- premature distributed architecture

## Final Rule

Make the repository easier to resume than you found it.
