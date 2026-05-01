# Repository Contract

## Purpose

This document defines the intended structure of the `{trinity}` repository.

## Core Separation

The repository is divided into six concerns:

1. docs
2. workflow core
3. memory and storage
4. product adapters
5. app surfaces
6. operations

These concerns must stay separate.

## Intended Layout

```text
trinity/
  README.md
  AGENTS.md
  docs/
  core/
    trinity_core/
      workflow/
      memory/
      adapters/
      schemas/
  apps/
    macos/
  tests/
```

## Directory Responsibilities

### `docs/`

Holds SSOT project documentation.

### `core/trinity_core/`

Holds reusable runtime code.

Includes:

- workflow stages
- schemas
- memory logic
- adapter interfaces

### `apps/macos/`

Holds the native operator shell.

This layer must consume runtime contracts, not redefine them.

### `tests/`

Holds deterministic tests for repository-level and runtime-level behavior.

## Boundary Rules

### Workflow vs Product

Core workflow logic belongs in `core/trinity_core/`.

Product-specific embedding logic belongs under product adapters.

### Model vs Product

Model adapters belong under `adapter.model.*`.

Product adapters belong under `adapter.product.*`.

Do not merge them.

### Runtime vs Optimizer

`{trinity}` is the runtime workflow.

`{train}` is the optimizer that improves components of the runtime.

Do not move optimizer concerns into `{trinity}` core.

