# Handover

## Purpose

This document captures the current resume point for `{trinity}`.

Snapshot date:

- `2026-05-24`

## Current Resume Point

The current tranche is the first full `{trinity}` portable-pack producer/export lane for `{train}`, plus the first bounded reverse import/adoption lane for selective Train runtime-candidate packs, with the macOS shell still hardened for better adapter visibility and safer local operator I/O.

What is true now:

- the relation-hardening code remains landed
- the foundation-policy and native Admin settings work remains landed
- `{trinity}` now has explicit source, outcome, memory, and delta export families for `{train}`
- the old bounded `export-training-bundle` seam still exists, but it is no longer the only Train-facing export path
- the new portable export seam is documented in [docs/PORTABLE_EXPORTS.md](/Users/Shared/Projects/trinity/docs/PORTABLE_EXPORTS.md)
- deterministic tests now cover stable serialization, cross-tenant rejection, Reply-origin mapping, family separation, attachment linkage, and cutoff-lineage validation
- the macOS governance page now loads persisted artifacts off-main and distinguishes missing data from unreadable data
- the macOS Admin settings page now reloads and saves config off-main, shows in-flight state, and derives adapter panels from the shared adapter catalog
- the public repo docs now include dedicated user, settings, and API-surface guides aligned with the current adapter-aware shell and portable export posture
- `{reply}` now has a bounded local source-backfill surface for Notes, Calendar, Contacts, Contact Intelligence, historical conversation rows, and accepted draft outcomes through its existing Trinity seam, so richer upstream local corpora can start feeding the current export families without waiting for a cold full re-sync
- accepted-outcome supervision is now hardened at the export seam too:
  - send-grade dispositions (`SENT_AS_IS`, `EDITED_THEN_SENT`, `MANUAL_REPLACEMENT`) are the only events allowed to create `final_outcome` export records
  - `SHOWN` and other ambiguous feedback may still exist as runtime traces, but they no longer promote candidate variants into accepted supervision for `{train}`
  - obviously generic operator-placeholder drafts such as `Thanks <id>, I saw this...` are now rejected from final supervision export even when they were technically sent
- `{trinity}` can now import one `{train}` `runtime-candidate-pack` into a staged local store
- staged candidates can now be inspected before adoption
- explicit adoption can now promote safe candidates into:
  - runtime memory summaries
  - retrieval documents and chunks
- low-confidence or conflicted candidates can be skipped during adoption instead of silently becoming runtime truth

## Most Important Current Reality

### Runtime And Adapters

- `reply` is the first mature downstream embedding
- `spot` is still a bounded reasoning/review adapter
- adapter registration and generic CLI dispatch are already established

### Active Local Provider State

- Reply is currently configured to use `mistral-cli`
- Spot is currently configured as `deterministic`
- Reply passed a live generator `provider-smoke`
- `foundation-check --adapter reply` currently passes with Gobii only as an optional warning
- `foundation-check --adapter spot` currently passes
- Spot remains intentionally LLM-disabled in the active config

### External Seams

- Train CLI is healthy locally
- Train API is still down locally at `http://127.0.0.1:8000`
- the foundation policy now treats Train `cli` as the default transport
- Reply compatibility check against sibling `/Users/Shared/Projects/reply` is currently passing
- Gobii is still unconfigured because `GOBII_API_KEY` is absent

## Commands To Re-Run First

If you resume this repo later, start with:

```bash
cd /Users/Shared/Projects/trinity
set -a
source .env.local
set +a
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply
PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter spot
PYTHONPATH=core uv run python -m trinity_core.cli show-foundation-policy --include-path
PYTHONPATH=core uv run python -m trinity_core.cli train-status --transport both
PYTHONPATH=core uv run python -m trinity_core.cli foundation-check --adapter reply
PYTHONPATH=core uv run python -m trinity_core.cli check-reply-compatibility --reply-root-dir /Users/Shared/Projects/reply
PYTHONPATH=core uv run python -m trinity_core.cli gobii-status --adapter reply --check-live
```

If you need to confirm the live Reply provider path again:

```bash
cd /Users/Shared/Projects/trinity
set -a
source .env.local
set +a
PYTHONPATH=core uv run python -m trinity_core.cli provider-smoke --adapter reply --role generator
```

## Files That Matter Most

Primary SSOT:

- [README.md](/Users/Shared/Projects/trinity/README.md)
- [docs/API_SURFACE.md](/Users/Shared/Projects/trinity/docs/API_SURFACE.md)
- [docs/CLI_REFERENCE.md](/Users/Shared/Projects/trinity/docs/CLI_REFERENCE.md)
- [docs/LOCAL_INSTALL.md](/Users/Shared/Projects/trinity/docs/LOCAL_INSTALL.md)
- [docs/USER_GUIDE.md](/Users/Shared/Projects/trinity/docs/USER_GUIDE.md)
- [docs/SETTINGS_GUIDE.md](/Users/Shared/Projects/trinity/docs/SETTINGS_GUIDE.md)
- [docs/PORTABLE_EXPORTS.md](/Users/Shared/Projects/trinity/docs/PORTABLE_EXPORTS.md)
- [docs/STATUS.md](/Users/Shared/Projects/trinity/docs/STATUS.md)
- [docs/RELATIONSHIP_HEALTH.md](/Users/Shared/Projects/trinity/docs/RELATIONSHIP_HEALTH.md)

