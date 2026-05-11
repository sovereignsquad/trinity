# Live Brain Runtime Architecture

## Purpose

This document is the current runtime contract for `{trinity}` as the live brain behind `{reply}` and the future shared reasoning core for additional projects such as `{spot}`.

It separates:

- implemented runtime behavior
- target expansion that is not fully implemented yet

## Runtime Role

`{trinity}` owns:

- live draft generation
- draft refinement and ranking
- runtime memory-event ingestion
- active scoped memory retrieval
- disagreement preservation and future minority-report ownership
- bounded runtime rework loops
- Human-in-the-Loop escalation contracts
- runtime-owned prepared-draft persistence
- runtime document registration
- runtime trace export
- bounded policy application and promotion gates

`{trinity}` does not own:

- channel transport
- product contact merge authority
- send execution
- product approval gates
- offline optimizer control loops in `{train}`

## Current Implemented Runtime Slice

The current implemented live-brain slice is:

1. `{reply}` sends `ThreadSnapshot` payloads to `{trinity}`.
2. `{trinity}` runs the Reply-backed suggest pipeline and returns ranked drafts.
3. `{trinity}` persists prepared drafts from normal suggest cycles.
4. `{reply}` can ask `{trinity}` for the latest prepared draft for one thread.
5. `{reply}` can send bounded memory events and document registrations into runtime storage.
6. `{trinity}` records structured outcomes and exports traces and training bundles.
7. `{train}` can propose bounded policy artifacts, but accepted runtime behavior still flows back through `{trinity}` review and promotion.

## Current Module Ownership

The current implementation is split across these live modules:

- `core/trinity_core/workflow`
  - live candidate pipeline
  - prepared-draft materialization
- `core/trinity_core/memory/storage.py`
  - SQLite-backed runtime memory store for Reply
- `core/trinity_core/adapters/product/reply`
  - Reply payload normalization for snapshots, outcomes, memory events, and documents
- `core/trinity_core/reply_runtime.py`
  - concrete Reply runtime implementation
- `core/trinity_core/runtime.py`
  - adapter-aware runtime facade
- `core/trinity_core/cli.py`
  - generic CLI surface plus Reply compatibility aliases
- `core/trinity_core/ops`
  - cycle/export storage, artifact registry, policy review, promotion, Train handoff

Important current reality:

- the runtime seam is adapter-aware
- the only implemented adapter is still `reply`
- the concrete live-brain behavior is still mostly Reply-backed
- the runtime does not yet expose first-class minority-report, loop-budget, or HiTL contracts in code

## Current Runtime Event Vocabulary

The current runtime memory-event contract is the implemented snake-case enum in `core/trinity_core/schemas/memory.py`:

- `inbound_message_recorded`
- `outbound_message_recorded`
- `contact_upserted`
- `document_registered`
- `document_deleted`
- `thread_viewed`
- `draft_shown`
- `draft_selected`
- `draft_edited`

These are the current contract names. Conceptual event-family names such as `InboundMessageEvent` are design shorthand, not the current wire format.

## Current Runtime Data Model

The current live-brain slice already persists runtime-owned records for:

- memory events
- contacts
- thread state
- documents
- retrieval chunks
- dirty-thread markers
- prepared drafts

Current invariants:

- records are tenant-bound by `company_id`
- prepared drafts are runtime artifacts, not product artifacts
- runtime-owned document and retrieval rows can be deleted when `document_deleted` is ingested
- prepared-draft refresh can reuse the latest stored thread snapshot for the thread

## Current Storage Layout

The implemented runtime root remains adapter-scoped beneath local application support storage.

Current Reply storage includes:

- cycles
- exports
- bundles
- policies
- prepared drafts
- runtime memory SQLite state

The working rule remains:

- repository code is versioned in git
- runtime memory and artifacts live outside the repo working tree

## Current Runtime APIs

The implemented callable runtime surface is:

- `suggest(thread_snapshot)`
- `record_outcome(draft_outcome_event)`
- `ingest_memory_event(memory_event)`
- `register_document(document_record)`
- `get_prepared_draft(company_id, thread_ref)`
- `refresh_prepared_draft(company_id, thread_ref, reason)`
- `export_trace(cycle_id)`
- `export_training_bundle(cycle_id, bundle_type)`
- `runtime_status(adapter)`

Current first-class CLI commands reflecting that surface are:

- `suggest --adapter reply --input-file <file>`
- `record-outcome --adapter reply --input-file <file>`
- `ingest-memory-event --adapter reply --input-file <file>`
- `register-document --adapter reply --input-file <file>`
- `get-prepared-draft --adapter reply --company-id <company> --thread-ref <thread>`
- `refresh-prepared-draft --adapter reply --company-id <company> --thread-ref <thread> [--reason <reason>]`

## Current Boundary With `{train}`

`{train}` remains outside live runtime ownership.

Current meaning:

- `{trinity}` owns live drafting and live runtime memory state
- `{train}` owns bounded offline proposal generation
- accepted policy changes still require `{trinity}` review and promotion

`{train}` is not:

- the live memory store
- the live retrieval owner
- the live prepared-draft scheduler
- the live draft generator

## Comparison To Current Code

Implemented now:

- adapter-aware runtime facade
- Reply payload adapters
- runtime memory-event ingestion
- runtime document registration
- prepared-draft lookup and explicit refresh
- prepared-draft persistence on normal suggest cycles
- bounded active-thread refresh planning for dirty, missing, and stale prepared drafts
- explicit file-driven scheduling of per-thread prepared-draft refresh jobs through the control plane
- document delete handling in runtime memory
- trace and training-bundle export
- bounded Train proposal and policy review flows

Still not fully implemented:

- deeper retrieval ranking and summarization behavior
- autonomous background scheduling for dirty-thread refresh
- broader first-class `memory.*` module decomposition beyond the current SQLite store and schemas
- first-class disagreement and minority-report artifacts
- explicit loop-budget and Human-in-the-Loop control surfaces
- a second real product adapter

## Target Expansion

The target runtime still includes work beyond the current slice:

- richer `memory.*` decomposition
- stronger retrieval and summarization loops
- explicit majority/minority reasoning artifacts
- bounded rework-loop control
- first-class Human-in-the-Loop escalation payloads
- autonomous prepared-draft refresh scheduling
- additional adapter implementations beyond Reply
- cleaner separation between generic runtime layers and Reply-specific policy/runtime details

Those should grow out of the current runtime-owned store and adapter seam. They should not move live brain ownership back into `{reply}` or forward into `{train}`.
