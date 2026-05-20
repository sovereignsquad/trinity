# Trinity Relationship Hardening Plan

## Purpose

This document turns the audit in [docs/RELATIONSHIP_HEALTH.md](/Users/Shared/Projects/trinity/docs/RELATIONSHIP_HEALTH.md) into one explicit implementation lane with GitHub issue anchors, dependency notes, and a recommended delivery order.

Current planning snapshot:

- `2026-05-20`

GitHub board:

- `{trinity} - From IDEA to LIVE` project `#6`

## Why This Lane Exists

The current repository boundary model is mostly correct.

The main weaknesses are now:

- Train seam transport health and diagnostics
- provider readiness clarity
- `mistral-cli` missing-executable and bounded-mode supervision
- machine-checked Reply cross-repo compatibility
- optional Gobii live seam verification

This lane hardens those relations without changing repository ownership.

## Delivery Issues

### Umbrella

- `#79` `{trinity}: Harden relation health for Train, providers, Reply compatibility, and Gobii seams`

### Deliverable Issues

1. `#80` `{trinity}: Add Train seam health probes and structured transport diagnostics`
2. `#81` `{trinity}: Add provider readiness and configured-route smoke verification`
3. `#82` `{trinity}: Harden mistral-cli executable detection and provider-status semantics`
4. `#83` `{trinity}: Add a machine-checked {reply} <-> {trinity} compatibility verification lane`
5. `#84` `{trinity}: Add credentialed Gobii smoke checks and operator-facing seam status`

## Recommended Delivery Order

### Phase 1. Train Seam

Issue:

- `#80`

Reason:

- this is the highest-risk operational seam from the audit
- the API path was unavailable on the audited machine
- Train is part of the core policy-learning story, so weak diagnostics here block trustworthy use of the lane

Expected outcome:

- explicit Train health probe
- structured transport and malformed-response diagnostics
- clearer API versus CLI operating guidance

### Phase 2. Provider Readiness

Issue:

- `#81`

Reason:

- current inventory visibility is stronger than actual execution readiness
- operators need route-level readiness, not just asset or executable presence

Expected outcome:

- configured-route smoke verification
- clearer operator-facing readiness explanations
- stronger provider-backed supervision for Reply and Spot

### Phase 3. Mistral CLI Hardening

Issue:

- `#82`

Reason:

- the current `mistral-cli` relation is the weakest live provider relation
- the code path exists, but the executable was not present on the audited machine

Expected outcome:

- explicit missing-executable detection
- clearer bounded-mode status semantics
- more honest provider supervision

### Phase 4. Reply Cross-Repo Verification

Issue:

- `#83`

Reason:

- Reply is the strongest downstream consumer, but compatibility is still too checklist-driven
- once Train and provider health are clearer, the next leverage point is machine-checked cross-repo compatibility

Expected outcome:

- one bounded compatibility verification lane
- earlier detection of contract drift between `{reply}` and `{trinity}`

### Phase 5. Gobii Live Smoke

Issue:

- `#84`

Reason:

- Gobii is optional and bounded
- the transport seam is already test-covered, so live smoke comes after the more critical Train and provider hardening

Expected outcome:

- opt-in credentialed smoke verification
- clearer operator-facing Gobii seam status

## Explicit Dependency Graph

### New Hardening Lane

- `#79`
  Child delivery sequence:
  `#80 -> #81 -> #82 -> #83 -> #84`

### Existing Issues Updated To Reference This Lane

- `#9`
  Now explicitly points at `#81` and `#82` as provider hardening follow-ons.
- `#13`
  Now explicitly points at `#80` and `#83` as Train and downstream compatibility hardening follow-ons.
- `#19`
  Now explicitly points at `#81` and `#82` as degradation and readiness hardening follow-ons.
- `#32`
  Now explicitly points at `#82` as the bounded `mistral-cli` hardening follow-on.
- `#33`
  Now includes `#84` as the bounded Gobii smoke and seam-status follow-on.
- `#54`
  Now has concrete dependencies on `#53`, `#80`, `#81`, and `#83`.
- `#55`
  Now has concrete dependencies on `#54`, `#80`, `#81`, and `#84`.
- `#65`
  Now references `#83` as a reusable pattern for future downstream compatibility verification.

## Board Status Snapshot

Current project `#6` status after implementation and reconciliation:

- `#32` `Done`
- `#33` `Done`
- `#54` `Backlog (SOONER)`
- `#55` `Roadmap (LATER)`
- `#65` `Done`
- `#79` `Done`
- `#80` `Done`
- `#81` `Done`
- `#82` `Done`
- `#83` `Done`
- `#84` `Done`

## Delivery Guidance

Do not treat this as one large observability project.

Keep each issue bounded:

- one seam
- one explicit status or verification improvement
- focused tests
- operator-facing docs

The hardening lane is successful if the most important relations become easier to verify automatically and harder to misconfigure silently.
