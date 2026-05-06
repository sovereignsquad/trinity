# CLI Reference

## Purpose

This document lists the current public CLI surface for `{trinity}`.

## Preferred Generic Commands

All new integrations should use the generic commands with explicit adapter selection.

### Runtime Operations

- `suggest --adapter <adapter>`
- `record-outcome --adapter <adapter>`
- `export-trace --adapter <adapter> --cycle-id <uuid>`
- `export-training-bundle --adapter <adapter> --cycle-id <uuid> --bundle-type <type>`
- `runtime-status --adapter <adapter>`
- `show-config --adapter <adapter> [--include-path]`
- `write-config --adapter <adapter> [options]`

### Policy Operations

- `policy-accept --adapter <adapter> --policy-file <path> --bundle-file <path>`
- `policy-promote --adapter <adapter> --artifact-key <key> --version <version> --source-project <project>`
- `policy-rollback --adapter <adapter> --artifact-key <key> [--target-version <version>]`
- `policy-status --adapter <adapter> --artifact-key <key>`

### Fixture Operations

- `run-shadow-fixtures --adapter <adapter> [--fixture-dir <dir>]`

## Reply Compatibility Aliases

The following commands remain supported for the Reply adapter:

- `reply-suggest`
- `reply-record-outcome`
- `reply-export-trace`
- `reply-export-training-bundle`
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
```

## Current Constraint

Only the `reply` adapter is implemented today. Unsupported adapters fail fast with an explicit error.
