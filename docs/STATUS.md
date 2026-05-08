# Status

## Purpose

This document records the current implementation state of `{trinity}`.

## Current Phase

Current phase:

- reusable runtime core is established
- Reply adapter integration remains the only implemented adapter
- generic adapter seam and generic CLI surface are now implemented
- compatibility aliases remain in place for downstream Reply integration safety

Primary active lane:

- keep the Reply adapter stable while broadening `{trinity}` into a genuinely reusable runtime for additional projects
- harden the Reply adapter runtime for parallel multi-company execution without cross-project artifact leakage

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
- company-scoped Reply behavior policy resolution
- tenant-aware runtime cycle, export, and training-bundle storage beneath the adapter runtime root
- atomic JSON writes for cycle, export, bundle, and accepted-artifact persistence
- Train API/CLI handoff client for autonomous bounded policy proposal generation
- concrete `{reply}` integration checklist for company identity, cycle tracking, outcomes, provenance, and Train triggering
- proposal review surface with holdout replay support, skeptical notes, and stronger scope rejection rules
- holdout-by-default policy review and acceptance flows, with explicit no-holdout override mode for local/dev use
- richer promotion review surface carrying acceptance mode and Train provenance in inspectable output
- training bundles now preserve surfaced and filtered negative candidates, stage evidence anchors, model routes, and policy-resolution summaries for hermetic offline learning
- policy resolution is now explainable through explicit resolution-path payloads instead of implicit scope fallback only
- policy review decisions can now be persisted as lineage-bearing review artifacts and linked from accepted artifact pointers
- focused design note documenting why the Train promotion seam now works
- deterministic coverage across workflow, policy, storage, and adapter behavior

## Verified Working

Verified locally in the current tranche:

- `uv run pytest`
- `PYTHONPATH=core uv run python -m trinity_core.cli show-config --adapter reply --include-path`
- `PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply`
- `PYTHONPATH=core uv run python -m trinity_core.cli run-shadow-fixtures --adapter reply`
- `uv run ruff check .`
- targeted Train proposal seam verified against sibling `/Users/Shared/Projects/train`
- policy review and acceptance gates verified with stricter company/channel/global scope rules
- bundle export now preserves negative samples and policy-resolution context for Replay training bundles

## Known Constraints

- only the `reply` adapter is implemented today
- the Train handoff, shadow fixtures, and policy artifact lifecycle are intentionally scoped to the Reply workflow today
- Reply policy artifacts remain Reply-specific by design and have not yet been generalized into multiple artifact families
- policy resolution is now company-aware, but it is still not a full company-plus-channel matrix; channel scope remains the shared fallback below company scope
- API transport to `{train}` still assumes the Train server is already running; CLI transport avoids that dependency
- no-holdout acceptance remains possible only through explicit CLI override and should stay out of normal production promotion flows
- policy scope precedence is still company -> channel -> global only; thread-level or composite scope remains intentionally out of contract

## Immediate Priorities

1. keep the new Train proposal seam explicit and bounded; do not let it bypass runtime acceptance
2. harden bundle consumers in `{train}` against the richer negative-sample and resolution payloads now emitted by `{trinity}`
3. extend company-aware policy resolution into richer scope precedence only when a second real scope dimension is justified
4. keep the Reply adapter stable while extracting more adapter-owned code into dedicated adapter packages
5. keep the current Reply workflow explicit and stable before attempting any second adapter
6. preserve explicit artifact promotion, rollback, and provenance rules
7. continue preferring deterministic replay coverage over heuristic runtime expansion
