# Trinity Execution Backlog

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
- [ ] Add shadow-mode fixtures comparing legacy `{reply}` drafting behavior to Trinity candidate outputs.

## Active Issue Queue

### Closed

- `TRINITY-001` Missing first-class Reply adapter contract
  The repository described downstream embedding but did not ship an explicit product-facing reply contract. Fixed by adding `core/trinity_core/schemas/integration.py` and this contract document.

- `TRINITY-002` Frontier ranking lived only in prose
  The formal production definition described frontier semantics, but the runtime core did not expose a frontier selector. Fixed by adding `core/trinity_core/workflow/frontier.py` with tests.

- `TRINITY-003` Missing feedback-memory application logic
  Runtime contracts existed, but downstream feedback still had no deterministic application path. Fixed by adding `core/trinity_core/workflow/feedback_memory.py` with tests.

### Open

- `TRINITY-005` Reply shadow comparison fixtures
  Trinity now exposes the local runtime surface and persistent cycle/export artifacts, but the repo still lacks dedicated fixtures proving how legacy Reply drafts compare to Trinity outputs on the same thread.

## Dependencies

- Depends on `{reply}` to supply real downstream product fixtures during integration.
- Feeds `{train}` with bounded runtime artifacts for optimization, but retains runtime ownership.
