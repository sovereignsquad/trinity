# {trinity}

`trinity` is a local-first candidate processing workflow for turning raw evidence into ranked, decision-ready outputs.

It is the runtime workflow layer for systems such as:

- omnichannel reply drafting
- domain-specific advisory assistants
- tutoring systems
- knowledge surfacing and action recommendation

`trinity` is not the same product as `{train}`.

- `{trinity}` runs the workflow that produces candidates
- `{train}` improves pieces of that workflow through bounded optimization

## Core Workflow

The workflow is intentionally staged:

1. ingest evidence
2. generate candidate outputs
3. refine candidate outputs
4. evaluate candidate outputs
5. select the frontier
6. learn from user feedback

The first production target is a macOS-first local operator experience.

## Repository Purpose

This repository exists to define and build:

- the runtime workflow contract
- the local data and memory model
- the macOS operator shell
- the evaluation and feedback pipeline
- the interfaces that downstream products such as `{reply}` can embed

## Platform Direction

Near term:

- lock the repository contract
- define the evidence, candidate, and feedback schemas
- build the first local macOS shell
- build a deterministic local development loop
- prepare runtime seams that `{train}` can optimize later

Longer term:

- integrate with `{reply}` as the first production embedding
- support multilingual local inference and ranking
- support domain-specific brains built on the same workflow

## Initial Repository Shape

```text
trinity/
  apps/
    macos/
  core/
    trinity_core/
  docs/
  tests/
```

## Local Development

Python tooling:

```bash
uv sync --dev
uv run ruff check .
uv run pytest
```

macOS app:

```bash
cd apps/macos
swift build
```

## Current State

This repository currently provides:

- repository operating docs
- coding standards and definition of done
- design system baseline
- macOS development guide
- minimal SwiftUI app scaffold
- Python workspace scaffold for future core/runtime code
- handover and status docs for resumable development

## License

This repository is licensed under `Apache-2.0`.

