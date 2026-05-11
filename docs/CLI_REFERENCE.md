# CLI Reference

## Purpose

This document lists the current public CLI surface for `{trinity}`.

## Preferred Generic Commands

All new integrations should use the generic commands with explicit adapter selection.

Important:

- generic command names do not imply every adapter supports every command
- command support is adapter-specific and should fail explicitly when a flow is not implemented for that adapter
- do not treat `reply` examples as the default shape for a new downstream app

### Runtime Operations

- `suggest --adapter <adapter>`
- `record-outcome --adapter <adapter>`
- `ingest-memory-event --adapter <adapter>`
- `register-document --adapter <adapter>`
- `get-prepared-draft --adapter <adapter> --company-id <company> --thread-ref <thread>`
- `refresh-prepared-draft --adapter <adapter> --company-id <company> --thread-ref <thread> [--reason <reason>] [--overwrite-mode <mode>]`
- `plan-prepared-draft-refresh --adapter <adapter> --company-id <company> [--limit <n>] [--stale-after-minutes <n>]`
- `schedule-prepared-draft-refresh --adapter <adapter> --company-id <company> [--limit <n>] [--stale-after-minutes <n>]`
- `export-trace --adapter <adapter> --cycle-id <uuid>`
- `runtime-status --adapter <adapter>`
- `show-config --adapter <adapter> [--include-path]`
- `write-config --adapter <adapter> [options]`
- `compare-providers --adapter <adapter> [options]`
- `curate-eval-dataset --adapter <adapter> [--cycle-id <uuid> ... | --trace-file <path> ...] --selection-reason <reason> [--dataset-name <name> | --dataset-file <path>]`
- `replay-eval-dataset --dataset-file <path>`
- `make-control-job --adapter <adapter> [options]`
- `run-control-job --job-file <path>`
- `control-run-status --adapter <adapter> --run-id <uuid>`
- `make-gobii-workflow --job-file <path> --schedule <expr>`
- `register-gobii-workflow --bundle-file <path> [options]`
- `submit-gobii-task --adapter <adapter> --prompt <text> [options]`
- `gobii-task-result --adapter <adapter> --task-id <id> [options]`
- `list-gobii-tasks --adapter <adapter> [options]`
- `cancel-gobii-task --adapter <adapter> --task-id <id> [options]`
- `normalize-gobii-task --adapter <adapter> --input-file <path>`

Current implemented Reply drafting path:

- `suggest --adapter reply`
- `record-outcome --adapter reply`
- `ingest-memory-event --adapter reply`
- `register-document --adapter reply`
- `get-prepared-draft --adapter reply --company-id <company> --thread-ref <thread>`
- `refresh-prepared-draft --adapter reply --company-id <company> --thread-ref <thread> [--reason <reason>] [--overwrite-mode <mode>]`
- `plan-prepared-draft-refresh --adapter reply --company-id <company> [--limit <n>] [--stale-after-minutes <n>]`
- `schedule-prepared-draft-refresh --adapter reply --company-id <company> [--limit <n>] [--stale-after-minutes <n>]`
- `export-trace --adapter reply --cycle-id <uuid>`
- `runtime-status --adapter reply`
- `show-config --adapter reply [--include-path]`
- `write-config --adapter reply [options]`
- `compare-providers --adapter reply [options]`
- `curate-eval-dataset --adapter reply [--cycle-id <uuid> ... | --trace-file <path> ...] --selection-reason <reason> [--dataset-name <name> | --dataset-file <path>]`
- `replay-eval-dataset --dataset-file <path>`
- `make-control-job --adapter reply [options]`
- `run-control-job --job-file <path>`
- `control-run-status --adapter reply --run-id <uuid>`
- `make-gobii-workflow --job-file <path> --schedule <expr>`
- `register-gobii-workflow --bundle-file <path> [options]`
- `submit-gobii-task --adapter reply --prompt <text> [options]`
- `gobii-task-result --adapter reply --task-id <id> [options]`
- `list-gobii-tasks --adapter reply [options]`
- `cancel-gobii-task --adapter reply --task-id <id> [options]`
- `normalize-gobii-task --adapter reply --input-file <path>`

Current implemented Spot reasoning path:

- `reason-spot --adapter spot --input-file <path>`
- `record-spot-review-outcome --adapter spot --input-file <path>`
- `export-training-bundle --adapter spot --cycle-id <uuid> --bundle-type spot-review-policy-learning`

