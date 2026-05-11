# Gobii Profile Enrichment Workflow Proof

## Purpose

This document describes the first bounded Gobii-backed sourcing and enrichment proof for `{trinity}`.

The chosen workflow is:

- tracked-entity profile enrichment on one known web profile URL

This is the right first enrichment proof because it:

- uses Gobii for external browser work without giving it runtime ownership
- produces one inspectable Trinity-owned document/evidence artifact
- stays narrow enough to replay and audit deterministically
- gives future contributors a copyable pattern for later bounded sourcing work

## Workflow Shape

The proof is intentionally split into three explicit steps.

Bundle construction:

- build one tracked-entity enrichment request
- generate one Gobii task prompt plus one required `output_schema`
- persist the bundle before remote execution

Gobii layer:

- run one browser-use task against the provided profile URL
- return only structured JSON matching the requested schema
- persist the returned Gobii task record under the adapter runtime root

Trinity layer:

- load the completed persisted task record
- extract the bounded result payload
- normalize it into one Trinity-owned document, memory event, retrieval chunk, and evidence unit

Gobii remains the external collection substrate. `{trinity}` remains the workflow and artifact owner.

## Current Commands

1. Build the bounded enrichment bundle:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli make-gobii-profile-enrichment \
  --adapter reply \
  --input-file /path/to/profile-enrichment-request.json \
  --agent-id <optional-agent-id>
```

2. Submit the persisted bundle through Gobii's Tasks API:

```bash
export GOBII_API_KEY=...
PYTHONPATH=core uv run python -m trinity_core.cli submit-gobii-profile-enrichment \
  --adapter reply \
  --bundle-file /path/to/candidate_jane-doe.json \
  --gobii-api-base-url https://gobii.ai
```

3. After the task record is completed and persisted, normalize the result into Trinity artifacts:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli normalize-gobii-profile-enrichment \
  --adapter reply \
  --bundle-file /path/to/candidate_jane-doe.json
```

## Input Contract

The request payload is intentionally small:

- `company_id`
- `entity_ref`
- `entity_name`
- `target_profile_url`
- optional `company_name`
- optional `role_hint`
- optional operator `notes`
- optional metadata

This keeps the first proof focused on enrichment of an already-known entity instead of broad discovery.

## Output Contract

The Gobii task requires structured JSON with:

- `entity_name`
- `profile_url`
- `summary`
- `evidence_points`
- optional `headline`
- optional `current_company`
- optional `location`

If the completed task does not contain that result shape, normalization fails closed.

## Persisted Artifacts

Trinity persists:

- `gobii_enrichment/bundles/<entity_ref>.json`
- `gobii_tasks/records/<task_id>.json`
- `gobii_tasks/normalized/<task_id>--gobii-profile-enrichment:<entity_ref>.json`
- runtime memory rows for:
  - `documents`
  - `memory_events`
  - `retrieval_chunks`

This gives operators one explicit trail from:

- enrichment request
- to Gobii task submission
- to Gobii task record
- to Trinity-owned normalized artifact bundle

## Why This Is Safe

This proof does not let Gobii:

- mutate runtime policy
- write hidden memory updates
- broaden into autonomous sourcing orchestration
- bypass explicit task review and normalization contracts

It only lets Gobii:

- fetch one bounded external profile artifact
- return structured data through one declared schema
- feed that result into Trinity through an explicit persisted normalization step

## Current Limitation

The current enrichment proof is intentionally narrow:

- it handles one tracked-entity profile enrichment pattern only
- it assumes the operator already knows the target entity and profile URL
- it normalizes only document-style runtime artifacts
- it does not add approval, delivery, or downstream product semantics

That is acceptable for this tranche because the goal is to prove:

- one trustworthy Gobii task contract
- one artifact-safe normalization pattern
- one copyable bounded enrichment workflow

before widening the Gobii seam further.
