# {trinity}

`{trinity}` is a local-first reasoning runtime with product adapters, active memory, and provider-neutral model routing.

It is the runtime layer that turns normalized evidence plus scoped memory into ranked, decision-ready outputs. It is not the product shell, and it is not the offline optimizer.

Current release:

- `0.1.4`
- [CHANGELOG.md](/Users/Shared/Projects/trinity/CHANGELOG.md)

Current system split:

- `{trinity}` owns runtime workflow, ranking, trace export, training-bundle export, and accepted-artifact application
- `{trinity}` owns live memory retrieval, disagreement handling, bounded rework loops, and Human-in-the-Loop escalation contracts
- product repositories own ingestion, operator workflow, transport rules, approval semantics, and send execution
- `{train}` owns offline bounded optimization of exported `{trinity}` artifacts

## Current State

This repository now exposes a generic runtime seam with adapter-aware storage, provider-neutral model routing, and generic CLI routing.

Implemented today:

- reusable workflow core under [core/trinity_core/workflow](/Users/Shared/Projects/trinity/core/trinity_core/workflow)
- adapter helpers under [core/trinity_core/adapters](/Users/Shared/Projects/trinity/core/trinity_core/adapters)
- provider-neutral model adapters under [core/trinity_core/adapters/model](/Users/Shared/Projects/trinity/core/trinity_core/adapters/model)
- generic runtime facade in [core/trinity_core/runtime.py](/Users/Shared/Projects/trinity/core/trinity_core/runtime.py)
- adapter-scoped storage helpers in [core/trinity_core/ops/runtime_storage.py](/Users/Shared/Projects/trinity/core/trinity_core/ops/runtime_storage.py)
- generic CLI surface in [core/trinity_core/cli.py](/Users/Shared/Projects/trinity/core/trinity_core/cli.py)
- first mature drafting adapter for `{reply}`
- one bounded reasoning adapter slice for `{spot}`
- explicit score-governance lifecycle across acceptance, release readiness, triage queues, triage resolution, and release-decision lineage

Current restoration focus:

- keep `{reply}` stable as the first production embedding without letting it define the platform identity
- restore `{trinity}` as the proper core system around active memory, minority reports, bounded loop control, and HiTL
- create clean downstream seams for `{spot}` and future apps without leaking Reply draft semantics

Implemented adapter support:

- `reply`
- `spot` as a bounded reasoning/review slice

## Who This Repo Is For

This repository is for:

- teams integrating a downstream app with `{trinity}`
- contributors extending the runtime core
- adapter authors adding a new product embedding

If you are integrating a new app, start here:

- [docs/INTEGRATING_NEW_APP.md](/Users/Shared/Projects/trinity/docs/INTEGRATING_NEW_APP.md)
- [docs/ADAPTER_AUTHORING_GUIDE.md](/Users/Shared/Projects/trinity/docs/ADAPTER_AUTHORING_GUIDE.md)
- [docs/THIRD_APP_PREPARATION_PLAN.md](/Users/Shared/Projects/trinity/docs/THIRD_APP_PREPARATION_PLAN.md)

Implemented model-provider support:

- `deterministic`
- `ollama`
- `mistral-cli`

Current `mistral-cli` operating note:

- the initial provider implementation targets the `vibe` programmatic CLI path
- route model names remain explicit in Trinity config and trace provenance
- for this first tranche, route model names are advisory rather than enforced by the CLI itself

Compatibility guarantee:

- the generic CLI is the preferred contract
- legacy `reply-*` commands remain supported as compatibility aliases
- the Reply adapter can still read legacy `reply_runtime` storage when a machine already has that layout
- the Reply adapter can be asked for a prepared draft on conversation open and must return a usable draft by reusing a fresh prepared artifact or generating a new best-available draft immediately when the prepared artifact is missing or stale

## Repository Layout

```text
trinity/
  core/
    trinity_core/
      adapters/
        model/
      ops/
      runtime.py
      schemas/
      workflow/
  docs/
  tests/
```

Primary responsibility split:

- `workflow/`: reusable stage execution and frontier logic
- `schemas/`: canonical runtime contracts
- `adapters/`: product adapter declarations plus provider-neutral model adapters
- `memory/`: runtime-owned live memory, retrieval, and lesson handling
- `ops/`: local storage, policy lifecycle, trace export, and fixture tooling

## CLI

The CLI surface is now large enough that this README only summarizes the main categories. The authoritative command list lives in [docs/CLI_REFERENCE.md](/Users/Shared/Projects/trinity/docs/CLI_REFERENCE.md).

Preferred generic commands:

