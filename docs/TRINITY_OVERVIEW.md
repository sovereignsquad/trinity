# Trinity Overview

## Purpose

This document is the high-level overview of `{trinity}` as it exists now.

## System Identity

`{trinity}` is a local-first runtime for converting normalized evidence into ranked, decision-ready candidates.

It is designed to serve multiple downstream products through explicit adapters.

It is not:

- a single-product codebase
- the operator shell itself
- the offline optimizer
- a queue manager

## Runtime Model

The runtime model is:

1. ingest evidence
2. generate candidates
3. refine candidates
4. evaluate candidates
5. surface a small frontier
6. record deterministic outcomes
7. export traceable artifacts for replay and learning

## Adapter Model

The repository now distinguishes:

- generic runtime core
- product adapters
- operational storage and policy lifecycle

Current adapter support:

- `reply`
- `spot` as a bounded reasoning/review slice

Current compatibility posture:

- generic commands are primary
- Reply compatibility aliases remain supported
- new installs use adapter-scoped runtime roots
- legacy Reply runtime roots still work when they already exist locally

## Core Contracts

Reusable runtime contracts live in:

- [core/trinity_core/schemas/evidence.py](/Users/Shared/Projects/trinity/core/trinity_core/schemas/evidence.py)
- [core/trinity_core/schemas/candidate.py](/Users/Shared/Projects/trinity/core/trinity_core/schemas/candidate.py)

Adapter-facing contracts currently live in:

- [core/trinity_core/schemas/integration.py](/Users/Shared/Projects/trinity/core/trinity_core/schemas/integration.py)
- [docs/REPLY_PRODUCT_ADAPTER_CONTRACT.md](/Users/Shared/Projects/trinity/docs/REPLY_PRODUCT_ADAPTER_CONTRACT.md)
- [core/trinity_core/schemas/spot_integration.py](/Users/Shared/Projects/trinity/core/trinity_core/schemas/spot_integration.py)

## Core Code Paths

- generic runtime facade: [core/trinity_core/runtime.py](/Users/Shared/Projects/trinity/core/trinity_core/runtime.py)
- Reply runtime implementation: [core/trinity_core/reply_runtime.py](/Users/Shared/Projects/trinity/core/trinity_core/reply_runtime.py)
- Spot runtime implementation: [core/trinity_core/adapters/product/spot/runtime.py](/Users/Shared/Projects/trinity/core/trinity_core/adapters/product/spot/runtime.py)
- adapter helpers: [core/trinity_core/adapters](/Users/Shared/Projects/trinity/core/trinity_core/adapters)
- CLI: [core/trinity_core/cli.py](/Users/Shared/Projects/trinity/core/trinity_core/cli.py)
- storage helpers: [core/trinity_core/ops/runtime_storage.py](/Users/Shared/Projects/trinity/core/trinity_core/ops/runtime_storage.py)

## Operational Direction

The repository is now in the correct shape to serve other projects, but it is not finished platform work.

What is done:

- adapter seam exists
- generic CLI exists
- adapter-scoped storage exists
- Reply compatibility is preserved

What remains:

- move more Reply-owned policy and mapping logic into deeper adapter packages
- generalize shared abstractions only where two adapters require them
- keep the Reply policy/train lane explicit until another adapter actually needs a shared promotion contract
- keep new downstream apps on their own adapter seams rather than stretching Reply semantics

## New App Rule

If you are connecting a new downstream app such as `{compare}`, add a new adapter.

Do not reuse `reply` unless the product is actually a reply-drafting workflow with Reply-shaped contracts.

Start here:

- [docs/INTEGRATING_NEW_APP.md](/Users/Shared/Projects/trinity/docs/INTEGRATING_NEW_APP.md)
- [docs/ADAPTER_AUTHORING_GUIDE.md](/Users/Shared/Projects/trinity/docs/ADAPTER_AUTHORING_GUIDE.md)
