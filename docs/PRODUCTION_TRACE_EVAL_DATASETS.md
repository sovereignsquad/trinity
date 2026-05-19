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
- score-health reports can now also be built from the same persisted traces to aggregate runtime score-audit signals without replaying the runtime

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

Build one score-health report from one or more persisted traces:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli report-score-health \
  --adapter reply \
  --report-name "Reply Score Health" \
  --cycle-id <cycle-id> \
  --selection-reason "manual governance review"
```

Review one score-health report with optional replay correlation:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli review-score-health \
  --report-file /path/to/reply-score-health.json \
  --replay-report-file /path/to/reply-production-trace-goldens-report.json
```

Persist one score-health review decision while reviewing:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli review-score-health \
  --report-file /path/to/reply-score-health.json \
  --decision-status investigate \
  --decision-notes "Recurring tuple clustering needs follow-up."
```

Compare multiple score-health reports over time:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli compare-score-health \
  --trend-report-name "Reply Score Health Trend" \
  --report-file /path/to/reply-score-health-a.json \
  --report-file /path/to/reply-score-health-b.json \
  --selection-reason "manual trend review"
```

Evaluate one score-health gate result for acceptance or release workflows:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli check-score-governance \
  --report-file /path/to/reply-score-health.json \
  --decision-file /path/to/reply-score-health-decision.json \
  --trend-report-file /path/to/reply-score-health-trend.json
```

Build one persisted release-readiness report from the same governance artifacts:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli check-release-governance \
  --report-file /path/to/reply-score-health.json \
  --decision-file /path/to/reply-score-health-decision.json \
  --release-report-name "Reply Release Governance"
```

Build one persisted operator triage queue from unresolved decisions, trend reports, and override history:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli list-score-governance-work \
  --adapter reply \
  --triage-report-name "Reply Governance Work"
```

Persist one operator resolution for a triage item:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli resolve-score-governance-item \
  --adapter reply \
  --item-id decision-reply-score-health-investigate \
  --resolution-status resolved \
  --notes "Operator handled this item."
```

Persist one operator release decision linked to a release-governance report:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli record-release-governance-decision \
  --release-report-file /path/to/reply-release-governance.json \
  --decision-status override_release \
  --notes "Approved with explicit exception."
```

Inspect the latest joined governance state for one adapter:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli governance-status \
  --adapter reply
```

Compare Reply and Spot score-bearing traces in one report:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli report-cross-adapter-scores \
  --report-name "Cross Adapter Scores" \
  --adapter reply \
  --adapter spot \
  --top-n 25
```

Build one aggregate governance dashboard across adapters:

```bash
PYTHONPATH=core uv run python -m trinity_core.cli report-score-governance-dashboard \
  --report-name "Governance Dashboard" \
  --adapter reply \
  --adapter spot
```

## Persisted Artifacts

Trinity persists:

- `eval_datasets/datasets/<dataset_id>.json`
- `eval_datasets/reports/<dataset_id>--<timestamp>.json`
- `eval_datasets/score_health_reports/<report_id>.json`
- `eval_datasets/score_health_review_decisions/<decision_id>.json`
- `eval_datasets/score_health_trend_reports/<trend_report_id>.json`
- `eval_datasets/score_governance_release_reports/<release_report_id>.json`
- `eval_datasets/score_governance_triage_reports/<triage_report_id>.json`
- `eval_datasets/score_governance_triage_resolutions/<resolution_id>.json`
- `eval_datasets/score_governance_release_decisions/<release_decision_id>.json`

Accepted policy transitions can now also persist score-governance lineage:

- checked report id
- checked decision id
- checked trend report id
- linked release-governance report id
- linked release-governance decision id and decision status
- final governance status
- explicit override notes when an operator proceeds past a blocked governance result

## Current Boundary

This first slice does not:

- auto-capture every trace
- mutate live route policy
- add hosted labeling infrastructure
- replace the existing shadow-fixture or provider-comparison lanes

It does:

- let real runtime successes and failures become reusable replay corpora
- preserve explicit provenance for later regression and offline improvement work
- let operators inspect recurring audit flags and repeated final-score tuple clusters across persisted traces without changing runtime behavior
- let workflow acceptance consume those governance artifacts explicitly instead of relying on report inspection alone
- let operators correlate aggregated score-health patterns with replay quality drift through one explicit review surface
- let operators persist explicit governance decisions and compare score-health patterns across multiple reports over time
- let release readiness consume the same governance artifacts through one persisted release report
- let operators build one queue of unresolved or repeatedly overridden governance work instead of inspecting files one by one
- let operators close or suppress queue items through explicit resolution artifacts
- let actual release decisions keep lineage back to the governance report that informed them
