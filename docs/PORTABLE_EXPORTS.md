# Portable Exports

## Purpose

This document defines the explicit `{trinity}` producer/export seam for `{train}` portable-pack builds.

`{trinity}` owns runtime state.
`{train}` owns offline packaging, training, eval, promotion, and release artifacts.

The seam is the governed export system.

`{train}` must not scrape `{trinity}` storage directly.

## Export Families

`{trinity}` now emits 4 first-class portable export families.

### 1. Source Export

Purpose:

- canonical raw source-record producer family for `mcs-knowledge-pack`
- canonical raw source-record producer family for `mcs-delta-pack`

Current record coverage where present:

- thread snapshots
- thread messages
- context snippets
- golden examples
- runtime memory events
- registered documents
- attachment references from runtime-owned metadata

### 2. Outcome Export

Purpose:

- canonical supervised behavior corpus for `mcs-llm-core`

Current record coverage where present:

- candidate variants
- supervision events
- final outcomes
- accepted draft text
- user-edited final text
- selected candidate lineage
- accepted artifact linkage
- policy-resolution linkage

### 3. Memory Export

Purpose:

- canonical structured memory producer family for `mcs-knowledge-pack`

Current record coverage where present:

- memory summaries
- contact profiles
- thread states
- provenance refs from runtime metadata
- evidence anchors from runtime metadata
- freshness metadata
- confidence metadata
- conflict metadata

### 4. Delta Export

Purpose:

- canonical cutoff-linked producer family for `mcs-delta-pack`
- canonical cutoff-linked producer family for next-snapshot builds

Current record coverage:

- all source export records after cutoff
- all outcome export records after cutoff
- all memory export records after cutoff
- explicit cutoff reference
- explicit prior snapshot or prior export lineage
- append-only manifest counts

## Envelope Contract

Each portable export envelope now carries explicit versioned metadata:

- `export_family`
- `export_version`
- `producer_system`
- `producer_adapter`
- `tenant_scope`
- `created_at`
- `snapshot_ref`
- `cutoff_ref` where applicable
- `source_manifest`
- `record_count`
- `lineage`
- `integrity`

Each contained record now carries:

- stable `record_id`
- family-specific `record_type`
- timestamps
- provenance or source refs
- runtime-owned refs
- tenant scope
- structured payload
- quality, confidence, or freshness metadata where meaningful

## CLI Surface

Portable export operators now have these explicit entrypoints:

- `build-source-export --adapter <adapter> --company-id <uuid> [--snapshot-ref <ref>]`
- `build-outcome-export --adapter <adapter> --company-id <uuid> [--snapshot-ref <ref>]`
- `build-memory-export --adapter <adapter> --company-id <uuid> [--snapshot-ref <ref>]`
- `build-delta-export --adapter <adapter> --company-id <uuid> --cutoff-at <iso> --snapshot-ref <ref> [--prior-snapshot-ref <ref> | --prior-export-id <id>]`
- `inspect-export-metadata --adapter <adapter> --company-id <uuid> --export-family <family> --export-id <id>`
- `validate-export-lineage --adapter <adapter> --company-id <uuid> --export-family <family> --export-id <id>`

## Reverse Import Surface

`{trinity}` now also has the first bounded reverse seam for selective
Markdown-derived runtime candidates coming back from `{train}`.

This is not a raw archive import.

It is a governed staging and adoption path for:

- `runtime-memory-candidate`
- `runtime-summary-candidate`
- `runtime-reply-support-candidate`

Current operator entrypoints:

- `import-runtime-candidate-pack --adapter <adapter> --company-id <uuid> --manifest-file <path> [--import-id <id>]`
- `inspect-runtime-candidate-import --adapter <adapter> --company-id <uuid> --import-id <id>`
- `adopt-runtime-candidate-import --adapter <adapter> --company-id <uuid> --import-id <id> [--min-confidence <float>] [--allow-conflicted]`

Current runtime rule:

- imported candidates are staged first
- only explicit adoption promotes them into runtime-owned summaries or
  retrieval documents
- low-confidence or conflicted candidates can be skipped at adoption time

Current bounded adoption targets:

- `runtime-memory-candidate` -> runtime memory summaries
- `runtime-summary-candidate` -> runtime memory summaries and retrieval docs
- `runtime-reply-support-candidate` -> retrieval docs

This gives `{reply}` a live runtime-useful surface without turning `{trinity}`
into the raw document warehouse.

## Current Boundary With Older Bundle Exports

`export-training-bundle` still exists.

It remains the older bounded optimization seam for policy learning.

It is not the full governed portable export system.

Do not confuse:

- runtime-owned memory
- raw source export
- accepted-outcome supervision export
- cutoff-linked delta export
- old bounded training-bundle export

Current supervision rule:

- only send-grade reply outcomes (`SENT_AS_IS`, `EDITED_THEN_SENT`, `MANUAL_REPLACEMENT`) may emit `final_outcome` export records
- `SHOWN` and other ambiguous feedback can still exist in runtime traces and `supervision_event` history, but they must not be promoted into accepted supervision for `{train}`

## Current Implementation Files

Primary implementation:

- [core/trinity_core/schemas/portable_exports.py](/Users/Shared/Projects/trinity/core/trinity_core/schemas/portable_exports.py)
- [core/trinity_core/ops/portable_exports.py](/Users/Shared/Projects/trinity/core/trinity_core/ops/portable_exports.py)
- [core/trinity_core/schemas/runtime_candidates.py](/Users/Shared/Projects/trinity/core/trinity_core/schemas/runtime_candidates.py)
- [core/trinity_core/ops/runtime_candidate_imports.py](/Users/Shared/Projects/trinity/core/trinity_core/ops/runtime_candidate_imports.py)
- [core/trinity_core/reply_runtime.py](/Users/Shared/Projects/trinity/core/trinity_core/reply_runtime.py)
- [core/trinity_core/cli.py](/Users/Shared/Projects/trinity/core/trinity_core/cli.py)

Supporting governed runtime substrates:

- [core/trinity_core/ops/cycle_store.py](/Users/Shared/Projects/trinity/core/trinity_core/ops/cycle_store.py)
- [core/trinity_core/memory/storage.py](/Users/Shared/Projects/trinity/core/trinity_core/memory/storage.py)

Related public docs:

- [docs/API_SURFACE.md](/Users/Shared/Projects/trinity/docs/API_SURFACE.md)
- [docs/CLI_REFERENCE.md](/Users/Shared/Projects/trinity/docs/CLI_REFERENCE.md)

Deterministic tests:

- [tests/test_portable_exports.py](/Users/Shared/Projects/trinity/tests/test_portable_exports.py)
- [tests/test_runtime_candidate_imports.py](/Users/Shared/Projects/trinity/tests/test_runtime_candidate_imports.py)
