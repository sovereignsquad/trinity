# Repository Contract

## Purpose

This document defines the intended structure and boundary rules of the `{trinity}` repository.

## Core Separation

The repository is divided into seven concerns:

1. documentation
2. workflow core
3. schemas and contracts
4. model adapters
5. product adapters
6. operations and storage
7. shipped app surfaces

These concerns must remain explicit.

## Intended Layout

```text
trinity/
  README.md
  docs/
  core/
    trinity_core/
      adapters/
        model/
        product/
      ops/
      runtime.py
      schemas/
      workflow/
  apps/
  tests/
```

## Directory Responsibilities

### `core/trinity_core/workflow/`

Reusable runtime logic:

- evidence ingestion
- stage execution
- frontier selection
- deterministic feedback application

No product-specific transport or approval rules belong here.

### `core/trinity_core/schemas/`

Canonical runtime contracts:

- evidence
- candidate
- stage-output
- adapter request and outcome envelopes
- bounded artifact schemas

### `core/trinity_core/adapters/`

Adapter declarations and future model and product adapter packages.

### `core/trinity_core/adapters/model/`

Provider-neutral model capability implementations.

This layer is where backend-specific invocation belongs:

- provider routing
- structured chat execution
- model inventory and capability discovery
- provider process or transport details

Workflow modules may depend on the capability contract exposed by this layer, but may not depend on provider-specific request formats.

### `core/trinity_core/adapters/product/`

This layer is where product-specific mapping belongs:

- request normalization
- product outcome mapping
- adapter naming
- adapter compatibility rules

### `core/trinity_core/ops/`

Operational support code:

- runtime storage
- trace persistence
- accepted-artifact registry
- adapter-scoped policy storage
- fixture replay tooling

### `apps/`

Shipped operator surfaces. These surfaces consume runtime contracts; they do not redefine them.

### `tests/`

Deterministic coverage for:

- workflow core
- adapter contracts
- storage semantics
- CLI behavior
- artifact lifecycle

## Runtime Data Boundary

The repository is not the home for live runtime state.

Runtime data belongs in machine-local storage outside the working tree, including:

- evidence stores
- candidate stores
- feedback memory
- logs
- caches
- model configuration
- execution traces
- accepted artifact state
- shadow fixtures copied for local use

## Adapter Rule

`{trinity}` is generic at the runtime boundary and specific at the adapter boundary.

That means:

- core runtime code may not assume `{reply}` semantics by default
- core runtime code may not assume Ollama semantics by default
- adapter-specific code may exist, but it must be isolated and named as adapter code
- compatibility aliases are acceptable when they preserve a stable downstream integration contract

## Storage Rule

New adapter work must use adapter-scoped runtime roots:

```text
.../trinity_runtime/adapters/<adapter>/
```

Legacy Reply storage compatibility may remain in place for migration safety, but new features must not introduce fresh hard-coded `reply_runtime` assumptions.

## Optimization Rule

`{train}` may optimize exported `{trinity}` artifacts.

`{train}` may not:

- mutate runtime state directly
- define product workflow semantics
- redefine adapter contracts from outside `{trinity}`
