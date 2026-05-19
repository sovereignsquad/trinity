# CLI Reference

## Purpose

This document lists the current public CLI surface for `{trinity}`.

Current repository release:

- `0.1.4`

## Preferred Generic Commands

All new integrations should use the generic commands with explicit adapter selection.

Important:

- generic command names do not imply every adapter supports every command
- command support is adapter-specific and should fail explicitly when a flow is not implemented for that adapter
- do not treat `reply` examples as the default shape for a new downstream app

Programmatic runtime surface:

- the stable local programmatic entrypoint remains `TrinityRuntime(adapter_name=...)`
- the CLI is the primary public operator contract
- governance operations now extend that contract through acceptance, release, triage, resolution, and release-decision commands

Runtime-status contract note:

- `runtime-status` now emits machine-readable contract metadata and readiness state, not just provider/config fragments
- downstream apps should treat `contract_version`, `status_schema_version`, and `readiness` as the primary compatibility surface for runtime supervision
- CLI failures now emit machine-readable JSON error payloads on `stderr` with `contract_version`, `error_schema_version`, and structured `error.*` fields instead of relying on raw traceback parsing

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
- `report-score-health --adapter <adapter> --report-name <name> [--cycle-id <uuid> ... | --trace-file <path> ...] [--selection-reason <reason>]`
- `review-score-health --report-file <path> [--replay-report-file <path>] [--decision-status <status>] [--decision-notes <notes>]`
- `compare-score-health --trend-report-name <name> --report-file <path> ... [--selection-reason <reason>]`
- `check-score-governance --report-file <path> [--decision-file <path>] [--trend-report-file <path>] [threshold options]`
- `check-release-governance --report-file <path> --release-report-name <name> [--decision-file <path>] [--trend-report-file <path>] [--replay-report-file <path>] [threshold options]`
- `list-score-governance-work --adapter <adapter> --triage-report-name <name> [--selection-reason <reason>]`
- `resolve-score-governance-item --adapter <adapter> --item-id <id> --resolution-status <status> [--notes <text>]`
- `record-release-governance-decision --release-report-file <path> --decision-status <status> [--notes <text>]`
- `governance-status --adapter <adapter>`
- `report-cross-adapter-scores --report-name <name> [--adapter <adapter> ...] [--top-n <n>]`
- `report-score-governance-dashboard --report-name <name> [--adapter <adapter> ...]`
- `export-post-training-dataset --adapter <adapter> --dataset-name <name> [--bundle-file <path> ... | --cycle-id <uuid> ... --bundle-type <type>] [--purpose <purpose> ...]`
- `build-post-training-split --dataset-file <path> --split-name <name> [--validation-ratio <ratio>] [--holdout-ratio <ratio>]`
- `curate-post-training-example --dataset-file <path> --example-id <id> --annotation-status <status> --reason <text>`
- `promote-post-training-dataset --dataset-file <path> --dataset-status <status> --reason <text>`
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
- `report-score-health --adapter reply --report-name <name> [--cycle-id <uuid> ... | --trace-file <path> ...] [--selection-reason <reason>]`
- `review-score-health --report-file <path> [--replay-report-file <path>] [--decision-status <status>] [--decision-notes <notes>]`
- `compare-score-health --trend-report-name <name> --report-file <path> ... [--selection-reason <reason>]`
- `check-score-governance --report-file <path> [--decision-file <path>] [--trend-report-file <path>] [threshold options]`
- `check-release-governance --report-file <path> --release-report-name <name> [--decision-file <path>] [--trend-report-file <path>] [--replay-report-file <path>] [threshold options]`
- `list-score-governance-work --adapter reply --triage-report-name <name> [--selection-reason <reason>]`
- `resolve-score-governance-item --adapter reply --item-id <id> --resolution-status <status> [--notes <text>]`
- `record-release-governance-decision --release-report-file <path> --decision-status <status> [--notes <text>]`
- `governance-status --adapter reply`
- `report-cross-adapter-scores --report-name <name> [--adapter reply --adapter spot] [--top-n <n>]`
- `report-score-governance-dashboard --report-name <name> [--adapter reply --adapter spot]`
- `export-post-training-dataset --adapter reply --dataset-name <name> [--bundle-file <path> ... | --cycle-id <uuid> ... --bundle-type <type>]`
- `build-post-training-split --dataset-file <path> --split-name <name> [--validation-ratio <ratio>] [--holdout-ratio <ratio>]`
- `curate-post-training-example --dataset-file <path> --example-id <id> --annotation-status <status> --reason <text>`
- `promote-post-training-dataset --dataset-file <path> --dataset-status <status> --reason <text>`
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
- `export-post-training-dataset --adapter spot --dataset-name <name> [--bundle-file <path> ... | --cycle-id <uuid> ... --bundle-type spot-review-policy-learning]`

