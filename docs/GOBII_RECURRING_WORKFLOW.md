# Gobii Recurring Workflow Proof

## Purpose

This document describes the first bounded Gobii-backed recurring workflow proof for `{trinity}`.

The chosen workflow is:

- scheduled Reply provider comparison maintenance

This is the right first proof because it:

- exercises the new control-plane seam
- produces bounded, inspectable benchmark artifacts
- does not mutate runtime policy directly
- is replayable enough to debug locally

The Gobii seam now also includes a narrow browser-use task lifecycle client for:

- create task
- list tasks
- fetch task result
- cancel task

Those task records are persisted locally under the adapter runtime root for observability and recovery. They can now also feed an explicit normalization step into Trinity-owned artifacts, but that remains secondary to the recurring workflow proof.

## Workflow Shape

The proof is intentionally split into two layers.

Gobii layer:

- recurring agent schedule
- persistent agent identity
- agent registration metadata

Trinity layer:

- persisted control-plane job definition
- persisted control-plane run artifact
- persisted provider comparison report artifact

Gobii is the orchestration substrate. `{trinity}` remains the runtime and artifact owner.

## Current Commands

1. Create a bounded control-plane job:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli make-control-job \
  --adapter reply \
  --job-kind reply_provider_comparison \
  --job-id nightly-shadow-benchmark \
  --include-current-config \
  --include-deterministic-baseline
```

2. Build the Gobii workflow bundle:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli make-gobii-workflow \
  --job-file /path/to/nightly-shadow-benchmark.json \
  --schedule "@daily"
```

3. Optionally register the bundle through Gobii's Agent API:

```bash
export GOBII_API_KEY=...
PYTHONPATH=core uv run python -m trinity_core.cli register-gobii-workflow \
  --bundle-file /path/to/gobii-nightly-shadow-benchmark.json \
  --gobii-api-base-url https://gobii.ai
```

4. Equivalent local recurring trigger for deterministic replay:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli run-control-job \
  --job-file /path/to/nightly-shadow-benchmark.json
```

## Persisted Artifacts

Trinity persists:

- `control_plane/jobs/<job_id>.json`
- `control_plane/runs/<run_id>.json`
- `provider_comparisons/reports/<report_id>.json`
- `gobii_workflows/bundles/<workflow_id>.json`
- `gobii_workflows/registrations/<workflow_id>.json`
- `gobii_tasks/records/<task_id>.json`
- `gobii_tasks/normalized/<task_id>--<document_ref>.json`

This gives operators one explicit trail from:

- scheduled Gobii agent intent
- to Trinity job definition
- to Trinity run record
- to Trinity benchmark report

## What Gobii Stores

The generated Gobii agent payload includes:

- `name`
- `charter`
- `schedule`
- `whitelist_policy`
- `is_active`
- `enabled_personal_server_ids`

This matches the current Gobii Agent API shape for creating persistent scheduled agents:

- [Create an Agent](https://docs.gobii.ai/api-reference/agents-api/create-an-agent)
- [Agent API](https://docs.gobii.ai/developers/developer-agents)

The task lifecycle surface matches the current Gobii browser-use Tasks API shape:

- [Tasks for Developers](https://docs.gobii.ai/developers/developer-tasks)
- [Get task result](https://docs.gobii.ai/api-reference/browser-use-tasks-api/get-tasksbrowser-use-result)
- [Get agent tasks](https://docs.gobii.ai/api-reference/browser-use-tasks-api/get-agentsbrowser-use-tasks)

## Why This Is Safe

This proof does not let Gobii:

- modify Trinity runtime policy
- write hidden memory updates
- bypass Train promotion
- become the runtime owner

It only lets Gobii:

- hold recurrence and agent lifecycle
- register one bounded recurring maintenance workflow
- point back to the Trinity-owned control-plane job and artifacts

## Current Limitation

The current Gobii proof is intentionally narrow:

- only `reply_provider_comparison` jobs can be packaged as Gobii recurring workflows
- Gobii registration is narrow Agent API support
- Gobii task lifecycle and normalization support are now present, but they remain bounded ops contracts rather than a runtime workflow engine
- the equivalent local trigger remains the deterministic proof path for repo validation

That is acceptable for this tranche because the goal is to prove:

- recurring schedule substrate
- bounded registration contract
- explicit artifact ownership
- recoverable run metadata

before widening the Gobii seam further.
