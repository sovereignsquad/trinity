# Operating Model

## Purpose

This document defines how `{trinity}` work is coordinated.

The goal is to keep delivery strict, explicit, and resumable:

- one source of truth for each information type
- one way to name and refer to work
- one execution path from concept to shipped behavior
- explicit boundaries between runtime workflow, product adapters, and operations

Current operating bias:

- restore `{trinity}` as the core memory-and-reasoning runtime first
- keep `{reply}` stable while extracting shared behavior
- make `{spot}` prove the shared reasoning seam later without importing Reply semantics
- keep provider additions and external-ops work secondary to the core-system restoration lane

## Communication Model

We communicate at four levels only:

### 1. Roadmap

System:

- GitHub Project board
- GitHub issues

Authoritative for:

- priority
- sequencing
- dependencies
- acceptance criteria

### 2. Specifications

System:

- docs under `docs/`

Authoritative for:

- workflow stages
- memory architecture
- minority-report rules
- Human-in-the-Loop escalation rules
- system boundaries
- repository contract
- operator standards

### 3. Execution

System:

- branches
- commits
- pull requests

### 4. Operations

System:

- repository docs
- local scripts
- runbooks
- handover docs

## Naming Rules

### Issues

Use:

- `{trinity}: <outcome>`

### Branches

Use:

- `issue-<number>-<slug>`

### Commits

Use:

- `<area>: <change>`

Examples:

- `docs: define repository contract`
- `macos: add shell scaffold`
- `workflow: define evidence schema`
