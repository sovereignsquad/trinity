# Production Trace Eval Datasets

## Purpose

This document defines the first bounded path from persisted runtime traces to replayable evaluation datasets.

The goal is explicit curation, not passive data hoarding.

## Current Contract

The current dataset seam is intentionally narrow:

- curated cases come from persisted runtime traces
- curation requires explicit operator selection metadata
- replay datasets are stable JSON artifacts under the adapter runtime root
- replay currently targets the Reply runtime path only

## Curated Case Shape

Each curated eval case preserves:

- source `cycle_id`
- optional `trace_ref`
- `selection_reason`
- expected reviewed text
- expected operator disposition
- original `ThreadSnapshot`
- accepted artifact provenance

This keeps the dataset replayable and auditable.

## Dataset Flow

1. A production or reviewed runtime trace already exists.
2. The trace is deliberately promoted into one eval case.
3. Cases are persisted into one dataset artifact.
4. The dataset is replayed through the runtime.
5. Replay results are persisted as a report artifact for later comparison work.

## Current Commands

Curate one dataset from one or more persisted traces:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli curate-eval-dataset \
  --adapter reply \
  --dataset-name "Reply Production Trace Goldens" \
  --cycle-id <cycle-id> \
  --selection-reason "human-reviewed gold trace"
```

Replay one curated dataset:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli replay-eval-dataset \
  --dataset-file /path/to/reply-production-trace-goldens.json
```

## Persisted Artifacts

Trinity persists:

- `eval_datasets/datasets/<dataset_id>.json`
- `eval_datasets/reports/<dataset_id>--<timestamp>.json`

## Current Boundary

This first slice does not:

- auto-capture every trace
- mutate live route policy
- add hosted labeling infrastructure
- replace the existing shadow-fixture or provider-comparison lanes

It does:

- let real runtime successes and failures become reusable replay corpora
- preserve explicit provenance for later regression and offline improvement work
