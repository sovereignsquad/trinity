# CLI Reference

## Purpose

This document lists the current public CLI surface for `{trinity}`.

Current release:

- `0.1.4`

## Contract Notes

- generic commands are the primary public contract
- adapter selection is explicit through `--adapter`
- Reply compatibility aliases remain supported for downstream safety
- CLI failures emit structured JSON error payloads
- `runtime-status` is the main supervision surface for adapter/provider readiness

Programmatic entrypoint:

- `TrinityRuntime(adapter_name=...)`

Authoritative command discovery:

```bash
cd /Users/Shared/Projects/trinity
PYTHONPATH=core uv run python -m trinity_core.cli --help
```

## Generic Commands

### Runtime

- `suggest --adapter <adapter>`
- `record-outcome --adapter <adapter>`
- `ingest-memory-event --adapter <adapter>`
- `register-document --adapter <adapter>`
- `get-prepared-draft --adapter <adapter> --company-id <company> --thread-ref <thread>`
- `refresh-prepared-draft --adapter <adapter> --company-id <company> --thread-ref <thread>`
- `plan-prepared-draft-refresh --adapter <adapter> --company-id <company>`
- `schedule-prepared-draft-refresh --adapter <adapter> --company-id <company>`
- `export-trace --adapter <adapter> --cycle-id <uuid>`
- `show-config --adapter <adapter> [--include-path]`
- `show-foundation-policy [--include-path]`
- `runtime-status --adapter <adapter>`
- `foundation-check --adapter <adapter> [preflight options]`
- `write-config --adapter <adapter> [provider options]`
- `write-foundation-policy [policy options]`

### Relation Health

- `train-status [--transport <api|cli|both>] [--train-api-base-url <url>] [--train-root-dir <path>]`
- `provider-smoke --adapter <adapter> [--role <generator|refiner|evaluator> ...] [--inventory-only]`
- `check-reply-compatibility [--reply-root-dir <path>]`
- `gobii-status --adapter <adapter> [--gobii-api-base-url <url>] [--api-key-env <name>] [--check-live]`

### Governance And Scoring

- `report-score-health --adapter <adapter> --report-name <name>`
- `review-score-health --report-file <path>`
- `compare-score-health --trend-report-name <name> --report-file <path> ...`
- `check-score-governance --report-file <path>`
- `check-release-governance --report-file <path> --release-report-name <name>`
- `list-score-governance-work --adapter <adapter> --triage-report-name <name>`
- `resolve-score-governance-item --adapter <adapter> --item-id <id> --resolution-status <status>`
- `record-release-governance-decision --release-report-file <path> --decision-status <status>`
- `governance-status --adapter <adapter>`
- `report-cross-adapter-scores --report-name <name> [--adapter <adapter> ...]`
- `report-score-governance-dashboard --report-name <name> [--adapter <adapter> ...]`

### Training And Policy

- `export-training-bundle --adapter <adapter> --cycle-id <uuid> --bundle-type <type>`
- `train-propose-policy --adapter <adapter> --learner-kind <kind> [source options]`
- `policy-review --adapter <adapter> --policy-file <path> --bundle-file <path>`
- `policy-review-surface --adapter <adapter> --policy-file <path> --bundle-file <path>`
- `policy-accept --adapter <adapter> --policy-file <path> --bundle-file <path>`
- `policy-promote --adapter <adapter> --artifact-key <key> --version <version> --source-project <project>`
- `policy-rollback --adapter <adapter> --artifact-key <key>`
- `policy-status --adapter <adapter> --artifact-key <key>`

Current release-gate rule:

- `policy-promote` now runs `foundation-check` by default and requires an explicit bypass note to skip it

### Evaluation And Post-Training Datasets

- `curate-eval-dataset --adapter <adapter> [trace selection options] --selection-reason <reason>`
- `replay-eval-dataset --dataset-file <path>`
- `export-post-training-dataset --adapter <adapter> --dataset-name <name> [bundle or cycle options]`
- `build-post-training-split --dataset-file <path> --split-name <name>`
- `curate-post-training-example --dataset-file <path> --example-id <id> --annotation-status <status> --reason <text>`
- `promote-post-training-dataset --dataset-file <path> --dataset-status <status> --reason <text>`

### Provider Comparison And Control Plane

