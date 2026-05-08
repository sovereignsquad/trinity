# {reply} <-> {trinity} Integration Checklist

## Purpose

This document turns the current cross-repo integration status into a concrete execution checklist.

Use it when updating `{reply}` to consume `{trinity}` correctly and safely.

Do not use it to move live runtime ownership back into `{reply}`.

## Current Boundary

`{reply}` owns:

- thread ingestion
- product retrieval
- operator workflow
- send execution
- product-side rollout controls

`{trinity}` owns:

- runtime interpretation
- ranked drafting
- policy application
- cycle persistence
- trace and training-bundle export
- accepted artifact provenance

## Current State

Already present in `{reply}` today:

- `{trinity}` is the live drafting runtime in normal product mode
- `ThreadSnapshot` construction exists
- structured outcomes go through `/api/trinity/outcome`
- draft context already carries `cycle_id`, `trace_ref`, and accepted artifact provenance
- developer shadow comparison already exists

This is visible in:

- [`/Users/Shared/Projects/reply/chat/brain-runtime.js`](/Users/Shared/Projects/reply/chat/brain-runtime.js)
- [`/Users/Shared/Projects/reply/chat/routes/messaging.js`](/Users/Shared/Projects/reply/chat/routes/messaging.js)
- [`/Users/Shared/Projects/reply/chat/js/api.js`](/Users/Shared/Projects/reply/chat/js/api.js)
- [`/Users/Shared/Projects/reply/docs/EXECUTION_BACKLOG.md`](/Users/Shared/Projects/reply/docs/EXECUTION_BACKLOG.md)

What still needs to be tightened is operational discipline around identity, outcomes, provenance, and the Train trigger.

## Checklist

### 1. Company Identity Discipline

Status:
- product path exists
- must be treated as non-optional now

Required updates in `{reply}`:

- ensure every `ThreadSnapshot` build path stamps one stable `company_id`
- ensure every `DraftOutcomeEvent` path preserves that same `company_id`
- reject or fail closed when product context cannot resolve company identity deterministically

Primary file surfaces:

- [`/Users/Shared/Projects/reply/chat/brain-runtime.js`](/Users/Shared/Projects/reply/chat/brain-runtime.js)
- [`/Users/Shared/Projects/reply/chat/routes/messaging.js`](/Users/Shared/Projects/reply/chat/routes/messaging.js)

Acceptance check:

- the same thread cannot produce different `company_id` values across suggest and outcome events

### 2. Cycle Identity Preservation

Status:
- mostly present
- must become invariant

Required updates in `{reply}`:

- preserve `{trinity}` `cycle_id` from suggestion through selection, edit, send, reject, and rework flows
- preserve `trace_ref` and `accepted_artifact_version` inside draft context until outcome emission
- prevent client-side paths from dropping `cycle_id` during draft replacement or manual edit flows

Primary file surfaces:

- [`/Users/Shared/Projects/reply/chat/brain-runtime.js`](/Users/Shared/Projects/reply/chat/brain-runtime.js)
- [`/Users/Shared/Projects/reply/chat/js/api.js`](/Users/Shared/Projects/reply/chat/js/api.js)
- [`/Users/Shared/Projects/reply/chat/routes/messaging.js`](/Users/Shared/Projects/reply/chat/routes/messaging.js)

Acceptance check:

- every emitted structured outcome tied to a Trinity draft includes the original `cycle_id`

### 3. Outcome Quality Hardening

Status:
- route exists
- payload quality still determines whether learning is useful

Required updates in `{reply}`:

- emit deterministic `DraftOutcomeEvent` payloads for:
  - `SELECTED`
  - `SENT_AS_IS`
  - `EDITED_THEN_SENT`
  - `REJECTED`
  - `IGNORED`
  - `MANUAL_REPLACEMENT`
  - `REWORK_REQUESTED`
- always include:
  - `company_id`
  - `cycle_id`
  - `thread_ref`
  - `channel`
  - `candidate_id` when applicable
  - `final_text` when applicable
  - `edit_distance`
  - `latency_ms`
  - `send_result`

Primary file surfaces:

- [`/Users/Shared/Projects/reply/chat/brain-runtime.js`](/Users/Shared/Projects/reply/chat/brain-runtime.js)
- [`/Users/Shared/Projects/reply/chat/routes/messaging.js`](/Users/Shared/Projects/reply/chat/routes/messaging.js)