Implementation seams:

- [core/trinity_core/cli.py](/Users/Shared/Projects/trinity/core/trinity_core/cli.py)
- [core/trinity_core/schemas/portable_exports.py](/Users/Shared/Projects/trinity/core/trinity_core/schemas/portable_exports.py)
- [core/trinity_core/ops/portable_exports.py](/Users/Shared/Projects/trinity/core/trinity_core/ops/portable_exports.py)
- [core/trinity_core/ops/foundation_policy.py](/Users/Shared/Projects/trinity/core/trinity_core/ops/foundation_policy.py)
- [core/trinity_core/ops/relation_health.py](/Users/Shared/Projects/trinity/core/trinity_core/ops/relation_health.py)
- [core/trinity_core/ops/train_client.py](/Users/Shared/Projects/trinity/core/trinity_core/ops/train_client.py)
- [apps/macos/Sources/TrinityApp/AdminSettingsSurface.swift](/Users/Shared/Projects/trinity/apps/macos/Sources/TrinityApp/AdminSettingsSurface.swift)
- [apps/macos/Sources/TrinityApp/GovernanceSurface.swift](/Users/Shared/Projects/trinity/apps/macos/Sources/TrinityApp/GovernanceSurface.swift)
- [apps/macos/Sources/TrinityApp/AdapterCatalog.swift](/Users/Shared/Projects/trinity/apps/macos/Sources/TrinityApp/AdapterCatalog.swift)
- [apps/macos/Sources/TrinityApp/ConstellationUI.swift](/Users/Shared/Projects/trinity/apps/macos/Sources/TrinityApp/ConstellationUI.swift)

Deterministic portable-export tests:

- [tests/test_portable_exports.py](/Users/Shared/Projects/trinity/tests/test_portable_exports.py)

## Open Operational Gaps

- Gobii still needs a real `GOBII_API_KEY` before live status can move beyond `not_configured`
- Train API still needs either a local server or an intentional decision to remain secondary to the CLI-first baseline
- `mistral-cli` is live locally now, but still remains a bounded `vibe`-path provider rather than a fully route-enforced backend

## Recommended Next Step

Do not start another architecture rewrite.

If the next task is operational:

1. re-run `foundation-check --adapter reply` after any provider or promotion-related change
2. decide whether Gobii should actually be turned on in this environment
3. if yes, create a Gobii platform API key and load it through `.env.local`
4. re-run `gobii-status --check-live`

If the next task is product/runtime:

1. keep the public docs aligned with the actual CLI and machine-readable status payloads
2. preserve the generic adapter boundary
3. avoid reintroducing Reply-specific assumptions into core workflow code
4. if Train-side portable-pack consumption changes, update the portable export doc and schema versions together

## 2026-05-24 Reverse Runtime-Candidate Lane

- the first reverse seam from `{train}` into `{trinity}` is now real
- new CLI entrypoints:
  - `import-runtime-candidate-pack`
  - `inspect-runtime-candidate-import`
  - `adopt-runtime-candidate-import`
- the current import contract expects the Train manifest-backed bundle:
  - `runtime-candidate-pack.manifest.json`
  - sibling `runtime-candidate-pack/runtime-candidates.json`
  - sibling `runtime-candidate-pack/bundle-metadata.json`
- currently supported candidate families:
  - `runtime-memory-candidate`
  - `runtime-summary-candidate`
  - `runtime-reply-support-candidate`
- current bounded adoption targets:
  - memory candidates -> `memory_summaries`
  - summary candidates -> `memory_summaries` + retrieval docs
  - reply-support candidates -> retrieval docs
- deterministic proof coverage now exists in:
  - [tests/test_runtime_candidate_imports.py](/Users/Shared/Projects/trinity/tests/test_runtime_candidate_imports.py)
- `{reply}` now consumes this adopted knowledge in the live draft path through Trinity `runtime_diagnostics`
- `ReplyRuntime.suggest(...)` now reports bounded imported-knowledge usage under:
  - `runtime_diagnostics.imported_runtime_knowledge`
- that payload is now the machine-readable handoff for:
  - imported record counts
  - candidate-family counts
  - artifact/import provenance
  - top supporting imported sources
- the next remaining work is quality improvement of the imported runtime knowledge itself, not more missing reverse-seam plumbing

## 2026-05-21 Historical Outcome Recovery

- the live accepted-outcome seam is now materially stronger:
  - `ReplyRuntime.record_outcome(...)` can now recover missing historical cycles for trusted send-grade outcomes by synthesizing a minimal cycle payload
  - those synthetic traces are explicitly marked with `historical_outcome_backfill=true`
  - source exports skip those synthetic historical thread snapshots so fake prompt context does not leak into `{train}`
- a fresh live outcome export for company `a41d752b-c983-5084-8b22-ecedaea270ce` with snapshot ref `mcs-live-2026-05-21b` now contains:
  - `551` `candidate_variant`
  - `10` `supervision_event`
  - `2` `final_outcome`
- this proves the portable export seam is no longer the blocker for the first honest MCS corpus rebuild
- the remaining blocker is upstream supervision volume in `{reply}`, not portable export correctness in `{trinity}`
