# Adapter Authoring Guide

## Purpose

This document explains how to add a new product adapter to `{trinity}` without collapsing product logic into runtime core.

## Design Rule

An adapter translates one product's world into Trinity runtime contracts.

The adapter owns:

- request normalization
- outcome normalization
- adapter-local policy scope mapping
- fixture loading for that product

The adapter does not own:

- stage semantics
- candidate lifecycle semantics
- artifact promotion mechanics
- trace persistence mechanics

## Minimum Steps

1. Choose an adapter name.
2. Add the adapter to [core/trinity_core/adapters/base.py](/Users/Shared/Projects/trinity/core/trinity_core/adapters/base.py).
3. Add a runtime implementation or runtime mapping layer.
4. Add adapter-scoped fixtures and tests.
5. Expose the adapter through the generic CLI.
6. Add adapter contract docs.

## Recommended Structure

```text
core/trinity_core/
  adapters/
    base.py
    product/
      <adapter>/
        __init__.py
        contract.py
        mapper.py
        fixtures.py
        policy.py
```

## Contract Shape

At minimum, an adapter should define how to:

- build a runtime request from product input
- map ranked runtime output back into product output
- map product feedback or outcomes into runtime events
- resolve adapter-local policy scope

## CLI Rule

The generic CLI is the primary integration surface.

New adapters should work through commands like:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli suggest --adapter <adapter>
PYTHONPATH=core uv run python -m trinity_core.cli record-outcome --adapter <adapter>
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter <adapter>
```

Do not add adapter-specific aliases until the generic path is stable and tested.

## Storage Rule

New adapters must use:

```text
.../trinity_runtime/adapters/<adapter>/
```

Do not create fresh top-level runtime roots analogous to `reply_runtime`.

## Testing Rule

Every adapter should add:

- contract validation tests
- fixture replay tests
- storage path tests when adapter-specific persistence is introduced
- CLI smoke coverage for the generic `--adapter` path

## Documentation Rule

Every adapter should ship:

- one adapter contract document
- one short usage example
- one note about what remains product-owned outside `{trinity}`
