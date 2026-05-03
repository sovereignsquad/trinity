# {trinity} Execution Backlog

## Objective

Deliver the canonical runtime boundary for cross-project development while keeping `{trinity}` product-agnostic.

## Milestones

### M1. Runtime Contract Hardening

- [x] Add first explicit `{reply}` product adapter contract.
- [x] Add canonical frontier selection helper and tests.
- [x] Record the execution backlog and issue queue in-repo.

### M2. Runtime Completion

- [x] Persist eligible candidate pools and frontier snapshots.
- [x] Add feedback-memory application logic on top of `ReplyFeedbackEvent`.
- [x] Export stable bounded artifacts that `{train}` can optimize and re-import.

### M3. Product Embedding

- [x] Add an application-facing adapter surface for `{reply}` integration.
- [ ] Add shadow-mode fixtures comparing legacy `{reply}` drafting behavior to `{trinity}` candidate outputs.

## Active Issue Queue

### Closed

- `TRINITY-001` Missing first-class `{reply}` adapter contract
  The repository described downstream embedding but did not ship an explicit product-facing reply contract. Fixed by adding `core/trinity_core/schemas/integration.py` and this contract document.

- `TRINITY-002` Frontier ranking lived only in prose
  The formal production definition described frontier semantics, but the runtime core did not expose a frontier selector. Fixed by adding `core/trinity_core/workflow/frontier.py` with tests.

- `TRINITY-003` Missing feedback-memory application logic
  Runtime contracts existed, but downstream feedback still had no deterministic application path. Fixed by adding `core/trinity_core/workflow/feedback_memory.py` with tests.

### Open

- `TRINITY-005` `{reply}` shadow comparison fixtures
  `{trinity}` now exposes the local runtime surface and persistent cycle/export artifacts, but the repo still lacks dedicated fixtures proving how legacy `{reply}` drafts compare to `{trinity}` outputs on the same thread.

- `TRINITY-POLICY-001` `ReplyBehaviorPolicy` schema and validator
  Define the first bounded policy artifact family for tone, brevity, and channel rules, with deterministic validation and precedence.

- `TRINITY-POLICY-002` Accepted policy/artifact registry
  Track immutable accepted runtime artifact versions with explicit promotion and rollback metadata.

- `TRINITY-POLICY-003` Training bundle export
  Export deterministic bounded learning bundles from live cycles for tone, brevity, and channel-formatting learning.

- `TRINITY-POLICY-004` Runtime policy loader/resolver
  Apply accepted artifacts at runtime for prompt shaping and ranking hints without taking over send lifecycle, transport, or safety semantics.

- `TRINITY-POLICY-005` Acceptance gate workflow
  Add schema validation, replay comparison, regression rejection, explicit promotion, and explicit rollback as a first-class runtime workflow.

## Dependencies

- Depends on `{reply}` to supply real downstream product fixtures during integration.
- Feeds `{train}` with bounded runtime artifacts for optimization, but retains runtime ownership.