- `suggest --adapter <adapter>`
- `record-outcome --adapter <adapter>`
- `ingest-memory-event --adapter <adapter>`
- `register-document --adapter <adapter>`
- `get-prepared-draft --adapter <adapter> --company-id <company> --thread-ref <thread>`
- `refresh-prepared-draft --adapter <adapter> --company-id <company> --thread-ref <thread>`
- `plan-prepared-draft-refresh --adapter <adapter> --company-id <company>`
- `schedule-prepared-draft-refresh --adapter <adapter> --company-id <company>`
- `export-trace --adapter <adapter>`
- `export-training-bundle --adapter <adapter>`
- `runtime-status --adapter <adapter>`
- `show-config --adapter <adapter>`
- `write-config --adapter <adapter>`
- `train-status`
- `provider-smoke`
- `check-reply-compatibility`
- `gobii-status`
- `compare-providers --adapter <adapter>`
- `curate-eval-dataset --adapter <adapter> --dataset-name <name> --cycle-id <uuid> --selection-reason <reason>`
- `replay-eval-dataset --dataset-file <path>`
- `report-score-health --adapter <adapter> --report-name <name>`
- `review-score-health --report-file <path>`
- `compare-score-health --trend-report-name <name> --report-file <path> ...`
- `make-control-job --adapter <adapter>`
- `run-control-job --job-file <path>`
- `control-run-status --adapter <adapter> --run-id <uuid>`
- `make-gobii-workflow --job-file <path> --schedule <expr>`
- `make-gobii-profile-enrichment`
- `register-gobii-workflow --bundle-file <path> [options]`
- `submit-gobii-task --adapter <adapter> --prompt <text> [options]`
- `submit-gobii-profile-enrichment`
- `gobii-task-result --adapter <adapter> --task-id <id> [options]`
- `list-gobii-tasks --adapter <adapter> [options]`
- `cancel-gobii-task --adapter <adapter> --task-id <id> [options]`
- `normalize-gobii-task --adapter <adapter> --input-file <path>`
- `normalize-gobii-profile-enrichment`
- `check-score-governance --report-file <path> [--decision-file <path>] [--trend-report-file <path>]`
- `check-release-governance --report-file <path> --release-report-name <name> [--decision-file <path>]`
- `list-score-governance-work --adapter <adapter> --triage-report-name <name>`
- `resolve-score-governance-item --adapter <adapter> --item-id <id> --resolution-status <status>`
- `record-release-governance-decision --release-report-file <path> --decision-status <status>`
- `governance-status --adapter <adapter>`
- `report-cross-adapter-scores --report-name <name>`
- `report-score-governance-dashboard --report-name <name>`
- `export-post-training-dataset --adapter <adapter> --dataset-name <name>`
- `build-post-training-split --dataset-file <path> --split-name <name>`
- `curate-post-training-example --dataset-file <path> --example-id <id> --annotation-status <status> --reason <text>`
- `promote-post-training-dataset --dataset-file <path> --dataset-status <status> --reason <text>`

Current implemented examples:

- `suggest --adapter reply`
- `reason-spot --adapter spot`
- `record-spot-review-outcome --adapter spot`

Compatibility aliases:

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

Examples:

```bash
cd /Users/Shared/Projects/trinity
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply
PYTHONPATH=core uv run python -m trinity_core.cli reason-spot --adapter spot --input-file /tmp/spot-request.json
```

Policy acceptance note:

- serious policy review and acceptance flows now default to holdout replay
- no-holdout acceptance is restricted to explicit local/dev override with `--allow-no-holdout`
- score-governance can now block acceptance and release deterministically unless an operator records an explicit override
- exported training bundles now preserve negative samples and policy-resolution context so `{train}` can learn from bounded runtime artifacts without silently reinterpreting the whole trace
- the current runtime, policy, Train handoff, and shadow-fixture lanes are intentionally centered on the `{reply} <-> {trinity} <-> {train}` workflow

## Runtime Storage

Runtime data must live outside the repository working tree.

Default adapter-scoped layout for new installs:

```text
~/Library/Application Support/Trinity/trinity_runtime/adapters/<adapter>/
```

Reply compatibility behavior:

- if a machine already has `~/Library/Application Support/Trinity/reply_runtime/` and no new namespaced Reply root exists yet, `{trinity}` continues using the legacy root
- new adapter integrations use adapter-scoped paths directly

## Development

Local install and dependency setup:

- [docs/LOCAL_INSTALL.md](/Users/Shared/Projects/trinity/docs/LOCAL_INSTALL.md)

Bootstrap:

```bash
cd /Users/Shared/Projects/trinity
uv sync --dev
```

Validation:

```bash
uv run ruff check .
uv run pytest
```

