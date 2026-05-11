# Gobii Normalization Contract

## Purpose

This document defines the trust boundary between external Gobii browser-use work and runtime-owned `{trinity}` state.

Gobii output is untrusted until `{trinity}` normalizes it through an explicit ingestion envelope.

## What Is Allowed In

The current normalization path may create these Trinity-owned artifacts:

- one `DocumentRecord`
- one `MemoryEvent` with kind `document_registered`
- one bounded `EvidenceUnit`
- one persisted normalization bundle under `gobii_tasks/normalized/`

This is enough to make Gobii-derived output:

- auditable
- replayable
- retrieval-eligible
- tenant-bound

without letting Gobii write arbitrary runtime state.

## Required Inputs

Normalization requires an explicit JSON envelope passed to:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli normalize-gobii-task \
  --adapter reply \
  --input-file /path/to/gobii-normalization.json
```

Required envelope fields:

- `company_id`
- `task_id` or `task_record_path`
- `document_ref`
- `path`
- `content_text`
- `source_type`

Optional but important:

- `title`
- `occurred_at`
- `thread_ref`, `channel`, `contact_handle`
- `source_external_id`
- `source_locator`
- `raw_origin_uri`
- `topic_hints`
- `metadata`

## Binding Rules

Normalization fails closed unless the persisted Gobii task record is already bound to:

- one Trinity adapter
- one company

That binding is carried in the local task record, not inferred later from the raw Gobii payload.

This is why `submit-gobii-task` now accepts `--company-id`, and why later task-result refreshes preserve the existing local binding when the record already exists.

## Persisted Output

Successful normalization persists:

- `gobii_tasks/normalized/<task_id>--<document_ref>.json`
- one document row in runtime memory storage
- one retrieval chunk when `content_text` is non-empty
- one `document_registered` memory event

If thread context is present, the associated thread is also marked dirty for downstream refresh work.

## Provenance Rules

Every normalized artifact carries Gobii provenance metadata, including:

- `gobii_task_id`
- `gobii_task_status`
- `gobii_task_record_path`
- `gobii_task_created_at`
- `gobii_task_updated_at`
- `gobii_agent_id` when available
- `gobii_task_prompt` when available
- normalization timestamp
- normalization contract version

The bounded `EvidenceUnit` also carries:

- `collector = gobii:<agent_id or browser-use>`
- `ingestion_channel = gobii_task_normalization`
- raw-origin URI
- task-id and task-record-path ingestion notes

## Rejection Rules

Normalization must reject:

- task records with no Trinity adapter binding
- task records with no company binding
- adapter mismatch
- company mismatch
- non-completed Gobii tasks
- missing or structurally invalid normalization envelopes

Prefer explicit rejection over silent ingestion.

## Current Boundary

This contract still does not allow Gobii to:

- mutate policy
- write hidden memory summaries
- bypass Train promotion
- own workbook or product-side storage
- define product interpretation rules

Gobii may collect. `{trinity}` decides what becomes runtime state.
