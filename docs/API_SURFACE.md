# API Surface

## Purpose

This document summarizes the public operator and integration surface for `{trinity}`.

## Public Entry Points

`{trinity}` currently exposes three main integration surfaces:

- generic CLI commands
- the programmatic Python runtime facade
- machine-readable JSON status and governance payloads

## Programmatic Runtime Entry Point

Primary programmatic entrypoint:

```python
from trinity_core.runtime import TrinityRuntime

runtime = TrinityRuntime(adapter_name="reply")
```

Current facade file:

- [core/trinity_core/runtime.py](/Users/Shared/Projects/trinity/core/trinity_core/runtime.py)

Current adapter registry:

- [core/trinity_core/adapters/base.py](/Users/Shared/Projects/trinity/core/trinity_core/adapters/base.py)

## Main Runtime Methods

The shared runtime facade currently exposes methods including:

- `suggest(...)`
- `record_outcome(...)`
- `export_trace(...)`
- `export_training_bundle(...)`
- `build_source_export(...)`
- `build_outcome_export(...)`
- `build_memory_export(...)`
- `build_delta_export(...)`
- `ingest_memory_event(...)`
- `register_document(...)`
- `get_prepared_draft(...)`
- `refresh_prepared_draft(...)`
- `inspect_prepared_draft_refresh(...)`

Adapter-specific bounded methods still exist where the behavior is not yet generalized, such as Spot review reasoning.

## CLI Surface

The generic CLI is the primary public contract.

Main categories:

- runtime operations
- relation-health operations
- governance and scoring
- training and policy
- portable Train producer exports
- eval/post-training datasets
- provider comparison and control plane
- Gobii workflows, tasks, and enrichment

Full command list:

- [docs/CLI_REFERENCE.md](/Users/Shared/Projects/trinity/docs/CLI_REFERENCE.md)

Command discovery:

```bash
cd /Users/Shared/Projects/trinity
PYTHONPATH=core uv run python -m trinity_core.cli --help
```

## Machine-Readable Status Surfaces

Key JSON-returning supervision surfaces include:

- `runtime-status --adapter <adapter>`
- `train-status`
- `foundation-check --adapter <adapter>`
- `provider-smoke --adapter <adapter>`
- `check-reply-compatibility`
- `gobii-status --adapter <adapter>`
- `governance-status --adapter <adapter>`
- `inspect-export-metadata --adapter <adapter> ...`
- `validate-export-lineage --adapter <adapter> ...`

These are the preferred machine-facing surfaces instead of reading internal storage directly.

## Configuration Surface

Machine-local configuration is managed through:

- `show-config --adapter <adapter>`
- `write-config --adapter <adapter>`
- `show-foundation-policy`
- `write-foundation-policy`

Those commands operate on the same machine-local JSON that the native macOS shell edits.

## Adapter Contract Posture

Current implemented adapters:

- `reply`
- `spot`

Current rule:

- new apps should add a new adapter instead of reusing Reply semantics by default

See:

- [docs/INTEGRATING_NEW_APP.md](/Users/Shared/Projects/trinity/docs/INTEGRATING_NEW_APP.md)
- [docs/ADAPTER_AUTHORING_GUIDE.md](/Users/Shared/Projects/trinity/docs/ADAPTER_AUTHORING_GUIDE.md)

## Storage And Direct Access Rule

External systems should not scrape runtime storage directly.

Preferred integration order:

1. use the generic CLI
2. use `TrinityRuntime(adapter_name=...)`
3. consume governed exported artifacts where offline pack/replay flows are required

## Related Docs

- [docs/CLI_REFERENCE.md](/Users/Shared/Projects/trinity/docs/CLI_REFERENCE.md)
- [docs/PORTABLE_EXPORTS.md](/Users/Shared/Projects/trinity/docs/PORTABLE_EXPORTS.md)
- [docs/USER_GUIDE.md](/Users/Shared/Projects/trinity/docs/USER_GUIDE.md)
- [docs/SETTINGS_GUIDE.md](/Users/Shared/Projects/trinity/docs/SETTINGS_GUIDE.md)