Compatibility verification:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter spot
```

Native shell build:

```bash
cd /Users/Shared/Projects/trinity/apps/macos
swift build
```

## Adapter Guidance

When adding a new product adapter:

1. keep reusable workflow logic in `core/trinity_core/workflow`
2. keep product contract types and mapping logic at the adapter boundary
3. namespace storage, fixtures, and accepted artifacts by adapter
4. expose the adapter through the generic CLI before adding product-specific aliases
5. prove the abstraction with deterministic tests and fixture replay

When adding a new model provider:

1. keep workflow stages dependent on role capabilities, not provider request formats
2. put transport, process, and inventory behavior under `core/trinity_core/adapters/model`
3. keep provider-specific configuration explicit in model config and runtime status output
4. preserve deterministic fallback as a valid operational mode
5. prove the provider through adapter-agnostic tests before adding more providers

Do not:

- move transport or approval semantics into runtime core
- broaden core schemas with product-only fields unless at least two adapters need them
- leak one product's semantics into another through hidden memory reuse
- use repository-local runtime data as the default storage path

## Read First

- [docs/STATUS.md](/Users/Shared/Projects/trinity/docs/STATUS.md)
- [docs/TRINITY_RESTORATION_PLAN.md](/Users/Shared/Projects/trinity/docs/TRINITY_RESTORATION_PLAN.md)
- [docs/TRINITY_CORE_LOOP.md](/Users/Shared/Projects/trinity/docs/TRINITY_CORE_LOOP.md)
- [docs/MEMORY_ARCHITECTURE.md](/Users/Shared/Projects/trinity/docs/MEMORY_ARCHITECTURE.md)
- [docs/MINORITY_REPORT_CONTRACT.md](/Users/Shared/Projects/trinity/docs/MINORITY_REPORT_CONTRACT.md)
- [docs/HITL_ESCALATION_CONTRACT.md](/Users/Shared/Projects/trinity/docs/HITL_ESCALATION_CONTRACT.md)
- [docs/REPOSITORY_CONTRACT.md](/Users/Shared/Projects/trinity/docs/REPOSITORY_CONTRACT.md)
- [docs/PROVIDER_COMPARISON_HARNESS.md](/Users/Shared/Projects/trinity/docs/PROVIDER_COMPARISON_HARNESS.md)
- [docs/PRODUCTION_TRACE_EVAL_DATASETS.md](/Users/Shared/Projects/trinity/docs/PRODUCTION_TRACE_EVAL_DATASETS.md)
- [docs/LIVE_BRAIN_RUNTIME_ARCHITECTURE.md](/Users/Shared/Projects/trinity/docs/LIVE_BRAIN_RUNTIME_ARCHITECTURE.md)
- [docs/CONTROL_PLANE_SEAM.md](/Users/Shared/Projects/trinity/docs/CONTROL_PLANE_SEAM.md)
- [docs/GOBII_RECURRING_WORKFLOW.md](/Users/Shared/Projects/trinity/docs/GOBII_RECURRING_WORKFLOW.md)
- [docs/GOBII_NORMALIZATION_CONTRACT.md](/Users/Shared/Projects/trinity/docs/GOBII_NORMALIZATION_CONTRACT.md)
- [docs/GOBII_PROFILE_ENRICHMENT_WORKFLOW.md](/Users/Shared/Projects/trinity/docs/GOBII_PROFILE_ENRICHMENT_WORKFLOW.md)
- [docs/TRINITY_OVERVIEW.md](/Users/Shared/Projects/trinity/docs/TRINITY_OVERVIEW.md)
- [docs/RELATIONSHIP_HEALTH.md](/Users/Shared/Projects/trinity/docs/RELATIONSHIP_HEALTH.md)
- [docs/RELATIONSHIP_HARDENING_PLAN.md](/Users/Shared/Projects/trinity/docs/RELATIONSHIP_HARDENING_PLAN.md)
- [docs/CLI_REFERENCE.md](/Users/Shared/Projects/trinity/docs/CLI_REFERENCE.md)
- [docs/LOCAL_INSTALL.md](/Users/Shared/Projects/trinity/docs/LOCAL_INSTALL.md)
- [docs/INTEGRATING_NEW_APP.md](/Users/Shared/Projects/trinity/docs/INTEGRATING_NEW_APP.md)
- [docs/ADAPTER_AUTHORING_GUIDE.md](/Users/Shared/Projects/trinity/docs/ADAPTER_AUTHORING_GUIDE.md)
- [docs/REPLY_PRODUCT_ADAPTER_CONTRACT.md](/Users/Shared/Projects/trinity/docs/REPLY_PRODUCT_ADAPTER_CONTRACT.md)
- [docs/REPLY_TRINITY_TRAIN_OPERATING_CONTRACT.md](/Users/Shared/Projects/trinity/docs/REPLY_TRINITY_TRAIN_OPERATING_CONTRACT.md)
- [docs/POLICY_LOOP_REPO_BREAKDOWN.md](/Users/Shared/Projects/trinity/docs/POLICY_LOOP_REPO_BREAKDOWN.md)

## License

This repository is licensed under `Apache-2.0`.