- `run-shadow-fixtures --adapter <adapter> [--fixture-dir <dir>]`
- `compare-providers --adapter <adapter> [comparison options]`
- `make-control-job --adapter <adapter> [job options]`
- `run-control-job --job-file <path>`
- `control-run-status --adapter <adapter> --run-id <uuid>`

### Gobii Workflows, Tasks, And Enrichment

- `make-gobii-workflow --job-file <path> --schedule <expr>`
- `register-gobii-workflow --bundle-file <path> [options]`
- `submit-gobii-task --adapter <adapter> --prompt <text> [options]`
- `gobii-task-result --adapter <adapter> --task-id <id> [options]`
- `list-gobii-tasks --adapter <adapter> [options]`
- `cancel-gobii-task --adapter <adapter> --task-id <id> [options]`
- `normalize-gobii-task --adapter <adapter> --input-file <path>`
- `make-gobii-profile-enrichment [bundle options]`
- `submit-gobii-profile-enrichment [submission options]`
- `normalize-gobii-profile-enrichment [normalization options]`

## Adapter-Specific Commands

### Spot

- `reason-spot --adapter spot --input-file <path>`
- `record-spot-review-outcome --adapter spot --input-file <path>`

### Reply Compatibility Aliases

- `reply-suggest`
- `reply-record-outcome`
- `reply-ingest-memory-event`
- `reply-register-document`
- `reply-get-prepared-draft`
- `reply-refresh-prepared-draft`
- `reply-export-trace`
- `reply-export-training-bundle`
- `reply-run-shadow-fixtures`
- `reply-train-propose-policy`
- `reply-policy-accept`
- `reply-policy-review`
- `reply-policy-review-surface`
- `reply-policy-promote`
- `reply-policy-rollback`
- `reply-policy-status`
- `reply-show-config`
- `reply-runtime-status`
- `reply-write-config`

## Runtime-Status Payload

`runtime-status --adapter <adapter>` returns a machine-readable JSON payload that includes:

- `contract_version`
- `status_schema_version`
- `command`
- `generated_at`
- `provider`
- `provider_status`
- `provider_error`
- `provider_error_code`
- `provider_inventory_supported`
- `foundation_policy`
- `shared_model_inventory`
- `readiness`
- `roles`

Current `status_schema_version`:

- `5`

Current readiness states include:

- `ready`
- `configured`
- `degraded`
- `offline`
- `unsupported`
- `not_configured`
- `disabled`

Each role payload includes:

- `provider`
- `model`
- `model_id`
- `temperature`
- `keep_alive`
- `inventory_found`
- `inventory_model_id`
- `inventory_path`
- `inventory_format`
- `inventory_status`

Current `inventory_status` values:

- `unknown`
- `present`
- `missing`
- `provider_managed`
- `inventory_disabled`

## Seam-Health Contracts

Current contract versions:

- `trinity_train_status.v1`
- `trinity_provider_smoke.v1`
- `trinity_reply_compat.v1`
- `trinity_gobii_status.v1`
- `trinity_foundation_policy.v1`
- `trinity_foundation_check.v1`

## Examples

```bash
cd /Users/Shared/Projects/trinity
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply
PYTHONPATH=core uv run python -m trinity_core.cli show-foundation-policy --include-path
PYTHONPATH=core uv run python -m trinity_core.cli train-status --transport both
PYTHONPATH=core uv run python -m trinity_core.cli foundation-check --adapter reply --check-gobii-live
PYTHONPATH=core uv run python -m trinity_core.cli provider-smoke --adapter reply --role generator
PYTHONPATH=core uv run python -m trinity_core.cli check-reply-compatibility --reply-root-dir /Users/Shared/Projects/reply
PYTHONPATH=core uv run python -m trinity_core.cli gobii-status --adapter reply --check-live
PYTHONPATH=core uv run python -m trinity_core.cli reason-spot --adapter spot --input-file /tmp/spot-request.json
```

## Current Constraints

- `reply` is still the only full downstream workflow
- `spot` remains bounded
- Train policy now defaults to `cli`
- Reply's preferred live provider policy is `mistral-cli`
- provider comparison and eval replay remain Reply-centric
- `mistral-cli` remains the bounded `vibe` path
- Gobii remains optional and should not be treated as a base runtime dependency
