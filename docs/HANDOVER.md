# Handover

## Purpose

This document exists so work can be resumed cleanly by:

- the same developer later
- another developer
- another coding agent

## Current Handover

### What Changed Last

Last completed increment:

- stage execution contract for `{trinity}`

Implemented:

- stage input contracts for generator, refiner, and evaluator
- raw stage output contracts normalized deterministically into runtime candidate schemas
- explicit stage failure surfacing for runner exceptions and invalid raw output
- end-to-end stage orchestration through `execute_candidate_pipeline()`
- deterministic tests for stage wiring, failure surfaces, and evaluator rework mapping
- stage execution contract documentation
- consolidated `docs/TRINITY_OVERVIEW.md` for fast repository orientation
- status and handover updates advancing the repo to issue `#6`

### What Was Verified

Verified:

- `uv run pytest`
- `uv run ruff check .`
- `swift build` in `apps/macos`

### What Needs To Happen Next

1. implement frontier selection, suppression, merge, and ranking semantics
2. add tenant-bound persistence and cycle orchestration
3. start the first real macOS operator shell slices against runtime contracts
4. add the `{reply}` adapter contract against the runtime seams

### Watch Carefully

- do not collapse `{trinity}` into `{train}`
- keep workflow core separate from product adapters
- keep the first embedding `{reply}`-aware but not `{reply}`-shaped
- keep candidate lifecycle semantics explicit instead of letting app code invent them
- keep generator, refiner, and evaluator execution contracts separate from lifecycle storage semantics
- keep frontier/ranking logic distinct from evaluator execution so precision policy stays inspectable
- keep local-private data out of git