Reply-only extended runtime operations:

- `export-training-bundle --adapter reply --cycle-id <uuid> --bundle-type <type>`
- `train-propose-policy --adapter reply --learner-kind <kind> [--cycle-id <uuid> ... | --bundle-file <path> ...]`
- `train-propose-policy --adapter reply --learner-kind <kind> [--score-health-report-file <path>] [--score-health-decision-file <path>] [--score-health-trend-report-file <path>]`

### Reply-Only Policy Operations

- `policy-review --adapter reply --policy-file <path> --bundle-file <path> [--holdout-bundle-file <path> ...]`
- `policy-review-surface --adapter reply --policy-file <path> --bundle-file <path> [--holdout-bundle-file <path> ...]`
- `policy-accept --adapter reply --policy-file <path> --bundle-file <path> [--holdout-bundle-file <path> ...]`
- `policy-accept --adapter reply --policy-file <path> --bundle-file <path> [--score-health-report-file <path>] [--score-health-decision-file <path>] [--score-health-trend-report-file <path>] [--release-governance-report-file <path>] [--release-governance-decision-status <status>] [--allow-score-governance-override --score-governance-override-note <text>]`
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

## Runtime-Status Payload

`runtime-status --adapter <adapter>` now returns a JSON payload that includes:

- `contract_version`
- `status_schema_version`
- `command`
- `generated_at`
- `provider_inventory_supported`
- `provider_status`
- `provider_error`
- `shared_model_inventory`
- `readiness`

The `shared_model_inventory` object includes:

- `enabled`
- `manifest_version`
- `models_root`
- `manifest_path`
- `entry_count`
- `error`

Each role payload now also carries:

- `model`
- `model_id`
- `inventory_found`
- `inventory_model_id`
- `inventory_path`
- `inventory_format`
- `inventory_status`

Current inventory-status values include:

- `unknown`
- `present`
- `missing`
- `provider_managed`
- `inventory_disabled`

Reply trace and training-bundle artifacts now also preserve `model_route_details`, which include:

- `provider`
- `model`
- `model_id`

The `readiness` object includes:

- `ready`
- `state`
- `reasons`
- `role_readiness`
- `can_suggest`
- `can_get_prepared_draft`
- `can_record_outcome`
- `can_ingest_memory_event`
- `can_register_document`

Current readiness states include:

- `ready`
- `configured`
- `degraded`
- `offline`
- `unsupported`
- `not_configured`
- `disabled`

CLI failure payloads now follow the same contract family on `stderr` and include:

- `ok`
- `contract_version`
- `error_schema_version`
- `generated_at`
- `error.code`
- `error.type`
- `error.message`
- `error.command`
- `error.adapter` when applicable

## Example

