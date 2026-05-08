# Impact Product Adapter Contract

## Purpose

This document defines the bounded Impact adapter boundary inside `{trinity}`.

The Impact adapter proves that `{trinity}` can serve a second real downstream
without pretending that every Reply-specific runtime and policy contract is
already generic.

## Current Contract Version

- `trinity.impact.v1alpha1`

## What Impact Sends To `{trinity}`

Impact sends a normalized profile snapshot through the generic CLI:

- `project_ref`
- `profile_ref`
- `requested_at`
- `machine_class`
- `os_name`
- `architecture`
- `readiness_summary`
- `runtimes[]`
- `models[]`
- optional bounded metadata

Canonical schema:

- [core/trinity_core/schemas/impact_integration.py](/Users/Shared/Projects/trinity/core/trinity_core/schemas/impact_integration.py)

## What `{trinity}` Returns To Impact

The runtime returns a ranked recommendation set:

- `cycle_id`
- `profile_ref`
- `generated_at`
- `recommendations[]`
- optional `trace_ref`
- `contract_version`

Each recommendation carries:

- `candidate_id`
- `headline`
- `recommendation_text`
- `rationale`
- `risk_flags`
- candidate scores
- source evidence ids

## Operator Outcome Contract

Impact records deterministic outcomes through:

- `profile_ref`
- `cycle_id`
- `disposition`
- `occurred_at`
- optional `candidate_id`
- optional `final_note`

Current supported dispositions:

- `SHOWN`
- `APPLIED`
- `DEFERRED`
- `REJECTED`
- `IGNORED`

## What The Impact Adapter Owns

- mapping one Impact profile into a bounded Trinity snapshot
- surfacing recommendation candidates grounded in profile evidence
- recording operator outcomes for those recommendation candidates
- exporting replayable adapter traces through the generic runtime path

## What The Impact Adapter Does Not Own

- machine scanning
- profile generation
- report generation
- benchmark or readiness truth outside the local profile
- policy promotion
- Train proposal handoff
- shadow-fixture replay

Those remain outside the current Impact adapter contract.

## Supported CLI Surface

Impact is supported on the generic CLI path for:

- `suggest --adapter impact`
- `record-outcome --adapter impact`
- `export-trace --adapter impact`
- `runtime-status --adapter impact`
- `show-config --adapter impact`
- `write-config --adapter impact`

Not currently supported for Impact:

- `export-training-bundle`
- `train-propose-policy`
- `policy-review`
- `policy-review-surface`
- `policy-accept`
- `policy-promote`
- `policy-rollback`
- `policy-status`
- `run-shadow-fixtures`

Those commands are currently Reply-only by contract.

## Architectural Rule

Impact exists to prove the runtime seam, not to smuggle Impact-specific product
semantics into Trinity core.

That means:

- keep Impact-specific snapshot and result types in the adapter contract layer
- keep policy lifecycle generic only where another adapter truly shares it
- do not retrofit Reply policy artifacts into the Impact surface unless Impact
  actually needs a learned promotion loop
