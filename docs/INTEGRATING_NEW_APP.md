# Integrating A New App

## Purpose

This document explains how a downstream product should connect to `{trinity}`.

## Core Rule

If your product is not `{reply}`, do not reuse the Reply adapter by default.

The correct integration model is:

1. keep `{trinity}` core generic
2. add a product adapter under `adapter.product.<yourapp>.*`
3. translate product input into runtime contracts
4. translate runtime output back into product-specific output

`{reply}` is the first mature embedding. It is not the identity of `{trinity}`.

## When To Add A New Adapter

Add a new adapter whenever the downstream app has its own:

- request shape
- candidate or result shape
- outcome or review loop
- item-level memory shape
- policy or training needs

Examples:

- reply drafting belongs in `reply`
- bounded per-item reasoning/review belongs in `spot`
- a comparison workflow should become `compare`, not a variation of `reply`

## Minimum Integration Surface

At minimum, a new app usually needs:

- adapter name registration
- payload normalization
- runtime dispatch
- one bounded CLI path
- deterministic tests

Typical files:

- `core/trinity_core/adapters/base.py`
- `core/trinity_core/runtime.py`
- `core/trinity_core/cli.py`
- `core/trinity_core/adapters/product/<adapter>/__init__.py`
- `core/trinity_core/adapters/product/<adapter>/payloads.py`
- `core/trinity_core/adapters/product/<adapter>/runtime.py`
- `tests/test_adapter_runtime.py`

## What Should Stay Generic

A new app should not require broad rewrites in:

- `workflow.*`
- `memory.*`
- `adapter.model.*`

If integration requires large changes there, the adapter boundary is probably unclear.

## Start Here

For the repository-wide preparation plan, read:

- [docs/THIRD_APP_PREPARATION_PLAN.md](/Users/Shared/Projects/trinity/docs/THIRD_APP_PREPARATION_PLAN.md)

For the adapter implementation checklist, read:

- [docs/ADAPTER_AUTHORING_GUIDE.md](/Users/Shared/Projects/trinity/docs/ADAPTER_AUTHORING_GUIDE.md)
