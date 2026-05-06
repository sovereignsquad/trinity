# Status

## Purpose

This document records the current implementation state of `{trinity}`.

## Current Phase

Current phase:

- reusable runtime core is established
- Reply adapter integration remains the only production adapter
- generic adapter seam and generic CLI surface are now implemented
- compatibility aliases remain in place for downstream Reply integration safety

Primary active lane:

- keep the Reply adapter stable while broadening `{trinity}` into a genuinely reusable runtime for additional projects

## Current Reality

The repository currently has:

- deterministic workflow core
- adapter helper layer
- generic `TrinityRuntime` facade
- adapter-scoped runtime storage for new installs
- legacy Reply storage fallback for migration safety
- generic CLI commands with `--adapter`
- compatibility `reply-*` aliases
- bounded Reply policy artifacts and acceptance workflow
- accepted-artifact promotion and rollback workflows
- training-bundle export
- shadow fixture replay
- deterministic coverage across workflow, policy, storage, and adapter behavior

## Verified Working

Verified locally in the current tranche:

- `uv run pytest`
- `PYTHONPATH=core uv run python -m trinity_core.cli show-config --adapter reply --include-path`
- `PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply`
- `PYTHONPATH=core uv run python -m trinity_core.cli run-shadow-fixtures --adapter reply`

## Known Constraints

- only the `reply` adapter is implemented today
- generic model configuration still resolves to Reply semantics because no second adapter exists yet
- Reply policy artifacts remain Reply-specific by design and have not yet been generalized into multiple artifact families

## Immediate Priorities

1. keep the Reply adapter stable while extracting more adapter-owned code into dedicated adapter packages
2. add a second real adapter before broadening generic schemas further
3. preserve explicit artifact promotion, rollback, and provenance rules
4. continue preferring deterministic replay coverage over heuristic runtime expansion
