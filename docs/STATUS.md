# Status

## Purpose

This is the current status document for the repository.

## Current Phase

Phase:

- workflow contract establishment
- macOS-first development baseline
- first runtime schema delivery

Primary active issue:

- `#6` `{trinity}: Build frontier selection, suppression, merge, and ranking semantics`

## Current Reality

The repository currently has:

- GitHub project board and initial issue roadmap
- core operating docs
- coding standards
- definition of done
- design system baseline
- macOS development baseline
- Python workspace scaffold
- minimal SwiftUI shell scaffold
- evidence ingestion schema and deterministic ingestion helpers
- evidence ingestion contract documentation
- candidate lifecycle schema and transition helpers
- candidate lifecycle contract documentation
- stage execution contracts and deterministic stage orchestration
- stage execution contract documentation
- consolidated Trinity overview documentation

## Verified Working

Verified locally:

- `uv run pytest`
- `uv run ruff check .`
- `swift build` in `apps/macos`

## Current Gaps

Still missing on the critical path:

- frontier selection, suppression, merge, and ranking semantics
- local evidence and feedback models
- tenant-bound persistence and cycle orchestration
- real macOS operator screens
- `{reply}` adapter contract

## Immediate Next Steps

1. implement frontier selection, suppression, merge, and ranking semantics
2. build tenant-bound persistence and cycle orchestration
3. build the first operator shell slices
4. add the `{reply}` adapter contract against the runtime seams

## Resume Point

If resuming work, start by reading:

1. `README.md`
2. `docs/STATUS.md`
3. `docs/HANDOVER.md`
4. `AGENTS.md`
