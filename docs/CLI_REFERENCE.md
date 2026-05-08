# CLI Reference

## Purpose

This document lists the current public CLI surface for `{trinity}`.

## Preferred Generic Commands

All new integrations should use the generic commands with explicit adapter selection.

### Runtime Operations

- `suggest --adapter <adapter>`
- `record-outcome --adapter <adapter>`
- `export-trace --adapter <adapter> --cycle-id <uuid>`
- `runtime-status --adapter <adapter>`
- `show-config --adapter <adapter> [--include-path]`
- `write-config --adapter <adapter> [options]`

Reply-only runtime operations:

- `export-training-bundle --adapter reply --cycle-id <uuid> --bundle-type <type>`
- `train-propose-policy --adapter reply --learner-kind <kind> [--cycle-id <uuid> ... | --bundle-file <path> ...]`

### Reply-Only Policy Operations

- `policy-review --adapter reply --policy-file <path> --bundle-file <path> [--holdout-bundle-file <path> ...]`
- `policy-review-surface --adapter reply --policy-file <path> --bundle-file <path> [--holdout-bundle-file <path> ...]`
- `policy-accept --adapter reply --policy-file <path> --bundle-file <path> [--holdout-bundle-file <path> ...]`
- `policy-promote --adapter reply --artifact-key <key> --version <version> --source-project <project>`
- `policy-rollback --adapter reply --artifact-key <key> [--target-version <version>]`
- `policy-status --adapter reply --artifact-key <key>`

### Reply-Only Fixture Operations

- `run-shadow-fixtures --adapter reply [--fixture-dir <dir>]`

## Reply Compatibility Aliases

The following commands remain supported for the Reply adapter:

- `reply-suggest`
- `reply-record-outcome`
- `reply-export-trace`
- `reply-export-training-bundle`
- `reply-train-propose-policy`
- `reply-policy-review`
- `reply-policy-review-surface`
- `reply-run-shadow-fixtures`
- `reply-policy-accept`
- `reply-policy-promote`
- `reply-policy-rollback`
- `reply-policy-status`
- `reply-runtime-status`
- `reply-show-config`
- `reply-write-config`

## Example

```bash
cd /Users/Shared/Projects/trinity
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply
PYTHONPATH=core uv run python -m trinity_core.cli suggest --adapter reply --input-file /tmp/thread.json
PYTHONPATH=core uv run python -m trinity_core.cli train-propose-policy --adapter reply --cycle-id <uuid> --bundle-type tone-learning --learner-kind tone --transport cli --accept --holdout-bundle-file /tmp/holdout-bundle.json
PYTHONPATH=core uv run python -m trinity_core.cli policy-review-surface --adapter reply --policy-file /tmp/proposal.json --bundle-file /tmp/proposal-bundle.json --holdout-bundle-file /tmp/holdout-bundle.json
PYTHONPATH=core uv run python -m trinity_core.cli policy-accept --adapter reply --policy-file /tmp/proposal.json --bundle-file /tmp/proposal-bundle.json --holdout-bundle-file /tmp/holdout-bundle.json
```

## Current Constraint

Implemented adapters today:

- `reply`
- `impact`

Current adapter constraint:

- `impact` supports the generic runtime path: `suggest`, `record-outcome`, `export-trace`, `runtime-status`, `show-config`, and `write-config`
- Train proposal, policy review, policy acceptance, policy promotion, training-bundle export, and shadow-fixture replay remain Reply-only

## Holdout Default

For normal policy review and acceptance flows, holdout replay is now the default operating mode.

Use `--holdout-bundle-file` for serious review and acceptance. The no-holdout path now requires the explicit local/dev override `--allow-no-holdout`.

## Review And Bundle Notes

- `policy-review` and `policy-review-surface` now persist a review-decision artifact before returning output.
- accepted artifact pointers can now carry `source_review_decision_id` for rollback and audit lineage.
- exported training bundles now include negative samples:
  - surfaced-but-not-selected candidates
  - filtered/non-surfaced candidates when present
- exported training bundles now also include:
  - `stage_evidence_anchors`
  - `model_routes`
  - `policy_resolution`
