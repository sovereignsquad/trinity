# Status

## Purpose

This document records the current implementation state of `{trinity}`.

Snapshot date:

- `2026-05-20`

Current release:

- `0.1.4`

## Current Phase

`{trinity}` is now operating as a generic local-first runtime with:

- explicit adapter seams
- explicit provider seams
- explicit governance and artifact lifecycle seams
- explicit relation-health supervision for the main external dependencies

The repository is no longer in the earlier “extract the generic runtime at all” phase. That work is done. The current state is a reusable runtime with bounded but real downstream and ops integrations.

## Implemented Today

### Core Runtime

- reusable workflow execution under `core/trinity_core/workflow`
- canonical contracts under `core/trinity_core/schemas`
- adapter registration and runtime dispatch through `core/trinity_core/adapters`
- generic runtime facade in `core/trinity_core/runtime.py`
- adapter-scoped runtime storage under `core/trinity_core/ops/runtime_storage.py`
- active memory retrieval, tiering, summaries, and similarity signals under `core/trinity_core/memory`

### Adapters

- `reply` as the first mature downstream embedding
- `spot` as the second bounded reasoning/review adapter

### Model Providers

- `deterministic`
- `ollama`
- `mistral-cli`

Current `mistral-cli` scope:

- `vibe` executable path only
- route model names remain explicit in config and trace provenance
- route model names are still advisory rather than CLI-enforced

### Public CLI Surface

The current CLI is generic-first and includes:

- runtime operations
- governance and policy operations
- post-training dataset operations
- control-plane operations
- Gobii workflow/task/enrichment operations
- provider and external relation health operations
- Reply compatibility aliases

Authoritative command reference:

- [docs/CLI_REFERENCE.md](/Users/Shared/Projects/trinity/docs/CLI_REFERENCE.md)

### Relation Health And External Seams

The relation-hardening tranche is implemented in code:

- `train-status`
- `provider-smoke`
- `check-reply-compatibility`
- `gobii-status`

The supporting implementation lives in:

- [core/trinity_core/ops/relation_health.py](/Users/Shared/Projects/trinity/core/trinity_core/ops/relation_health.py)
- [core/trinity_core/ops/train_client.py](/Users/Shared/Projects/trinity/core/trinity_core/ops/train_client.py)

### Code Comments And Docstrings

- the recent documentation sweep now also includes a repo-wide code comment and docstring audit across the active Python runtime surface
- stale module/class wording was corrected where the code had outgrown the older narrower description, especially around Train handoff scope, `mistral-cli` bounded mode, eval/governance ownership, Gobii agent registration scope, and accepted-artifact governance lineage
- the follow-on `tests/` pass found very little prose drift; the useful fixes there were naming-precision updates in a small number of tests/helpers rather than broad comment rewrites

### Governance And Learning Artifacts

- score-health reporting, review, trend comparison, and governance checks
- release-governance reports, triage queues, triage resolution, and release-decision lineage
- policy review, acceptance, promotion, rollback, and status
- post-training dataset export, curation, promotion, and deterministic split generation

### Ops And Control Plane

- Reply provider-comparison harness
- curated eval-dataset replay
- bounded control-plane job/run artifacts
- bounded Gobii workflow packaging and registration
- bounded Gobii task lifecycle
- bounded Gobii normalization
- bounded Gobii tracked-entity profile enrichment

### Native Shell

- macOS native shell remains present under `apps/macos`
- the shell is positioned as a native operator surface, not a web wrapper

## Current Verified Local State

These checks were rerun on `2026-05-20`.

### Reply

- `runtime-status --adapter reply` now reports `provider=mistral-cli`
- `readiness.ready=true`
- `readiness.can_suggest=true`
- current config path is the legacy-compatible Reply root at `~/Library/Application Support/Trinity/reply_runtime/model_config.json`
- `provider-smoke --adapter reply --role generator` passed live

Interpretation:

- Reply is currently configured for live LLM-backed runtime use on this machine
- the active provider is `mistral-cli`, not `deterministic`

### Spot

- `runtime-status --adapter spot` reports `provider=deterministic`
- `llm_enabled=false`
- `readiness.state=disabled`
- `readiness.can_suggest=false`

Interpretation:

- Spot remains intentionally bounded and LLM-disabled in the active local config

### Train

- `train-status --transport both` reports:
  - API `connection_refused`
  - CLI `online`
  - `recommended_transport=cli`

Interpretation:

- the Train seam is usable locally through CLI
- the default local Train API path at `http://127.0.0.1:8000` is still down

### Reply Cross-Repo Compatibility

- `check-reply-compatibility --reply-root-dir /Users/Shared/Projects/reply` returned `ready=true`

Interpretation:

- the current local `{reply}` sibling repo and the Trinity-side contract parser surface are in sync for the bounded check

### Gobii

- `gobii-status --adapter reply --check-live` reports `state=not_configured`
- `GOBII_API_KEY` is still absent in the active shell environment

Interpretation:

- the Gobii seam is implemented and test-covered, but still not live-configured on this machine

## Verified Commands

Most relevant recent verification:

- `uv run pytest`
- `uv run ruff check .`
- `PYTHONPATH=core uv run pytest tests/test_train_client.py tests/test_relation_health.py tests/test_adapter_runtime.py tests/test_public_contracts.py -q`
- `PYTHONPATH=core uv run ruff check core/trinity_core/ops/relation_health.py core/trinity_core/ops/train_client.py core/trinity_core/ops/__init__.py core/trinity_core/cli.py tests/test_relation_health.py tests/test_train_client.py tests/test_adapter_runtime.py tests/test_public_contracts.py`
- `set -a && source .env.local && set +a && PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter reply`
- `set -a && source .env.local && set +a && PYTHONPATH=core uv run python -m trinity_core.cli runtime-status --adapter spot`
- `set -a && source .env.local && set +a && PYTHONPATH=core uv run python -m trinity_core.cli train-status --transport both`
- `set -a && source .env.local && set +a && PYTHONPATH=core uv run python -m trinity_core.cli provider-smoke --adapter reply --role generator`
- `set -a && source .env.local && set +a && PYTHONPATH=core uv run python -m trinity_core.cli check-reply-compatibility --reply-root-dir /Users/Shared/Projects/reply`
- `set -a && source .env.local && set +a && PYTHONPATH=core uv run python -m trinity_core.cli gobii-status --adapter reply --check-live`

## Current Constraints

- `reply` is the only full downstream workflow; `spot` is still intentionally narrower
- Reply-only compatibility aliases remain part of the public contract
- provider comparison and eval replay are still Reply-centric
- `mistral-cli` remains bounded to the `vibe` path and advisory model binding
- Train API transport still depends on an already-running Train server
- Gobii remains optional and currently unconfigured locally
- legacy Reply storage compatibility still exists and should not be expanded

## Immediate Priorities

1. Keep the generic runtime stable while continuing to prevent Reply semantics from leaking into core workflow code.
2. Preserve the relation-health commands as the main operator seam for Train, provider, Reply compatibility, and Gobii supervision.
3. Keep Spot explicitly documented as bounded until its product-side workflow actually expands.
4. Decide whether Train API should be restored locally or whether CLI should remain the normal recommended transport.
5. Configure Gobii only when the bounded browser-agent lanes are actually needed.
