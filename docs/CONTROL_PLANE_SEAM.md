# Control Plane Seam

## Purpose

This document defines the bounded control-plane seam for `{trinity}` recurring work.

The control plane exists so replay, refresh, and benchmark workflows can run repeatedly
without embedding scheduler ownership inside `workflow.*` or product adapters.

## Ownership Split

Control plane owns:

- job definitions
- run execution records
- scheduling hints
- run status, failure reason, and output references
- launching bounded runtime or ops workflows

Runtime owns:

- reasoning
- memory boundaries
- traces
- prepared-draft artifacts
- provider comparison artifacts
- policy acceptance and promotion rules

The control plane may trigger runtime work. It does not take over runtime ownership.

## Current Job Kinds

Implemented today:

- `reply_provider_comparison`
- `reply_prepared_draft_refresh`

These are intentionally narrow.

They prove:

- explicit job contracts
- persisted run artifacts
- inspectable success/failure metadata
- one recurring benchmark lane
- one recurring refresh lane

before any stronger scheduler substrate is attached.

## Persistence Layout

Control-plane artifacts live under the adapter runtime root:

- `control_plane/jobs/<job_id>.json`
- `control_plane/runs/<run_id>.json`

This keeps orchestration artifacts local-first and adapter-scoped.

## CLI

Current commands:

- `make-control-job --adapter reply ...`
- `run-control-job --job-file <path>`
- `control-run-status --adapter reply --run-id <uuid>`
- `schedule-prepared-draft-refresh --adapter reply --company-id <company> [options]`

These commands are file-driven on purpose.

The first seam is not a hidden daemon. It is an explicit launch-and-inspect contract.

## Provider Comparison Job

`reply_provider_comparison` payload supports:

- `fixture_dir`
- `route_set_files`
- `corpus_id`
- `include_current_config`
- `include_deterministic_baseline`

Execution result includes:

- provider-comparison report path
- report id
- route summary count

The benchmark artifact still lives in the provider-comparison lane. The control plane only records the run.

## Prepared Draft Refresh Job

`reply_prepared_draft_refresh` payload supports:

- `company_id`
- `thread_ref`
- `generation_reason`

Execution result is the runtime refresh payload returned by `{trinity}`.

That means:

- the runtime still decides how refresh works
- the control plane only records that refresh was launched and what happened

## Active Thread Refresh Planning

The stronger prepared-draft loop now includes one explicit planning step:

- the runtime can inspect active threads with stored snapshots
- dirty threads, missing prepared drafts, and stale prepared drafts are ranked into a bounded refresh plan
- the control plane can materialize one persisted refresh job per recommended thread

This currently happens through:

- `plan-prepared-draft-refresh`
- `schedule-prepared-draft-refresh`

The important boundary remains:

- planning and job creation are explicit repo-owned artifacts
- there is still no resident scheduler daemon
- operators or external control planes can trigger those commands later without changing runtime ownership

## Failure Surface

Each run artifact records:

- `status`
- `started_at`
- `completed_at`
- `failure_reason`
- `outputs`

Failures are explicit and persisted. They do not disappear into scheduler logs only.

## Scheduler Boundary

This seam is compatible with future schedulers or operators, including Gobii-like control planes, because:

- job definitions are explicit JSON artifacts
- run results are explicit JSON artifacts
- runtime work is still launched through bounded repo-owned contracts

What is still intentionally missing:

- resident scheduler daemon
- external platform ownership
- automatic retry policy
- automatic policy mutation from recurring results

## Governance Boundary

Recurring jobs must not:

- mutate live route config automatically
- bypass runtime traces
- bypass Train promotion or policy review
- write hidden memory changes outside normal runtime contracts

Recurring jobs may:

- trigger explicit runtime refresh
- trigger explicit provider comparison runs
- create inspectable artifacts for later review