Acceptance check:

- `{trinity}` can export replayable training bundles from normal product traffic without missing required outcome facts

### 4. Provenance Visibility

Status:
- provenance is carried internally
- operator-facing visibility is still easy to underdo

Required updates in `{reply}`:

- surface accepted artifact provenance in operator-visible draft metadata
- make it possible to inspect:
  - artifact key
  - artifact version
  - source project
  - trace reference
- keep this visible at least in debug or advanced runtime views even if not shown in the main compose surface

Primary file surfaces:

- [`/Users/Shared/Projects/reply/chat/brain-runtime.js`](/Users/Shared/Projects/reply/chat/brain-runtime.js)
- [`/Users/Shared/Projects/reply/app/reply-app/Sources/NativeSettingsView.swift`](/Users/Shared/Projects/reply/app/reply-app/Sources/NativeSettingsView.swift)
- any operator draft-inspection UI that already renders runtime metadata

Acceptance check:

- an operator can explain which accepted runtime artifact produced a shown draft

### 5. Train Trigger Ownership

Status:
- `{trinity}` can now invoke `{train}`
- `{reply}` still needs a policy for when to request it

Required decision in `{reply}`:

- choose whether Train proposal triggering is:
  - operator-driven
  - scheduler-driven
  - threshold-driven inside product operations

Recommended first implementation:

- keep trigger explicit and operator- or scheduler-driven
- do not auto-trigger on every send
- require a minimum corpus threshold before invoking:
  - tone learner
  - brevity learner
  - channel-formatting learner

Suggested product integration surface:

- add one bounded product-side action that shells into:
  - `train-propose-policy --adapter reply --learner-kind <kind> ...`
- keep acceptance separate unless an operator explicitly opts into `--accept`

Primary file surfaces:

- [`/Users/Shared/Projects/reply/chat/brain-runtime.js`](/Users/Shared/Projects/reply/chat/brain-runtime.js)
- product-side ops/admin action surfaces in `{reply}`

Acceptance check:

- `{reply}` can intentionally trigger one bounded `{trinity} -> {train} -> {trinity}` proposal loop without manual JSON hand-carrying

### 6. Retrieval And Tone Ownership Cleanup

Status:
- `{reply}` still correctly provides context
- it must not pretend to own long-term behavior policy anymore

Required updates in `{reply}`:

- keep `{reply}` responsible for:
  - thread history
  - retrieved snippets
  - golden examples
- stop treating product-local heuristics as the long-term tone authority when accepted `{trinity}` policies exist
- ensure product hints remain hints, while accepted runtime policies remain runtime-owned

Primary file surfaces:

- [`/Users/Shared/Projects/reply/chat/brain-runtime.js`](/Users/Shared/Projects/reply/chat/brain-runtime.js)
- any product-side prompt or style shaping layer

Acceptance check:

- changing a Train-accepted Reply behavior policy changes runtime behavior without requiring duplicate style rule updates inside `{reply}`

### 7. Comparison And Rollout Discipline

Status:
- shadow comparison exists
- rollout proof still depends on disciplined use

Required updates in `{reply}`:

- preserve comparison between:
  - legacy shadow drafts
  - baseline Trinity drafts
  - Trinity drafts under accepted Train-produced policies
- keep those comparisons inspectable by company and channel
- use them before broad rollout of accepted policy changes

Primary file surfaces:

- [`/Users/Shared/Projects/reply/chat/brain-runtime.js`](/Users/Shared/Projects/reply/chat/brain-runtime.js)
- [`/Users/Shared/Projects/reply/chat/routes/messaging.js`](/Users/Shared/Projects/reply/chat/routes/messaging.js)
- any internal shadow-comparison viewer path

Acceptance check:

- accepted policy changes can be compared against the previous runtime behavior before product-wide trust is assumed

## Recommended Delivery Order

1. Company identity discipline
2. Cycle identity preservation
3. Outcome quality hardening
4. Provenance visibility
5. Train trigger ownership
6. Retrieval and tone ownership cleanup
7. Comparison and rollout discipline

## Non-Negotiables

- `{reply}` must not regain live drafting ownership
- `{reply}` must not bypass `DraftOutcomeEvent`
- `{reply}` must not auto-accept Train proposals by default
- `{reply}` must not blur company boundaries after Trinity now enforces them
- accepted policy provenance must remain inspectable