```bash
cd /Users/Shared/Projects/trinity
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply
PYTHONPATH=core uv run python -m trinity_core.cli reason-spot --adapter spot --input-file /tmp/spot-request.json
PYTHONPATH=core uv run python -m trinity_core.cli show-config --adapter spot
PYTHONPATH=core uv run python -m trinity_core.cli compare-providers --adapter reply --include-deterministic-baseline --include-current-config
PYTHONPATH=core uv run python -m trinity_core.cli curate-eval-dataset --adapter reply --dataset-name "Reply Production Trace Goldens" --cycle-id <uuid> --selection-reason "human-reviewed gold trace"
PYTHONPATH=core uv run python -m trinity_core.cli replay-eval-dataset --dataset-file /tmp/reply-production-trace-goldens.json
PYTHONPATH=core uv run python -m trinity_core.cli report-score-health --adapter reply --report-name "Reply Score Health" --cycle-id <uuid> --selection-reason "manual governance review"
PYTHONPATH=core uv run python -m trinity_core.cli review-score-health --report-file /tmp/reply-score-health.json --replay-report-file /tmp/reply-production-trace-goldens-report.json
PYTHONPATH=core uv run python -m trinity_core.cli compare-score-health --trend-report-name "Reply Score Health Trend" --report-file /tmp/reply-score-health-a.json --report-file /tmp/reply-score-health-b.json
PYTHONPATH=core uv run python -m trinity_core.cli check-score-governance --report-file /tmp/reply-score-health.json --decision-file /tmp/reply-score-health-decision.json --trend-report-file /tmp/reply-score-health-trend.json
PYTHONPATH=core uv run python -m trinity_core.cli check-release-governance --report-file /tmp/reply-score-health.json --decision-file /tmp/reply-score-health-decision.json --release-report-name "Reply Release Governance"
PYTHONPATH=core uv run python -m trinity_core.cli list-score-governance-work --adapter reply --triage-report-name "Reply Governance Work"
PYTHONPATH=core uv run python -m trinity_core.cli resolve-score-governance-item --adapter reply --item-id decision-reply-score-health-investigate --resolution-status resolved --notes "Operator handled this item."
PYTHONPATH=core uv run python -m trinity_core.cli record-release-governance-decision --release-report-file /tmp/reply-release-governance.json --decision-status override_release --notes "Approved with explicit exception."
PYTHONPATH=core uv run python -m trinity_core.cli governance-status --adapter reply
PYTHONPATH=core uv run python -m trinity_core.cli report-cross-adapter-scores --report-name "Cross Adapter Scores" --adapter reply --adapter spot --top-n 25
PYTHONPATH=core uv run python -m trinity_core.cli report-score-governance-dashboard --report-name "Governance Dashboard" --adapter reply --adapter spot
PYTHONPATH=core uv run python -m trinity_core.cli export-post-training-dataset --adapter reply --dataset-name "Reply Local Learning" --cycle-id <uuid> --bundle-type tone-learning
PYTHONPATH=core uv run python -m trinity_core.cli curate-post-training-example --dataset-file /tmp/reply-local-learning.json --example-id reply-negative-... --annotation-status excluded --reason "Operator excluded this sample."
PYTHONPATH=core uv run python -m trinity_core.cli promote-post-training-dataset --dataset-file /tmp/reply-local-learning.json --dataset-status curated --reason "Approved for split generation."
PYTHONPATH=core uv run python -m trinity_core.cli build-post-training-split --dataset-file /tmp/reply-local-learning.json --split-name "Reply Local Learning Split"
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
PYTHONPATH=core uv run python -m trinity_core.cli policy-accept --adapter reply --policy-file /tmp/proposal.json --bundle-file /tmp/proposal-bundle.json --holdout-bundle-file /tmp/holdout-bundle.json --score-health-report-file /tmp/reply-score-health.json --score-health-decision-file /tmp/reply-score-health-decision.json
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
- `export-post-training-dataset` is now the first bounded post-training artifact seam: it builds a Trinity-owned dataset from existing training bundles for Reply or Spot, but it does not choose or run a training backend
- `build-post-training-split` now adds deterministic `train` / `validation` / `holdout` assignments on top of that dataset contract while skipping explicitly excluded examples
- candidate post-training datasets are now first-class lifecycle artifacts: `curate-post-training-example` persists per-example curation decisions, `promote-post-training-dataset` moves datasets from `candidate` to `curated` or `ready`, and `build-post-training-split` now refuses to split unpromoted candidate datasets
- it replays bounded Reply shadow fixtures
- it persists report artifacts under the adapter runtime root

Current eval-dataset note:

- curated eval datasets are explicit promotions from persisted runtime traces
- replay is currently Reply-only
- this slice exists to compound real reviewed runs into reusable replay corpora without mutating live runtime policy

Current score-health note:

- `report-score-health` builds one explicit governance artifact from persisted traces
- `review-score-health` turns that artifact into a triage-ready review surface and can optionally correlate it with one replay report
- `review-score-health` can now also persist a review-decision artifact when given a decision status
- `compare-score-health` builds a bounded trend report across multiple score-health reports
- `check-score-governance` evaluates one report plus optional decision/trend artifacts into a deterministic workflow gate result
- `check-release-governance` turns those same inputs into one persisted release-readiness artifact with release risk and operator recommendation
- `list-score-governance-work` builds one persisted triage queue from unresolved review decisions, risky trend reports, and accepted-artifact override history
- `resolve-score-governance-item` lets operators suppress or close triage work explicitly through persisted resolution artifacts
- `record-release-governance-decision` links the actual operator release call back to the release-governance report used
- `governance-status` joins the latest review status, release status, triage counts, and accepted-artifact governance lineage for one adapter
- `report-cross-adapter-scores` compares ICE, frontier-priority semantics, audit flags, and latest adapter governance state across persisted Reply and Spot traces
- `report-score-governance-dashboard` aggregates rising flags, recurring tuple clusters, unresolved triage work, and override churn across adapters
- it aggregates runtime score-audit flags and recurring final-score tuples
- acceptance flows can now consume those artifacts through `policy-accept` and `train-propose-policy --accept`, block by default on configured governance failures, and persist override provenance when an operator proceeds anyway
- when acceptance flows use score-governance artifacts, they now also require a release-governance report file and persist a linked release decision artifact during acceptance
- release and operator triage can now consume the same artifact family through explicit CLI surfaces instead of bespoke analysis

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