Reply-only extended runtime operations:

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
- `reply-ingest-memory-event`
- `reply-register-document`
- `reply-get-prepared-draft`
- `reply-refresh-prepared-draft`
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
PYTHONPATH=core uv run python -m trinity_core.cli reason-spot --adapter spot --input-file /tmp/spot-request.json
PYTHONPATH=core uv run python -m trinity_core.cli show-config --adapter spot
PYTHONPATH=core uv run python -m trinity_core.cli compare-providers --adapter reply --include-deterministic-baseline --include-current-config
PYTHONPATH=core uv run python -m trinity_core.cli curate-eval-dataset --adapter reply --dataset-name "Reply Production Trace Goldens" --cycle-id <uuid> --selection-reason "human-reviewed gold trace"
PYTHONPATH=core uv run python -m trinity_core.cli replay-eval-dataset --dataset-file /tmp/reply-production-trace-goldens.json
PYTHONPATH=core uv run python -m trinity_core.cli make-control-job --adapter reply --job-kind reply_provider_comparison --job-id nightly-shadow --include-current-config --include-deterministic-baseline
PYTHONPATH=core uv run python -m trinity_core.cli run-control-job --job-file /tmp/nightly-shadow.json
PYTHONPATH=core uv run python -m trinity_core.cli make-gobii-workflow --job-file /tmp/nightly-shadow.json --schedule "@daily"
PYTHONPATH=core uv run python -m trinity_core.cli submit-gobii-task --adapter reply --company-id <company-uuid> --prompt "Run the nightly benchmark now" --agent-id <agent-id>
PYTHONPATH=core uv run python -m trinity_core.cli normalize-gobii-task --adapter reply --input-file /tmp/gobii-normalization.json
PYTHONPATH=core uv run python -m trinity_core.cli suggest --adapter reply --input-file /tmp/thread.json
PYTHONPATH=core uv run python -m trinity_core.cli ingest-memory-event --adapter reply --input-file /tmp/memory-event.json
PYTHONPATH=core uv run python -m trinity_core.cli register-document --adapter reply --input-file /tmp/document.json
PYTHONPATH=core uv run python -m trinity_core.cli get-prepared-draft --adapter reply --company-id acme --thread-ref thread-123
PYTHONPATH=core uv run python -m trinity_core.cli refresh-prepared-draft --adapter reply --company-id acme --thread-ref thread-123 --reason thread_open --overwrite-mode if_stale_or_dirty
PYTHONPATH=core uv run python -m trinity_core.cli plan-prepared-draft-refresh --adapter reply --company-id acme --limit 5
PYTHONPATH=core uv run python -m trinity_core.cli schedule-prepared-draft-refresh --adapter reply --company-id acme --limit 5 --reason scheduled_active_thread_refresh
PYTHONPATH=core uv run python -m trinity_core.cli train-propose-policy --adapter reply --cycle-id <uuid> --bundle-type tone-learning --learner-kind tone --transport cli --accept --holdout-bundle-file /tmp/holdout-bundle.json
PYTHONPATH=core uv run python -m trinity_core.cli policy-review-surface --adapter reply --policy-file /tmp/proposal.json --bundle-file /tmp/proposal-bundle.json --holdout-bundle-file /tmp/holdout-bundle.json
PYTHONPATH=core uv run python -m trinity_core.cli policy-accept --adapter reply --policy-file /tmp/proposal.json --bundle-file /tmp/proposal-bundle.json --holdout-bundle-file /tmp/holdout-bundle.json
```

## Current Constraint

Implemented adapters today:

- `reply`
- `spot`

If you are integrating a new app, the correct path is to add a new adapter rather than reusing `reply` by default.

See:

- [docs/INTEGRATING_NEW_APP.md](/Users/Shared/Projects/trinity/docs/INTEGRATING_NEW_APP.md)

Implemented model providers today:

- `deterministic`
- `ollama`
- `mistral-cli`

Current `mistral-cli` note:

- the first provider slice targets the `vibe` programmatic CLI path
- route model names remain explicit in Trinity config and trace provenance
- route model names are currently advisory rather than enforced by the CLI itself

Current comparison-harness note:

- the first `compare-providers` slice is Reply-only
- it replays bounded Reply shadow fixtures
- it persists report artifacts under the adapter runtime root

Current eval-dataset note:

- curated eval datasets are explicit promotions from persisted runtime traces
- replay is currently Reply-only
- this slice exists to compound real reviewed runs into reusable replay corpora without mutating live runtime policy

Current control-plane note:

- the first control-plane seam is job-file driven, not daemon-driven
- it currently supports bounded provider comparison and prepared-draft refresh jobs
- it records explicit run artifacts instead of hiding recurring work in scheduler state only
- active-thread refresh scheduling is now explicit and file-driven through `schedule-prepared-draft-refresh`; it materializes per-thread refresh jobs, but it is still not a resident scheduler

Current Gobii recurring-workflow note:

- the first Gobii proof packages only `reply_provider_comparison` jobs
- Gobii holds recurrence and agent lifecycle; Trinity still owns the runtime job, run artifact, and comparison report
- local deterministic replay remains available through the equivalent control-plane trigger command

Current Gobii task-lifecycle note:

- the task client is a bounded ops surface only
- task records are persisted under the adapter runtime root for recovery
- task records may now carry explicit adapter/company binding for later safe ingestion
- task lifecycle support does not turn Gobii into the Trinity runtime owner

Current Gobii normalization note:

- normalization is explicit and file-driven through `normalize-gobii-task`
- only completed, bound Gobii task records may enter runtime state
- the first normalization slice persists a document, retrieval chunk, memory event, and bounded evidence bundle

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
